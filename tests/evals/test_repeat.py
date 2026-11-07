"""Tests for `Repeat` - running a case N times and folding the runs.

The wrapper runs task + evaluators `runs` times in sequence, then folds the
scores: metrics report mean/min/max, verdicts pass if they held in at least
`min_passes` runs. A single run must stay byte-identical to the old payload.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any

import pytest

from apte.entities.events import EvalPayload, EvalScoreEntry
from apte.evals import (
    EvalCase,
    EvalContext,
    Metric,
    Reason,
    Repeat,
    ShortCircuit,
    TaskResult,
    Verdict,
    evaluator,
)
from apte.evals.wrapper import make_eval_wrapper
from apte.exceptions import NoEvaluatorsError


@dataclass
class _Scored:
    score: Annotated[float, Metric]
    ok: Annotated[bool, Verdict]
    label: Annotated[str, Reason]


@evaluator
def _scored(ctx: EvalContext) -> _Scored:
    value = float(ctx.output)
    return _Scored(score=value, ok=value >= 0.5, label="hi" if value >= 0.5 else "lo")


@evaluator
def _is_good(ctx: EvalContext) -> bool:
    return bool(float(ctx.output) >= 0.5)


@evaluator
def _always_true(ctx: EvalContext) -> bool:
    return True


def _run(
    outputs: list[Any],
    evaluators: list[Any],
    repeat: Repeat,
    case: EvalCase | None = None,
) -> tuple[EvalPayload, list[int]]:
    """Run a task that returns `outputs` in order; return payload and call log."""
    queue = list(outputs)
    calls: list[int] = []

    def task(case: EvalCase) -> Any:
        calls.append(len(calls))
        return queue.pop(0)

    wrapped = make_eval_wrapper(task, evaluators, repeat=repeat)
    payload = asyncio.run(wrapped(case=case or EvalCase(inputs="x", name="c")))
    return payload, calls


class TestRepeatConstructors:
    def test_all(self) -> None:
        assert Repeat.all(5) == Repeat(runs=5, min_passes=5)

    @pytest.mark.parametrize(("runs", "k"), [(1, 1), (2, 2), (4, 3), (5, 3)])
    def test_majority_is_strictly_more_than_half(self, runs: int, k: int) -> None:
        assert Repeat.majority(runs).min_passes == k

    def test_at_least(self) -> None:
        assert Repeat.at_least(2, of=5) == Repeat(runs=5, min_passes=2)

    @pytest.mark.parametrize(("runs", "k"), [(0, 1), (3, 0), (3, 4), (-1, -1)], ids=str)
    def test_invalid_rejected(self, runs: int, k: int) -> None:
        with pytest.raises(ValueError, match="Repeat"):
            Repeat(runs=runs, min_passes=k)


class TestSingleRunUnchanged:
    def test_entries_carry_no_repeat_data(self) -> None:
        payload, calls = _run([0.8], [_scored], Repeat.all(1))
        assert calls == [0]
        assert payload.runs == 1
        assert payload.scores["_scored.score"] == EvalScoreEntry(value=0.8)
        assert payload.scores["_scored.ok"] == EvalScoreEntry(value=True)
        assert all(e.runs_suffix() == "" for e in payload.scores.values())


class TestFolding:
    def test_task_runs_n_times(self) -> None:
        _, calls = _run([0.8] * 4, [_scored], Repeat.all(4))
        assert calls == [0, 1, 2, 3]

    def test_metric_mean_min_max(self) -> None:
        payload, _ = _run([0.6, 0.8, 1.0], [_scored], Repeat.all(3))
        entry = payload.scores["_scored.score"]
        assert entry.value == pytest.approx(0.8)
        assert (entry.min_value, entry.max_value, entry.runs) == (0.6, 1.0, 3)
        assert entry.runs_suffix() == "[0.60-1.00]"

    def test_reason_is_most_frequent(self) -> None:
        payload, _ = _run([0.1, 0.9, 0.9], [_scored], Repeat.at_least(1, of=3))
        assert payload.scores["_scored.label"].value == "hi"

    def test_tokens_summed_duration_mean(self) -> None:
        outputs = [TaskResult(output=0.9, input_tokens=10, cost=0.5)] * 3
        payload, _ = _run(outputs, [_is_good], Repeat.all(3))
        assert payload.task_input_tokens == 30
        assert payload.task_cost == pytest.approx(1.5)
        assert payload.runs == 3


class TestVerdictRule:
    # 3 runs, one bad: passes 2/3.
    flaky = (0.9, 0.1, 0.9)

    def test_all_fails_on_one_bad_run(self) -> None:
        payload, _ = _run(list(self.flaky), [_is_good], Repeat.all(3))
        entry = payload.scores["_is_good"]
        assert (entry.value, entry.passes, entry.runs) == (False, 2, 3)
        assert entry.runs_suffix() == "(2/3)"
        assert payload.passed is False

    def test_majority_tolerates_one_bad_run(self) -> None:
        payload, _ = _run(list(self.flaky), [_is_good], Repeat.majority(3))
        assert payload.scores["_is_good"].passed is True
        assert payload.passed is True

    def test_at_least_threshold(self) -> None:
        payload, _ = _run([0.9, 0.1, 0.1], [_is_good], Repeat.at_least(2, of=3))
        assert payload.passed is False
        payload, _ = _run([0.9, 0.1, 0.1], [_is_good], Repeat.at_least(1, of=3))
        assert payload.passed is True

    def test_failed_case_shows_first_failing_output(self) -> None:
        payload, _ = _run([0.9, 0.2, 0.1], [_is_good], Repeat.all(3))
        assert payload.output == 0.2

    def test_passing_case_shows_last_output(self) -> None:
        payload, _ = _run([0.9, 0.2, 0.7], [_is_good], Repeat.majority(3))
        assert payload.output == 0.7


class TestShortCircuitSkips:
    def test_skipped_runs_do_not_count_as_failures(self) -> None:
        # Run 2 fails _is_good, so _always_true is skipped there. Under
        # Repeat.all, _always_true never failed: it must still hold.
        sc = ShortCircuit([_is_good, _always_true])
        payload, _ = _run([0.9, 0.1, 0.9], [sc], Repeat.all(3))
        entry = payload.scores["_always_true"]
        assert (entry.passed, entry.runs, entry.passes) == (True, 2, 2)
        assert payload.scores["_is_good"].passed is False

    def test_skipped_in_every_run_stays_skipped(self) -> None:
        sc = ShortCircuit([_is_good, _always_true])
        payload, _ = _run([0.1, 0.1], [sc], Repeat.majority(2))
        entry = payload.scores["_always_true"]
        assert entry.skipped is True
        assert entry.runs == 0


class TestCaseOverride:
    def test_case_repeat_wins_over_eval_default(self) -> None:
        case = EvalCase(inputs="x", name="c", repeat=Repeat.all(2))
        _, calls = _run([0.9, 0.9], [_is_good], Repeat.all(5), case=case)
        assert len(calls) == 2

    def test_guards_run_once_before_any_run(self) -> None:
        # The pre-task guards are not repeated: zero evaluators fails before
        # the first task call, whatever the repeat count.
        with pytest.raises(NoEvaluatorsError):
            _run([0.9] * 3, [], Repeat.all(3))
