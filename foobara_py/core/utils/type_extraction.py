"""Type extraction utilities for generic types."""

from typing import Any, Type, get_args, get_origin


def extract_generic_types(cls: Type[Any]) -> tuple[Type[Any], ...]:
    """
    Extract generic type arguments from a class.

    Args:
        cls: A generic class with type parameters

    Returns:
        Tuple of type arguments, or empty tuple if not generic

    Example:
        >>> class MyCommand(Command[MyInputs, MyResult]): pass
        >>> extract_generic_types(MyCommand)
        (MyInputs, MyResult)
    """
    # Check if class has __orig_bases__ (for generic subclasses)
    if hasattr(cls, "__orig_bases__"):
        for base in cls.__orig_bases__:
            if get_origin(base) is not None:
                args = get_args(base)
                if args:
                    return args

    # Check __args__ directly (for instantiated generics)
    if hasattr(cls, "__args__"):
        return cls.__args__

    return ()


def extract_inputs_type(command_class: Type[Any]) -> Type[Any] | None:
    """
    Extract the inputs type from a Command class.

    Args:
        command_class: A Command subclass

    Returns:
        The inputs type, or None if not found

    Example:
        >>> class MyCommand(Command[MyInputs, MyResult]): pass
        >>> extract_inputs_type(MyCommand)
        MyInputs
    """
    types = extract_generic_types(command_class)
    return types[0] if types else None


def extract_result_type(command_class: Type[Any]) -> Type[Any] | None:
    """
    Extract the result type from a Command class.

    Args:
        command_class: A Command subclass

    Returns:
        The result type, or None if not found

    Example:
        >>> class MyCommand(Command[MyInputs, MyResult]): pass
        >>> extract_result_type(MyCommand)
        MyResult
    """
    types = extract_generic_types(command_class)
    return types[1] if len(types) > 1 else None
