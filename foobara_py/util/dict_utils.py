"""
Dictionary utility functions for Foobara.

Provides utility functions for working with dictionaries,
including sorting by keys and other common operations.
"""

from typing import Any, Dict, TypeVar

K = TypeVar('K')
V = TypeVar('V')


def sort_by_keys(d: Dict[K, V]) -> Dict[K, V]:
    """
    Sort a dictionary by its keys and return a new dictionary.

    Creates a new dictionary with the same key-value pairs as the input,
    but with keys sorted in ascending order. The original dictionary is
    not modified.

    Args:
        d: The dictionary to sort

    Returns:
        A new dictionary with keys sorted in ascending order

    Examples:
        >>> sort_by_keys({'c': 3, 'a': 1, 'b': 2})
        {'a': 1, 'b': 2, 'c': 3}

        >>> sort_by_keys({3: 'three', 1: 'one', 2: 'two'})
        {1: 'one', 2: 'two', 3: 'three'}
    """
    keys = list(d.keys())
    keys.sort()

    sorted_dict: Dict[K, V] = {}

    for key in keys:
        sorted_dict[key] = d[key]

    return sorted_dict


def sort_by_keys_in_place(d: Dict[K, V]) -> Dict[K, V]:
    """
    Sort a dictionary by its keys in-place and return the same dictionary.

    Modifies the input dictionary to have its keys in sorted order.
    This is done by removing and re-inserting keys that are out of order.
    Since Python 3.7+, dictionaries maintain insertion order, so this
    preserves the sorted order.

    Args:
        d: The dictionary to sort in-place

    Returns:
        The same dictionary reference with keys now sorted

    Examples:
        >>> d = {'c': 3, 'a': 1, 'b': 2}
        >>> result = sort_by_keys_in_place(d)
        >>> result is d  # Same object
        True
        >>> d
        {'a': 1, 'b': 2, 'c': 3}

    Note:
        This function uses an algorithm similar to the Ruby version:
        - Scans through to find keys that are out of order
        - Collects them and sorts them
        - Removes and re-inserts them in the correct order
    """
    last_key = None
    keys_to_move = None

    for key in list(d.keys()):
        if last_key is not None:
            if key < last_key:
                if keys_to_move is not None:
                    keys_to_move.append(key)
                else:
                    keys_to_move = [key]

                continue

        last_key = key

    if keys_to_move is None:
        return d

    keys_to_move.sort()

    for key in keys_to_move:
        value = d.pop(key)
        d[key] = value

    return d


__all__ = [
    "sort_by_keys",
    "sort_by_keys_in_place",
]
