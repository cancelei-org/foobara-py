"""
Baseline benchmarks for current callback system.

Establishes performance metrics before enhancing callback flexibility.
"""

import time
import statistics
from typing import Callable, List
from pydantic import BaseModel

from foobara_py import Command
from foobara_py.core.callbacks import CallbackPhase, CallbackRegistry
from foobara_py.core.state_machine import CommandState


class SimpleInputs(BaseModel):
    value: int


class NoCallbackCommand(Command[SimpleInputs, int]):
    """Command with no callbacks"""

    def execute(self) -> int:
        return self.inputs.value * 2


class BeforeCallbackCommand(Command[SimpleInputs, int]):
    """Command with before_execute hook"""

    def before_execute(self) -> None:
        pass  # Minimal overhead

    def execute(self) -> int:
        return self.inputs.value * 2


class AfterCallbackCommand(Command[SimpleInputs, int]):
    """Command with after_execute hook"""

    def execute(self) -> int:
        return self.inputs.value * 2

    def after_execute(self, result: int) -> int:
        return result  # Minimal overhead


class BothCallbacksCommand(Command[SimpleInputs, int]):
    """Command with both before and after hooks"""

    def before_execute(self) -> None:
        pass

    def execute(self) -> int:
        return self.inputs.value * 2

    def after_execute(self, result: int) -> int:
        return result


class MultiPhaseCallbackCommand(Command[SimpleInputs, int]):
    """Command with callbacks on multiple phases"""

    def before_execute(self) -> None:
        pass

    def validate(self) -> None:
        pass

    def execute(self) -> int:
        return self.inputs.value * 2

    def after_execute(self, result: int) -> int:
        return result


def benchmark(func: Callable, iterations: int = 10000) -> dict:
    """Run benchmark and return stats."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1_000_000)  # Convert to microseconds

    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times),
        'p95': statistics.quantiles(times, n=20)[18],  # 95th percentile
        'p99': statistics.quantiles(times, n=100)[98],  # 99th percentile
    }


def format_stats(stats: dict, name: str) -> str:
    """Format benchmark stats."""
    return (
        f"{name}:\n"
        f"  Mean:   {stats['mean']:>8.2f} μs\n"
        f"  Median: {stats['median']:>8.2f} μs\n"
        f"  StdDev: {stats['stdev']:>8.2f} μs\n"
        f"  Min:    {stats['min']:>8.2f} μs\n"
        f"  Max:    {stats['max']:>8.2f} μs\n"
        f"  P95:    {stats['p95']:>8.2f} μs\n"
        f"  P99:    {stats['p99']:>8.2f} μs"
    )


def main():
    """Run baseline benchmarks."""
    print("=" * 80)
    print("BASELINE CALLBACK SYSTEM BENCHMARKS")
    print("=" * 80)
    print()

    iterations = 10000

    # Benchmark 1: No callbacks
    print("1. No Callbacks (baseline)")
    print("-" * 80)
    stats = benchmark(lambda: NoCallbackCommand.run(value=42), iterations)
    print(format_stats(stats, "No callbacks"))
    baseline_mean = stats['mean']
    print()

    # Benchmark 2: Before callback only
    print("2. Before Execute Hook")
    print("-" * 80)
    stats = benchmark(lambda: BeforeCallbackCommand.run(value=42), iterations)
    print(format_stats(stats, "Before callback"))
    overhead = stats['mean'] - baseline_mean
    print(f"  Overhead: {overhead:>8.2f} μs ({overhead/baseline_mean*100:.1f}%)")
    print()

    # Benchmark 3: After callback only
    print("3. After Execute Hook")
    print("-" * 80)
    stats = benchmark(lambda: AfterCallbackCommand.run(value=42), iterations)
    print(format_stats(stats, "After callback"))
    overhead = stats['mean'] - baseline_mean
    print(f"  Overhead: {overhead:>8.2f} μs ({overhead/baseline_mean*100:.1f}%)")
    print()

    # Benchmark 4: Both callbacks
    print("4. Before + After Execute Hooks")
    print("-" * 80)
    stats = benchmark(lambda: BothCallbacksCommand.run(value=42), iterations)
    print(format_stats(stats, "Both callbacks"))
    overhead = stats['mean'] - baseline_mean
    print(f"  Overhead: {overhead:>8.2f} μs ({overhead/baseline_mean*100:.1f}%)")
    print()

    # Benchmark 5: Multiple phase callbacks
    print("5. Multiple Phase Callbacks")
    print("-" * 80)
    stats = benchmark(lambda: MultiPhaseCallbackCommand.run(value=42), iterations)
    print(format_stats(stats, "Multi-phase callbacks"))
    overhead = stats['mean'] - baseline_mean
    print(f"  Overhead: {overhead:>8.2f} μs ({overhead/baseline_mean*100:.1f}%)")
    print()

    # Memory usage
    print("6. Memory Usage")
    print("-" * 80)
    import sys

    cmd = NoCallbackCommand(value=42)
    size = sys.getsizeof(cmd)
    print(f"Command instance size: {size} bytes")

    if hasattr(cmd, '_state_machine'):
        sm_size = sys.getsizeof(cmd._state_machine)
        print(f"State machine size: {sm_size} bytes")

    if hasattr(cmd, '_callback_executor'):
        cb_size = sys.getsizeof(cmd._callback_executor) if cmd._callback_executor else 0
        print(f"Callback executor size: {cb_size} bytes")

    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Baseline (no callbacks): {baseline_mean:.2f} μs")
    print()
    print("Current callback system characteristics:")
    print("- Hook-based: before_execute(), after_execute()")
    print("- Phase-based: validate(), load_records(), etc.")
    print("- Detection overhead: Single boolean check (optimized in v0.3.0)")
    print("- Callback executor: Conditionally allocated")
    print()
    print("Limitations:")
    print("- No from/to state-specific callbacks")
    print("- No transition-specific callbacks")
    print("- Limited to pre-defined hooks")
    print("=" * 80)


if __name__ == "__main__":
    main()
