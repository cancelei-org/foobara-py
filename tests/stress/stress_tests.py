"""
Comprehensive Stress Tests for foobara-py

This module contains comprehensive stress tests that measure:
1. Command Performance
2. Type System Performance
3. Error Handling Performance
4. Concern Architecture Performance
5. Integration Tests
6. Stress Testing under load
7. Memory and Resource Management

Run with: pytest tests/stress/stress_tests.py -v --benchmark-only
Or: python tests/stress/stress_tests.py
"""

import asyncio
import gc
import json
import statistics
import sys
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from foobara_py import Command, AsyncCommand, CommandOutcome
from foobara_py.core.errors import ErrorCollection, FoobaraError
from foobara_py.persistence import EntityBase, InMemoryRepository, entity
from foobara_py.domain import Domain


# ==================== Benchmark Utilities ====================

@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""
    name: str
    iterations: int
    min_ns: float
    max_ns: float
    mean_ns: float
    median_ns: float
    p95_ns: float
    p99_ns: float
    stdev_ns: float
    total_ms: float
    ops_per_sec: float
    memory_peak_mb: Optional[float] = None
    memory_allocated_mb: Optional[float] = None


def benchmark(
    func: Callable,
    iterations: int = 1000,
    warmup: int = 100,
    measure_memory: bool = False
) -> BenchmarkResult:
    """
    Run benchmark and return detailed timing statistics.

    Args:
        func: Function to benchmark
        iterations: Number of iterations to run
        warmup: Number of warmup iterations
        measure_memory: Whether to measure memory usage
    """
    # Warmup
    for _ in range(warmup):
        func()

    # Collect garbage before measuring
    gc.collect()

    # Start memory tracking if requested
    if measure_memory:
        tracemalloc.start()
        tracemalloc.reset_peak()

    # Benchmark
    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        func()
        end = time.perf_counter_ns()
        times.append(end - start)

    # Get memory stats
    memory_peak = None
    memory_allocated = None
    if measure_memory:
        current, peak = tracemalloc.get_traced_memory()
        memory_peak = peak / (1024 * 1024)  # Convert to MB
        memory_allocated = current / (1024 * 1024)
        tracemalloc.stop()

    # Calculate statistics
    times_sorted = sorted(times)
    total_ns = sum(times)

    return BenchmarkResult(
        name=func.__name__ if hasattr(func, '__name__') else str(func),
        iterations=iterations,
        min_ns=min(times),
        max_ns=max(times),
        mean_ns=statistics.mean(times),
        median_ns=statistics.median(times),
        p95_ns=times_sorted[int(len(times) * 0.95)],
        p99_ns=times_sorted[int(len(times) * 0.99)],
        stdev_ns=statistics.stdev(times) if len(times) > 1 else 0,
        total_ms=total_ns / 1_000_000,
        ops_per_sec=iterations / (total_ns / 1_000_000_000),
        memory_peak_mb=memory_peak,
        memory_allocated_mb=memory_allocated,
    )


def format_benchmark_result(result: BenchmarkResult) -> str:
    """Format benchmark result for display"""
    output = f"\n{result.name}:\n"
    output += f"  Iterations: {result.iterations:,}\n"
    output += f"  Mean: {result.mean_ns:,.2f} ns ({result.mean_ns / 1_000:.2f} μs)\n"
    output += f"  Median: {result.median_ns:,.2f} ns ({result.median_ns / 1_000:.2f} μs)\n"
    output += f"  P95: {result.p95_ns:,.2f} ns ({result.p95_ns / 1_000:.2f} μs)\n"
    output += f"  P99: {result.p99_ns:,.2f} ns ({result.p99_ns / 1_000:.2f} μs)\n"
    output += f"  Min: {result.min_ns:,.2f} ns\n"
    output += f"  Max: {result.max_ns:,.2f} ns\n"
    output += f"  StdDev: {result.stdev_ns:,.2f} ns\n"
    output += f"  Throughput: {result.ops_per_sec:,.0f} ops/sec\n"

    if result.memory_peak_mb is not None:
        output += f"  Memory Peak: {result.memory_peak_mb:.2f} MB\n"
    if result.memory_allocated_mb is not None:
        output += f"  Memory Current: {result.memory_allocated_mb:.2f} MB\n"

    return output


# ==================== Test 1: Command Performance ====================

class SimpleInputs(BaseModel):
    """Simple inputs for basic command"""
    a: int
    b: int


class SimpleCommand(Command[SimpleInputs, int]):
    """Simple command for basic benchmarking"""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b


class ComplexInputs(BaseModel):
    """Complex inputs with validation"""
    name: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: int = Field(..., ge=0, le=150)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if len(v) > 10:
            raise ValueError("Too many tags")
        return v


class ComplexOutput(BaseModel):
    """Complex output model"""
    id: int
    name: str
    email: str
    processed: bool = True
    timestamp: float


class ComplexCommand(Command[ComplexInputs, ComplexOutput]):
    """Complex command with validation"""

    def execute(self) -> ComplexOutput:
        return ComplexOutput(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            timestamp=time.time()
        )


class ParentInputs(BaseModel):
    """Inputs for parent command"""
    x: int
    y: int


class ChildCommand(Command[ParentInputs, int]):
    """Child command for subcommand testing"""

    def execute(self) -> int:
        return self.inputs.x * self.inputs.y


class ParentCommand(Command[ParentInputs, int]):
    """Parent command that calls subcommand"""

    def execute(self) -> int:
        result = self.run_subcommand_bang(ChildCommand, x=self.inputs.x, y=self.inputs.y)
        return result + 1


class AsyncSimpleInputs(BaseModel):
    """Inputs for async command"""
    value: int


class AsyncSimpleCommand(AsyncCommand[AsyncSimpleInputs, int]):
    """Simple async command"""

    async def execute(self) -> int:
        await asyncio.sleep(0.001)  # Simulate async work
        return self.inputs.value * 2


def test_command_performance():
    """Test 1: Command Performance"""
    print("\n" + "=" * 70)
    print("TEST 1: COMMAND PERFORMANCE")
    print("=" * 70)

    results = []

    # 1.1 Simple command execution (1000 iterations)
    print("\n1.1 Simple Command Execution (1000 iterations)")
    result = benchmark(
        lambda: SimpleCommand.run(a=5, b=3),
        iterations=1000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 1.2 Complex command with validation (1000 iterations)
    print("\n1.2 Complex Command with Validation (1000 iterations)")
    result = benchmark(
        lambda: ComplexCommand.run(
            name="John Doe",
            email="john@example.com",
            age=30,
            tags=["user", "active"],
            metadata={"source": "api"}
        ),
        iterations=1000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 1.3 Command with subcommands (500 iterations)
    print("\n1.3 Command with Subcommands (500 iterations)")
    result = benchmark(
        lambda: ParentCommand.run(x=5, y=3),
        iterations=500,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 1.4 Async command performance (skipped - requires different setup)
    print("\n1.4 Async Command Performance (SKIPPED)")
    print("  Note: Async command testing requires specialized setup")

    return results


# ==================== Test 2: Type System Performance ====================

class TypeValidationInputs(BaseModel):
    """Inputs for type validation testing"""
    string_field: str
    int_field: int
    float_field: float
    bool_field: bool
    list_field: List[str]


class TypeValidationCommand(Command[TypeValidationInputs, bool]):
    """Command for testing type validation performance"""

    def execute(self) -> bool:
        return True


class CoercionInputs(BaseModel):
    """Inputs for type coercion testing"""
    value: str


class CoercionCommand(Command[CoercionInputs, int]):
    """Command for testing type coercion"""

    def execute(self) -> int:
        return int(self.inputs.value)


def test_type_system_performance():
    """Test 2: Type System Performance"""
    print("\n" + "=" * 70)
    print("TEST 2: TYPE SYSTEM PERFORMANCE")
    print("=" * 70)

    results = []

    # 2.1 Type validation speed (10000 iterations)
    print("\n2.1 Type Validation Speed (10000 iterations)")
    result = benchmark(
        lambda: TypeValidationCommand.run(
            string_field="test",
            int_field=42,
            float_field=3.14,
            bool_field=True,
            list_field=["a", "b", "c"]
        ),
        iterations=10000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 2.2 Pydantic model generation (1000 iterations)
    print("\n2.2 Pydantic Model Generation (1000 iterations)")
    result = benchmark(
        lambda: ComplexInputs(
            name="John",
            email="john@test.com",
            age=30,
            tags=["tag1"],
            metadata={"key": "value"}
        ),
        iterations=1000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 2.3 Type coercion performance (10000 iterations)
    print("\n2.3 Type Coercion Performance (10000 iterations)")
    result = benchmark(
        lambda: CoercionCommand.run(value="42"),
        iterations=10000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    return results


# ==================== Test 3: Error Handling Performance ====================

class ErrorInputs(BaseModel):
    """Inputs for error testing"""
    should_fail: bool = False


class ErrorCreationCommand(Command[ErrorInputs, int]):
    """Command that creates errors"""

    def execute(self) -> int:
        if self.inputs.should_fail:
            self.add_runtime_error("test_error", "Test error message", halt=False)
            self.add_runtime_error("another_error", "Another error", halt=False)
        return 0


class ValidationErrorCommand(Command[ComplexInputs, bool]):
    """Command that triggers validation errors"""

    def execute(self) -> bool:
        return True


class ErrorRecoveryCommand(Command[ErrorInputs, int]):
    """Command with error recovery"""

    def execute(self) -> int:
        try:
            if self.inputs.should_fail:
                raise ValueError("Intentional error")
            return 1
        except ValueError:
            self.add_runtime_error("recovered", "Recovered from error", halt=False)
            return 0


def test_error_handling_performance():
    """Test 3: Error Handling Performance"""
    print("\n" + "=" * 70)
    print("TEST 3: ERROR HANDLING PERFORMANCE")
    print("=" * 70)

    results = []

    # 3.1 Error creation and collection (10000 iterations)
    print("\n3.1 Error Creation and Collection (10000 iterations)")
    result = benchmark(
        lambda: ErrorCreationCommand.run(should_fail=True),
        iterations=10000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 3.2 Error serialization (5000 iterations)
    print("\n3.2 Error Serialization (5000 iterations)")
    def serialize_errors():
        outcome = ErrorCreationCommand.run(should_fail=True)
        if not outcome.is_success():
            return outcome.to_dict()

    result = benchmark(
        serialize_errors,
        iterations=5000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 3.3 Error recovery mechanisms (1000 iterations)
    print("\n3.3 Error Recovery Mechanisms (1000 iterations)")
    result = benchmark(
        lambda: ErrorRecoveryCommand.run(should_fail=True),
        iterations=1000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 3.4 Validation error handling (5000 iterations)
    print("\n3.4 Validation Error Handling (5000 iterations)")
    result = benchmark(
        lambda: ValidationErrorCommand.run(
            name="ab",  # Too short
            email="invalid",
            age=200,  # Too old
            tags=[],
            metadata={}
        ),
        iterations=5000,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    return results


# ==================== Test 4: Concern Architecture ====================

class MinimalCommand(Command[SimpleInputs, int]):
    """Minimal command without extra concerns"""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b


def test_concern_architecture():
    """Test 4: Concern Architecture"""
    print("\n" + "=" * 70)
    print("TEST 4: CONCERN ARCHITECTURE PERFORMANCE")
    print("=" * 70)

    results = []

    # 4.1 Measure mixin overhead
    print("\n4.1 Mixin Overhead (10000 iterations)")

    # Baseline: direct Pydantic model creation
    result_baseline = benchmark(
        lambda: SimpleInputs(a=5, b=3),
        iterations=10000,
        measure_memory=True
    )
    print("\nBaseline (Pydantic only):")
    print(format_benchmark_result(result_baseline))
    results.append(result_baseline)

    # With Command wrapper
    result_command = benchmark(
        lambda: SimpleCommand.run(a=5, b=3),
        iterations=10000,
        measure_memory=True
    )
    print("\nWith Command Architecture:")
    print(format_benchmark_result(result_command))
    results.append(result_command)

    # Calculate overhead
    overhead = result_command.mean_ns / result_baseline.mean_ns
    print(f"\nArchitecture Overhead: {overhead:.2f}x")

    # 4.2 Memory usage comparison
    print("\n4.2 Memory Usage Comparison")

    # Measure memory for 1000 command instances
    tracemalloc.start()
    tracemalloc.reset_peak()

    commands = []
    for i in range(1000):
        commands.append(SimpleCommand.run(a=i, b=i+1))

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"  1000 command executions:")
    print(f"    Peak memory: {peak / (1024 * 1024):.2f} MB")
    print(f"    Current memory: {current / (1024 * 1024):.2f} MB")
    print(f"    Avg per command: {peak / 1000 / 1024:.2f} KB")

    return results


# ==================== Test 5: Integration Tests ====================

@entity(primary_key='id')
class User(EntityBase):
    """User entity for integration testing"""
    id: Optional[int] = None
    name: str
    email: str
    age: int


class UserRepository(InMemoryRepository):
    """Repository for users"""
    pass


class CreateUserInputs(BaseModel):
    """Inputs for creating a user"""
    name: str
    email: str
    age: int


class CreateUserCommand(Command[CreateUserInputs, User]):
    """Command to create a user"""

    def __init__(self, *args, repository: Optional[UserRepository] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.repository = repository or UserRepository()

    def execute(self) -> User:
        user = User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )
        self.repository.save(user)
        return user


def test_integration_performance():
    """Test 5: Integration Tests"""
    print("\n" + "=" * 70)
    print("TEST 5: INTEGRATION PERFORMANCE")
    print("=" * 70)

    results = []

    # 5.1 E2E workflow (100 iterations)
    print("\n5.1 E2E Workflow (100 iterations)")

    repo = UserRepository()

    def e2e_workflow():
        outcome = CreateUserCommand.run(
            name="John Doe",
            email="john@example.com",
            age=30,
            repository=repo
        )
        return outcome.is_success()

    result = benchmark(
        e2e_workflow,
        iterations=100,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    # 5.2 Database operations (500 iterations)
    print("\n5.2 Repository Operations (500 iterations)")

    def repo_operations():
        user = User(id=None, name="Test", email="test@example.com", age=25)
        saved = repo.save(user)
        loaded = repo.find(type(user), saved.id)
        return loaded is not None

    result = benchmark(
        repo_operations,
        iterations=500,
        measure_memory=True
    )
    results.append(result)
    print(format_benchmark_result(result))

    return results


# ==================== Test 6: Stress Testing ====================

def test_concurrent_execution():
    """Test 6: Concurrent Command Execution (100 threads)"""
    print("\n" + "=" * 70)
    print("TEST 6: STRESS TESTING - CONCURRENT EXECUTION")
    print("=" * 70)

    results = []

    # 6.1 Concurrent command execution
    print("\n6.1 Concurrent Command Execution (100 threads, 10 ops each)")

    def worker():
        for _ in range(10):
            outcome = SimpleCommand.run(a=5, b=3)
            assert outcome.is_success()

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(worker) for _ in range(100)]
        for future in futures:
            future.result()

    duration = time.perf_counter() - start
    total_ops = 100 * 10

    print(f"  Total operations: {total_ops}")
    print(f"  Duration: {duration:.2f} seconds")
    print(f"  Throughput: {total_ops / duration:,.0f} ops/sec")
    print(f"  Avg latency: {duration / total_ops * 1000:.2f} ms")

    # 6.2 Memory leak detection
    print("\n6.2 Memory Leak Detection (10000 iterations)")

    tracemalloc.start()
    gc.collect()
    start_mem = tracemalloc.get_traced_memory()[0]

    for i in range(10000):
        outcome = SimpleCommand.run(a=i, b=i+1)
        if i % 1000 == 0:
            gc.collect()

    gc.collect()
    end_mem = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    memory_growth = (end_mem - start_mem) / (1024 * 1024)
    print(f"  Start memory: {start_mem / (1024 * 1024):.2f} MB")
    print(f"  End memory: {end_mem / (1024 * 1024):.2f} MB")
    print(f"  Memory growth: {memory_growth:.2f} MB")
    print(f"  Growth per 1000 ops: {memory_growth / 10:.4f} MB")

    # 6.3 Resource cleanup verification
    print("\n6.3 Resource Cleanup Verification")

    initial_refs = len(gc.get_objects())

    # Create and execute many commands
    for i in range(1000):
        outcome = ComplexCommand.run(
            name="User " + str(i),
            email=f"user{i}@example.com",
            age=30,
            tags=["tag1", "tag2"],
            metadata={"id": i}
        )

    gc.collect()
    final_refs = len(gc.get_objects())

    print(f"  Initial object count: {initial_refs}")
    print(f"  Final object count: {final_refs}")
    print(f"  Objects created: {final_refs - initial_refs}")
    print(f"  Objects per command: {(final_refs - initial_refs) / 1000:.2f}")

    return results


# ==================== Test Runner ====================

def run_all_tests() -> Dict[str, List[BenchmarkResult]]:
    """Run all stress tests and return results"""
    print("\n" + "=" * 70)
    print("FOOBARA-PY COMPREHENSIVE STRESS TESTS")
    print("=" * 70)
    print(f"Python Version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print()

    all_results = {}

    # Run all tests
    all_results['command_performance'] = test_command_performance()
    all_results['type_system'] = test_type_system_performance()
    all_results['error_handling'] = test_error_handling_performance()
    all_results['concern_architecture'] = test_concern_architecture()
    all_results['integration'] = test_integration_performance()
    all_results['stress_testing'] = test_concurrent_execution()

    return all_results


def save_results_json(results: Dict[str, List[BenchmarkResult]], filename: str):
    """Save results to JSON file"""
    json_data = {}

    for category, benchmark_list in results.items():
        json_data[category] = []
        for result in benchmark_list:
            if result is not None and isinstance(result, BenchmarkResult):
                json_data[category].append({
                    'name': result.name,
                    'iterations': result.iterations,
                    'mean_ns': result.mean_ns,
                    'median_ns': result.median_ns,
                    'p95_ns': result.p95_ns,
                    'p99_ns': result.p99_ns,
                    'min_ns': result.min_ns,
                    'max_ns': result.max_ns,
                    'stdev_ns': result.stdev_ns,
                    'ops_per_sec': result.ops_per_sec,
                    'memory_peak_mb': result.memory_peak_mb,
                    'memory_allocated_mb': result.memory_allocated_mb,
                })

    with open(filename, 'w') as f:
        json.dump(json_data, f, indent=2)

    print(f"\nResults saved to: {filename}")


if __name__ == "__main__":
    results = run_all_tests()

    # Save results
    output_file = "/home/cancelei/Projects/foobara-universe/foobara-ecosystem-python/foobara-py/benchmarks/stress_test_results.json"
    save_results_json(results, output_file)

    print("\n" + "=" * 70)
    print("ALL STRESS TESTS COMPLETED")
    print("=" * 70)
