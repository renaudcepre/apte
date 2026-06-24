"""Tests for max_concurrency inheritance in nested suites (issue #52)."""

import pytest

from apte import ApteSession, ApteSuite
from apte.core.runner import TestRunner
from apte.entities import SuitePath
from apte.exceptions import ConcurrencyMismatchError
from tests.conftest import ConcurrencyTracker, register_concurrent_tests


class TestEffectiveMaxConcurrencyProperty:
    """Tests for effective_max_concurrency property."""

    def test_explicit_value_returned(self) -> None:
        """Suite with explicit max_concurrency returns it."""
        suite = ApteSuite("test", max_concurrency=5)
        assert suite.effective_max_concurrency == 5

    def test_none_when_not_set_and_no_parent(self) -> None:
        """Suite without max_concurrency and no parent returns None."""
        suite = ApteSuite("test")
        assert suite.effective_max_concurrency is None

    def test_inherits_from_parent(self) -> None:
        """Child without explicit max_concurrency inherits from parent."""
        parent = ApteSuite("parent", max_concurrency=5)
        child = ApteSuite("child")
        parent.add_suite(child)

        assert child.effective_max_concurrency == 5

    def test_explicit_overrides_parent(self) -> None:
        """Child with explicit max_concurrency uses its own value."""
        parent = ApteSuite("parent", max_concurrency=10)
        child = ApteSuite("child", max_concurrency=3)
        parent.add_suite(child)

        assert child.effective_max_concurrency == 3

    def test_deeply_nested_inheritance(self) -> None:
        """Deeply nested suites inherit through the chain."""
        grandparent = ApteSuite("gp", max_concurrency=8)
        parent = ApteSuite("p")
        child = ApteSuite("c")

        grandparent.add_suite(parent)
        parent.add_suite(child)

        assert parent.effective_max_concurrency == 8
        assert child.effective_max_concurrency == 8

    def test_intermediate_override(self) -> None:
        """Intermediate suite can override and child inherits new value."""
        grandparent = ApteSuite("gp", max_concurrency=10)
        parent = ApteSuite("p", max_concurrency=5)
        child = ApteSuite("c")

        grandparent.add_suite(parent)
        parent.add_suite(child)

        assert child.effective_max_concurrency == 5

    def test_max_concurrency_unchanged(self) -> None:
        """Original max_concurrency property still returns explicit value."""
        parent = ApteSuite("parent", max_concurrency=5)
        child = ApteSuite("child")
        parent.add_suite(child)

        # max_concurrency returns what was explicitly set
        assert child.max_concurrency is None
        # effective_max_concurrency returns inherited value
        assert child.effective_max_concurrency == 5


class TestConcurrencyValidation:
    """Tests for max_concurrency validation in add_suite()."""

    def test_child_lower_than_parent_allowed(self) -> None:
        """Child with lower max_concurrency than parent is valid."""
        parent = ApteSuite("parent", max_concurrency=10)
        child = ApteSuite("child", max_concurrency=5)

        parent.add_suite(child)

        assert child.full_path == SuitePath("parent::child")

    def test_child_equal_to_parent_allowed(self) -> None:
        """Child with equal max_concurrency to parent is valid."""
        parent = ApteSuite("parent", max_concurrency=5)
        child = ApteSuite("child", max_concurrency=5)

        parent.add_suite(child)

    def test_child_none_with_parent_set_allowed(self) -> None:
        """Child with None max_concurrency inherits from parent."""
        parent = ApteSuite("parent", max_concurrency=5)
        child = ApteSuite("child")

        parent.add_suite(child)

    def test_child_set_with_parent_none_allowed(self) -> None:
        """Child can set max_concurrency when parent has None."""
        parent = ApteSuite("parent")
        child = ApteSuite("child", max_concurrency=100)

        parent.add_suite(child)

    def test_both_none_allowed(self) -> None:
        """Both parent and child with None is valid."""
        parent = ApteSuite("parent")
        child = ApteSuite("child")

        parent.add_suite(child)

    def test_child_exceeds_parent_raises(self) -> None:
        """Child with higher max_concurrency than parent raises error."""
        parent = ApteSuite("parent", max_concurrency=5)
        child = ApteSuite("child", max_concurrency=10)

        with pytest.raises(ConcurrencyMismatchError) as exc_info:
            parent.add_suite(child)

        assert "child" in str(exc_info.value)
        assert "max_concurrency=10" in str(exc_info.value)
        assert "parent" in str(exc_info.value)
        assert "5" in str(exc_info.value)

    def test_child_exceeds_inherited_parent_raises(self) -> None:
        """Child cannot exceed parent's inherited max_concurrency."""
        grandparent = ApteSuite("gp", max_concurrency=5)
        parent = ApteSuite("p")
        grandparent.add_suite(parent)

        child = ApteSuite("c", max_concurrency=10)

        with pytest.raises(ConcurrencyMismatchError):
            parent.add_suite(child)

    def test_error_message_contains_details(self) -> None:
        """Error message is descriptive."""
        parent = ApteSuite("APITests", max_concurrency=3)
        child = ApteSuite("LoadTests", max_concurrency=100)

        with pytest.raises(ConcurrencyMismatchError) as exc_info:
            parent.add_suite(child)

        error_msg = str(exc_info.value)
        assert "LoadTests" in error_msg
        assert "100" in error_msg
        assert "APITests" in error_msg
        assert "3" in error_msg


class TestRunnerUsesEffectiveConcurrency:
    """Integration tests for runner using effective_max_concurrency."""

    def test_runner_respects_inherited_concurrency(self) -> None:
        """Runner uses effective_max_concurrency for nested suites."""
        session = ApteSession(concurrency=10)
        parent = ApteSuite("parent", max_concurrency=2)
        child = ApteSuite("child")
        parent.add_suite(child)
        session.add_suite(parent)

        tracker = ConcurrencyTracker()
        register_concurrent_tests(child, count=4, tracker=tracker)

        runner = TestRunner(session)
        runner.run()

        assert tracker.max_seen <= 2

    def test_child_explicit_lower_respected(self) -> None:
        """Child's explicit lower max_concurrency is respected."""
        session = ApteSession(concurrency=10)
        parent = ApteSuite("parent", max_concurrency=5)
        child = ApteSuite("child", max_concurrency=1)
        parent.add_suite(child)
        session.add_suite(parent)

        tracker = ConcurrencyTracker()
        register_concurrent_tests(child, count=4, tracker=tracker)

        runner = TestRunner(session)
        runner.run()

        assert tracker.max_seen == 1

    def test_session_concurrency_still_caps(self) -> None:
        """Session concurrency still caps effective_max_concurrency."""
        session = ApteSession(concurrency=2)
        parent = ApteSuite("parent", max_concurrency=10)
        child = ApteSuite("child")
        parent.add_suite(child)
        session.add_suite(parent)

        tracker = ConcurrencyTracker()
        register_concurrent_tests(child, count=4, tracker=tracker)

        runner = TestRunner(session)
        runner.run()

        # min(session=2, effective=10) = 2
        assert tracker.max_seen <= 2
