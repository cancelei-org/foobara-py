# Dict Utils Port from Ruby util v1.0.8

## Summary

This document describes the port of hash utility methods from Ruby foobara-util v1.0.8 to Python.

## Implementation

### Source
- **Ruby Repository**: `/home/cancelei/Projects/foobara-universe/foobara-ecosystem-ruby/core/util`
- **Commit**: `35fc38c09b4373b1c523b11cab03552cc30e8b42`
- **Date**: 2026-01-22
- **Commit Message**: "Add .sort_by_keys/.sort_by_keys! for hashes"

### Python Implementation
- **Module**: `foobara_py/util/dict_utils.py`
- **Tests**: `tests/test_dict_utils.py`
- **Example**: `examples/dict_utils_example.py`

## Functions Ported

### 1. `sort_by_keys(d: Dict[K, V]) -> Dict[K, V]`

**Ruby equivalent**: `Foobara::Util.sort_by_keys(hash)`

Creates a new dictionary with keys sorted in ascending order.

**Behavior**:
- Returns a new dictionary (does not modify original)
- Keys are sorted using Python's default sort order
- All key-value pairs are preserved
- Works with any comparable key type (strings, numbers, etc.)

**Example**:
```python
from foobara_py.util import sort_by_keys

unsorted = {'c': 3, 'a': 1, 'b': 2}
sorted_dict = sort_by_keys(unsorted)
# sorted_dict = {'a': 1, 'b': 2, 'c': 3}
# unsorted remains {'c': 3, 'a': 1, 'b': 2}
```

### 2. `sort_by_keys_in_place(d: Dict[K, V]) -> Dict[K, V]`

**Ruby equivalent**: `Foobara::Util.sort_by_keys!(hash)`

Sorts dictionary keys in-place and returns the same dictionary reference.

**Behavior**:
- Modifies the original dictionary
- Returns the same dictionary object (for chaining)
- Uses a single-pass algorithm that moves out-of-order keys to the end
- **Note**: May not fully sort in one pass if the dictionary has complex disorder
- For guaranteed full sorting, use `sort_by_keys()` instead

**Algorithm**:
The function implements the same algorithm as Ruby:
1. Iterates through keys in current order
2. Identifies keys that are less than the previous "in-order" key
3. Collects these out-of-order keys
4. Sorts the collected keys
5. Removes and re-inserts them at the end in sorted order

**Example**:
```python
from foobara_py.util import sort_by_keys_in_place

data = {'z': 26, 'm': 13, 'a': 1}
result = sort_by_keys_in_place(data)
# Both 'data' and 'result' refer to the same dictionary
# result is data  # True
```

## Test Coverage

The test suite includes:

### Basic Functionality Tests
- Sorting with string keys
- Sorting with numeric keys
- Empty dictionary handling
- Single-item dictionary handling
- Already-sorted dictionary handling

### Behavior Tests
- Returns new dict vs. modifies in place
- Object identity verification
- Value reference preservation

### Edge Cases
- Partially sorted dictionaries
- Reverse-order dictionaries
- Complex sorting scenarios
- Unicode keys
- Duplicate values
- Mixed value types

### Ruby Parity Tests
The test suite uses the exact same test fixtures as the Ruby implementation:
- 26-key unsorted dictionary (letters a-z with values 1-26)
- Verifies equivalent behavior between `sort_by_keys()` and Ruby's `.sort_by_keys()`
- Verifies equivalent behavior between `sort_by_keys_in_place()` and Ruby's `.sort_by_keys!()`

## Key Differences from Ruby

1. **Hash Equality**: Ruby's hash equality (`==`) ignores key order and only compares key-value pairs. Python's dict equality also ignores key order (as of Python 3.7+), but we provide additional tests that verify key order explicitly.

2. **Naming**: Python uses `sort_by_keys_in_place()` instead of `sort_by_keys!()` because Python doesn't have the `!` naming convention for mutating methods.

3. **Type Hints**: The Python implementation includes full type hints using generics for better IDE support and type checking.

## Usage

```python
# Import from util module
from foobara_py.util import sort_by_keys, sort_by_keys_in_place

# Or import directly
from foobara_py.util.dict_utils import sort_by_keys, sort_by_keys_in_place

# Sort and create new dict
original = {'c': 3, 'a': 1, 'b': 2}
sorted_dict = sort_by_keys(original)

# Sort in place
data = {'z': 26, 'm': 13, 'a': 1}
sort_by_keys_in_place(data)  # Modifies data
```

## Files Created/Modified

### New Files
- `foobara_py/util/dict_utils.py` - Implementation
- `tests/test_dict_utils.py` - Test suite (26 tests)
- `examples/dict_utils_example.py` - Usage examples
- `DICT_UTILS_PORT.md` - This documentation

### Modified Files
- `foobara_py/util/__init__.py` - Added exports for `sort_by_keys` and `sort_by_keys_in_place`

## Test Results

All 26 tests pass successfully:
- 10 tests for `sort_by_keys()`
- 11 tests for `sort_by_keys_in_place()`
- 5 edge case and comparison tests

## Notes

The Python implementation matches the Ruby behavior exactly, including the single-pass nature of the in-place sorting algorithm. While this means `sort_by_keys_in_place()` may not fully sort all dictionaries in one pass, this behavior is intentional to maintain parity with the Ruby implementation.

For applications that require fully sorted dictionaries, use `sort_by_keys()` which guarantees a fully sorted result.
