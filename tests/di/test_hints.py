"""Tests for the type-hint resolver (`get_type_hints_compat`), issue #112.

DI reads Use/From markers out of resolved type hints. get_type_hints resolves
the whole signature atomically, so a single unresolvable name (typically a
return annotation imported only under `if TYPE_CHECKING:`) drops every hint,
markers included. That used to silently disable injection; now it raises
TypeHintResolutionError when a DI marker is at stake, and keeps degrading to
{} when nothing is silently lost.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

from protest.di.hints import get_type_hints_compat
from protest.exceptions import TypeHintResolutionError

if TYPE_CHECKING:
    from pathlib import Path


def _load(tmp_path: Path, name: str, source: str) -> object:
    """Write a module to tmp_path, import it, return the named eval function."""
    inner = tmp_path / "inner112.py"
    if not inner.exists():
        inner.write_text(
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class MyResult:\n"
            "    value: str = ''\n"
            "def my_fixture() -> str:\n"
            "    return 'injected'\n"
        )
    mod_path = tmp_path / f"{name}.py"
    mod_path.write_text(textwrap.dedent(source))

    sys.path.insert(0, str(tmp_path))
    try:
        spec = importlib.util.spec_from_file_location(name, mod_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module.my_eval
    finally:
        sys.path.remove(str(tmp_path))


class TestSilentInjectionFailureNowLoud:
    def test_unresolvable_return_with_di_marker_raises(self, tmp_path: Path) -> None:
        """A TYPE_CHECKING-only return type that breaks resolution, on a
        signature with a Use() param, raises instead of dropping the dep."""
        func = _load(
            tmp_path,
            "sess_raise",
            """
            from __future__ import annotations
            from typing import TYPE_CHECKING, Annotated
            from protest import Use
            from inner112 import my_fixture

            if TYPE_CHECKING:
                import inner112

            def my_eval(
                dep: Annotated[str, Use(my_fixture)],
            ) -> "inner112.MyResult":
                return None
            """,
        )
        with pytest.raises(TypeHintResolutionError) as excinfo:
            get_type_hints_compat(func)
        msg = str(excinfo.value)
        assert "my_eval" in msg
        assert "TYPE_CHECKING" in msg

    def test_typecheck_only_generic_inner_still_resolves(self, tmp_path: Path) -> None:
        """TaskResult[MyResult] with MyResult under TYPE_CHECKING resolves via
        the substitute-Any fallback - the Use() dep is still injected."""
        func = _load(
            tmp_path,
            "sess_ok",
            """
            from __future__ import annotations
            from typing import TYPE_CHECKING, Annotated
            from protest import Use
            from protest.evals.types import TaskResult
            from inner112 import my_fixture

            if TYPE_CHECKING:
                from inner112 import MyResult

            def my_eval(
                dep: Annotated[str, Use(my_fixture)],
            ) -> TaskResult[MyResult]:
                return TaskResult(output="x")
            """,
        )
        hints = get_type_hints_compat(func)
        assert "dep" in hints

    def test_unresolvable_return_without_di_marker_degrades(
        self, tmp_path: Path
    ) -> None:
        """No DI marker at stake -> keep degrading to {}, don't raise: a plain
        function with a TYPE_CHECKING-only return annotation stays usable."""
        func = _load(
            tmp_path,
            "sess_plain",
            """
            from __future__ import annotations
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                import inner112

            def my_eval() -> "inner112.MyResult":
                return None
            """,
        )
        assert get_type_hints_compat(func) == {}


class TestResolvableSignaturesUnaffected:
    def test_plain_resolvable_signature(self) -> None:
        def my_eval(x: int, y: str) -> bool:
            return True

        hints = get_type_hints_compat(my_eval)
        assert hints == {"x": int, "y": str, "return": bool}
