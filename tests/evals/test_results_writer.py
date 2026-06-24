"""Tests for EvalResultsWriter robustness (issue #119).

Two silent-data-loss gaps in the per-case markdown artifacts:

- distinct case names that sanitize to the same stem (``a/b`` and ``a:b`` ->
  ``a_b``) overwrote each other;
- two runs of the same suite within one second merged into one directory
  (timestamp has one-second resolution).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apte.evals.results_writer import EvalResultsWriter, _make_run_dir
from apte.evals.types import EvalCaseResult

if TYPE_CHECKING:
    from pathlib import Path


def _case(name: str) -> EvalCaseResult:
    return EvalCaseResult(
        case_name=name,
        node_id=f"mod::{name}",
        scores=(),
        duration=0.0,
        passed=True,
    )


class TestCaseNameCollisions:
    def test_colliding_sanitized_names_do_not_overwrite(self, tmp_path: Path) -> None:
        writer = EvalResultsWriter(history_dir=tmp_path)
        writer._write_case_file(_case("a/b"), "suite")
        writer._write_case_file(_case("a:b"), "suite")

        run_dir = next((tmp_path / "results").iterdir())
        files = sorted(p.name for p in run_dir.iterdir())
        assert files == ["a_b-2.md", "a_b.md"]

    def test_each_file_keeps_its_own_content(self, tmp_path: Path) -> None:
        writer = EvalResultsWriter(history_dir=tmp_path)
        writer._write_case_file(_case("a/b"), "suite")
        writer._write_case_file(_case("a:b"), "suite")

        run_dir = next((tmp_path / "results").iterdir())
        contents = {(run_dir / name).read_text() for name in ("a_b.md", "a_b-2.md")}
        # The original (unsanitized) names survive in the rendered title.
        assert any("a/b" in c for c in contents)
        assert any("a:b" in c for c in contents)

    def test_empty_name_falls_back_to_case_stem(self, tmp_path: Path) -> None:
        # case_name can be "" (payload.case_name or ""); sanitizing yields an
        # empty stem, which would produce a bare ".md" - fall back to "case".
        writer = EvalResultsWriter(history_dir=tmp_path)
        writer._write_case_file(_case(""), "suite")

        run_dir = next((tmp_path / "results").iterdir())
        assert [p.name for p in run_dir.iterdir()] == ["case.md"]


class TestRunDirUniqueness:
    def test_successive_runs_get_distinct_dirs(self, tmp_path: Path) -> None:
        # Three back-to-back calls almost certainly share a one-second
        # timestamp, exercising the suffix-bump loop. Regardless of whether a
        # second boundary is crossed, each dir must be unique and exist.
        dirs = [_make_run_dir("suite", tmp_path) for _ in range(3)]
        assert len({str(d) for d in dirs}) == 3
        assert all(d.exists() for d in dirs)

    def test_collision_with_existing_dir_is_suffixed(self, tmp_path: Path) -> None:
        # Pre-create the exact directory the next call will compute, forcing
        # the FileExistsError branch deterministically.
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        (tmp_path / f"suite_{ts}").mkdir()

        run_dir = _make_run_dir("suite", tmp_path)
        # Either the pre-created second elapsed (new ts) or we got the suffix;
        # in the common same-second case the suffix branch is taken.
        assert run_dir.name != f"suite_{ts}"
        assert run_dir.exists()
