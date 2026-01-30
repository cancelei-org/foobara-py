#!/usr/bin/env python3
"""
Master benchmark runner for foobara-py.

This script runs all available benchmarks and generates a comprehensive report.

Usage:
    python -m benchmarks.run_all_benchmarks
    python benchmarks/run_all_benchmarks.py
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import benchmark modules
from benchmarks.benchmark_command_execution import (
    run_all_benchmarks as run_command_benchmarks,
)
from benchmarks.benchmark_transactions import (
    run_all_benchmarks as run_transaction_benchmarks,
)


def generate_summary_report(all_results: Dict[str, Any]) -> str:
    """Generate a summary report of all benchmarks"""
    lines = []
    lines.append("=" * 80)
    lines.append("FOOBARA-PY BENCHMARK SUITE - SUMMARY REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Command Execution Benchmarks
    if "command_execution" in all_results:
        lines.append("1. Command Execution Benchmarks")
        lines.append("-" * 80)
        cmd_results = all_results["command_execution"].get("benchmarks", {})

        if "simple_command" in cmd_results:
            sc = cmd_results["simple_command"]
            lines.append(
                f"   Simple Command:     {sc['ops_per_sec']:>12,.0f} ops/sec  "
                f"({sc['mean_ns']/1000:>8.2f} μs/op)"
            )

        if "validated" in cmd_results:
            vc = cmd_results["validated"]
            lines.append(
                f"   Validated Command:  {vc['ops_per_sec']:>12,.0f} ops/sec  "
                f"({vc['mean_ns']/1000:>8.2f} μs/op)"
            )

        if "with_callbacks" in cmd_results:
            cb = cmd_results["with_callbacks"]
            lines.append(
                f"   With Callbacks:     {cb['ops_per_sec']:>12,.0f} ops/sec  "
                f"({cb['mean_ns']/1000:>8.2f} μs/op)"
            )

        if "composite" in cmd_results:
            cp = cmd_results["composite"]
            lines.append(
                f"   Subcommands:        {cp['ops_per_sec']:>12,.0f} ops/sec  "
                f"({cp['mean_ns']/1000:>8.2f} μs/op)"
            )

        if "complex" in cmd_results:
            cx = cmd_results["complex"]
            lines.append(
                f"   Complex Validation: {cx['ops_per_sec']:>12,.0f} ops/sec  "
                f"({cx['mean_ns']/1000:>8.2f} μs/op)"
            )

        lines.append("")

    # Transaction Benchmarks
    if "transactions" in all_results:
        lines.append("2. Transaction Benchmarks")
        lines.append("-" * 80)
        tx_results = all_results["transactions"].get("benchmarks", {})

        if "with_transaction" in tx_results:
            tx = tx_results["with_transaction"]
            lines.append(
                f"   With Transaction:   {tx['ops_per_sec']:>12,.0f} ops/sec  "
                f"({tx['mean_ns']/1000:>8.2f} μs/op)"
            )

        if "nested" in tx_results:
            nt = tx_results["nested"]
            lines.append(
                f"   Nested Transaction: {nt['ops_per_sec']:>12,.0f} ops/sec  "
                f"({nt['mean_ns']/1000:>8.2f} μs/op)"
            )

        if "rollback" in tx_results:
            rb = tx_results["rollback"]
            lines.append(
                f"   Rollback:           {rb['ops_per_sec']:>12,.0f} ops/sec  "
                f"({rb['mean_ns']/1000:>8.2f} μs/op)"
            )

        lines.append("")

    # Performance Summary
    lines.append("=" * 80)
    lines.append("PERFORMANCE SUMMARY")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Target Performance (vs foobara-ruby):")
    lines.append("  • Command execution: within 2x of Ruby")
    lines.append("  • Validation: within 1.5x of Ruby")
    lines.append("  • Transactions: within 2x of Ruby")
    lines.append("")
    lines.append("Next Steps:")
    lines.append("  1. Run Ruby benchmarks: ruby benchmarks/benchmark_command_execution.rb")
    lines.append("  2. Compare results: python -m benchmarks.compare_results")
    lines.append("  3. Review comparison report in benchmarks/results/")
    lines.append("")

    return "\n".join(lines)


def save_combined_results(all_results: Dict[str, Any]):
    """Save all benchmark results to a single file"""
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "all_benchmarks_python.json"

    combined = {
        "framework": "foobara-py",
        "language": "python",
        "timestamp": time.time(),
        "results": all_results,
    }

    with open(output_file, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\nCombined results saved to: {output_file}")


def main():
    """Run all benchmarks and generate reports"""
    print("\n")
    print("=" * 80)
    print("FOOBARA-PY COMPREHENSIVE BENCHMARK SUITE")
    print("=" * 80)
    print("\nRunning all performance benchmarks...")
    print("This may take several minutes.\n")

    start_time = time.time()
    all_results = {}

    # 1. Command Execution Benchmarks
    print("\n" + "=" * 80)
    print("RUNNING: Command Execution Benchmarks")
    print("=" * 80)
    try:
        cmd_results = run_command_benchmarks(
            simple_iterations=10000, complex_iterations=5000, save_to_file=True
        )
        all_results["command_execution"] = {
            "framework": "foobara-py",
            "language": "python",
            "timestamp": time.time(),
            "benchmarks": cmd_results,
        }
        print("✓ Command execution benchmarks complete")
    except Exception as e:
        print(f"✗ Command execution benchmarks failed: {e}")
        all_results["command_execution"] = {"error": str(e)}

    # 2. Transaction Benchmarks
    print("\n" + "=" * 80)
    print("RUNNING: Transaction Benchmarks")
    print("=" * 80)
    try:
        tx_results = run_transaction_benchmarks(iterations=5000, save_to_file=True)
        all_results["transactions"] = {
            "framework": "foobara-py",
            "language": "python",
            "timestamp": time.time(),
            "benchmarks": tx_results,
        }
        print("✓ Transaction benchmarks complete")
    except Exception as e:
        print(f"✗ Transaction benchmarks failed: {e}")
        all_results["transactions"] = {"error": str(e)}

    # Calculate total time
    end_time = time.time()
    duration = end_time - start_time

    # Generate and print summary
    print("\n")
    summary = generate_summary_report(all_results)
    print(summary)

    # Save combined results
    save_combined_results(all_results)

    print("=" * 80)
    print(f"Total benchmark time: {duration:.2f} seconds")
    print("=" * 80)
    print("\n✓ All benchmarks complete!")
    print("\nResults saved in: benchmarks/results/")
    print()


if __name__ == "__main__":
    main()
