"""Validation that evaluators=[...] only accepts @evaluator-wrapped objects.

Plain callables and arbitrary values used to be silently accepted, forcing a
runtime ``isinstance`` dispatch in the executor. Validating at the boundary
turns the failure into a clear TypeError at registration time and lets the
downstream code work on a uniform ``Evaluator | ShortCircuit`` Union.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import pytest

from apte.evals.evaluator import (
    EvalCase,
    EvalContext,
    Metric,
    Reason,
    ShortCircuit,
    Verdict,
    evaluator,
    validate_evaluators,
)


@evaluator
def _ok(ctx: EvalContext) -> bool:
    return True


def _plain_callable(ctx: EvalContext) -> bool:
    return True


# Module-level dataclasses so get_type_hints can resolve the return annotation.
@dataclass
class _NoAnnotatedFields:
    note: str
    count: int


@dataclass
class _MetricOnly:
    overlap: Annotated[float, Metric]


@dataclass
class _VerdictOnly:
    ok: Annotated[bool, Verdict]


@dataclass
class _ReasonOnly:
    why: Annotated[str, Reason]


@dataclass
class _AnnotatedPlusMetadata:
    ok: Annotated[bool, Verdict]
    debug: dict  # unannotated free metadata, ignored by the runner


class TestValidateEvaluators:
    def test_accepts_evaluator(self) -> None:
        validate_evaluators([_ok])

    def test_accepts_short_circuit(self) -> None:
        validate_evaluators([ShortCircuit([_ok])])

    def test_rejects_plain_callable(self) -> None:
        with pytest.raises(TypeError, match="@evaluator"):
            validate_evaluators([_plain_callable])

    def test_rejects_non_callable(self) -> None:
        with pytest.raises(TypeError, match="Expected Evaluator or ShortCircuit"):
            validate_evaluators(["not_an_evaluator"])  # type: ignore[list-item]

    def test_rejects_nested_short_circuit(self) -> None:
        with pytest.raises(TypeError, match="cannot nest"):
            ShortCircuit([ShortCircuit([_ok])])  # type: ignore[list-item]


class TestEvalCaseValidates:
    def test_evalcase_rejects_plain_callable(self) -> None:
        with pytest.raises(TypeError, match="@evaluator"):
            EvalCase(inputs="x", name="c", evaluators=[_plain_callable])

    def test_evalcase_accepts_evaluator(self) -> None:
        EvalCase(inputs="x", name="c", evaluators=[_ok])


class TestDataclassReturnMustHaveAnnotatedField:
    """A dataclass return with zero Metric/Verdict/Reason fields emits no
    scores, so a case relying only on it passes vacuously - the silent pass
    that survives the NoEvaluatorsError guard (that guard counts evaluators,
    not scores). Reject it at decoration time.
    """

    def test_zero_annotated_fields_raises(self) -> None:
        with pytest.raises(TypeError, match="no Metric/Verdict/Reason"):

            @evaluator
            def empty(ctx: EvalContext) -> _NoAnnotatedFields:
                return _NoAnnotatedFields(note="x", count=1)

    def test_metric_only_accepted(self) -> None:
        """Tracking-only evaluators (e.g. word_overlap) stay valid."""

        @evaluator
        def tracker(ctx: EvalContext) -> _MetricOnly:
            return _MetricOnly(overlap=1.0)

        assert tracker.score_names() == ["tracker.overlap"]

    def test_verdict_only_accepted(self) -> None:
        @evaluator
        def verdict(ctx: EvalContext) -> _VerdictOnly:
            return _VerdictOnly(ok=True)

        assert verdict.score_names() == ["verdict.ok"]

    def test_reason_only_accepted(self) -> None:
        @evaluator
        def reason(ctx: EvalContext) -> _ReasonOnly:
            return _ReasonOnly(why="because")

        assert reason.score_names() == ["reason.why"]

    def test_annotated_field_alongside_metadata_accepted(self) -> None:
        @evaluator
        def mixed(ctx: EvalContext) -> _AnnotatedPlusMetadata:
            return _AnnotatedPlusMetadata(ok=True, debug={})

        assert mixed.score_names() == ["mixed.ok"]
