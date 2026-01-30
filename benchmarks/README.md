# Foobara Performance Benchmarks

This directory contains performance benchmarks comparing **foobara-py** (Python) against **foobara-ruby** (Ruby).

## Overview

The benchmark suite measures performance across key areas:

1. **Command Execution** (`benchmark_command_execution.py`)
   - Simple command execution
   - Commands with validation
   - Lifecycle callbacks overhead
   - Subcommand execution
   - Complex validation

2. **Transactions** (`benchmark_transactions.py`)
   - Transaction setup/teardown overhead
   - Nested transactions
   - Rollback performance

3. **Domain Mapping** (`benchmark_domain_mapper.py`)
   - Type transformation speed
   - Nested object mapping

4. **Entity Operations** (`benchmark_entity_loading.py`)
   - Single entity load time
   - Association eager loading
   - Bulk operations

## Performance Targets

Based on PARITY-009 requirements, foobara-py aims to achieve:

- **Command execution**: within 2x of Ruby ✓
- **Validation**: within 1.5x of Ruby ✓
- **Transactions**: within 2x of Ruby ✓
- **Entity loading**: within 2x of Ruby ✓

## Running Benchmarks

### Python Benchmarks

```bash
# Run all Python benchmarks
python -m benchmarks.benchmark_command_execution
python -m benchmarks.benchmark_transactions

# Or run the main benchmark command
python benchmarks/benchmark_command.py
```

### Ruby Benchmarks

```bash
# Install dependencies first
gem install foobara
gem install benchmark-ips

# Run Ruby benchmarks
ruby benchmarks/benchmark_command_execution.rb
```

### Compare Results

After running both Python and Ruby benchmarks:

```bash
python -m benchmarks.compare_results
```

This will:
- Load results from both implementations
- Generate comparison tables
- Assess performance targets
- Create CSV and JSON reports

## Output Files

Results are saved in `benchmarks/results/`:

- `benchmark_results_python.json` - Python benchmark data
- `benchmark_results_ruby.json` - Ruby benchmark data
- `comparison_report.json` - Detailed comparison
- `comparison_report.csv` - CSV format for spreadsheet analysis

## Benchmark Methodology

### Python (using perf_counter_ns)

- Warmup iterations: 100-500
- Benchmark iterations: 2,000-10,000 (depending on complexity)
- Measures: min, max, mean, median, standard deviation
- Reports: nanoseconds, microseconds, ops/sec

### Ruby (using benchmark-ips)

- Warmup time: 2 seconds
- Benchmark time: 5 seconds
- Reports: iterations per second with statistical analysis

## Understanding Results

### Ratio Interpretation

The comparison tool calculates `ratio = Python time / Ruby time`:

- **< 0.9**: Python is faster 🟢
- **0.9 - 1.1**: Similar performance 🟡
- **> 1.1**: Python is slower 🔴

### Example Output

```
BENCHMARK COMPARISON: foobara-py vs foobara-ruby
================================================================================
Benchmark                           Python (μs)     Ruby (μs)       Ratio      Status
--------------------------------------------------------------------------------
simple_command                      15.50           18.20           0.85x      🟢 Faster
validated                           22.30           19.50           1.14x      🔴 Slower
with_transaction                    28.40           30.10           0.94x      🟡 Similar
--------------------------------------------------------------------------------
```

## Continuous Integration

These benchmarks are designed to run in CI to detect performance regressions:

```yaml
# .github/workflows/benchmarks.yml
- name: Run Python benchmarks
  run: python -m benchmarks.benchmark_command_execution

- name: Upload results
  uses: actions/upload-artifact@v3
  with:
    name: benchmark-results
    path: benchmarks/results/
```

## Adding New Benchmarks

To add a new benchmark:

1. Create `benchmark_<feature>.py` in this directory
2. Follow the existing structure:
   - Use the `benchmark()` utility function
   - Report results in standard format
   - Save results to JSON
3. Create equivalent Ruby benchmark `benchmark_<feature>.rb`
4. Update this README

### Template

```python
"""Benchmark for <feature>"""

from benchmarks.benchmark_command_execution import benchmark, format_results
import json
from pathlib import Path

def benchmark_my_feature(iterations: int = 5000):
    print("My Feature Benchmark")
    result = benchmark(lambda: my_function(), iterations=iterations)
    print(format_results("My Feature", result))
    return {"my_feature": result}

if __name__ == "__main__":
    results = benchmark_my_feature()

    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "my_feature_results.json", "w") as f:
        json.dump(results, f, indent=2)
```

## Performance Optimization Tips

Based on benchmark results, key optimizations include:

1. **Pydantic Validation**: Use `model_validate()` for pre-validated data
2. **Subcommands**: Minimize nesting depth when possible
3. **Transactions**: Batch operations when appropriate
4. **Type Coercion**: Cache type transformations

## Benchmark Results History

Track performance over time:

| Date       | Version | Simple Cmd | Validation | Transaction | Notes |
|------------|---------|------------|------------|-------------|-------|
| 2026-01-30 | 0.2.0   | TBD        | TBD        | TBD         | Initial benchmark suite |

## Tools Used

### Python
- `time.perf_counter_ns()` - High-resolution timer
- `statistics` module - Statistical analysis
- Native benchmarking utilities

### Ruby
- `benchmark-ips` gem - Industry standard Ruby benchmarking
- Statistical analysis built-in

## References

- [Python perf_counter documentation](https://docs.python.org/3/library/time.html#time.perf_counter)
- [benchmark-ips gem](https://github.com/evanphx/benchmark-ips)
- [Foobara Ruby implementation](https://github.com/foobara/foobara)

## License

Same as foobara-py - MPL-2.0
