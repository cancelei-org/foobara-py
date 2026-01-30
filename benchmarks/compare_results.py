"""
Compare benchmark results between foobara-py and foobara-ruby.

This script:
1. Loads benchmark results from both Python and Ruby implementations
2. Compares performance metrics
3. Generates comparison reports and visualizations

Run with: python -m benchmarks.compare_results
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import sys


@dataclass
class BenchmarkComparison:
    """Comparison between Python and Ruby benchmark results"""
    name: str
    python_ops_per_sec: float
    ruby_ops_per_sec: float
    python_mean_us: float
    ruby_mean_us: float
    ratio: float  # Python / Ruby (< 1.0 means Python is faster)
    status: str  # "faster", "slower", "similar"


class BenchmarkComparer:
    """Compare benchmark results between Python and Ruby"""

    def __init__(self, results_dir: Optional[Path] = None):
        if results_dir is None:
            results_dir = Path(__file__).parent / "results"
        self.results_dir = results_dir
        self.python_results = {}
        self.ruby_results = {}

    def load_results(self):
        """Load benchmark results from JSON files"""
        python_file = self.results_dir / "benchmark_results_python.json"
        ruby_file = self.results_dir / "benchmark_results_ruby.json"

        if python_file.exists():
            with open(python_file) as f:
                self.python_results = json.load(f)
            print(f"✓ Loaded Python results from {python_file}")
        else:
            print(f"⚠ Python results not found: {python_file}")

        if ruby_file.exists():
            with open(ruby_file) as f:
                self.ruby_results = json.load(f)
            print(f"✓ Loaded Ruby results from {ruby_file}")
        else:
            print(f"⚠ Ruby results not found: {ruby_file}")

    def compare_benchmark(
        self, name: str, python_data: Dict[str, Any], ruby_data: Dict[str, Any]
    ) -> BenchmarkComparison:
        """Compare a single benchmark between Python and Ruby"""
        python_ops = python_data.get("ops_per_sec", 0)
        ruby_ops = ruby_data.get("ops_per_sec", 0)
        python_mean_ns = python_data.get("mean_ns", 0)
        ruby_mean_ns = ruby_data.get("mean_ns", 0)

        python_mean_us = python_mean_ns / 1000
        ruby_mean_us = ruby_mean_ns / 1000

        # Calculate ratio (Python time / Ruby time)
        # < 1.0 means Python is faster
        # > 1.0 means Ruby is faster
        if ruby_mean_ns > 0:
            ratio = python_mean_ns / ruby_mean_ns
        else:
            ratio = 0

        # Determine status
        if 0.9 <= ratio <= 1.1:
            status = "similar"
        elif ratio < 0.9:
            status = "faster"
        else:
            status = "slower"

        return BenchmarkComparison(
            name=name,
            python_ops_per_sec=python_ops,
            ruby_ops_per_sec=ruby_ops,
            python_mean_us=python_mean_us,
            ruby_mean_us=ruby_mean_us,
            ratio=ratio,
            status=status,
        )

    def generate_comparison_report(self) -> List[BenchmarkComparison]:
        """Generate comparison report for all benchmarks"""
        comparisons = []

        if not self.python_results or not self.ruby_results:
            print("⚠ Missing benchmark results. Run benchmarks first.")
            return comparisons

        python_benchmarks = self.python_results.get("benchmarks", {})
        ruby_benchmarks = self.ruby_results.get("benchmarks", {})

        # Find common benchmarks
        python_keys = set(python_benchmarks.keys())
        ruby_keys = set(ruby_benchmarks.keys())
        common_keys = python_keys & ruby_keys

        for key in sorted(common_keys):
            python_data = python_benchmarks[key]
            ruby_data = ruby_benchmarks[key]

            # Handle nested structures
            if isinstance(python_data, dict) and "ops_per_sec" in python_data:
                comparison = self.compare_benchmark(key, python_data, ruby_data)
                comparisons.append(comparison)

        return comparisons

    def print_comparison_table(self, comparisons: List[BenchmarkComparison]):
        """Print comparison results as a formatted table"""
        print("\n" + "=" * 100)
        print("BENCHMARK COMPARISON: foobara-py vs foobara-ruby")
        print("=" * 100)
        print(
            f"{'Benchmark':<35} {'Python (μs)':<15} {'Ruby (μs)':<15} {'Ratio':<10} {'Status':<10}"
        )
        print("-" * 100)

        for comp in comparisons:
            status_symbol = {
                "faster": "🟢 Faster",
                "slower": "🔴 Slower",
                "similar": "🟡 Similar",
            }.get(comp.status, comp.status)

            print(
                f"{comp.name:<35} {comp.python_mean_us:<15.2f} {comp.ruby_mean_us:<15.2f} "
                f"{comp.ratio:<10.2f}x {status_symbol:<10}"
            )

        print("-" * 100)

        # Summary statistics
        faster_count = sum(1 for c in comparisons if c.status == "faster")
        slower_count = sum(1 for c in comparisons if c.status == "slower")
        similar_count = sum(1 for c in comparisons if c.status == "similar")

        print(f"\nSummary:")
        print(f"  🟢 Python faster: {faster_count}")
        print(f"  🔴 Python slower: {slower_count}")
        print(f"  🟡 Similar performance: {similar_count}")

        if comparisons:
            avg_ratio = sum(c.ratio for c in comparisons) / len(comparisons)
            print(f"\nAverage ratio (Python/Ruby): {avg_ratio:.2f}x")

            if avg_ratio < 1.0:
                print(
                    f"✓ Python is on average {(1 - avg_ratio) * 100:.1f}% faster than Ruby"
                )
            elif avg_ratio > 1.0:
                print(
                    f"⚠ Python is on average {(avg_ratio - 1) * 100:.1f}% slower than Ruby"
                )
            else:
                print("✓ Python and Ruby have similar performance")

    def generate_performance_targets_report(self, comparisons: List[BenchmarkComparison]):
        """Generate report on meeting performance targets"""
        print("\n" + "=" * 100)
        print("PERFORMANCE TARGETS ASSESSMENT")
        print("=" * 100)
        print("\nTargets (from task description):")
        print("  • Command execution: within 2x of Ruby")
        print("  • Validation: within 1.5x of Ruby")
        print("  • Transactions: within 2x of Ruby")
        print("  • Entity loading: within 2x of Ruby")
        print()

        targets = {
            "simple_command": ("Command execution", 2.0),
            "validated": ("Validation", 1.5),
            "with_transaction": ("Transactions", 2.0),
            "complex": ("Complex validation", 1.5),
        }

        results = {}
        for comp in comparisons:
            for key, (category, target) in targets.items():
                if key in comp.name.lower() or comp.name == key:
                    meets_target = comp.ratio <= target
                    status = "✓ PASS" if meets_target else "✗ FAIL"
                    results[category] = {
                        "ratio": comp.ratio,
                        "target": target,
                        "meets_target": meets_target,
                    }
                    print(
                        f"{status} {category}: {comp.ratio:.2f}x (target: {target:.2f}x)"
                    )

        # Overall assessment
        if results:
            passed = sum(1 for r in results.values() if r["meets_target"])
            total = len(results)
            print(f"\nOverall: {passed}/{total} targets met ({passed/total*100:.0f}%)")

    def save_comparison_report(
        self, comparisons: List[BenchmarkComparison], filename: str = "comparison_report.json"
    ):
        """Save comparison report to JSON"""
        output_file = self.results_dir / filename

        report_data = {
            "python_framework": self.python_results.get("framework", "foobara-py"),
            "ruby_framework": self.ruby_results.get("framework", "foobara-ruby"),
            "python_timestamp": self.python_results.get("timestamp"),
            "ruby_timestamp": self.ruby_results.get("timestamp"),
            "comparisons": [
                {
                    "name": c.name,
                    "python_ops_per_sec": c.python_ops_per_sec,
                    "ruby_ops_per_sec": c.ruby_ops_per_sec,
                    "python_mean_us": c.python_mean_us,
                    "ruby_mean_us": c.ruby_mean_us,
                    "ratio": c.ratio,
                    "status": c.status,
                }
                for c in comparisons
            ],
        }

        with open(output_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\nComparison report saved to: {output_file}")

    def generate_csv_report(
        self, comparisons: List[BenchmarkComparison], filename: str = "comparison_report.csv"
    ):
        """Generate CSV report for spreadsheet analysis"""
        output_file = self.results_dir / filename

        with open(output_file, "w") as f:
            # Header
            f.write(
                "Benchmark,Python (μs),Ruby (μs),Python (ops/sec),Ruby (ops/sec),Ratio,Status\n"
            )

            # Data rows
            for comp in comparisons:
                f.write(
                    f"{comp.name},{comp.python_mean_us:.2f},{comp.ruby_mean_us:.2f},"
                    f"{comp.python_ops_per_sec:.0f},{comp.ruby_ops_per_sec:.0f},"
                    f"{comp.ratio:.2f},{comp.status}\n"
                )

        print(f"CSV report saved to: {output_file}")

    def run(self):
        """Run full comparison analysis"""
        print("\n" + "=" * 100)
        print("FOOBARA BENCHMARK COMPARISON TOOL")
        print("=" * 100)

        self.load_results()

        if not self.python_results and not self.ruby_results:
            print("\n⚠ No benchmark results found.")
            print("Run the following to generate benchmark data:")
            print("  1. Python: python -m benchmarks.benchmark_command_execution")
            print("  2. Ruby: ruby benchmarks/benchmark_command_execution.rb")
            return

        comparisons = self.generate_comparison_report()

        if comparisons:
            self.print_comparison_table(comparisons)
            self.generate_performance_targets_report(comparisons)
            self.save_comparison_report(comparisons)
            self.generate_csv_report(comparisons)
        else:
            print("\n⚠ No comparable benchmarks found.")
            print("Ensure both Python and Ruby benchmarks have been run.")


def main():
    """Main entry point"""
    comparer = BenchmarkComparer()
    comparer.run()


if __name__ == "__main__":
    main()
