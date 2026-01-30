"""
Performance benchmarks for command execution comparing foobara-py vs foobara-ruby.

This module benchmarks basic command execution patterns including:
- Simple command execution
- Commands with validation
- Commands with lifecycle callbacks
- Subcommand execution

Run with: python -m benchmarks.benchmark_command_execution
"""

import time
import statistics
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator
from pathlib import Path

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
        f"  Mean: {results['mean_ns']:.2f} ns ({results['mean_ns']/1000:.2f} μs)\n"
        f"  Median: {results['median_ns']:.2f} ns ({results['median_ns']/1000:.2f} μs)\n"
        f"  Min: {results['min_ns']:.2f} ns\n"
        f"  Max: {results['max_ns']:.2f} ns\n"
        f"  StdDev: {results['stdev_ns']:.2f} ns\n"
        f"  Ops/sec: {results['ops_per_sec']:,.0f}\n"
    )


# ==================== Test Commands ====================

# 1. Simple command (baseline)
class AddInputs(BaseModel):
    a: int
    b: int


class AddCommand(Command[AddInputs, int]):
    """Add two numbers"""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b


# 2. Command with validation
class ValidatedAddInputs(BaseModel):
    a: int = Field(ge=0, le=1000)
    b: int = Field(ge=0, le=1000)

    @field_validator('a', 'b')
    @classmethod
    def validate_not_negative(cls, v):
        if v < 0:
            raise ValueError('must be non-negative')
        return v


class ValidatedAddCommand(Command[ValidatedAddInputs, int]):
    """Add two numbers with validation"""

    def execute(self) -> int:
        return self.inputs.a + self.inputs.b


# 3. Command with lifecycle callbacks
class CallbackInputs(BaseModel):
    value: int


class CommandWithCallbacks(Command[CallbackInputs, int]):
    """Command with lifecycle callbacks"""

    callback_count: int = 0

    def before_execute(self):
        self.callback_count += 1

    def after_execute(self, result: int):
        self.callback_count += 1

    def execute(self) -> int:
        return self.inputs.value * 2


# 4. Nested subcommand execution
class MultiplyInputs(BaseModel):
    x: int
    y: int


class MultiplyCommand(Command[MultiplyInputs, int]):
    """Multiply two numbers"""

    def execute(self) -> int:
        return self.inputs.x * self.inputs.y


class CompositeInputs(BaseModel):
    a: int
    b: int
    c: int


class CompositeCommand(Command[CompositeInputs, int]):
    """Command that uses subcommands"""

    def execute(self) -> int:
        # (a + b) * c
        sum_result = self.run_subcommand_bang(AddCommand, a=self.inputs.a, b=self.inputs.b)
        product_result = self.run_subcommand_bang(
            MultiplyCommand, x=sum_result, y=self.inputs.c
        )
        return product_result


# 5. Complex validation command
class ComplexInputs(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: int = Field(ge=0, le=120)
    tags: List[str] = Field(default_factory=list, max_length=10)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ComplexOutput(BaseModel):
    id: int
    name: str
    status: str


class ComplexCommand(Command[ComplexInputs, ComplexOutput]):
    """Command with complex validation"""

    def execute(self) -> ComplexOutput:
        return ComplexOutput(id=1, name=self.inputs.name, status="active")


# ==================== Benchmark Suites ====================

def benchmark_simple_command(iterations: int = 10000) -> Dict[str, Any]:
    """Benchmark simple command execution speed"""
    print("\n" + "=" * 60)
    print("1. Simple Command Execution Benchmark")
    print("=" * 60)

    result = benchmark(lambda: AddCommand.run(a=5, b=3), iterations=iterations)
    print(format_results("AddCommand (2 int inputs)", result))
    return {"simple_command": result}


def benchmark_command_with_validation(iterations: int = 10000) -> Dict[str, Any]:
    """Benchmark validation overhead"""
    print("\n" + "=" * 60)
    print("2. Command with Validation Benchmark")
    print("=" * 60)

    # Simple command (no extra validation)
    simple_result = benchmark(lambda: AddCommand.run(a=5, b=3), iterations=iterations)
    print(format_results("AddCommand (no validation)", simple_result))

    # Validated command
    validated_result = benchmark(
        lambda: ValidatedAddCommand.run(a=5, b=3), iterations=iterations
    )
    print(format_results("ValidatedAddCommand (with validators)", validated_result))

    overhead = validated_result["mean_ns"] / simple_result["mean_ns"]
    print(f"\nValidation overhead: {overhead:.2f}x")

    return {
        "simple": simple_result,
        "validated": validated_result,
        "overhead": overhead,
    }


def benchmark_lifecycle_callbacks(iterations: int = 10000) -> Dict[str, Any]:
    """Benchmark lifecycle callback overhead"""
    print("\n" + "=" * 60)
    print("3. Lifecycle Callbacks Benchmark")
    print("=" * 60)

    # Without callbacks
    simple_result = benchmark(lambda: AddCommand.run(a=5, b=3), iterations=iterations)
    print(format_results("AddCommand (no callbacks)", simple_result))

    # With callbacks
    callback_result = benchmark(
        lambda: CommandWithCallbacks.run(value=10), iterations=iterations
    )
    print(format_results("CommandWithCallbacks (2 callbacks)", callback_result))

    overhead = callback_result["mean_ns"] / simple_result["mean_ns"]
    print(f"\nCallback overhead: {overhead:.2f}x")

    return {
        "no_callbacks": simple_result,
        "with_callbacks": callback_result,
        "overhead": overhead,
    }


def benchmark_subcommands(iterations: int = 5000) -> Dict[str, Any]:
    """Benchmark subcommand execution overhead"""
    print("\n" + "=" * 60)
    print("4. Subcommand Execution Benchmark")
    print("=" * 60)

    # Single command
    single_result = benchmark(lambda: MultiplyCommand.run(x=8, y=3), iterations=iterations)
    print(format_results("Single command", single_result))

    # Composite command (2 subcommands)
    composite_result = benchmark(
        lambda: CompositeCommand.run(a=5, b=3, c=2), iterations=iterations
    )
    print(format_results("Composite command (2 subcommands)", composite_result))

    overhead = composite_result["mean_ns"] / single_result["mean_ns"]
    print(f"\nSubcommand overhead: {overhead:.2f}x")

    return {
        "single": single_result,
        "composite": composite_result,
        "overhead": overhead,
    }


def benchmark_complex_validation(iterations: int = 5000) -> Dict[str, Any]:
    """Benchmark complex validation overhead"""
    print("\n" + "=" * 60)
    print("5. Complex Validation Benchmark")
    print("=" * 60)

    # Simple command
    simple_result = benchmark(lambda: AddCommand.run(a=5, b=3), iterations=iterations)
    print(format_results("Simple (2 int inputs)", simple_result))

    # Complex command
    complex_result = benchmark(
        lambda: ComplexCommand.run(
            name="John Doe",
            email="john@example.com",
            age=30,
            tags=["user", "active"],
            metadata={"source": "api", "version": "1.0"},
        ),
        iterations=iterations,
    )
    print(format_results("Complex (5 fields with validation)", complex_result))

    overhead = complex_result["mean_ns"] / simple_result["mean_ns"]
    print(f"\nComplex validation overhead: {overhead:.2f}x")

    return {
        "simple": simple_result,
        "complex": complex_result,
        "overhead": overhead,
    }


def save_results(results: Dict[str, Any], filename: str = "benchmark_results_python.json"):
    """Save benchmark results to JSON file"""
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / filename
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_file}")


# ==================== Main ====================

def run_all_benchmarks(
    simple_iterations: int = 10000,
    complex_iterations: int = 5000,
    save_to_file: bool = True,
):
    """Run all command execution benchmarks"""
    print("\n")
    print("=" * 60)
    print("FOOBARA-PY COMMAND EXECUTION BENCHMARKS")
    print("=" * 60)
    print(f"Python implementation benchmark suite")
    print(f"Simple operations: {simple_iterations:,} iterations")
    print(f"Complex operations: {complex_iterations:,} iterations")

    all_results = {}

    # Run benchmarks
    all_results.update(benchmark_simple_command(simple_iterations))
    all_results.update(benchmark_command_with_validation(simple_iterations))
    all_results.update(benchmark_lifecycle_callbacks(simple_iterations))
    all_results.update(benchmark_subcommands(complex_iterations))
    all_results.update(benchmark_complex_validation(complex_iterations))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nSimple command: {all_results['simple_command']['ops_per_sec']:,.0f} ops/sec")
    print(
        f"Simple command mean: {all_results['simple_command']['mean_ns']/1000:.2f} μs/op"
    )

    if save_to_file:
        # Add metadata
        results_with_metadata = {
            "framework": "foobara-py",
            "language": "python",
            "timestamp": time.time(),
            "benchmarks": all_results,
        }
        save_results(results_with_metadata)

    return all_results


if __name__ == "__main__":
    run_all_benchmarks()
    print("\nBenchmarks complete!")
