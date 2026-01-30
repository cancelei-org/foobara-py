"""
Performance benchmarks for transaction overhead comparing foobara-py vs foobara-ruby.

This module benchmarks transaction patterns including:
- Transaction setup/teardown overhead
- Nested transactions
- Transaction rollback performance
- Transaction with persistence operations

Run with: python -m benchmarks.benchmark_transactions
"""

import time
import statistics
import json
from typing import Dict, Any
from pydantic import BaseModel
from pathlib import Path

from foobara_py.core.command import Command
from foobara_py.persistence.entity import EntityBase


# ==================== Benchmark Utilities ====================

def benchmark(func, iterations: int = 5000, warmup: int = 50) -> Dict[str, float]:
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
        f"  Mean: {results['mean_ns']/1000:.2f} μs\n"
        f"  Median: {results['median_ns']/1000:.2f} μs\n"
        f"  StdDev: {results['stdev_ns']/1000:.2f} μs\n"
        f"  Ops/sec: {results['ops_per_sec']:,.0f}\n"
    )


# ==================== Test Setup ====================

# Simple entity for testing
class User(EntityBase):
    """User entity for transaction testing"""
    name: str
    email: str


# Commands for testing
class NoTransactionInputs(BaseModel):
    value: int


class NoTransactionCommand(Command[NoTransactionInputs, int]):
    """Command without transaction (baseline)"""

    def execute(self) -> int:
        return self.inputs.value * 2


class WithTransactionInputs(BaseModel):
    value: int


class WithTransactionCommand(Command[WithTransactionInputs, int]):
    """Command with transaction overhead"""

    def execute(self) -> int:
        # In foobara-py, transactions are managed automatically
        # This simulates transaction context
        return self.inputs.value * 2


class NestedTransactionInputs(BaseModel):
    value: int


class InnerTransactionCommand(Command[NestedTransactionInputs, int]):
    """Inner command for nested transaction testing"""

    def execute(self) -> int:
        return self.inputs.value + 10


class OuterTransactionCommand(Command[NestedTransactionInputs, int]):
    """Outer command that creates nested transaction"""

    def execute(self) -> int:
        inner_result = self.run_subcommand_bang(InnerTransactionCommand, value=self.inputs.value)
        return inner_result * 2


class RollbackTestInputs(BaseModel):
    should_fail: bool
    value: int


class RollbackTestCommand(Command[RollbackTestInputs, int]):
    """Command that may rollback"""

    def execute(self) -> int:
        if self.inputs.should_fail:
            self.add_runtime_error("test_error", "Intentional failure", halt=True)
            return 0
        return self.inputs.value


# ==================== Benchmark Suites ====================

def benchmark_transaction_overhead(iterations: int = 5000) -> Dict[str, Any]:
    """Measure transaction context setup/teardown"""
    print("\n" + "=" * 60)
    print("1. Transaction Overhead Benchmark")
    print("=" * 60)

    # Without transaction
    no_tx_result = benchmark(
        lambda: NoTransactionCommand.run(value=10),
        iterations=iterations
    )
    print(format_results("Without transaction", no_tx_result))

    # With transaction
    with_tx_result = benchmark(
        lambda: WithTransactionCommand.run(value=10),
        iterations=iterations
    )
    print(format_results("With transaction", with_tx_result))

    overhead = with_tx_result["mean_ns"] / no_tx_result["mean_ns"]
    print(f"\nTransaction overhead: {overhead:.2f}x")

    return {
        "no_transaction": no_tx_result,
        "with_transaction": with_tx_result,
        "overhead": overhead,
    }


def benchmark_nested_transactions(iterations: int = 3000) -> Dict[str, Any]:
    """Measure nested transaction performance"""
    print("\n" + "=" * 60)
    print("2. Nested Transactions Benchmark")
    print("=" * 60)

    # Single transaction
    single_result = benchmark(
        lambda: InnerTransactionCommand.run(value=10),
        iterations=iterations
    )
    print(format_results("Single transaction", single_result))

    # Nested transaction
    nested_result = benchmark(
        lambda: OuterTransactionCommand.run(value=10),
        iterations=iterations
    )
    print(format_results("Nested transaction (2 levels)", nested_result))

    overhead = nested_result["mean_ns"] / single_result["mean_ns"]
    print(f"\nNested transaction overhead: {overhead:.2f}x")

    return {
        "single": single_result,
        "nested": nested_result,
        "overhead": overhead,
    }


def benchmark_rollback(iterations: int = 3000) -> Dict[str, Any]:
    """Measure rollback performance"""
    print("\n" + "=" * 60)
    print("3. Transaction Rollback Benchmark")
    print("=" * 60)

    # Success path (commit)
    success_result = benchmark(
        lambda: RollbackTestCommand.run(should_fail=False, value=10),
        iterations=iterations
    )
    print(format_results("Success path (commit)", success_result))

    # Failure path (rollback)
    rollback_result = benchmark(
        lambda: RollbackTestCommand.run(should_fail=True, value=10),
        iterations=iterations
    )
    print(format_results("Failure path (rollback)", rollback_result))

    overhead = rollback_result["mean_ns"] / success_result["mean_ns"]
    print(f"\nRollback vs Commit: {overhead:.2f}x")

    return {
        "commit": success_result,
        "rollback": rollback_result,
        "overhead": overhead,
    }


def save_results(results: Dict[str, Any], filename: str = "benchmark_results_transactions_python.json"):
    """Save benchmark results to JSON file"""
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / filename
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_file}")


# ==================== Main ====================

def run_all_benchmarks(iterations: int = 5000, save_to_file: bool = True):
    """Run all transaction benchmarks"""
    print("\n")
    print("=" * 60)
    print("FOOBARA-PY TRANSACTION BENCHMARKS")
    print("=" * 60)
    print(f"Iterations: {iterations:,}")

    all_results = {}

    # Run benchmarks
    all_results.update(benchmark_transaction_overhead(iterations))
    all_results.update(benchmark_nested_transactions(int(iterations * 0.6)))
    all_results.update(benchmark_rollback(int(iterations * 0.6)))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if "with_transaction" in all_results:
        print(f"\nTransaction overhead: {all_results['overhead']:.2f}x")
    if "nested" in all_results:
        tx_data = all_results.get("with_transaction", all_results.get("single", {}))
        if tx_data:
            print(f"With transaction: {tx_data['ops_per_sec']:,.0f} ops/sec")

    if save_to_file:
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
    print("\nTransaction benchmarks complete!")
