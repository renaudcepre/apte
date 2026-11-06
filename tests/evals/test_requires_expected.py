"""Tests for `MissingExpectedError` - the pre-task `requires_expected` guard.

Evaluators declared with `@evaluator(requires_expected=True)` have nothing
to check when `EvalCase.expected` is None. The wrapper knows `expected` and
the full evaluator list from the kwargs, so it rejects such a case before
running the task (typically the expensive LLM call), alongside the
zero-evaluators and duplicate-name guards. The in-evaluator raise stays as
the backstop for direct `ev.run(ctx)` calls.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from apte.evals import EvalCase, EvalContext, ShortCircuit, evaluator
from apte.evals.evaluators import contains_expected, not_empty, word_overlap
from apte.evals.wrapper import make_eval_wrapper
from apte.exceptions import MissingExpectedError


@evaluator(requires_expected=True)
def _equals_expected(ctx: EvalContext) -> bool:
    return bool(ctx.output == ctx.expected_output)


async def _invoke(evaluators: list, case: EvalCase, calls: list[str]) -> Any:
    def task(case: EvalCase) -> str:
        calls.append(case.name or "")
        return str(case.inputs)

    wrapped = make_eval_wrapper(task, evaluators)
    return await wrapped(case=case)


class TestRequiresExpectedFlag:
    def test_builtins_that_read_expected_declare_it(self) -> None:
        assert contains_expected.requires_expected is True
        assert word_overlap.requires_expected is True

    def test_default_is_false(self) -> None:
        assert not_empty.requires_expected is False

    def test_flag_survives_param_rebinding(self) -> None:
        assert contains_expected(case_sensitive=True).requires_expected is True


class TestGuardRunsBeforeTask:
    @pytest.mark.parametrize("ev", [contains_expected, word_overlap])
    def test_builtin_missing_expected_skips_task(self, ev: Any) -> None:
        calls: list[str] = []
        with pytest.raises(MissingExpectedError) as excinfo:
            asyncio.run(_invoke([ev], EvalCase(inputs="x", name="c1"), calls))
        assert calls == []
        msg = str(excinfo.value)
        assert "c1" in msg
        assert ev.name in msg

    def test_inside_short_circuit_skips_task(self) -> None:
        calls: list[str] = []
        with pytest.raises(MissingExpectedError):
            asyncio.run(
                _invoke(
                    [ShortCircuit([not_empty, contains_expected])],
                    EvalCase(inputs="x", name="c1"),
                    calls,
                )
            )
        assert calls == []

    def test_per_case_evaluator_skips_task(self) -> None:
        calls: list[str] = []
        case = EvalCase(inputs="x", name="c1", evaluators=[word_overlap])
        with pytest.raises(MissingExpectedError):
            asyncio.run(_invoke([not_empty], case, calls))
        assert calls == []

    def test_custom_evaluator_with_flag_skips_task(self) -> None:
        calls: list[str] = []
        with pytest.raises(MissingExpectedError) as excinfo:
            asyncio.run(
                _invoke([_equals_expected], EvalCase(inputs="x", name="c1"), calls)
            )
        assert calls == []
        assert "_equals_expected" in str(excinfo.value)


class TestGuardPassesWhenExpectedPresent:
    def test_builtin_with_expected_runs_task(self) -> None:
        calls: list[str] = []
        case = EvalCase(inputs="hello world", expected="hello", name="c1")
        payload = asyncio.run(_invoke([contains_expected, word_overlap], case, calls))
        assert calls == ["c1"]
        assert payload.passed is True
        assert "contains_expected" in payload.scores

    def test_custom_evaluator_with_expected_runs_task(self) -> None:
        calls: list[str] = []
        case = EvalCase(inputs="x", expected="x", name="c1")
        payload = asyncio.run(_invoke([_equals_expected], case, calls))
        assert calls == ["c1"]
        assert payload.scores["_equals_expected"].passed is True

    def test_evaluator_without_flag_ignores_missing_expected(self) -> None:
        calls: list[str] = []
        payload = asyncio.run(
            _invoke([not_empty], EvalCase(inputs="x", name="c1"), calls)
        )
        assert calls == ["c1"]
        assert payload.passed is True


class TestInEvaluatorBackstop:
    """Direct `run(ctx)` bypasses the wrapper: the evaluator still raises."""

    @staticmethod
    def _ctx() -> EvalContext:
        return EvalContext(
            name="c1",
            inputs="x",
            output="x",
            expected_output=None,
            metadata=None,
            duration=0.0,
        )

    def test_contains_expected_direct_run_raises(self) -> None:
        with pytest.raises(ValueError, match="expected_output is None"):
            contains_expected.run(self._ctx())

    def test_word_overlap_direct_run_raises(self) -> None:
        with pytest.raises(ValueError, match="expected_output is None"):
            word_overlap.run(self._ctx())
