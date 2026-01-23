"""
Performance benchmarks for foobara-py.

Compares new high-performance implementation against:
- Raw function calls
- Basic class instantiation
- Alternative command patterns

Run with: python -m benchmarks.benchmark_command
"""

import time
import statistics
from typing import Dict, Any, List
from pydantic import BaseModel
from dataclasses import dataclass

# Import new implementation
from foobara_py.core.command import Command
from foobara_py.core.outcome import CommandOutcome


# ==================== Benchmark Utilities ====================

def benchmark(func, iterations: int = 10000, warmup: int = 100) -> Dict[str, float]:
    """Run benchmark and return timing statistics"""
    # Warmup
    for _ in range(warmup):
        func()

    # Benchmark
    times = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        func()
        end = time.perf_counter_ns()
        times.append(end - start)

    return {
        "iterations": iterations,
        "min_ns": min(times),
        "max_ns": max(times),
        "mean_ns": statistics.mean(times),
        "median_ns": statistics.median(times),
        "stdev_ns": statistics.stdev(times) if len(times) > 1 else 0,
        "total_ms": sum(times) / 1_000_000,
        "ops_per_sec": iterations / (sum(times) / 1_000_000_000),
    }


def format_results(name: str, results: Dict[str, float]) -> str:
    """Format benchmark results for display"""
    return (
        f"{name}:\n"
        f"  Iterations: {results['iterations']:,}\n"
        f"  Mean: {results['mean_ns']:.2f} ns\n"
        f"  Median: {results['median_ns']:.2f} ns\n"
        f"  Min: {results['min_ns']:.2f} ns\n"
        f"  Max: {results['max_ns']:.2f} ns\n"
        f"  StdDev: {results['stdev_ns']:.2f} ns\n"
        f"  Ops/sec: {results['ops_per_sec']:,.0f}\n"
    )


# ==================== Test Cases ====================

# 1. Raw function (baseline)
def raw_add(a: int, b: int) -> int:
    return a + b


# 2. Class-based (simple)
class SimpleAddClass:
    def __init__(self, a: int, b: int):
        self.a = a
        self.b = b

    def run(self) -> int:
        return self.a + self.b


# 3. Dataclass-based
@dataclass
class DataclassAdd:
    a: int
    b: int

    def run(self) -> int:
        return self.a + self.b


# 4. Pydantic-based (no command pattern)
class PydanticAddInputs(BaseModel):
    a: int
    b: int


def pydantic_add(inputs: PydanticAddInputs) -> int:
    return inputs.a + inputs.b


# 5. foobara-py Command
class AddInputs(BaseModel):
    a: int
    b: int


class AddCommand(Command[AddInputs, int]):
    """Add two numbers"""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b


# ==================== Run Benchmarks ====================

def run_benchmarks(iterations: int = 10000):
    """Run all benchmarks and print results"""
    print("=" * 60)
    print("foobara-py Performance Benchmarks")
    print("=" * 60)
    print()

    results = {}

    # 1. Raw function
    results["raw_function"] = benchmark(
        lambda: raw_add(5, 3),
        iterations=iterations
    )
    print(format_results("1. Raw Function (baseline)", results["raw_function"]))

    # 2. Simple class
    results["simple_class"] = benchmark(
        lambda: SimpleAddClass(5, 3).run(),
        iterations=iterations
    )
    print(format_results("2. Simple Class", results["simple_class"]))

    # 3. Dataclass
    results["dataclass"] = benchmark(
        lambda: DataclassAdd(5, 3).run(),
        iterations=iterations
    )
    print(format_results("3. Dataclass", results["dataclass"]))

    # 4. Pydantic only
    results["pydantic"] = benchmark(
        lambda: pydantic_add(PydanticAddInputs(a=5, b=3)),
        iterations=iterations
    )
    print(format_results("4. Pydantic (validation only)", results["pydantic"]))

    # 5. foobara-py Command
    results["foobara_command"] = benchmark(
        lambda: AddCommand.run(a=5, b=3),
        iterations=iterations
    )
    print(format_results("5. foobara-py Command", results["foobara_command"]))

    # Summary comparison
    print("=" * 60)
    print("Relative Performance (vs raw function)")
    print("=" * 60)

    baseline = results["raw_function"]["mean_ns"]
    for name, res in results.items():
        ratio = res["mean_ns"] / baseline
        print(f"  {name}: {ratio:.2f}x slower")

    print()
    print("=" * 60)
    print("Operations per Second")
    print("=" * 60)

    for name, res in sorted(results.items(), key=lambda x: -x[1]["ops_per_sec"]):
        print(f"  {name}: {res['ops_per_sec']:,.0f} ops/sec")

    return results


# ==================== Additional Benchmarks ====================

def benchmark_validation_overhead(iterations: int = 5000):
    """Benchmark validation overhead specifically"""
    print()
    print("=" * 60)
    print("Validation Overhead Benchmark")
    print("=" * 60)
    print()

    # Command with complex inputs
    class ComplexInputs(BaseModel):
        name: str
        email: str
        age: int
        tags: List[str] = []
        metadata: Dict[str, Any] = {}

    class ComplexOutput(BaseModel):
        id: int
        name: str

    class ComplexCommand(Command[ComplexInputs, ComplexOutput]):
        def execute(self) -> ComplexOutput:
            return ComplexOutput(id=1, name=self.inputs.name)

    # Simple command
    results_simple = benchmark(
        lambda: AddCommand.run(a=5, b=3),
        iterations=iterations
    )
    print(format_results("Simple inputs (2 ints)", results_simple))

    # Complex command
    results_complex = benchmark(
        lambda: ComplexCommand.run(
            name="John",
            email="john@example.com",
            age=30,
            tags=["user", "active"],
            metadata={"source": "api"}
        ),
        iterations=iterations
    )
    print(format_results("Complex inputs (5 fields)", results_complex))

    overhead = results_complex["mean_ns"] / results_simple["mean_ns"]
    print(f"Complex vs Simple overhead: {overhead:.2f}x")


def benchmark_error_handling(iterations: int = 5000):
    """Benchmark error handling performance"""
    print()
    print("=" * 60)
    print("Error Handling Benchmark")
    print("=" * 60)
    print()

    class FailingCommand(Command[AddInputs, int]):
        def execute(self) -> int:
            self.add_runtime_error("test_error", "Test error", halt=False)
            return 0

    # Success case
    results_success = benchmark(
        lambda: AddCommand.run(a=5, b=3),
        iterations=iterations
    )
    print(format_results("Success path", results_success))

    # Failure case (validation error)
    results_validation_error = benchmark(
        lambda: AddCommand.run(a="invalid", b=3),  # type: ignore
        iterations=iterations
    )
    print(format_results("Validation error path", results_validation_error))

    # Failure case (runtime error)
    results_runtime_error = benchmark(
        lambda: FailingCommand.run(a=5, b=3),
        iterations=iterations
    )
    print(format_results("Runtime error path", results_runtime_error))


def benchmark_subcommands(iterations: int = 2000):
    """Benchmark subcommand execution overhead"""
    print()
    print("=" * 60)
    print("Subcommand Execution Benchmark")
    print("=" * 60)
    print()

    class InnerCommand(Command[AddInputs, int]):
        def execute(self) -> int:
            return self.inputs.a + self.inputs.b

    class OuterWithSubcommand(Command[AddInputs, int]):
        def execute(self) -> int:
            result = self.run_subcommand_bang(InnerCommand, a=self.inputs.a, b=self.inputs.b)
            return result

    class OuterWithoutSubcommand(Command[AddInputs, int]):
        def execute(self) -> int:
            return self.inputs.a + self.inputs.b

    results_without = benchmark(
        lambda: OuterWithoutSubcommand.run(a=5, b=3),
        iterations=iterations
    )
    print(format_results("Without subcommand", results_without))

    results_with = benchmark(
        lambda: OuterWithSubcommand.run(a=5, b=3),
        iterations=iterations
    )
    print(format_results("With subcommand", results_with))

    overhead = results_with["mean_ns"] / results_without["mean_ns"]
    print(f"Subcommand overhead: {overhead:.2f}x")


if __name__ == "__main__":
    print()
    print("Running foobara-py benchmarks...")
    print()

    run_benchmarks(iterations=10000)
    benchmark_validation_overhead(iterations=5000)
    benchmark_error_handling(iterations=5000)
    benchmark_subcommands(iterations=2000)

    print()
    print("Benchmarks complete!")
