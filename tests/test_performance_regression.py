"""
Performance regression tests for foobara-py.

These tests establish baseline performance thresholds to detect
performance regressions in critical paths.

Uses pytest-benchmark for consistent, reliable performance testing.

Note: Install pytest-benchmark to run these tests:
    pip install pytest-benchmark
"""

import pytest
from pydantic import BaseModel

from foobara_py.core.command import Command
from foobara_py.core.errors import ErrorCollection, FoobaraError

# Check if pytest-benchmark is available
try:
    import pytest_benchmark
    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False

pytestmark = pytest.mark.skipif(
    not HAS_BENCHMARK,
    reason="pytest-benchmark not installed. Install with: pip install pytest-benchmark"
)


# Baseline performance thresholds (in microseconds)
THRESHOLDS = {
    "simple_command": 150,  # μs - Simple command execution
    "error_heavy": 300,  # μs - Error handling and validation
    "subcommand": 250,  # μs - Subcommand delegation
}


class SimpleInputs(BaseModel):
    value: int


class SimpleCommand(Command[SimpleInputs, int]):
    """Minimal command for baseline performance testing"""

    def execute(self) -> int:
        return self.inputs.value * 2


class ErrorHeavyInputs(BaseModel):
    email: str
    age: int
    password: str


class ErrorHeavyCommand(Command[ErrorHeavyInputs, str]):
    """Command with extensive validation for error handling performance"""

    def execute(self) -> str:
        errors = []

        # Validate email
        if "@" not in self.inputs.email:
            self.add_input_error(
                path=["email"], symbol="invalid_format", message="Email must contain @"
            )
            errors.append("email")

        if len(self.inputs.email) < 5:
            self.add_input_error(
                path=["email"], symbol="too_short", message="Email too short"
            )
            errors.append("email_short")

        # Validate age
        if self.inputs.age < 0:
            self.add_input_error(
                path=["age"], symbol="invalid_value", message="Age must be positive"
            )
            errors.append("age")

        if self.inputs.age > 150:
            self.add_input_error(
                path=["age"], symbol="too_large", message="Age too large"
            )
            errors.append("age_large")

        # Validate password
        if len(self.inputs.password) < 8:
            self.add_input_error(
                path=["password"], symbol="too_short", message="Password too short"
            )
            errors.append("password")

        if not any(c.isupper() for c in self.inputs.password):
            self.add_input_error(
                path=["password"],
                symbol="missing_uppercase",
                message="Password needs uppercase",
            )
            errors.append("password_upper")

        if errors:
            return ""

        return "valid"


class OuterCommandInputs(BaseModel):
    value: int


class InnerCommand(Command[SimpleInputs, int]):
    """Inner command for subcommand testing"""

    def execute(self) -> int:
        return self.inputs.value + 10


class OuterCommand(Command[OuterCommandInputs, int]):
    """Command that delegates to subcommand"""

    def execute(self) -> int:
        # Call subcommand
        result = self.run_subcommand(InnerCommand, {"value": self.inputs.value})
        if result.is_success():
            return result.value * 2
        return 0


@pytest.mark.benchmark
class TestPerformanceRegression:
    """Performance regression test suite"""

    def test_simple_command_performance(self, benchmark):
        """
        Baseline: Simple command execution should complete within 150μs.

        This establishes the minimum overhead of the command framework.
        """

        def execute_simple():
            return SimpleCommand.run(value=42)

        result = benchmark(execute_simple)

        # Verify correctness
        assert result.is_success()
        assert result.value == 84

        # Check performance threshold
        stats = benchmark.stats
        mean_time_us = stats.mean * 1_000_000  # Convert to microseconds

        assert (
            mean_time_us < THRESHOLDS["simple_command"]
        ), f"Simple command execution took {mean_time_us:.2f}μs, threshold is {THRESHOLDS['simple_command']}μs"

    def test_error_heavy_performance(self, benchmark):
        """
        Baseline: Error-heavy validation should complete within 300μs.

        Tests performance of error collection and validation logic.
        """

        def execute_with_errors():
            return ErrorHeavyCommand.run(email="bad", age=-5, password="short")

        result = benchmark(execute_with_errors)

        # Verify errors are collected correctly
        assert result.is_failure()
        assert len(result.errors) > 0

        # Check performance threshold
        stats = benchmark.stats
        mean_time_us = stats.mean * 1_000_000

        assert (
            mean_time_us < THRESHOLDS["error_heavy"]
        ), f"Error-heavy execution took {mean_time_us:.2f}μs, threshold is {THRESHOLDS['error_heavy']}μs"

    def test_subcommand_performance(self, benchmark):
        """
        Baseline: Subcommand delegation should complete within 250μs.

        Tests performance of subcommand execution path.
        """

        def execute_with_subcommand():
            return OuterCommand.run(value=10)

        result = benchmark(execute_with_subcommand)

        # Verify correctness
        assert result.is_success()
        assert result.value == 40  # (10 + 10) * 2

        # Check performance threshold
        stats = benchmark.stats
        mean_time_us = stats.mean * 1_000_000

        assert (
            mean_time_us < THRESHOLDS["subcommand"]
        ), f"Subcommand execution took {mean_time_us:.2f}μs, threshold is {THRESHOLDS['subcommand']}μs"

    def test_error_collection_performance(self, benchmark):
        """Test error collection operations performance"""

        def create_error_collection():
            collection = ErrorCollection()
            for i in range(10):
                collection.add(
                    FoobaraError.data_error(
                        symbol=f"error_{i}", path=["field", str(i)], message=f"Error {i}"
                    )
                )
            return collection

        collection = benchmark(create_error_collection)

        # Verify correctness
        assert collection.count() == 10
        assert not collection.is_empty()

    def test_error_querying_performance(self, benchmark):
        """Test error collection query performance"""
        # Setup: Create a collection with various errors
        collection = ErrorCollection()
        for i in range(20):
            category = "data" if i % 2 == 0 else "runtime"
            if category == "data":
                collection.add(
                    FoobaraError.data_error(
                        symbol=f"error_{i}",
                        path=["field", str(i)],
                        message=f"Error {i}",
                    )
                )
            else:
                collection.add(
                    FoobaraError.runtime_error(
                        symbol=f"error_{i}", message=f"Error {i}"
                    )
                )

        def query_errors():
            data_errors = collection.data_errors()
            runtime_errors = collection.runtime_errors()
            field_0_errors = collection.at_path(["field", "0"])
            required_errors = collection.with_symbol("error_0")
            return len(data_errors) + len(runtime_errors) + len(field_0_errors)

        result = benchmark(query_errors)

        # Verify queries work correctly
        assert result > 0


@pytest.mark.benchmark
class TestPerformanceBaseline:
    """Additional baseline tests for performance monitoring"""

    def test_command_instantiation(self, benchmark):
        """Test command instance creation overhead"""

        def create_command():
            return SimpleCommand(inputs=SimpleInputs(value=42))

        cmd = benchmark(create_command)
        assert cmd is not None

    def test_outcome_creation(self, benchmark):
        """Test outcome object creation overhead"""

        def create_outcome():
            from foobara_py.core.outcome import CommandOutcome

            return CommandOutcome(value=42, errors=ErrorCollection())

        outcome = benchmark(create_outcome)
        assert outcome.is_success()

    def test_error_key_generation(self, benchmark):
        """Test error key generation performance"""
        error = FoobaraError.data_error(
            symbol="test_error", path=["user", "email"], message="Test"
        )

        def generate_key():
            return error.key()

        key = benchmark(generate_key)
        assert key == "data.user.email.test_error"


if __name__ == "__main__":
    # Run with: pytest tests/test_performance_regression.py -v --benchmark-only
    pytest.main([__file__, "-v", "--benchmark-only"])
