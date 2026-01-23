"""
Base transformer classes and pipeline for Foobara Python.

Transformers modify data at various stages of command execution:
- Input transformers: before validation
- Result transformers: after execution
- Error transformers: before returning errors
"""

import threading
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Transformer(ABC, Generic[T]):
    """
    Base transformer interface.

    Transformers apply a specific transformation to a value.
    They are composable and can be chained in pipelines.

    Usage:
        class UppercaseTransformer(Transformer[str]):
            def transform(self, value: str) -> str:
                return value.upper()

        transformer = UppercaseTransformer()
        result = transformer.transform("hello")  # "HELLO"
    """

    @abstractmethod
    def transform(self, value: T) -> T:
        """
        Transform the input value.

        Args:
            value: The value to transform

        Returns:
            The transformed value
        """
        pass

    def __call__(self, value: T) -> T:
        """Allow transformer to be called as a function"""
        return self.transform(value)


class TransformerPipeline(Generic[T]):
    """
    Chain multiple transformers into a pipeline.

    Transformers are applied in order, with each transformer
    receiving the output of the previous one.

    Usage:
        pipeline = TransformerPipeline(
            Transformer1(),
            Transformer2(),
            Transformer3()
        )
        result = pipeline.transform(value)
    """

    def __init__(self, *transformers: Transformer[T]):
        """
        Initialize pipeline with transformers.

        Args:
            *transformers: Variable number of transformers to chain
        """
        self.transformers: list[Transformer[T]] = list(transformers)

    def add(self, transformer: Transformer[T]) -> "TransformerPipeline[T]":
        """
        Add a transformer to the end of the pipeline.

        Args:
            transformer: Transformer to add

        Returns:
            Self for method chaining
        """
        self.transformers.append(transformer)
        return self

    def prepend(self, transformer: Transformer[T]) -> "TransformerPipeline[T]":
        """
        Add a transformer to the beginning of the pipeline.

        Args:
            transformer: Transformer to add

        Returns:
            Self for method chaining
        """
        self.transformers.insert(0, transformer)
        return self

    def transform(self, value: T) -> T:
        """
        Apply all transformers in sequence.

        Args:
            value: Initial value

        Returns:
            Value after all transformations
        """
        for transformer in self.transformers:
            value = transformer.transform(value)
        return value

    def __call__(self, value: T) -> T:
        """Allow pipeline to be called as a function"""
        return self.transform(value)

    def __len__(self) -> int:
        """Get number of transformers in pipeline"""
        return len(self.transformers)


class TransformerRegistry:
    """
    Global registry for transformers.

    Allows registration and lookup of transformers by name or category.
    Useful for command connectors to apply standard transformations.

    Usage:
        # Register transformer
        TransformerRegistry.register("uppercase", UppercaseTransformer)

        # Get transformer
        transformer = TransformerRegistry.get("uppercase")

        # Get all transformers for a category
        input_transformers = TransformerRegistry.by_category("input")
    """

    _transformers: dict[str, type[Transformer]] = {}
    _categories: dict[str, list[str]] = {}
    _lock = threading.Lock()

    @classmethod
    def register(
        cls, name: str, transformer_class: type[Transformer], category: str = None
    ) -> type[Transformer]:
        """
        Register a transformer class.

        Args:
            name: Unique name for the transformer
            transformer_class: The transformer class
            category: Optional category (e.g., "input", "result", "error")

        Returns:
            The transformer class (for decorator usage)
        """
        with cls._lock:
            cls._transformers[name] = transformer_class

            if category:
                if category not in cls._categories:
                    cls._categories[category] = []
                cls._categories[category].append(name)

        return transformer_class

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a transformer"""
        with cls._lock:
            cls._transformers.pop(name, None)
            # Remove from categories
            for category_list in cls._categories.values():
                if name in category_list:
                    category_list.remove(name)

    @classmethod
    def get(cls, name: str) -> type[Transformer] | None:
        """Get transformer class by name"""
        with cls._lock:
            return cls._transformers.get(name)

    @classmethod
    def by_category(cls, category: str) -> list[type[Transformer]]:
        """Get all transformer classes in a category"""
        with cls._lock:
            names = cls._categories.get(category, [])
            return [cls._transformers[name] for name in names if name in cls._transformers]

    @classmethod
    def list_all(cls) -> dict[str, type[Transformer]]:
        """List all registered transformers"""
        with cls._lock:
            return cls._transformers.copy()

    @classmethod
    def list_categories(cls) -> list[str]:
        """List all categories"""
        with cls._lock:
            return list(cls._categories.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered transformers (for testing)"""
        with cls._lock:
            cls._transformers.clear()
            cls._categories.clear()


def transformer(name: str = None, category: str = None):
    """
    Decorator to register a transformer.

    Usage:
        @transformer(name="uppercase", category="input")
        class UppercaseTransformer(Transformer[str]):
            def transform(self, value: str) -> str:
                return value.upper()
    """

    def decorator(cls: type[Transformer]) -> type[Transformer]:
        transformer_name = name or cls.__name__
        TransformerRegistry.register(transformer_name, cls, category)
        return cls

    return decorator
