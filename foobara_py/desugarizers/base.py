"""
Base desugarizer classes and pipeline for Foobara Python.

Desugarizers transform raw input data before command execution.
They run before validation to normalize, clean, or restructure inputs.
"""

import threading
from abc import ABC, abstractmethod
from typing import Any


class Desugarizer(ABC):
    """
    Base desugarizer interface.

    Desugarizers transform raw input data before it reaches
    the command's input validation. They're useful for:
    - Normalizing different input formats
    - Renaming keys to match expected schema
    - Setting default values
    - Filtering unwanted keys

    Usage:
        class UppercaseKeysDesugarizer(Desugarizer):
            def desugarize(self, data: dict) -> dict:
                return {k.upper(): v for k, v in data.items()}

        desugarizer = UppercaseKeysDesugarizer()
        result = desugarizer.desugarize({"name": "John"})  # {"NAME": "John"}
    """

    @abstractmethod
    def desugarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform raw input data.

        Args:
            data: Raw input dictionary

        Returns:
            Transformed input dictionary
        """
        pass

    def __call__(self, data: dict[str, Any]) -> dict[str, Any]:
        """Allow desugarizer to be called as a function"""
        return self.desugarize(data)


class DesugarizePipeline:
    """
    Chain multiple desugarizers into a pipeline.

    Desugarizers are applied in order, with each desugarizer
    receiving the output of the previous one.

    Usage:
        pipeline = DesugarizePipeline(
            RenameKey(old_name="new_name"),
            OnlyInputs("name", "email"),
            SetInputs(status="active")
        )
        result = pipeline.process(raw_data)
    """

    def __init__(self, *desugarizers: Desugarizer):
        """
        Initialize pipeline with desugarizers.

        Args:
            *desugarizers: Variable number of desugarizers to chain
        """
        self.desugarizers: list[Desugarizer] = list(desugarizers)

    def add(self, desugarizer: Desugarizer) -> "DesugarizePipeline":
        """
        Add a desugarizer to the end of the pipeline.

        Args:
            desugarizer: Desugarizer to add

        Returns:
            Self for method chaining
        """
        self.desugarizers.append(desugarizer)
        return self

    def prepend(self, desugarizer: Desugarizer) -> "DesugarizePipeline":
        """
        Add a desugarizer to the beginning of the pipeline.

        Args:
            desugarizer: Desugarizer to add

        Returns:
            Self for method chaining
        """
        self.desugarizers.insert(0, desugarizer)
        return self

    def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Apply all desugarizers in sequence.

        Args:
            data: Initial raw input data

        Returns:
            Data after all desugarizations
        """
        for desugarizer in self.desugarizers:
            data = desugarizer.desugarize(data)
        return data

    def __call__(self, data: dict[str, Any]) -> dict[str, Any]:
        """Allow pipeline to be called as a function"""
        return self.process(data)

    def __len__(self) -> int:
        """Get number of desugarizers in pipeline"""
        return len(self.desugarizers)


class DesugarizerRegistry:
    """
    Global registry for desugarizers.

    Allows registration and lookup of desugarizers by name.
    Useful for command connectors to apply standard desugarizations.

    Usage:
        # Register desugarizer
        DesugarizerRegistry.register("only_inputs", OnlyInputs)

        # Get desugarizer
        desugarizer_class = DesugarizerRegistry.get("only_inputs")

        # Create instance and use
        desugarizer = desugarizer_class("name", "email")
        result = desugarizer.desugarize(data)
    """

    _desugarizers: dict[str, type[Desugarizer]] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, name: str, desugarizer_class: type[Desugarizer]) -> type[Desugarizer]:
        """
        Register a desugarizer class.

        Args:
            name: Unique name for the desugarizer
            desugarizer_class: The desugarizer class

        Returns:
            The desugarizer class (for decorator usage)
        """
        with cls._lock:
            cls._desugarizers[name] = desugarizer_class
        return desugarizer_class

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a desugarizer"""
        with cls._lock:
            cls._desugarizers.pop(name, None)

    @classmethod
    def get(cls, name: str) -> type[Desugarizer] | None:
        """Get desugarizer class by name"""
        with cls._lock:
            return cls._desugarizers.get(name)

    @classmethod
    def list_all(cls) -> dict[str, type[Desugarizer]]:
        """List all registered desugarizers"""
        with cls._lock:
            return cls._desugarizers.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered desugarizers (for testing)"""
        with cls._lock:
            cls._desugarizers.clear()


def desugarizer(name: str = None):
    """
    Decorator to register a desugarizer.

    Usage:
        @desugarizer(name="only_required")
        class OnlyRequiredDesugarizer(Desugarizer):
            def desugarize(self, data: dict) -> dict:
                ...
    """

    def decorator(cls: type[Desugarizer]) -> type[Desugarizer]:
        desugarizer_name = name or cls.__name__
        DesugarizerRegistry.register(desugarizer_name, cls)
        return cls

    return decorator
