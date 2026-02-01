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

from foobara_py.core.callbacks_enhanced import EnhancedCallbackRegistry
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
        """
        Create a new Command class with enhanced callback support and type caching.

        This metaclass performs three critical initialization tasks:
        1. Callback Registry Setup: Ensures each Command class has its own callback registry
           for managing before/after/around/error callbacks on state transitions.

        2. Callback Inheritance: Merges parent class callbacks with child class callbacks,
           maintaining proper inheritance hierarchy and callback priority ordering.

        3. Type Cache Initialization: Prepares class-level cache for Input and Result type
           extraction, enabling fast type lookups without repeated generic inspection.

        Args:
            name: Name of the class being created
            bases: Tuple of base classes
            namespace: Class namespace dictionary
            **kwargs: Additional metaclass arguments

        Returns:
            Newly created Command class with initialized callback system
        """
        cls = super().__new__(mcs, name, bases, namespace)

        # Initialize enhanced callback registry
        if not hasattr(cls, "_enhanced_callback_registry") or cls._enhanced_callback_registry is None:
            cls._enhanced_callback_registry = EnhancedCallbackRegistry()

        # Inherit callbacks from parent
        for base in bases:
            if hasattr(base, "_enhanced_callback_registry") and base._enhanced_callback_registry:
                cls._enhanced_callback_registry = base._enhanced_callback_registry.merge(cls._enhanced_callback_registry)

        # Extract and cache type parameters
        cls._cached_inputs_type = None
        cls._cached_result_type = None

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
    _enhanced_callback_registry: ClassVar[Optional["EnhancedCallbackRegistry"]] = None
    _cached_inputs_type: ClassVar[Optional[type[BaseModel]]] = None
    _cached_result_type: ClassVar[Optional[type]] = None

    # Instance attributes (using __slots__ for performance)
    __slots__ = (
        "_raw_inputs",                    # Dict[str, Any]: Original unvalidated input kwargs
        "_inputs",                        # Optional[InputT]: Validated Pydantic input model instance
        "_errors",                        # ErrorCollection: Accumulated validation and execution errors
        "_result",                        # Optional[ResultT]: Command execution result
        "_outcome",                       # Optional[CommandOutcome]: Success/failure outcome with result or errors
        "_state_machine",                 # CommandStateMachine: 8-state execution flow state tracker
        "_transaction",                   # Optional[TransactionContext]: Database transaction context manager
        "_subcommand_runtime_path",       # Tuple[str, ...]: Parent command chain for nested execution
        "_loaded_records",                # Dict[str, Any]: Entity records loaded during load_records phase
        "_enhanced_callback_executor",    # Optional[EnhancedCallbackExecutor]: Callback execution engine
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
            normalized_errors = {}
            for error_item in cls._possible_errors:
                is_valid_tuple = isinstance(error_item, tuple) and len(error_item) >= 2
                if is_valid_tuple:
                    error_symbol = error_item[0]
                    error_message = error_item[1]
                    error_entry = {"symbol": error_symbol, "message": error_message, "context": {}}
                    normalized_errors[error_symbol] = error_entry
            cls._possible_errors = normalized_errors

    def __init__(self, _runtime_path: Tuple[str, ...] = (), **inputs):
        """
        Initialize command with inputs.

        Args:
            _runtime_path: Internal parameter for tracking command execution hierarchy.
                          When a command runs as a subcommand of another command,
                          this tuple contains the chain of parent command names,
                          enabling proper error context and debugging information.
                          Example: ("ParentCommand", "ChildCommand") indicates this
                          command was invoked by ChildCommand which was invoked by ParentCommand.
                          Empty tuple () for top-level command execution.
            **inputs: Command inputs to be validated against the InputT type
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
        self._enhanced_callback_executor: Optional["EnhancedCallbackExecutor"] = None


# Import here to avoid circular dependency
from foobara_py.core.outcome import CommandOutcome
from foobara_py.core.transactions import TransactionContext, TransactionConfig
from foobara_py.core.callbacks_enhanced import EnhancedCallbackExecutor

# Ensure TransactionConfig is available
Command._transaction_config = TransactionConfig()
