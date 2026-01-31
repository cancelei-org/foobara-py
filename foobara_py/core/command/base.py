"""
Command base class - orchestrator using modular concerns.

This module provides the main Command class built from focused concerns,
following the Ruby Foobara pattern of ~100-150 LOC concerns.

Architecture:
- TypesConcern: Type extraction and caching
- NamingConcern: Command naming and identification
- ErrorsConcern: Error handling and collection
- InputsConcern: Input validation
- ValidationConcern: Record loading and validation hooks
- ExecutionConcern: Core execution logic
- SubcommandConcern: Subcommand execution
- TransactionConcern: Transaction management
- StateConcern: State machine and flow
- MetadataConcern: Manifest and reflection
- CallbacksConcern: Ruby-like callback DSL
"""

from abc import ABC, ABCMeta
from typing import Any, ClassVar, Dict, Generic, Optional, Tuple, TypeVar

from pydantic import BaseModel

from foobara_py.core.callbacks import CallbackRegistry
from foobara_py.core.errors import ErrorCollection
from foobara_py.core.state_machine import CommandStateMachine

from .concerns import (
    CallbacksConcern,
    ErrorsConcern,
    ExecutionConcern,
    InputsConcern,
    MetadataConcern,
    NamingConcern,
    StateConcern,
    SubcommandConcern,
    TransactionConcern,
    TypesConcern,
    ValidationConcern,
)

InputT = TypeVar("InputT", bound=BaseModel)
ResultT = TypeVar("ResultT")


class CommandMeta(ABCMeta):
    """
    Metaclass for Command classes.

    Handles:
    - Callback registration from decorated methods
    - Input/Result type extraction and caching
    - Inheritance of callbacks from parent classes

    Inherits from ABCMeta to support ABC (abstract base class) features.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: dict, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace)

        # Initialize callback registry
        if not hasattr(cls, "_callback_registry") or cls._callback_registry is None:
            cls._callback_registry = CallbackRegistry()

        # Initialize enhanced callback registry
        if not hasattr(cls, "_enhanced_callback_registry") or cls._enhanced_callback_registry is None:
            from foobara_py.core.callbacks_enhanced import EnhancedCallbackRegistry
            cls._enhanced_callback_registry = EnhancedCallbackRegistry()

        # Inherit callbacks from parent
        for base in bases:
            if hasattr(base, "_callback_registry") and base._callback_registry:
                cls._callback_registry = base._callback_registry.merge(cls._callback_registry)
            if hasattr(base, "_enhanced_callback_registry") and base._enhanced_callback_registry:
                cls._enhanced_callback_registry = base._enhanced_callback_registry.merge(cls._enhanced_callback_registry)

        # Register callbacks from decorated methods
        for attr_name, attr_value in namespace.items():
            if hasattr(attr_value, "_callbacks"):
                for phase, callback_type, priority in attr_value._callbacks:
                    cls._callback_registry.register(phase, callback_type, attr_value, priority)

        # Extract and cache type parameters
        cls._cached_inputs_type = None
        cls._cached_result_type = None

        # Detect hook overrides for performance optimization
        # Check if before_execute is overridden from base ExecutionConcern
        from foobara_py.core.command.concerns.execution_concern import ExecutionConcern
        cls._has_before_execute = (
            'before_execute' in namespace or
            any(hasattr(base, 'before_execute') and
                getattr(base, 'before_execute', None) is not ExecutionConcern.before_execute
                for base in bases if base is not ExecutionConcern)
        )

        # Check if after_execute is overridden from base ExecutionConcern
        cls._has_after_execute = (
            'after_execute' in namespace or
            any(hasattr(base, 'after_execute') and
                getattr(base, 'after_execute', None) is not ExecutionConcern.after_execute
                for base in bases if base is not ExecutionConcern)
        )

        # Check if any callbacks are registered
        cls._has_callbacks = cls._callback_registry and cls._callback_registry.has_any_callbacks()

        # Pre-compile callback chains for faster execution (cache at class level)
        if cls._has_callbacks:
            cls._callback_registry.precompile_chains()

        return cls


class Command(
    ABC,
    Generic[InputT, ResultT],
    TypesConcern,
    NamingConcern,
    ErrorsConcern,
    InputsConcern[InputT],
    ValidationConcern,
    ExecutionConcern[ResultT],
    SubcommandConcern,
    TransactionConcern,
    StateConcern,
    MetadataConcern,
    CallbacksConcern,
    metaclass=CommandMeta,
):
    """
    High-performance Command base class with full Ruby Foobara parity.

    Built from modular concerns (~100-150 LOC each):
    - TypesConcern: Type handling
    - NamingConcern: Naming and identification
    - ErrorsConcern: Error handling
    - InputsConcern: Input validation
    - ValidationConcern: Record validation
    - ExecutionConcern: Core execution
    - SubcommandConcern: Subcommand support
    - TransactionConcern: Transactions
    - StateConcern: State machine
    - MetadataConcern: Reflection
    - CallbacksConcern: Ruby-like callback DSL

    Implements complete 8-state execution flow:
    1. open_transaction - Begin database transaction
    2. cast_and_validate_inputs - Validate inputs via Pydantic
    3. load_records - Load entity records from database
    4. validate_records - Validate loaded records exist
    5. validate - Custom validation hook
    6. execute - Core business logic
    7. commit_transaction - Commit transaction
    8. succeed/fail/error - Terminal states

    Usage:
        class CreateUserInputs(BaseModel):
            name: str
            email: str

        class User(BaseModel):
            id: int
            name: str
            email: str

        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                return User(id=1, name=self.inputs.name, email=self.inputs.email)

        outcome = CreateUser.run(name="John", email="john@example.com")
    """

    # Class-level configuration (inherited from concerns, declared here for clarity)
    _domain: ClassVar[Optional[str]] = None
    _organization: ClassVar[Optional[str]] = None
    _description: ClassVar[Optional[str]] = None
    _depends_on: ClassVar[Tuple[str, ...]] = ()
    _possible_errors: ClassVar[Dict[str, Dict]] = {}
    _callback_registry: ClassVar[Optional[CallbackRegistry]] = None
    _enhanced_callback_registry: ClassVar[Optional["EnhancedCallbackRegistry"]] = None
    _cached_inputs_type: ClassVar[Optional[type[BaseModel]]] = None
    _cached_result_type: ClassVar[Optional[type]] = None
    _has_before_execute: ClassVar[bool] = False
    _has_after_execute: ClassVar[bool] = False
    _has_callbacks: ClassVar[bool] = False

    # Instance attributes (using __slots__ for performance)
    __slots__ = (
        "_raw_inputs",
        "_inputs",
        "_errors",
        "_result",
        "_outcome",
        "_state_machine",
        "_transaction",
        "_subcommand_runtime_path",
        "_loaded_records",
        "_callback_executor",
        "_enhanced_callback_executor",
    )

    def __init_subclass__(cls, **kwargs):
        """
        Normalize _possible_errors format.

        Supports both dict and list of tuples formats:
        - Dict: {"symbol": {"message": "...", "context": {...}}}
        - List: [("symbol", "message"), ...]
        """
        super().__init_subclass__(**kwargs)

        # Convert list format to dict format
        if isinstance(cls._possible_errors, list):
            normalized = {}
            for item in cls._possible_errors:
                if isinstance(item, tuple) and len(item) >= 2:
                    symbol, message = item[0], item[1]
                    normalized[symbol] = {"symbol": symbol, "message": message, "context": {}}
            cls._possible_errors = normalized

    def __init__(self, _runtime_path: Tuple[str, ...] = (), **inputs):
        """
        Initialize command with inputs.

        Args:
            _runtime_path: Internal - path through parent commands (for subcommands)
            **inputs: Command inputs
        """
        self._raw_inputs: Dict[str, Any] = inputs
        self._inputs: Optional[InputT] = None
        self._errors: ErrorCollection = ErrorCollection()
        self._result: Optional[ResultT] = None
        self._outcome: Optional["CommandOutcome[ResultT]"] = None
        self._state_machine: CommandStateMachine = CommandStateMachine()
        self._transaction: Optional["TransactionContext"] = None
        self._subcommand_runtime_path: Tuple[str, ...] = _runtime_path
        self._loaded_records: Dict[str, Any] = {}
        self._callback_executor: Optional["CallbackExecutor"] = None
        self._enhanced_callback_executor: Optional["EnhancedCallbackExecutor"] = None


# Import here to avoid circular dependency
from foobara_py.core.outcome import CommandOutcome
from foobara_py.core.transactions import TransactionContext, TransactionConfig
from foobara_py.core.callbacks import CallbackExecutor
from foobara_py.core.callbacks_enhanced import EnhancedCallbackExecutor

# Ensure TransactionConfig is available
Command._transaction_config = TransactionConfig()
