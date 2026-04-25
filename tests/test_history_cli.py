"""Tests for `protest history` CLI argument parsing.

Covers mutually-exclusive flag groups:
- Action: `--runs` / `--show` / `--compare`
- Kind:   `--evals` / `--tests`

`handle_history_command(argv)` triggers `SystemExit(2)` from argparse when a
mutex is violated. Tests assert both the exit code and the stderr message
mentioning the conflicting flag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from protest.cli.history import handle_history_command
from protest.history.storage import HISTORY_FILE, append_entry

if TYPE_CHECKING:
    from pathlib import Path


class TestActionMutex:
    """`--runs`, `--show`, `--compare` cannot be combined."""

    @pytest.mark.parametrize(
        ("argv", "expected_flag"),
        [
            (["--runs", "--compare"], "--compare"),
            (["--compare", "--runs"], "--runs"),
            (["--runs", "--show", "0"], "--show"),
            (["--show", "0", "--runs"], "--runs"),
            (["--show", "1", "--compare"], "--compare"),
            (["--compare", "--show", "1"], "--show"),
        ],
    )
    def test_mutex_violation_exits_with_error(
        self,
        argv: list[str],
        expected_flag: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            handle_history_command(argv)
        assert exc_info.value.code == 2
        stderr = capsys.readouterr().err
        assert "not allowed with argument" in stderr
        assert expected_flag in stderr


class TestKindMutex:
    """`--evals` and `--tests` cannot be combined."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["--evals", "--tests"],
            ["--tests", "--evals"],
        ],
    )
    def test_mutex_violation_exits_with_error(
        self,
        argv: list[str],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            handle_history_command(argv)
        assert exc_info.value.code == 2
        stderr = capsys.readouterr().err
        assert "not allowed with argument" in stderr


class TestMutexIndependence:
    """Flags from different groups can be combined freely."""

    @pytest.mark.parametrize(
        "action_flags",
        [
            ["--runs"],
            ["--compare"],
            ["--show", "0"],
        ],
    )
    @pytest.mark.parametrize("kind_flag", ["--evals", "--tests"])
    def test_cross_group_combinations_parse_cleanly(
        self,
        action_flags: list[str],
        kind_flag: str,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        argv = [*action_flags, kind_flag, "--path", str(tmp_path)]
        with pytest.raises(SystemExit) as exc_info:
            handle_history_command(argv)
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "not allowed with argument" not in captured.err


class TestHelpShowsMutex:
    """`--help` output surfaces both mutex groups in usage line."""

    def test_help_output_shows_action_and_kind_groups(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            handle_history_command(["--help"])
        assert exc_info.value.code == 0
        stdout = capsys.readouterr().out
        assert "[--runs | --show [N] | --compare]" in stdout
        assert "[--evals | --tests]" in stdout


class TestRunsOrderRecentFirst:
    """`--runs` lists most-recent run first (git log convention).

    Storage returns entries oldest→newest; the CLI must reverse for display
    so #1 maps to the newest run, matching `git stash list` / `git log`.
    """

    def _seed(self, tmp_path: Path, commits: list[tuple[str, str]]) -> None:
        path = tmp_path / HISTORY_FILE
        for ts, commit in commits:
            append_entry(
                path,
                {
                    "schema_version": 1,
                    "run_id": commit,
                    "timestamp": ts,
                    "git": {"commit_short": commit},
                    "suites": {},
                },
            )

    def test_runs_displays_newest_first(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Seed in chronological order — storage preserves write order.
        self._seed(
            tmp_path,
            [
                ("2026-04-25T10:00:00", "old1234"),
                ("2026-04-25T11:00:00", "mid5678"),
                ("2026-04-25T12:00:00", "newabcd"),
            ],
        )
        handle_history_command(["--runs", "--path", str(tmp_path)])
        stdout = capsys.readouterr().out
        # #1 is newest, #3 is oldest.
        assert stdout.index("#1") < stdout.index("#2") < stdout.index("#3")
        assert (
            stdout.index("newabcd") < stdout.index("mid5678") < stdout.index("old1234")
        )
        # And #1 lines up with the newest commit, not the oldest.
        newest_line = next(line for line in stdout.splitlines() if "#1" in line)
        assert "newabcd" in newest_line
