"""Eval wrapper - turns a function into a scored eval test.

The wrapper intercepts the return value, runs evaluators, and returns
an EvalPayload. The rest of the pipeline (executor, outcome builder,
reporters) handles it like any eval test.
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Annotated, Any, get_args, get_origin

from protest.di.hints import get_type_hints_compat
from protest.di.markers import From
from protest.entities.events import EvalPayload, EvalScoreEntry
from protest.evals.evaluator import (
    EvalCase,
    EvalContext,
    Evaluator,
    ShortCircuit,
    extract_scores_from_result,
    validate_evaluators,
)
from protest.evals.hashing import compute_case_hash, compute_eval_hash
from protest.evals.types import EvalScore, TaskResult
from protest.exceptions import (
    FixtureError,
    MultipleEvalCaseParamsError,
    NoEvaluatorsError,
    ScoreNameCollisionError,
)


def make_eval_wrapper(
    func: Any,
    evaluators: list[Evaluator | ShortCircuit],
    judge: Any = None,
) -> Any:
    """Wrap a function to run evaluators on its return value."""

    # Resolve which parameter carries the EvalCase once, statically. The name
    # is then used for a direct kwargs lookup below - the case is never
    # rediscovered by scanning values.
    case_param = _resolve_case_param(func)
    validate_evaluators(evaluators)

    @functools.wraps(func)
    async def eval_wrapper(**kwargs: Any) -> EvalPayload:
        case = kwargs.get(case_param) if case_param is not None else None
        expected = case.expected if case is not None else None
        case_name = case.name if case is not None else func.__name__
        inputs = case.inputs if case is not None else None
        metadata = (case.metadata or None) if case is not None else None

        all_evaluators = list(evaluators)
        if case is not None and case.evaluators:
            all_evaluators.extend(case.evaluators)

        # Both guards run before the task itself: the evaluator list is
        # fully known from the kwargs alone, and the task is typically the
        # expensive LLM call. Zero evaluators would silently pass
        # (all([]) is True), and duplicate names guarantee colliding score
        # keys - fail before spending any tokens on a doomed case.
        flat_evaluators = _flatten_evaluators(all_evaluators)
        if not flat_evaluators:
            raise NoEvaluatorsError(case_name)
        _check_duplicate_evaluator_names(flat_evaluators, case_name)

        start = time.perf_counter()
        if asyncio.iscoroutinefunction(func):
            raw_output = await func(**kwargs)
        else:
            raw_output = func(**kwargs)
        task_duration = time.perf_counter() - start

        # Unwrap TaskResult if returned
        task_input_tokens = 0
        task_output_tokens = 0
        task_cost = 0.0
        if isinstance(raw_output, TaskResult):
            output = raw_output.output
            task_input_tokens = raw_output.input_tokens or 0
            task_output_tokens = raw_output.output_tokens or 0
            task_cost = raw_output.cost or 0.0
        else:
            output = raw_output

        scores, eval_ctx = await run_evaluators(
            all_evaluators,
            case_name,
            inputs,
            output,
            expected,
            metadata,
            task_duration,
            judge=judge,
        )

        # Defense-in-depth backstop. With per-evaluator namespacing and the
        # pre-execution name check above, no known path reaches this -
        # distinct evaluator names can't emit the same key. Kept because
        # EvalPayload.scores is a dict: if a future extraction path ever
        # produces duplicate keys, silent overwrite is the worst failure.
        seen: set[str] = set()
        duplicates: list[str] = []
        for s in scores:
            if s.name in seen and s.name not in duplicates:
                duplicates.append(s.name)
            seen.add(s.name)
        if duplicates:
            raise ScoreNameCollisionError(case_name, duplicates)

        return EvalPayload(
            case_name=case_name,
            passed=all(s.passed for s in scores),
            task_duration=task_duration,
            inputs=inputs,
            output=output,
            expected_output=expected,
            scores={
                s.name: EvalScoreEntry(
                    value=s.value,
                    passed=s.passed,
                    skipped=s.skipped,
                )
                for s in scores
            },
            case_hash=compute_case_hash(inputs, expected),
            eval_hash=compute_eval_hash(all_evaluators),
            task_input_tokens=task_input_tokens,
            task_output_tokens=task_output_tokens,
            task_cost=task_cost,
            judge_call_count=eval_ctx.judge_call_count,
            judge_input_tokens=eval_ctx.judge_input_tokens,
            judge_output_tokens=eval_ctx.judge_output_tokens,
            judge_cost=eval_ctx.judge_cost,
        )

    return eval_wrapper


# ---------------------------------------------------------------------------
# Registration-time validation
# ---------------------------------------------------------------------------


def _resolve_case_param(func: Any) -> str | None:
    """Return the name of the single parameter that carries the EvalCase.

    Resolved once at decoration time, from the signature alone. A parameter
    is the case parameter when either signal holds:

    - its declared type is an EvalCase (subclass) - ``case: EvalCase`` or
      ``Annotated[EvalCase, From(cases)]``; or
    - it is bound via ``From(source)`` whose source yields EvalCase instances -
      ``Annotated[Any, From(cases)]``, where the type is deliberately loose.

    The returned name drives a direct ``kwargs[name]`` lookup at runtime. This
    is the whole point: the case is identified by *which parameter it is*, not
    by scanning kwargs values for an EvalCase instance. A fixture that merely
    returns an EvalCase on an unrelated parameter therefore cannot be mistaken
    for the case (the silent misattribution the old isinstance scan allowed).

    Raises MultipleEvalCaseParamsError if more than one parameter qualifies -
    only one case per eval defines its identity (name, expected, inputs,
    metadata, per-case evaluators). Returns None when no parameter qualifies
    (a static eval, or one parametrized over non-EvalCase values).
    """
    hints = get_type_hints_compat(func)
    matches = [
        name
        for name, annotation in hints.items()
        if name != "return" and _is_case_param(annotation)
    ]
    if len(matches) > 1:
        raise MultipleEvalCaseParamsError(func.__name__, matches)
    return matches[0] if matches else None


def _is_case_param(annotation: Any) -> bool:
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        underlying = args[0]
        if isinstance(underlying, type) and issubclass(underlying, EvalCase):
            return True
        return any(
            isinstance(meta, From) and _source_yields_evalcase(meta.source)
            for meta in args[1:]
        )
    return isinstance(annotation, type) and issubclass(annotation, EvalCase)


def _source_yields_evalcase(source: Any) -> bool:
    """True if a From source yields EvalCase instances (ForEach is non-empty)."""
    return isinstance(next(iter(source), None), EvalCase)


# ---------------------------------------------------------------------------
# Evaluator list helpers
# ---------------------------------------------------------------------------


def _check_duplicate_evaluator_names(
    evaluators: list[Evaluator], case_name: str
) -> None:
    """Raise ScoreNameCollisionError if an evaluator name appears twice.

    Score names are namespaced per evaluator, so a duplicate evaluator name
    (the same @evaluator attached twice, possibly rebound with different
    kwargs) guarantees colliding score keys. Takes the flattened list;
    runs before the task and any evaluator executes.
    """
    seen: set[str] = set()
    duplicates: list[str] = []
    for ev in evaluators:
        if ev.name in seen and ev.name not in duplicates:
            duplicates.append(ev.name)
        seen.add(ev.name)
    if duplicates:
        raise ScoreNameCollisionError(case_name, duplicates)


def _flatten_evaluators(
    evaluators: list[Evaluator | ShortCircuit],
) -> list[Evaluator]:
    flat: list[Evaluator] = []
    for ev in evaluators:
        if isinstance(ev, ShortCircuit):
            flat.extend(ev.evaluators)
        else:
            flat.append(ev)
    return flat


# ---------------------------------------------------------------------------
# Evaluator execution
# ---------------------------------------------------------------------------


async def run_evaluators(
    evaluators: list[Evaluator | ShortCircuit],
    case_name: str,
    inputs: Any,
    output: Any,
    expected_output: Any,
    metadata: Any,
    duration: float,
    judge: Any = None,
) -> tuple[list[EvalScore], EvalContext[Any, Any]]:
    """Run evaluators and return (scores, ctx with judge stats).

    Callers must have validated the list (Evaluator | ShortCircuit only) at the
    boundary; the loop below trusts the Union and uses isinstance solely to
    narrow it - the only legitimate isinstance kept in this module.
    """
    ctx = EvalContext(
        name=case_name,
        inputs=inputs,
        output=output,
        expected_output=expected_output,
        metadata=metadata,
        duration=duration,
        _judge=judge,
    )

    scores: list[EvalScore] = []
    for ev in evaluators:
        if isinstance(ev, ShortCircuit):
            scores.extend(await _run_short_circuit(ev.evaluators, ctx))
            continue

        try:
            raw = ev.run(ctx)
            result = await raw if asyncio.iscoroutine(raw) else raw
            scores.extend(extract_scores_from_result(result, ev.name))
        except Exception as exc:
            raise FixtureError(f"evaluator '{ev.name}'", exc) from exc

    return scores, ctx


async def _run_short_circuit(
    evaluators: list[Evaluator],
    ctx: EvalContext[Any, Any],
) -> list[EvalScore]:
    """Run evaluators in order, stop at first Verdict=False."""
    scores: list[EvalScore] = []
    for i, ev in enumerate(evaluators):
        try:
            raw = ev.run(ctx)
            result = await raw if asyncio.iscoroutine(raw) else raw
        except Exception as exc:
            raise FixtureError(f"evaluator '{ev.name}'", exc) from exc
        extracted = extract_scores_from_result(result, ev.name)
        scores.extend(extracted)
        if any(s.is_verdict and not s.passed for s in extracted):
            # Mark remaining evaluators as skipped. Placeholders carry the
            # same namespaced keys a real run would emit, so score keys
            # stay identical across runs whether the short-circuit fired
            # or not (run-over-run history comparison relies on this).
            for skipped_ev in evaluators[i + 1 :]:
                scores.extend(
                    EvalScore(name=score_name, value=False, skipped=True)
                    for score_name in skipped_ev.score_names()
                )
            break
    return scores
