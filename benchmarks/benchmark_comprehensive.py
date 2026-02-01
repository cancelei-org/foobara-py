"""
Comprehensive benchmark suite for establishing performance baseline.

Measures all critical paths before readability improvements.
"""

import time
import statistics
import gc
from typing import Callable
from pydantic import BaseModel

from foobara_py import Command
from foobara_py.core.state_machine import CommandState


class SimpleInputs(BaseModel):
    value: int


class ComplexInputs(BaseModel):
    name: str
    email: str
    age: int
    is_active: bool = True


# ========== Test Commands ==========

class MinimalCommand(Command[SimpleInputs, int]):
    """Absolute minimal command - no callbacks"""
    def execute(self) -> int:
        return self.inputs.value


class SimpleCallbackCommand(Command[SimpleInputs, int]):
    """Command with single before callback"""
    def execute(self) -> int:
        return self.inputs.value * 2


SimpleCallbackCommand.before_execute_transition(lambda cmd: None)


class MultiCallbackCommand(Command[SimpleInputs, int]):
    """Command with multiple callbacks"""
    def execute(self) -> int:
        return self.inputs.value * 2


MultiCallbackCommand.before_execute_transition(lambda cmd: None, priority=0)
MultiCallbackCommand.before_execute_transition(lambda cmd: None, priority=10)
MultiCallbackCommand.after_execute_transition(lambda cmd: None)


class ConditionalCallbackCommand(Command[SimpleInputs, int]):
    """Command with conditional callbacks"""
    def execute(self) -> int:
        return self.inputs.value * 2


ConditionalCallbackCommand.before_transition(
    lambda cmd: None,
    from_state=CommandState.VALIDATING,
    to_state=CommandState.EXECUTING,
    transition="execute"
)


class AroundCallbackCommand(Command[SimpleInputs, int]):
    """Command with around callback"""
    def execute(self) -> int:
        return self.inputs.value * 2


AroundCallbackCommand.around_execute_transition(
    lambda cmd, action: action()
)


class ComplexValidationCommand(Command[ComplexInputs, str]):
    """Command with complex validation"""
    def execute(self) -> str:
        return f"{self.inputs.name} <{self.inputs.email}>"


ComplexValidationCommand.before_execute_transition(
    lambda cmd: cmd.add_runtime_error("test", "test") if cmd.inputs.age < 0 else None
)


# Pre-compile all callback chains
for cmd in [
    SimpleCallbackCommand,
    MultiCallbackCommand,
    ConditionalCallbackCommand,
    AroundCallbackCommand,
    ComplexValidationCommand
]:
    if hasattr(cmd, '_enhanced_callback_registry') and cmd._enhanced_callback_registry:
        cmd._enhanced_callback_registry.precompile_common_transitions()


def benchmark(func: Callable, iterations: int = 10000, warmup: int = 100) -> dict:
    """Run benchmark with warmup and return detailed stats."""
    # Warmup
    for _ in range(warmup):
        func()

    # Force garbage collection before benchmark
    gc.collect()

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1_000_000)  # μs

    times.sort()

    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times),
        'p50': statistics.quantiles(times, n=2)[0],
        'p90': statistics.quantiles(times, n=10)[8],
        'p95': statistics.quantiles(times, n=20)[18],
        'p99': statistics.quantiles(times, n=100)[98],
        'throughput': 1_000_000 / statistics.mean(times),  # ops/sec
    }


def print_stats(name: str, stats: dict, baseline: float = None):
    """Print formatted statistics."""
    print(f"{name}:")
    print(f"  Mean:       {stats['mean']:>10.2f} μs")
    print(f"  Median:     {stats['median']:>10.2f} μs")
    print(f"  StdDev:     {stats['stdev']:>10.2f} μs")
    print(f"  Min:        {stats['min']:>10.2f} μs")
    print(f"  P50:        {stats['p50']:>10.2f} μs")
    print(f"  P90:        {stats['p90']:>10.2f} μs")
    print(f"  P95:        {stats['p95']:>10.2f} μs")
    print(f"  P99:        {stats['p99']:>10.2f} μs")
    print(f"  Max:        {stats['max']:>10.2f} μs")
    print(f"  Throughput: {stats['throughput']:>10,.0f} ops/sec")

    if baseline:
        overhead = stats['mean'] - baseline
        pct = (overhead / baseline * 100) if baseline > 0 else 0
        print(f"  vs Baseline: {overhead:>+9.2f} μs ({pct:+.1f}%)")


def main():
    """Run comprehensive benchmarks."""
    print("=" * 80)
    print("COMPREHENSIVE PERFORMANCE BASELINE")
    print("=" * 80)
    print()
    print("Configuration:")
    print("  Iterations: 10,000 per test")
    print("  Warmup: 100 iterations")
    print("  GC: Forced before each benchmark")
    print()

    results = {}

    # 1. Minimal command (absolute baseline)
    print("1. MINIMAL COMMAND (Absolute Baseline)")
    print("-" * 80)
    stats = benchmark(lambda: MinimalCommand.run(value=42))
    print_stats("Minimal command (no callbacks)", stats)
    results['minimal'] = stats
    baseline = stats['mean']
    print()

    # 2. Simple callback
    print("2. SIMPLE CALLBACK")
    print("-" * 80)
    stats = benchmark(lambda: SimpleCallbackCommand.run(value=42))
    print_stats("Single before callback", stats, baseline)
    results['simple_callback'] = stats
    print()

    # 3. Multiple callbacks
    print("3. MULTIPLE CALLBACKS")
    print("-" * 80)
    stats = benchmark(lambda: MultiCallbackCommand.run(value=42))
    print_stats("Multiple callbacks (3 total)", stats, baseline)
    results['multi_callback'] = stats
    print()

    # 4. Conditional callback
    print("4. CONDITIONAL CALLBACK")
    print("-" * 80)
    stats = benchmark(lambda: ConditionalCallbackCommand.run(value=42))
    print_stats("Conditional (from/to/transition)", stats, baseline)
    results['conditional'] = stats
    print()

    # 5. Around callback
    print("5. AROUND CALLBACK")
    print("-" * 80)
    stats = benchmark(lambda: AroundCallbackCommand.run(value=42))
    print_stats("Around callback", stats, baseline)
    results['around'] = stats
    print()

    # 6. Complex validation
    print("6. COMPLEX VALIDATION")
    print("-" * 80)
    stats = benchmark(
        lambda: ComplexValidationCommand.run(
            name="John Doe",
            email="john@example.com",
            age=30
        )
    )
    print_stats("Complex input validation", stats, baseline)
    results['complex'] = stats
    print()

    # 7. Error path
    print("7. ERROR PATH")
    print("-" * 80)
    stats = benchmark(
        lambda: ComplexValidationCommand.run(
            name="John Doe",
            email="john@example.com",
            age=-1  # Triggers error
        )
    )
    print_stats("Command with error", stats, baseline)
    results['error'] = stats
    print()

    # Cache statistics
    print("8. CACHE STATISTICS")
    print("-" * 80)
    for name, cmd in [
        ("SimpleCallbackCommand", SimpleCallbackCommand),
        ("MultiCallbackCommand", MultiCallbackCommand),
        ("ConditionalCallbackCommand", ConditionalCallbackCommand),
    ]:
        if hasattr(cmd, '_enhanced_callback_registry') and cmd._enhanced_callback_registry:
            stats = cmd._enhanced_callback_registry.get_cache_stats()
            print(f"{name}:")
            print(f"  Hits:    {stats['hits']:>10,}")
            print(f"  Misses:  {stats['misses']:>10,}")
            print(f"  Hit rate: {stats['hit_rate']:>9.1f}%")
            print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Baseline (minimal):     {results['minimal']['mean']:>10.2f} μs")
    print(f"                        {results['minimal']['throughput']:>10,.0f} ops/sec")
    print()
    print("Callback Overhead:")
    print(f"  Simple (1 callback):  {results['simple_callback']['mean'] - baseline:>+10.2f} μs")
    print(f"  Multi (3 callbacks):  {results['multi_callback']['mean'] - baseline:>+10.2f} μs")
    print(f"  Conditional:          {results['conditional']['mean'] - baseline:>+10.2f} μs")
    print(f"  Around:               {results['around']['mean'] - baseline:>+10.2f} μs")
    print()
    print("Percentile Distribution (p50/p90/p95/p99):")
    for name, key in [
        ("Minimal", 'minimal'),
        ("Simple callback", 'simple_callback'),
        ("Multi callback", 'multi_callback'),
    ]:
        r = results[key]
        print(f"  {name:20s} {r['p50']:>7.2f} / {r['p90']:>7.2f} / {r['p95']:>7.2f} / {r['p99']:>7.2f} μs")

    print()
    print("=" * 80)
    print("BASELINE ESTABLISHED")
    print("=" * 80)
    print()
    print("Save these numbers for comparison after readability improvements.")
    print()

    # Save results to file
    import json
    with open('benchmarks/baseline_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("Results saved to: benchmarks/baseline_results.json")


if __name__ == "__main__":
    main()
