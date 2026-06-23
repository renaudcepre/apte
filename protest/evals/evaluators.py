"""Built-in evaluators for common eval patterns.

Evaluators return either bool (simple verdict) or a dataclass with
annotated fields: Annotated[bool, Verdict], Annotated[float, Metric],
Annotated[str, Reason]. Unannotated fields are ignored by the runner.
"""

from __future__ import annotations

import json as json_module
import re
from collections.abc import Sized
from dataclasses import dataclass
from typing import Annotated, Any

from protest.evals.evaluator import EvalContext, Metric, Verdict, evaluator


@dataclass(frozen=True, slots=True)
class ContainsKeywordsResult:
    recall: Annotated[float, Metric]
    all_present: Annotated[bool, Verdict]


@dataclass(frozen=True, slots=True)
class DoesNotContainResult:
    ok: Annotated[bool, Verdict]


@dataclass(frozen=True, slots=True)
class MaxLengthResult:
    conciseness: Annotated[float, Metric]
    within_limit: Annotated[bool, Verdict]


@dataclass(frozen=True, slots=True)
class JsonValidResult:
    valid: Annotated[bool, Verdict]
    has_required_keys: Annotated[bool, Verdict]


@dataclass(frozen=True, slots=True)
class WordOverlapResult:
    overlap: Annotated[float, Metric]


@evaluator
def contains_keywords(
    ctx: EvalContext[Any, str], keywords: list[str], min_recall: float = 1.0
) -> ContainsKeywordsResult:
    """Check that the output contains expected keywords (case-insensitive).

    `min_recall` is the minimum fraction of keywords that must appear for
    the verdict to pass. Default `1.0` requires all keywords to be present;
    set to `0.5` for "at least half", `0.0` to ignore the verdict and only
    track the metric.
    """
    output_lower = ctx.output.lower()
    found = sum(1 for kw in keywords if kw.lower() in output_lower)
    total = len(keywords)
    recall = found / total if total else 1.0
    return ContainsKeywordsResult(
        recall=recall,
        all_present=recall >= min_recall,
    )


@evaluator
def contains_expected(ctx: EvalContext[Any, str], case_sensitive: bool = False) -> bool:
    """Check that the output contains expected_output as a substring.

    Requires a non-empty `expected` on the case: with None there is nothing
    to check, and with an empty or whitespace-only string ``"" in output`` is
    true for every output. Either way a vacuous pass would make a wiring
    mistake (case data not reaching the eval) look like a healthy run.
    """
    if ctx.expected_output is None:
        raise ValueError(
            f"contains_expected on case '{ctx.name}': expected_output is None. "
            f"This evaluator needs EvalCase(expected=...) to have something to "
            f"check; a vacuous pass would hide a case-wiring mistake. Set "
            f"expected on the case, or attach this evaluator per-case via "
            f"EvalCase(evaluators=[...]) when only some cases carry expected."
        )
    if isinstance(ctx.expected_output, str) and not ctx.expected_output.strip():
        raise ValueError(
            f"contains_expected on case '{ctx.name}': expected_output is empty "
            f"or whitespace-only. An empty string is a substring of every "
            f"output, so the check would pass vacuously regardless of the "
            f"result. Set a non-empty expected on the case, or attach this "
            f"evaluator per-case via EvalCase(evaluators=[...])."
        )
    if case_sensitive:
        return ctx.expected_output in ctx.output
    return ctx.expected_output.lower() in ctx.output.lower()


@evaluator
def does_not_contain(
    ctx: EvalContext[Any, str], forbidden: list[str], case_sensitive: bool = False
) -> DoesNotContainResult:
    """Check that the output does not contain forbidden words."""
    output = ctx.output if case_sensitive else ctx.output.lower()
    found = [w for w in forbidden if (w if case_sensitive else w.lower()) in output]
    return DoesNotContainResult(ok=len(found) == 0)


@evaluator
def not_empty(ctx: EvalContext[Any, Any]) -> bool:
    """Check that the output is not empty.

    - `None` -> False.
    - `str`: False if empty or whitespace-only.
    - Sized (list, dict, set, tuple, ...): False if `len() == 0`.
    - Other (int, float, dataclass, custom objects): True.
    """
    if ctx.output is None:
        return False
    if isinstance(ctx.output, str):
        return len(ctx.output.strip()) > 0
    if isinstance(ctx.output, Sized):
        return len(ctx.output) > 0
    return True


@evaluator
def max_length(ctx: EvalContext[Any, str], max_chars: int = 500) -> MaxLengthResult:
    """Check that the output doesn't exceed a character limit."""
    length = len(ctx.output)
    return MaxLengthResult(
        conciseness=min(1.0, max_chars / max(length, 1)),
        within_limit=length <= max_chars,
    )


@evaluator
def min_length(ctx: EvalContext[Any, str], min_chars: int = 1) -> bool:
    """Check that the output meets a minimum length."""
    return len(ctx.output) >= min_chars


@evaluator
def matches_regex(ctx: EvalContext[Any, str], pattern: str, flags: int = 0) -> bool:
    """Check that the output matches a regex pattern."""
    return bool(re.search(pattern, ctx.output, flags))


@evaluator
def json_valid(
    ctx: EvalContext[Any, str], required_keys: list[str] | None = None
) -> JsonValidResult:
    """Check that the output is valid JSON, optionally with required keys."""
    if required_keys is None:
        required_keys = []
    try:
        parsed = json_module.loads(ctx.output)
    except (json_module.JSONDecodeError, TypeError):
        return JsonValidResult(valid=False, has_required_keys=False)

    has_keys = (
        all(k in parsed for k in required_keys)
        if required_keys and isinstance(parsed, dict)
        else True
    )
    return JsonValidResult(valid=True, has_required_keys=has_keys)


@evaluator
def word_overlap(ctx: EvalContext[Any, str]) -> WordOverlapResult:
    """Compute word overlap between output and expected_output (tracking-only).

    Requires a non-empty `expected` on the case: with None there is nothing
    to overlap with, and with an empty or whitespace-only string there are no
    words to compare against. Either way reporting a perfect 1.0 would poison
    the tracked metric while hiding a case-wiring mistake.
    """
    if ctx.expected_output is None:
        raise ValueError(
            f"word_overlap on case '{ctx.name}': expected_output is None. "
            f"This evaluator needs EvalCase(expected=...) to have something "
            f"to compare against; a fake 1.0 would poison the tracked "
            f"metric. Set expected on the case, or attach this evaluator "
            f"per-case via EvalCase(evaluators=[...]) when only some cases "
            f"carry expected."
        )
    expected = str(ctx.expected_output)
    expected_words = set(expected.lower().split())
    output_words = set(ctx.output.lower().split())
    if not expected_words:
        raise ValueError(
            f"word_overlap on case '{ctx.name}': expected_output is empty or "
            f"whitespace-only, so there are no words to compare against. "
            f"Reporting overlap=1.0 would poison the tracked metric. Set a "
            f"non-empty expected on the case, or attach this evaluator "
            f"per-case via EvalCase(evaluators=[...])."
        )
    return WordOverlapResult(
        overlap=len(expected_words & output_words) / len(expected_words),
    )
