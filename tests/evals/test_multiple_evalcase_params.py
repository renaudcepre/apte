"""Tests for case-parameter resolution (`_resolve_case_param`).

The wrapper identifies the EvalCase by *which parameter carries it*, resolved
once from the signature at decoration time, not by scanning kwargs values at
runtime. This file covers:

- single case parameter accepted (typed, subclass, or loose-typed via `From`);
- more than one case parameter rejected loudly at registration;
- a parameter that merely *holds* an EvalCase at runtime, without being the
  declared case parameter, is ignored - not misattributed (issue #120).
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

import pytest

from apte import ApteSession, ForEach, From
from apte.evals import EvalCase, EvalContext, evaluator
from apte.evals.suite import EvalSuite
from apte.evals.wrapper import make_eval_wrapper
from apte.exceptions import MultipleEvalCaseParamsError

# Module-level case sources so `get_type_hints()` can resolve Annotated args.
_cases_a = ForEach([EvalCase(inputs="a", name="a1")])
_cases_b = ForEach([EvalCase(inputs="b", name="b1")])
_loose_cases = ForEach([EvalCase(inputs="loose", name="loose1")])
_dict_cases = ForEach([{"inputs": "d"}])


class _MyCase(EvalCase):
    """Subclass to verify the check covers user-defined EvalCase types."""


_subclass_cases = ForEach([_MyCase(inputs="x", name="x1")])


@evaluator
def _ok(ctx: EvalContext) -> bool:
    return True


class TestSingleEvalCaseParamAccepted:
    def test_one_evalcase_param_via_annotated_from(self) -> None:
        session = ApteSession()
        suite = EvalSuite("evals")

        @suite.eval()
        def good(case: Annotated[EvalCase, From(_cases_a)]) -> str:
            return str(case.inputs)

        _ = good
        session.add_suite(suite)  # no raise

    def test_zero_evalcase_param_accepted(self) -> None:
        """Evals without parametrization (or without EvalCase) are valid."""
        session = ApteSession()
        suite = EvalSuite("evals")

        @suite.eval()
        def no_case() -> str:
            return "static"

        _ = no_case
        session.add_suite(suite)  # no raise

    def test_subclass_param_accepted_when_alone(self) -> None:
        session = ApteSession()
        suite = EvalSuite("evals")

        @suite.eval()
        def good(case: Annotated[_MyCase, From(_subclass_cases)]) -> str:
            return str(case.inputs)

        _ = good
        session.add_suite(suite)

    def test_loose_typed_from_source_is_recognized_as_case(self) -> None:
        """`Annotated[Any, From(cases)]` over EvalCase items is the case param.

        The type is deliberately loose; resolution keys off the From source
        yielding EvalCase instances, so case identity is still wired up.
        """

        def task(case: Annotated[Any, From(_loose_cases)]) -> str:
            return str(case.inputs)

        wrapped = make_eval_wrapper(task, [_ok])
        payload = asyncio.run(wrapped(case=EvalCase(inputs="z", name="z1")))
        assert payload.case_name == "z1"

    def test_from_source_of_non_evalcase_is_not_a_case_param(self) -> None:
        """A `From` over plain dicts is parametrization, not a case: the eval
        falls back to the function name and carries no expected/inputs."""

        def task(case: Annotated[dict, From(_dict_cases)]) -> str:
            return str(case["inputs"])

        wrapped = make_eval_wrapper(task, [_ok])
        payload = asyncio.run(wrapped(case={"inputs": "d"}))
        assert payload.case_name == "task"
        assert payload.expected_output is None


class TestMultipleEvalCaseParamRejected:
    def test_two_evalcase_params_raise(self) -> None:
        suite = EvalSuite("evals")

        with pytest.raises(MultipleEvalCaseParamsError) as excinfo:

            @suite.eval()
            def bad(
                case_a: Annotated[EvalCase, From(_cases_a)],
                case_b: Annotated[EvalCase, From(_cases_b)],
            ) -> str:
                return f"{case_a.inputs}+{case_b.inputs}"

        msg = str(excinfo.value)
        assert "bad" in msg
        assert "case_a" in msg
        assert "case_b" in msg

    def test_subclass_counts_as_evalcase(self) -> None:
        """A param typed `_MyCase` (subclass) collides with a `EvalCase` param."""
        suite = EvalSuite("evals")

        with pytest.raises(MultipleEvalCaseParamsError) as excinfo:

            @suite.eval()
            def bad(
                case_a: Annotated[EvalCase, From(_cases_a)],
                case_b: Annotated[_MyCase, From(_subclass_cases)],
            ) -> str:
                return str(case_a.inputs) + str(case_b.inputs)

        assert "case_a" in str(excinfo.value)
        assert "case_b" in str(excinfo.value)

    def test_loose_from_collides_with_typed_case(self) -> None:
        """A loose `From(EvalCase items)` param and a typed EvalCase param both
        qualify - two case params, rejected at registration."""
        suite = EvalSuite("evals")

        with pytest.raises(MultipleEvalCaseParamsError) as excinfo:

            @suite.eval()
            def bad(
                case_a: Annotated[EvalCase, From(_cases_a)],
                case_b: Annotated[Any, From(_loose_cases)],
            ) -> str:
                return str(case_a.inputs)

        assert "case_a" in str(excinfo.value)
        assert "case_b" in str(excinfo.value)


class TestRuntimeEvalCaseOnUnrelatedParamIgnored:
    """Issue #120, resolved structurally. The case is identified by parameter
    name (resolved at decoration), not by scanning values. A fixture that
    returns an EvalCase on an unrelated parameter is therefore simply ignored -
    it cannot shadow or be misattributed as the declared case.
    """

    def test_evalcase_on_unrelated_param_is_ignored(self) -> None:
        def task(case: EvalCase, sneaky: object) -> str:
            return str(case.inputs)

        wrapped = make_eval_wrapper(task, [_ok])
        payload = asyncio.run(
            wrapped(
                case=EvalCase(inputs="a", name="a1"),
                sneaky=EvalCase(inputs="b", name="b1"),
            )
        )
        # The declared case wins; `sneaky` is not consulted.
        assert payload.case_name == "a1"
        assert payload.expected_output is None

    def test_single_runtime_evalcase_kwarg_ok(self) -> None:
        def task(case: EvalCase) -> str:
            return str(case.inputs)

        wrapped = make_eval_wrapper(task, [_ok])
        payload = asyncio.run(wrapped(case=EvalCase(inputs="a", name="a1")))
        assert payload.case_name == "a1"
