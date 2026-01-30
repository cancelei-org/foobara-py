# Async Commands Examples

This directory contains comprehensive examples demonstrating async command usage in Foobara.

## Prerequisites

Install required dependencies:

```bash
pip install foobara-py httpx pytest-asyncio
```

## Examples

### 1. fetch_api_data.py

Demonstrates fetching data from external APIs with:
- Basic async HTTP requests
- Error handling for network failures
- Timeout configuration
- Retry logic with exponential backoff
- Sequential API calls with data aggregation

**Run it:**
```bash
python examples/async_commands/fetch_api_data.py
```

### 2. batch_processing.py

Shows concurrent batch processing with:
- Parallel processing using asyncio.gather
- Rate limiting with semaphores
- Progress tracking
- Error handling for partial failures
- Performance comparisons (sequential vs concurrent)

**Run it:**
```bash
python examples/async_commands/batch_processing.py
```

### 3. concurrent_commands.py

Demonstrates running multiple commands concurrently:
- Command composition and orchestration
- Fan-out/fan-in patterns
- Error propagation across commands
- Complex workflows with dependencies
- Resource sharing between commands

**Run it:**
```bash
python examples/async_commands/concurrent_commands.py
```

## Testing

All examples use the GitHub API (no authentication required for basic usage).

To test the examples:

```bash
# Run all examples
for file in examples/async_commands/*.py; do
    python "$file"
done
```

## Key Concepts Covered

1. **Basic Async Commands**: Creating and running async commands
2. **Error Handling**: Adding errors, handling exceptions, graceful degradation
3. **Concurrency**: Running multiple operations in parallel
4. **Rate Limiting**: Controlling concurrent operation limits
5. **Progress Tracking**: Monitoring long-running batch operations
6. **Retries**: Implementing retry logic with backoff
7. **Timeouts**: Setting and handling operation timeouts
8. **Orchestration**: Composing multiple commands into workflows

## Further Reading

See the comprehensive guide: `docs/ASYNC_COMMANDS.md`
