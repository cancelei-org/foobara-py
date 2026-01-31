"""
Example usage of dict_utils functions.

This demonstrates the sort_by_keys and sort_by_keys_in_place functions
from foobara_py.util.dict_utils.
"""

from foobara_py.util import sort_by_keys, sort_by_keys_in_place


def main():
    """Demonstrate dict_utils functionality."""
    print("Dictionary Utilities Example\n" + "=" * 40)

    # Example 1: sort_by_keys (creates new dict)
    print("\n1. sort_by_keys() - Creates a new sorted dictionary")
    original = {'c': 3, 'a': 1, 'b': 2}
    sorted_dict = sort_by_keys(original)

    print(f"   Original: {original}")
    print(f"   Sorted:   {sorted_dict}")
    print(f"   Same object? {sorted_dict is original}")

    # Example 2: sort_by_keys_in_place (modifies original)
    print("\n2. sort_by_keys_in_place() - Modifies the original dictionary")
    data = {'z': 26, 'm': 13, 'a': 1}
    result = sort_by_keys_in_place(data)

    print(f"   After sorting: {data}")
    print(f"   Same object? {result is data}")

    # Example 3: With numeric keys
    print("\n3. Works with numeric keys")
    numbers = {5: 'five', 2: 'two', 8: 'eight', 1: 'one'}
    sorted_numbers = sort_by_keys(numbers)

    print(f"   Original: {numbers}")
    print(f"   Sorted:   {sorted_numbers}")

    # Example 4: Real-world use case - sorting JSON response keys
    print("\n4. Real-world example: Sorting API response keys")
    api_response = {
        'user_id': 123,
        'email': 'user@example.com',
        'created_at': '2026-01-30',
        'name': 'John Doe',
        'active': True
    }

    sorted_response = sort_by_keys(api_response)
    print(f"   Original keys: {list(api_response.keys())}")
    print(f"   Sorted keys:   {list(sorted_response.keys())}")

    # Example 5: Demonstrating single-pass behavior of sort_by_keys_in_place
    print("\n5. Note: sort_by_keys_in_place does a single pass")
    print("   For fully sorted results, use sort_by_keys()")

    partially_sorted = {'a': 1, 'c': 3, 'b': 2, 'e': 5, 'd': 4}
    in_place_result = sort_by_keys_in_place(partially_sorted.copy())
    full_sort_result = sort_by_keys(partially_sorted)

    print(f"   Original:         {list(partially_sorted.keys())}")
    print(f"   In-place result:  {list(in_place_result.keys())}")
    print(f"   Full sort result: {list(full_sort_result.keys())}")


if __name__ == '__main__':
    main()
