class ApteError(Exception):
    """Base exception for all errors raised by the Apte framework."""


class FixtureError(ApteError):
    """Raised when a factory fixture fails during test execution."""

    def __init__(self, fixture_name: str, original: Exception):
        self.fixture_name = fixture_name
        self.original = original
        super().__init__(f"Factory '{fixture_name}' failed: {original}")


class ScopeMismatchError(ApteError):
    def __init__(
        self,
        requester_name: str,
        requester_scope: str,
        dependency_name: str,
        dependency_scope: str,
    ):
        super().__init__(
            f"Fixture '{requester_name}' at scope '{requester_scope}' "
            f"cannot depend on '{dependency_name}' at scope '{dependency_scope}'."
        )


class AlreadyRegisteredError(ApteError):
    def __init__(self, function_name: str):
        super().__init__(f"Function '{function_name}' is already registered.")


class UnregisteredDependencyError(ApteError):
    def __init__(self, fixture_name: str, dependency_name: str):
        super().__init__(
            f"Fixture '{fixture_name}' depends on unregistered "
            f"function '{dependency_name}'. "
            f"Register '{dependency_name}' first."
        )


class FixtureNotFoundError(ApteError):
    def __init__(self, fixture_name: str):
        super().__init__(f"Fixture '{fixture_name}' is not registered.")


class TypeHintResolutionError(ApteError):
    """Raised when a function's type hints can't be resolved at runtime and
    that failure would silently disable dependency injection.

    DI reads the ``Use(...)``/``From(...)`` markers out of resolved type
    hints. ``get_type_hints`` resolves the whole signature atomically, so a
    single unresolvable name anywhere - typically a return annotation whose
    inner type is imported only under ``if TYPE_CHECKING:`` - drops every
    hint, markers included, and injection would silently inject nothing.
    Raising points at the culprit instead of degrading silently.
    """

    def __init__(
        self, func_name: str, annotations: dict[str, object], original: Exception
    ):
        self.func_name = func_name
        self.original = original
        rendered = ", ".join(f"{k}: {v!r}" for k, v in annotations.items())
        super().__init__(
            f"Could not resolve type hints for '{func_name}' ({original}). "
            f"A type referenced in its signature is not importable at runtime "
            f"- is it imported only under `if TYPE_CHECKING:`? It must be "
            f"importable at runtime (module level, not TYPE_CHECKING) for "
            f"dependency injection to resolve the Use(...)/From(...) markers; "
            f"otherwise injection silently does nothing. Annotations: {rendered}"
        )


class ParameterizedFixtureError(ApteError):
    def __init__(self, fixture_name: str, param_names: list[str]):
        params = ", ".join(param_names)
        super().__init__(
            f"Fixture '{fixture_name}' uses From() on parameters: {params}. "
            f"From() is only allowed in tests, not fixtures. "
            f"Use a factory instead and let the test control parameterization."
        )


class PlainFunctionError(ApteError):
    def __init__(self, func_name: str):
        super().__init__(
            f"Function '{func_name}' must be decorated with @fixture() or @factory(). "
            f"Plain functions are not allowed as fixtures."
        )


class CircularDependencyError(ApteError):
    def __init__(self, cycle_path: list[str]):
        cycle_str = " -> ".join(cycle_path)
        super().__init__(f"Circular dependency detected: {cycle_str}")


class ConcurrencyMismatchError(ApteError):
    """Raised when a child suite has higher max_concurrency than its parent."""

    def __init__(
        self,
        child_name: str,
        child_max_concurrency: int,
        parent_name: str,
        parent_effective_concurrency: int,
    ):
        super().__init__(
            f"Suite '{child_name}' has max_concurrency={child_max_concurrency} "
            f"which exceeds parent '{parent_name}' "
            f"(effective max_concurrency={parent_effective_concurrency})."
        )


class InvalidMaxConcurrencyError(ApteError):
    """Raised when max_concurrency has an invalid value."""

    def __init__(self, value: int):
        super().__init__(
            f"max_concurrency must be >= 1, got {value}. "
            f"Use None for unlimited concurrency."
        )


class MultipleEvalCaseParamsError(ApteError):
    """Raised when an eval function declares more than one EvalCase parameter.

    Only one EvalCase per eval is supported: it determines the case identity
    (name, expected, inputs, metadata, per-case evaluators) used by the
    runner, history, and reporters. Additional EvalCase parameters would be
    silently ignored downstream.
    """

    def __init__(self, func_name: str, param_names: list[str]):
        params = ", ".join(param_names)
        super().__init__(
            f"Eval '{func_name}' declares multiple EvalCase parameters: {params}. "
            f"Only one EvalCase parameter is supported per eval - it is used "
            f"for case identity (name), expected output, inputs, metadata, "
            f"and per-case evaluators. Merge the cases into a single EvalCase, "
            f"or split into separate evals."
        )


class NoEvaluatorsError(ApteError):
    """Raised when an eval case ends up with zero evaluators at runtime.

    `passed` is computed as `all(s.passed for s in scores)` and `all([])`
    is `True` - an eval with no evaluators would silently pass no matter
    what the task returned, making a wiring mistake (forgotten
    `evaluators=`, per-case evaluators not attached) indistinguishable
    from a healthy eval. The guard runs at execution time because
    per-case evaluators are only known then.
    """

    def __init__(self, case_name: str):
        super().__init__(
            f"Eval '{case_name}' has no evaluators. An eval with zero "
            f"evaluators would always pass (all([]) is True), hiding wiring "
            f"mistakes. Pass evaluators= to @suite.eval(...) or attach "
            f"per-case evaluators via EvalCase(evaluators=[...])."
        )


class ScoreNameCollisionError(ApteError):
    """Raised when two evaluators in the same eval emit scores with the same name.

    Score names are namespaced by evaluator (`<evaluator>.<field>` for
    dataclass results, the evaluator's name for bool results), so distinct
    evaluators can freely share field names like `ok` or `detail`. A
    collision therefore means the same evaluator name appears twice on one
    case - e.g. the same `@evaluator` function attached twice (possibly with
    different bound kwargs), or two functions sharing a `__name__`. The
    duplicate scores would silently overwrite each other in the per-case
    report and history, so we fail loud instead.
    """

    def __init__(self, case_name: str, duplicates: list[str]):
        dup_str = ", ".join(repr(d) for d in sorted(duplicates))
        super().__init__(
            f"Score-name collision in eval '{case_name}': {dup_str}. "
            f"Scores are namespaced per evaluator, so this means the same "
            f"evaluator name appears more than once on this case - the same "
            f"@evaluator attached twice (e.g. with different bound kwargs) "
            f"or two functions sharing a name. Wrap each binding in its own "
            f"named @evaluator function so every score name is unique."
        )
