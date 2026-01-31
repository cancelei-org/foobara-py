"""
Enhanced callback system with Ruby-level flexibility and Python performance.

Provides:
- Conditional callbacks (from/to/transition filtering)
- before/after/around/error callback types
- Pre-compiled callback chains for performance
- Type-safe API with autocomplete support

Performance targets:
- <2μs overhead for callback matching
- <5μs overhead for callback execution
- Pre-compilation at class definition time
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from foobara_py.core.state_machine import CommandState

if TYPE_CHECKING:
    from foobara_py.core.command import Command


@dataclass(frozen=True, slots=True)
class CallbackCondition:
    """
    Conditions for callback matching.

    Frozen dataclass for immutability and hashability (enables LRU caching).
    Uses __slots__ for minimal memory footprint.
    """

    from_state: Optional[CommandState] = None
    to_state: Optional[CommandState] = None
    transition: Optional[str] = None  # e.g., "execute", "validate"

    def matches(
        self,
        from_state: CommandState,
        to_state: CommandState,
        transition: str
    ) -> bool:
        """
        Check if this condition matches the transition.

        Returns True if all non-None conditions match.
        Uses fast None checks and early returns for performance.

        Args:
            from_state: The state being transitioned from
            to_state: The state being transitioned to
            transition: The transition name

        Returns:
            True if condition matches, False otherwise
        """
        if self.from_state is not None and self.from_state != from_state:
            return False
        if self.to_state is not None and self.to_state != to_state:
            return False
        if self.transition is not None and self.transition != transition:
            return False
        return True


@dataclass(slots=True)
class RegisteredCallback:
    """
    A registered callback with its conditions.

    Uses __slots__ for memory efficiency.
    Not frozen since we may want to adjust priority dynamically.
    """

    callback: Callable
    callback_type: str  # "before", "after", "around", "error"
    condition: CallbackCondition
    priority: int = 0  # Lower number = higher priority (executes earlier)

    def __lt__(self, other: "RegisteredCallback") -> bool:
        """Support sorting by priority."""
        return self.priority < other.priority


class EnhancedCallbackRegistry:
    """
    High-performance callback registry with conditional matching.

    Features:
    - Fast callback lookup using compiled chains
    - LRU cache for repeated lookups
    - Minimal overhead for common case (no callbacks)
    - Supports conditional filtering on state transitions

    Performance optimizations:
    - __slots__ for fast attribute access
    - Pre-compiled callback chains for common transitions
    - LRU cache for callback matching
    - Fast-path for "no callbacks" case
    """

    __slots__ = ("_callbacks", "_compiled_chains", "_cache_hits", "_cache_misses")

    def __init__(self):
        """Initialize empty registry."""
        # Store all registered callbacks
        self._callbacks: List[RegisteredCallback] = []

        # Pre-compiled chains for specific transitions
        # Key: (from_state, to_state, transition)
        # Value: {"before": [...], "after": [...], "around": [...], "error": [...]}
        self._compiled_chains: Dict[Tuple, Dict[str, List[Callable]]] = {}

        # Cache statistics (for profiling)
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    def register(
        self,
        callback_type: str,
        callback: Callable,
        from_state: Optional[CommandState] = None,
        to_state: Optional[CommandState] = None,
        transition: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        """
        Register a callback with conditions.

        Args:
            callback_type: Type of callback ("before", "after", "around", "error")
            callback: The callback function to execute
            from_state: Optional state to transition from
            to_state: Optional state to transition to
            transition: Optional transition name
            priority: Priority (lower = higher priority)
        """
        condition = CallbackCondition(
            from_state=from_state,
            to_state=to_state,
            transition=transition
        )

        registered = RegisteredCallback(
            callback=callback,
            callback_type=callback_type,
            condition=condition,
            priority=priority
        )

        self._callbacks.append(registered)
        # Keep callbacks sorted by priority for efficient execution
        self._callbacks.sort()

        # Clear caches when new callbacks are registered
        self.clear_cache()

    def get_callbacks(
        self,
        callback_type: str,
        from_state: CommandState,
        to_state: CommandState,
        transition: str
    ) -> List[Callable]:
        """
        Get matching callbacks for a transition.

        Uses compiled chains for performance when available.

        Args:
            callback_type: Type of callback to retrieve
            from_state: State transitioning from
            to_state: State transitioning to
            transition: Transition name

        Returns:
            List of matching callbacks in priority order
        """
        # Try compiled chain first (fastest path)
        cache_key = (from_state, to_state, transition)
        if cache_key in self._compiled_chains:
            self._cache_hits += 1
            return self._compiled_chains[cache_key].get(callback_type, [])

        # Cache miss - match callbacks manually
        self._cache_misses += 1

        matching: List[Callable] = []
        for registered in self._callbacks:
            if (registered.callback_type == callback_type and
                registered.condition.matches(from_state, to_state, transition)):
                matching.append(registered.callback)

        return matching

    def compile_chain(
        self,
        from_state: CommandState,
        to_state: CommandState,
        transition: str
    ) -> Dict[str, List[Callable]]:
        """
        Pre-compile callback chain for a specific transition.

        This is useful for hot paths - call this at class definition
        time for transitions that will happen frequently.

        Args:
            from_state: State transitioning from
            to_state: State transitioning to
            transition: Transition name

        Returns:
            Dictionary mapping callback types to callback lists
        """
        cache_key = (from_state, to_state, transition)

        # Return cached if available
        if cache_key in self._compiled_chains:
            return self._compiled_chains[cache_key]

        # Compile the chain
        chain: Dict[str, List[Callable]] = {
            "before": [],
            "after": [],
            "around": [],
            "error": []
        }

        for registered in self._callbacks:
            if registered.condition.matches(from_state, to_state, transition):
                chain[registered.callback_type].append(registered.callback)

        # Cache the compiled chain
        self._compiled_chains[cache_key] = chain
        return chain

    def clear_cache(self) -> None:
        """Clear compiled chains cache."""
        self._compiled_chains.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def precompile_common_transitions(self) -> None:
        """
        Pre-compile chains for common state transitions.

        Call this after all callbacks are registered to optimize
        hot paths in command execution.
        """
        # Common transitions in normal execution flow
        common_transitions = [
            (CommandState.INITIALIZED, CommandState.OPENING_TRANSACTION, "open_transaction"),
            (CommandState.OPENING_TRANSACTION, CommandState.CASTING_AND_VALIDATING_INPUTS, "cast_and_validate_inputs"),
            (CommandState.CASTING_AND_VALIDATING_INPUTS, CommandState.LOADING_RECORDS, "load_records"),
            (CommandState.LOADING_RECORDS, CommandState.VALIDATING_RECORDS, "validate_records"),
            (CommandState.VALIDATING_RECORDS, CommandState.VALIDATING, "validate"),
            (CommandState.VALIDATING, CommandState.EXECUTING, "execute"),
            (CommandState.EXECUTING, CommandState.COMMITTING_TRANSACTION, "commit_transaction"),
            (CommandState.COMMITTING_TRANSACTION, CommandState.SUCCEEDED, "succeed"),
        ]

        for from_state, to_state, transition in common_transitions:
            self.compile_chain(from_state, to_state, transition)

    def has_callbacks(self) -> bool:
        """Fast check if any callbacks are registered."""
        return bool(self._callbacks)

    def merge(self, other: "EnhancedCallbackRegistry") -> "EnhancedCallbackRegistry":
        """
        Merge another registry into a new registry (for inheritance).

        Args:
            other: Registry to merge with this one

        Returns:
            New merged registry with callbacks from both registries
        """
        merged = EnhancedCallbackRegistry()
        # Add callbacks from self (parent)
        merged._callbacks.extend(self._callbacks)
        # Add callbacks from other (child)
        merged._callbacks.extend(other._callbacks)
        # Sort by priority
        merged._callbacks.sort()
        # Clear cache so it gets rebuilt
        merged.clear_cache()
        return merged

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "total": total,
            "hit_rate": hit_rate,
            "compiled_chains": len(self._compiled_chains)
        }


class EnhancedCallbackExecutor:
    """
    Executes callbacks with around-callback support.

    Handles the full callback lifecycle:
    1. Before callbacks (in priority order)
    2. Around callbacks (nested, innermost calls action)
    3. Action execution
    4. After callbacks (in priority order)
    5. Error callbacks (on exception)

    Performance features:
    - Fast-path for no callbacks
    - Minimal overhead for callback execution
    - Support for error handling
    """

    __slots__ = ("_registry", "_command")

    def __init__(self, registry: EnhancedCallbackRegistry, command: "Command"):
        """
        Initialize executor.

        Args:
            registry: The callback registry to use
            command: The command instance being executed
        """
        self._registry = registry
        self._command = command

    def execute_transition(
        self,
        from_state: CommandState,
        to_state: CommandState,
        transition: str,
        action: Callable[[], Any]
    ) -> Any:
        """
        Execute action with before/after/around callbacks.

        Args:
            from_state: State transitioning from
            to_state: State transitioning to
            transition: Transition name
            action: The core action to execute

        Returns:
            Result of the action (or outermost around callback)

        Raises:
            Any exception from action or callbacks
        """
        # Fast path: no callbacks registered
        if not self._registry.has_callbacks():
            return action()

        # Get callbacks for this transition
        before_callbacks = self._registry.get_callbacks(
            "before", from_state, to_state, transition
        )
        after_callbacks = self._registry.get_callbacks(
            "after", from_state, to_state, transition
        )
        around_callbacks = self._registry.get_callbacks(
            "around", from_state, to_state, transition
        )
        error_callbacks = self._registry.get_callbacks(
            "error", from_state, to_state, transition
        )

        try:
            # Execute before callbacks
            for callback in before_callbacks:
                callback(self._command)

            # Build around callback chain
            if around_callbacks:
                # Nest around callbacks from outside to inside
                # Last callback in list is innermost (calls action directly)
                def build_chain(callbacks: List[Callable], core: Callable) -> Callable:
                    """Recursively build nested around callback chain."""
                    if not callbacks:
                        return core

                    def wrapped() -> Any:
                        # Current callback wraps the rest of the chain
                        return callbacks[0](
                            self._command,
                            build_chain(callbacks[1:], core)
                        )

                    return wrapped

                chained_action = build_chain(around_callbacks, action)
                result = chained_action()
            else:
                # No around callbacks, execute action directly
                result = action()

            # Execute after callbacks
            for callback in after_callbacks:
                callback(self._command)

            return result

        except Exception as e:
            # Execute error callbacks
            for callback in error_callbacks:
                callback(self._command, e)

            # Re-raise the exception
            raise

    def execute_simple(
        self,
        callback_type: str,
        from_state: CommandState,
        to_state: CommandState,
        transition: str
    ) -> None:
        """
        Execute simple callbacks (before/after/error) without an action.

        Useful for standalone callback execution.

        Args:
            callback_type: Type of callback to execute
            from_state: State transitioning from
            to_state: State transitioning to
            transition: Transition name
        """
        callbacks = self._registry.get_callbacks(
            callback_type, from_state, to_state, transition
        )

        for callback in callbacks:
            callback(self._command)