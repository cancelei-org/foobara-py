"""
Callback system for command lifecycle hooks.

Implements Ruby Foobara's before/after/around callback pattern.
Uses descriptors and class-level storage for performance.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from foobara_py.core.command import Command


class CallbackPhase(Enum):
    """Phases where callbacks can be registered"""

    OPEN_TRANSACTION = "open_transaction"
    CAST_AND_VALIDATE_INPUTS = "cast_and_validate_inputs"
    LOAD_RECORDS = "load_records"
    VALIDATE_RECORDS = "validate_records"
    VALIDATE = "validate"
    EXECUTE = "execute"
    COMMIT_TRANSACTION = "commit_transaction"


class CallbackType(Enum):
    """Types of callbacks"""

    BEFORE = "before"
    AFTER = "after"
    AROUND = "around"


@dataclass(slots=True)
class Callback:
    """
    Represents a registered callback.

    Using slots and dataclass for memory efficiency.
    """

    phase: CallbackPhase
    callback_type: CallbackType
    handler: Callable
    priority: int = 100  # Lower = earlier execution

    def __lt__(self, other: "Callback") -> bool:
        return self.priority < other.priority


class CallbackRegistry:
    """
    Registry for command callbacks.

    Stored at class level for inheritance support.
    Uses tuple storage for immutability and cache-friendliness.
    """

    __slots__ = ("_callbacks", "_compiled_chains", "_has_any")

    def __init__(self):
        self._callbacks: Dict[CallbackPhase, Dict[CallbackType, List[Callback]]] = {
            phase: {ct: [] for ct in CallbackType} for phase in CallbackPhase
        }
        self._compiled_chains: Optional[Dict[CallbackPhase, Dict[str, Any]]] = None
        self._has_any: Optional[bool] = None

    def register(
        self,
        phase: CallbackPhase,
        callback_type: CallbackType,
        handler: Callable,
        priority: int = 100,
    ) -> None:
        """Register a callback"""
        callback = Callback(
            phase=phase, callback_type=callback_type, handler=handler, priority=priority
        )
        self._callbacks[phase][callback_type].append(callback)
        # Keep sorted by priority
        self._callbacks[phase][callback_type].sort()
        # Invalidate cache when callbacks are registered
        self._has_any = None
        self._compiled_chains = None

    def get_callbacks(self, phase: CallbackPhase, callback_type: CallbackType) -> List[Callback]:
        """Get callbacks for phase and type"""
        return self._callbacks[phase][callback_type]

    def merge(self, other: "CallbackRegistry") -> "CallbackRegistry":
        """Merge another registry (for inheritance)"""
        merged = CallbackRegistry()
        for phase in CallbackPhase:
            for ct in CallbackType:
                merged._callbacks[phase][ct] = (
                    self._callbacks[phase][ct] + other._callbacks[phase][ct]
                )
                merged._callbacks[phase][ct].sort()
        return merged

    def copy(self) -> "CallbackRegistry":
        """Create a copy of this registry"""
        new_registry = CallbackRegistry()
        for phase in CallbackPhase:
            for ct in CallbackType:
                new_registry._callbacks[phase][ct] = list(self._callbacks[phase][ct])
        return new_registry

    def has_any_callbacks(self) -> bool:
        """Check if any callbacks are registered (cached for performance)"""
        if self._has_any is None:
            self._has_any = False
            for phase in CallbackPhase:
                for ct in CallbackType:
                    if self._callbacks[phase][ct]:
                        self._has_any = True
                        break
                if self._has_any:
                    break
        return self._has_any

    def precompile_chains(self) -> None:
        """Pre-compile callback chains for faster execution"""
        if self._compiled_chains is not None:
            return  # Already compiled

        self._compiled_chains = {}
        for phase in CallbackPhase:
            # Pre-compile which callback types have callbacks for this phase
            self._compiled_chains[phase] = {
                'has_before': bool(self._callbacks[phase][CallbackType.BEFORE]),
                'has_after': bool(self._callbacks[phase][CallbackType.AFTER]),
                'has_around': bool(self._callbacks[phase][CallbackType.AROUND]),
            }


class CallbackExecutor:
    """
    Executes callbacks for a command instance.

    Handles before/after/around callback chains efficiently.
    """

    __slots__ = ("_registry", "_command")

    def __init__(self, registry: CallbackRegistry, command: "Command"):
        self._registry = registry
        self._command = command

    def execute_phase(self, phase: CallbackPhase, core_action: Callable[[], Any]) -> Any:
        """
        Execute a phase with all its callbacks.

        1. Run before callbacks
        2. Run around callbacks wrapping core action
        3. Run core action
        4. Run after callbacks
        """
        # Fast path: Check if phase has any callbacks using pre-compiled chains
        if self._registry._compiled_chains:
            phase_info = self._registry._compiled_chains.get(phase, {})
            if not (phase_info.get('has_before') or phase_info.get('has_after') or phase_info.get('has_around')):
                # No callbacks for this phase, execute directly
                return core_action()

        # Before callbacks
        before_callbacks = self._registry.get_callbacks(phase, CallbackType.BEFORE)
        if before_callbacks:
            for callback in before_callbacks:
                callback.handler(self._command)

        # Build around chain
        around_callbacks = self._registry.get_callbacks(phase, CallbackType.AROUND)

        if around_callbacks:
            def build_chain(callbacks: List[Callback], action: Callable) -> Callable:
                """Build nested around callback chain"""
                if not callbacks:
                    return action

                def wrapped():
                    return callbacks[0].handler(
                        self._command, lambda: build_chain(callbacks[1:], action)()
                    )

                return wrapped

            # Execute with around callbacks
            chained_action = build_chain(around_callbacks, core_action)
            result = chained_action()
        else:
            # No around callbacks, execute directly
            result = core_action()

        # After callbacks
        after_callbacks = self._registry.get_callbacks(phase, CallbackType.AFTER)
        if after_callbacks:
            for callback in after_callbacks:
                callback.handler(self._command)

        return result


# Decorator factories for registering callbacks


def before(phase: CallbackPhase, priority: int = 100):
    """
    Decorator to register a before callback.

    Usage:
        class MyCommand(Command):
            @before(CallbackPhase.VALIDATE)
            def check_permissions(self):
                if not self.inputs.user.can_edit:
                    self.add_runtime_error("not_allowed", "No permission")
    """

    def decorator(method: Callable) -> Callable:
        if not hasattr(method, "_callbacks"):
            method._callbacks = []
        method._callbacks.append((phase, CallbackType.BEFORE, priority))
        return method

    return decorator


def after(phase: CallbackPhase, priority: int = 100):
    """
    Decorator to register an after callback.

    Usage:
        class MyCommand(Command):
            @after(CallbackPhase.EXECUTE)
            def log_result(self):
                logger.info(f"Executed {self.__class__.__name__}")
    """

    def decorator(method: Callable) -> Callable:
        if not hasattr(method, "_callbacks"):
            method._callbacks = []
        method._callbacks.append((phase, CallbackType.AFTER, priority))
        return method

    return decorator


def around(phase: CallbackPhase, priority: int = 100):
    """
    Decorator to register an around callback.

    Usage:
        class MyCommand(Command):
            @around(CallbackPhase.EXECUTE)
            def with_timing(self, proceed):
                start = time.time()
                result = proceed()
                elapsed = time.time() - start
                logger.info(f"Took {elapsed:.2f}s")
                return result
    """

    def decorator(method: Callable) -> Callable:
        if not hasattr(method, "_callbacks"):
            method._callbacks = []
        method._callbacks.append((phase, CallbackType.AROUND, priority))
        return method

    return decorator


# Convenience decorators for common phases


def before_validate(priority: int = 100):
    """Shortcut for @before(CallbackPhase.VALIDATE)"""
    return before(CallbackPhase.VALIDATE, priority)


def after_validate(priority: int = 100):
    """Shortcut for @after(CallbackPhase.VALIDATE)"""
    return after(CallbackPhase.VALIDATE, priority)


def before_execute(priority: int = 100):
    """Shortcut for @before(CallbackPhase.EXECUTE)"""
    return before(CallbackPhase.EXECUTE, priority)


def after_execute(priority: int = 100):
    """Shortcut for @after(CallbackPhase.EXECUTE)"""
    return after(CallbackPhase.EXECUTE, priority)


def around_execute(priority: int = 100):
    """Shortcut for @around(CallbackPhase.EXECUTE)"""
    return around(CallbackPhase.EXECUTE, priority)


def before_load_records(priority: int = 100):
    """Shortcut for @before(CallbackPhase.LOAD_RECORDS)"""
    return before(CallbackPhase.LOAD_RECORDS, priority)


def after_load_records(priority: int = 100):
    """Shortcut for @after(CallbackPhase.LOAD_RECORDS)"""
    return after(CallbackPhase.LOAD_RECORDS, priority)
