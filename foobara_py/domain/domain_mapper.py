"""
Domain Mappers for cross-domain type/model mapping.

Domain mappers transform data between different domain types, enabling
commands to call subcommands from other domains with automatic data transformation.

Usage:
    class UserBToDomainA(DomainMapper[UserB, UserA]):
        def map(self) -> UserA:
            return UserA(
                id=self.from_value.id,
                name=self.from_value.name
            )

    # In a command:
    result = self.run_mapped_subcommand(
        SomeOtherDomainCommand,
        unmapped_inputs={"user": user_b_instance},
        to=UserA
    )
"""

import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from foobara_py.core.utils import extract_generic_types

FromT = TypeVar("FromT")
ToT = TypeVar("ToT")


class DomainMapper(ABC, Generic[FromT, ToT]):
    """
    Base class for domain mappers that transform data between types.

    Domain mappers are similar to commands but specialized for type transformations.
    They enable cross-domain communication by mapping between different domain models.

    Features:
    - Generic type safety with FromT and ToT
    - Automatic type matching and scoring
    - Registry integration for mapper discovery
    - Bidirectional mapping support

    Usage:
        class UserInternalToExternal(DomainMapper[UserInternal, UserExternal]):
            '''Maps internal user model to external API model'''

            def map(self) -> UserExternal:
                return UserExternal(
                    id=str(self.from_value.id),
                    name=self.from_value.full_name,
                    email=self.from_value.email
                )
    """

    # Class-level configuration
    _domain: Optional[str] = None
    _organization: Optional[str] = None
    _cached_from_type: Optional[Type] = None
    _cached_to_type: Optional[Type] = None

    __slots__ = ("from_value", "_result")

    def __init__(self, from_value: FromT):
        """
        Initialize mapper with source value.

        Args:
            from_value: The value to map from
        """
        self.from_value = from_value
        self._result: Optional[ToT] = None

    @abstractmethod
    def map(self) -> ToT:
        """
        Perform the mapping transformation.

        Override this method to implement the mapping logic.

        Returns:
            The mapped value of type ToT
        """
        pass

    def run(self) -> ToT:
        """Run the mapper and return the mapped value"""
        if self._result is None:
            self._result = self.map()
        return self._result

    # ==================== Type Extraction ====================

    @classmethod
    def from_type(cls) -> Type[FromT]:
        """Get the source type (FromT) for this mapper"""
        if cls._cached_from_type is not None:
            return cls._cached_from_type

        types = extract_generic_types(cls)
        if not types or len(types) < 1:
            raise TypeError(f"Could not determine from_type for {cls.__name__}")

        cls._cached_from_type = types[0]
        return types[0]

    @classmethod
    def to_type(cls) -> Type[ToT]:
        """Get the destination type (ToT) for this mapper"""
        if cls._cached_to_type is not None:
            return cls._cached_to_type

        types = extract_generic_types(cls)
        if not types or len(types) < 2:
            raise TypeError(f"Could not determine to_type for {cls.__name__}")

        cls._cached_to_type = types[1]
        return types[1]

    # ==================== Type Matching ====================

    @classmethod
    def applicable(cls, from_value: Any, to_value: Any) -> bool:
        """
        Check if this mapper is applicable for the given from/to values.

        Args:
            from_value: The source value or type
            to_value: The destination value or type

        Returns:
            True if this mapper can handle the transformation
        """
        return cls.match_score(from_value, to_value) > 0

    @classmethod
    def match_score(cls, from_value: Any, to_value: Any) -> int:
        """
        Calculate a match score for this mapper.

        Higher scores indicate better matches. Used for selecting
        the most appropriate mapper when multiple options exist.

        Scoring:
        - 20: Exact type match
        - 10: Type class match
        - 5: Pydantic model compatible
        - 1: Generic fallback
        - 0: Not applicable

        Args:
            from_value: The source value or type
            to_value: The destination value or type

        Returns:
            Match score (0 = not applicable, higher = better match)
        """
        from_score = cls._match_single(cls.from_type(), from_value)
        to_score = cls._match_single(cls.to_type(), to_value)

        if from_score == 0 or to_score == 0:
            return 0

        return from_score + to_score

    @classmethod
    def _match_single(cls, expected_type: Type, value: Any) -> int:
        """Calculate match score for a single type/value pair"""
        if value is None or expected_type is None:
            return 1

        # Exact type match
        if expected_type == value:
            return 20

        # Check if value is an instance of expected type
        if isinstance(value, type):
            if issubclass(
                value, expected_type if isinstance(expected_type, type) else type(expected_type)
            ):
                return 10
        else:
            if isinstance(
                value, expected_type if isinstance(expected_type, type) else type(expected_type)
            ):
                return 10

        # Pydantic model compatibility
        if isinstance(expected_type, type) and issubclass(expected_type, BaseModel):
            if isinstance(value, dict):
                try:
                    expected_type(**value)
                    return 5
                except Exception:
                    pass

        return 0

    # ==================== Class Methods ====================

    @classmethod
    def map_value(cls, from_value: FromT) -> ToT:
        """
        Class method to map a value (convenience method).

        Usage:
            user_external = UserInternalToExternal.map_value(user_internal)
        """
        mapper = cls(from_value)
        return mapper.run()

    @classmethod
    def full_name(cls) -> str:
        """Get fully qualified mapper name"""
        parts = []
        if cls._organization:
            parts.append(cls._organization)
        if cls._domain:
            parts.append(cls._domain)
        parts.append(cls.__name__)
        return "::".join(parts)


class DomainMapperRegistry:
    """
    Global registry for domain mappers.

    Manages mapper registration and discovery across domains.
    Supports finding the best mapper for a given from/to type pair.
    """

    _mappers: Dict[str, Type[DomainMapper]] = {}
    _domain_mappers: Dict[str, Dict[str, Type[DomainMapper]]] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, mapper_class: Type[DomainMapper], domain: str = None) -> None:
        """
        Register a mapper class.

        Args:
            mapper_class: The mapper class to register
            domain: Optional domain name (uses mapper._domain if not provided)
        """
        with cls._lock:
            domain_name = domain or mapper_class._domain or "Global"
            full_name = mapper_class.full_name()

            cls._mappers[full_name] = mapper_class

            if domain_name not in cls._domain_mappers:
                cls._domain_mappers[domain_name] = {}
            cls._domain_mappers[domain_name][full_name] = mapper_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[DomainMapper]]:
        """Get mapper by full name"""
        with cls._lock:
            return cls._mappers.get(name)

    @classmethod
    def list_for_domain(cls, domain: str) -> Dict[str, Type[DomainMapper]]:
        """List all mappers registered for a domain"""
        with cls._lock:
            return cls._domain_mappers.get(domain, {}).copy()

    @classmethod
    def find_matching_mapper(
        cls, from_value: Any, to_value: Any, domain: str = None
    ) -> Optional[Type[DomainMapper]]:
        """
        Find the best matching mapper for from/to values.

        Searches mappers in the specified domain (or globally) and
        returns the one with the highest match score.

        Args:
            from_value: Source value or type
            to_value: Destination value or type
            domain: Optional domain to search (None = global search)

        Returns:
            Best matching mapper class, or None if no match found
        """
        with cls._lock:
            if domain:
                mappers = cls._domain_mappers.get(domain, {}).values()
            else:
                mappers = cls._mappers.values()

            best_mapper = None
            best_score = 0

            for mapper in mappers:
                score = mapper.match_score(from_value, to_value)
                if score > best_score:
                    best_score = score
                    best_mapper = mapper

            return best_mapper

    @classmethod
    def clear(cls) -> None:
        """Clear all registered mappers (for testing)"""
        with cls._lock:
            cls._mappers.clear()
            cls._domain_mappers.clear()


def domain_mapper(domain: str = None, organization: str = None):
    """
    Decorator to register a domain mapper.

    Usage:
        @domain_mapper(domain="Users", organization="MyApp")
        class UserInternalToExternal(DomainMapper[UserInternal, UserExternal]):
            def map(self) -> UserExternal:
                ...
    """

    def decorator(cls: Type[DomainMapper]) -> Type[DomainMapper]:
        if domain:
            cls._domain = domain
        if organization:
            cls._organization = organization

        # Auto-register
        DomainMapperRegistry.register(cls)

        return cls

    return decorator
