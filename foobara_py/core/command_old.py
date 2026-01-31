"""
High-performance Command base class with full Ruby Foobara parity.

Features:
- Full 8-state execution flow
- Lifecycle callbacks (before/after/around)
- Subcommand execution with error propagation
- Transaction management
- Domain dependencies
- Entity loading
- Performance optimized with __slots__
"""

import inspect
import weakref
from abc import ABC, ABCMeta, abstractmethod
from functools import lru_cache
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel, ValidationError

from foobara_py.core.callbacks import (
    CallbackExecutor,
    CallbackPhase,
    CallbackRegistry,
    CallbackType,
)
from foobara_py.core.errors import ErrorCollection, FoobaraError, Symbols
from foobara_py.core.state_machine import STATE_NAMES, CommandState, CommandStateMachine, Halt
from foobara_py.core.transactions import (
    NoOpTransactionHandler,
    TransactionConfig,
    TransactionContext,
    TransactionRegistry,
    get_current_transaction,
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

        # Inherit callbacks from parent
        for base in bases:
            if hasattr(base, "_callback_registry") and base._callback_registry:
                cls._callback_registry = base._callback_registry.merge(cls._callback_registry)

        # Register callbacks from decorated methods
        for attr_name, attr_value in namespace.items():
            if hasattr(attr_value, "_callbacks"):
                for phase, callback_type, priority in attr_value._callbacks:
                    cls._callback_registry.register(phase, callback_type, attr_value, priority)

        # Extract and cache type parameters
        cls._cached_inputs_type = None
        cls._cached_result_type = None

        return cls


class Command(ABC, Generic[InputT, ResultT], metaclass=CommandMeta):
    """
    High-performance Command base class with full Ruby Foobara parity.

    Implements complete 8-state execution flow:
    1. open_transaction - Begin database transaction
    2. cast_and_validate_inputs - Validate inputs via Pydantic
    3. load_records - Load entity records from database
    4. validate_records - Validate loaded records exist
    5. validate - Custom validation hook
    6. execute - Core business logic
    7. commit_transaction - Commit transaction
    8. succeed/fail/error - Terminal states

    Supports:
    - Lifecycle callbacks (before/after/around for each phase)
    - Subcommand execution with automatic error propagation
    - Transaction management (auto or explicit)
    - Domain dependencies validation
    - Entity loading declarations

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

    # Class-level configuration (can be overridden in subclasses)
    _domain: ClassVar[Optional[str]] = None
    _organization: ClassVar[Optional[str]] = None
    _description: ClassVar[Optional[str]] = None
    _depends_on: ClassVar[Tuple[str, ...]] = ()
    _possible_errors: ClassVar[Dict[str, Dict]] = {}
    _transaction_config: ClassVar[TransactionConfig] = TransactionConfig()
    _callback_registry: ClassVar[Optional[CallbackRegistry]] = None

    # Type caching
    _cached_inputs_type: ClassVar[Optional[Type[BaseModel]]] = None
    _cached_result_type: ClassVar[Optional[Type]] = None

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
        self._transaction: Optional[TransactionContext] = None
        self._subcommand_runtime_path: Tuple[str, ...] = _runtime_path
        self._loaded_records: Dict[str, Any] = {}
        self._callback_executor: Optional[CallbackExecutor] = None

    # ==================== Properties ====================

    @property
    def inputs(self) -> InputT:
        """Get validated inputs (raises if not yet validated)"""
        if self._inputs is None:
            raise ValueError("Inputs not yet validated")
        return self._inputs

    @property
    def errors(self) -> ErrorCollection:
        """Get error collection"""
        return self._errors

    @property
    def state(self) -> CommandState:
        """Get current execution state"""
        return self._state_machine.state

    @property
    def state_name(self) -> str:
        """Get current state name"""
        return STATE_NAMES[self._state_machine.state]

    # ==================== Type Extraction ====================

    @classmethod
    def inputs_type(cls) -> Type[InputT]:
        """Get the inputs Pydantic model class (cached)"""
        if cls._cached_inputs_type is not None:
            return cls._cached_inputs_type

        # Extract from Generic parameters
        for base in getattr(cls, "__orig_bases__", []):
            origin = get_origin(base)
            if origin is Command or (isinstance(origin, type) and issubclass(origin, Command)):
                args = get_args(base)
                if args and len(args) >= 1:
                    inputs_cls = args[0]
                    if isinstance(inputs_cls, type) and issubclass(inputs_cls, BaseModel):
                        cls._cached_inputs_type = inputs_cls
                        return inputs_cls

        raise TypeError(f"Could not determine inputs type for {cls.__name__}")

    @classmethod
    def result_type(cls) -> Type[ResultT]:
        """Get the result type (cached)"""
        if cls._cached_result_type is not None:
            return cls._cached_result_type

        for base in getattr(cls, "__orig_bases__", []):
            origin = get_origin(base)
            if origin is Command or (isinstance(origin, type) and issubclass(origin, Command)):
                args = get_args(base)
                if args and len(args) >= 2:
                    cls._cached_result_type = args[1]
                    return args[1]

        cls._cached_result_type = Any
        return Any

    @classmethod
    def inputs_schema(cls) -> dict:
        """Get JSON Schema for inputs (for MCP integration)"""
        return cls.inputs_type().model_json_schema()

    # ==================== Naming ====================

    @classmethod
    def full_name(cls) -> str:
        """Get fully qualified command name (Organization::Domain::Command)"""
        parts = []
        if cls._organization:
            parts.append(cls._organization)
        if cls._domain:
            parts.append(cls._domain)
        parts.append(cls.__name__)
        return "::".join(parts)

    @classmethod
    def full_command_symbol(cls) -> str:
        """Get command symbol (snake_case full name)"""
        return cls.full_name().replace("::", "_").lower()

    @classmethod
    def description(cls) -> str:
        """Get command description"""
        if cls._description:
            return cls._description
        return cls.__doc__ or ""

    # ==================== Error Handling ====================

    def add_error(self, error: FoobaraError) -> None:
        """Add an error to the collection"""
        # Add runtime path prefix if we're a subcommand
        if self._subcommand_runtime_path:
            error = error.with_runtime_path_prefix(*self._subcommand_runtime_path)
        self._errors.add(error)

    def add_input_error(
        self, path: Union[List[str], Tuple[str, ...]], symbol: str, message: str, **context
    ) -> None:
        """Add an input validation error"""
        self.add_error(FoobaraError.data_error(symbol, path, message, **context))

    def add_runtime_error(self, symbol: str, message: str, halt: bool = True, **context) -> None:
        """Add a runtime error, optionally halting execution"""
        self.add_error(FoobaraError.runtime_error(symbol, message, **context))
        if halt:
            raise Halt()

    def halt(self) -> None:
        """Halt command execution (transitions to failed state)"""
        raise Halt()

    # ==================== Subcommand Execution ====================

    def run_subcommand(
        self, command_class: Type["Command[Any, Any]"], **inputs
    ) -> Any:
        """
        Run a subcommand and return its result.

        Propagates errors from subcommand to parent command.
        Returns None if the subcommand fails.

        Validates domain dependencies before execution.

        Raises:
            DomainDependencyError: If cross-domain call is not allowed
        """
        # Validate domain dependencies
        self._validate_cross_domain_call(command_class)

        # Create subcommand with runtime path
        runtime_path = self._subcommand_runtime_path + (self.full_command_symbol(),)
        subcommand = command_class(_runtime_path=runtime_path, **inputs)
        outcome = subcommand.run_instance()

        if outcome.is_failure():
            # Propagate errors from subcommand with context
            for error in outcome.errors:
                # Add subcommand name to error context
                error_with_context = FoobaraError(
                    category=error.category,
                    symbol=error.symbol,
                    path=error.path,
                    message=error.message,
                    context={**error.context, "subcommand": command_class.__name__},
                    runtime_path=error.runtime_path,
                    is_fatal=error.is_fatal,
                )
                self._errors.add(error_with_context)
            return None

        return outcome.result

    def run_subcommand_bang(self, command_class: Type["Command[Any, Any]"], **inputs) -> Any:
        """
        Run a subcommand, halting on failure.

        Similar to Ruby's run_subcommand!
        Returns result on success, raises Halt on failure (errors already propagated).
        """
        result = self.run_subcommand(command_class, **inputs)

        if result is None and self._errors.has_errors():
            # Subcommand failed, errors already propagated by run_subcommand
            raise Halt()

        return result

    # Alias for Ruby-like syntax
    run_subcommand_ = run_subcommand_bang

    def _validate_cross_domain_call(self, target_command: Type["Command"]) -> None:
        """
        Validate that calling target_command from this command is allowed per domain dependencies.

        Raises:
            DomainDependencyError: If the cross-domain call is not allowed
        """
        # Get domain information
        source_domain = getattr(self.__class__, "_domain", None)
        target_domain = getattr(target_command, "_domain", None)

        # If either command has no domain, allow (global domain)
        if not source_domain or not target_domain:
            return

        # If same domain, always allow
        if source_domain == target_domain:
            return

        # Import here to avoid circular dependency
        from foobara_py.domain.domain import Domain, DomainDependencyError

        # Get the source domain object
        with Domain._lock:
            domain_obj = Domain._registry.get(source_domain)

        if not domain_obj:
            # Domain not registered, allow (lenient mode)
            return

        # Validate using domain's can_call_from logic
        if not domain_obj.can_call_from(target_domain):
            raise DomainDependencyError(
                f"Domain '{source_domain}' cannot call commands from '{target_domain}'. "
                f"Add '{target_domain}' to {source_domain}.depends_on() or use GlobalDomain."
            )

        # Track the cross-domain call for observability
        if source_domain != target_domain:
            Domain.track_cross_domain_call(source_domain, target_domain)

    def run_mapped_subcommand(
        self,
        command_class: Type["Command[Any, Any]"],
        unmapped_inputs: Dict[str, Any] = None,
        to: Type = None,
        **extra_inputs,
    ) -> Any:
        """
        Run a subcommand with automatic domain mapping.

        Automatically finds and applies domain mappers to:
        1. Transform unmapped_inputs to the subcommand's input type
        2. Transform the subcommand's result to the target 'to' type

        Args:
            command_class: The subcommand to run
            unmapped_inputs: Inputs to map before passing to subcommand
            to: Optional target type for result mapping
            **extra_inputs: Additional inputs to pass directly (not mapped)

        Returns:
            The mapped result value

        Raises:
            Halt: If mapping fails or subcommand fails

        Usage:
            # Map inputs and result
            result = self.run_mapped_subcommand(
                ExternalServiceCommand,
                unmapped_inputs={"user": internal_user},
                to=ExternalUser
            )
        """
        from foobara_py.domain.domain import Domain
        from foobara_py.domain.domain_mapper import DomainMapperRegistry

        if unmapped_inputs is None:
            unmapped_inputs = {}

        mapped_something = False
        final_inputs = unmapped_inputs.copy()
        final_inputs.update(extra_inputs)

        # Get the command's domain for mapper lookup
        domain = Domain.find_domain_for_command(self.__class__)

        # Try to find mapper for inputs
        if unmapped_inputs:
            inputs_type = command_class.inputs_type()

            # First try to map the whole inputs dict
            inputs_mapper = None
            if domain:
                inputs_mapper = DomainMapperRegistry.find_matching_mapper(
                    unmapped_inputs, inputs_type, domain=domain.name
                )
            if not inputs_mapper:
                inputs_mapper = DomainMapperRegistry.find_matching_mapper(
                    unmapped_inputs, inputs_type
                )

            if inputs_mapper:
                mapped_something = True
                mapped_inputs = inputs_mapper.map_value(unmapped_inputs)

                if isinstance(mapped_inputs, dict):
                    final_inputs = {**mapped_inputs, **extra_inputs}
                else:
                    if hasattr(mapped_inputs, "model_dump"):
                        final_inputs = {**mapped_inputs.model_dump(), **extra_inputs}
                    else:
                        final_inputs = mapped_inputs
            else:
                # If whole dict can't be mapped, try mapping individual values
                # Get expected input types from the Pydantic model
                inputs_schema = inputs_type.model_fields
                mapped_inputs = {}

                for key, value in unmapped_inputs.items():
                    # Get the expected type for this field
                    field_info = inputs_schema.get(key)
                    if field_info:
                        expected_type = field_info.annotation

                        # Try to find a mapper for this specific value
                        value_mapper = None
                        if domain:
                            value_mapper = DomainMapperRegistry.find_matching_mapper(
                                value, expected_type, domain=domain.name
                            )
                        if not value_mapper:
                            value_mapper = DomainMapperRegistry.find_matching_mapper(
                                value, expected_type
                            )

                        if value_mapper:
                            mapped_something = True
                            mapped_inputs[key] = value_mapper.map_value(value)
                        else:
                            mapped_inputs[key] = value
                    else:
                        mapped_inputs[key] = value

                final_inputs = {**mapped_inputs, **extra_inputs}

        # Run the subcommand
        result = self.run_subcommand_bang(command_class, **final_inputs)

        # Try to find mapper for result
        if to is not None:
            result_mapper = None

            if domain:
                result_mapper = DomainMapperRegistry.find_matching_mapper(
                    result, to, domain=domain.name
                )

            if not result_mapper:
                result_mapper = DomainMapperRegistry.find_matching_mapper(result, to)

            if result_mapper:
                mapped_something = True
                result = result_mapper.map_value(result)

        if not mapped_something:
            # No mapping occurred - add runtime error
            self.add_runtime_error(
                "no_domain_mapper_found",
                f"No domain mapper found for {command_class.full_name()}",
                halt=True,
                subcommand=command_class.full_name(),
                to=str(to) if to else None,
            )

        return result

    # ==================== Lifecycle Methods ====================

    def open_transaction(self) -> None:
        """Open database transaction (override for custom behavior)"""
        if self._transaction_config.enabled:
            handler = None
            if self._transaction_config.handler_factory:
                handler = self._transaction_config.handler_factory()
            elif self._transaction_config.auto_detect:
                handler = TransactionRegistry.detect()

            if handler:
                self._transaction = TransactionContext(handler)
                self._transaction.__enter__()

    def cast_and_validate_inputs(self) -> None:
        """
        Cast and validate raw inputs using Pydantic model.

        Converts raw input dictionary to a strongly-typed Pydantic model instance,
        performing type coercion and validation. Validation errors are collected
        and added to the command's error list rather than raising exceptions.

        Raises:
            Halt: If validation errors occur (via add_error with halt=True)

        Note:
            Runs automatically during command execution before execute().
            Override inputs_type() to customize the validation model.
        """
        try:
            inputs_class = self.inputs_type()
            self._inputs = inputs_class(**self._raw_inputs)
        except ValidationError as e:
            for error in e.errors():
                path = tuple(str(p) for p in error["loc"])
                self.add_error(
                    FoobaraError(
                        category="data",
                        symbol=error["type"],
                        path=path,
                        message=error["msg"],
                        context={"input": error.get("input")},
                    )
                )

    def load_records(self) -> None:
        """
        Load entity records from the database.

        Automatically loads entities specified in LoadSpec declarations into
        command instance variables. Entities are fetched from their repositories
        using primary keys from validated inputs.

        Example:
            class UpdateUser(Command[UpdateUserInputs, User]):
                user: Loaded[User]  # Auto-loaded from inputs.user_id

                def execute(self) -> User:
                    # self.user is already loaded and available
                    self.user.name = self.inputs.name
                    return self.user.save()

        Note:
            Runs automatically after cast_and_validate_inputs().
            Override for custom loading logic or to load from multiple sources.
        """
        # Process _loads declarations
        loads = getattr(self.__class__, "_loads", None)
        if not loads:
            return

        for load_spec in loads:
            # Get the primary key from inputs
            input_value = getattr(self.inputs, load_spec.from_input, None)
            if input_value is None:
                if load_spec.required:
                    self.add_input_error(
                        (load_spec.from_input,),
                        "not_found",
                        f"{load_spec.entity_class.__name__} not found",
                    )
                continue

            # Load the entity
            entity = load_spec.entity_class.find(input_value)

            if entity is None:
                if load_spec.required:
                    self.add_input_error(
                        (load_spec.from_input,),
                        "not_found",
                        f"{load_spec.entity_class.__name__} with id {input_value} not found",
                    )
                else:
                    setattr(self, load_spec.into, None)
            else:
                setattr(self, load_spec.into, entity)

    def validate_records(self) -> None:
        """
        Validate that loaded entity records exist and are accessible.

        Override this method to verify loaded entities meet existence requirements,
        permissions checks, or state validations before execute() runs.

        Example:
            def validate_records(self) -> None:
                if not self.user.is_active:
                    self.add_runtime_error('inactive_user', 'User is inactive')

        Raises:
            Halt: If validation errors occur (via add_error with halt=True)

        Note:
            Runs automatically after load_records().
        """
        pass

    def validate(self) -> None:
        """
        Custom business logic validation hook.

        Override this method to implement domain-specific validation rules that
        go beyond input type checking. Use this for cross-field validations,
        business rule checks, or invariant enforcement.

        Example:
            def validate(self) -> None:
                if self.inputs.start_date > self.inputs.end_date:
                    self.add_input_error('date_range', 'Start must be before end')

        Raises:
            Halt: If validation errors occur (via add_error with halt=True)

        Note:
            Runs automatically after validate_records() and before execute().
        """
        pass

    def before_execute(self) -> None:
        """
        Lifecycle hook called before execute().

        Override to add logic that runs before the main execute() method.
        Add errors via add_error() to prevent execute() from running.
        """
        pass

    def after_execute(self, result: ResultT) -> ResultT:
        """
        Lifecycle hook called after execute().

        Override to transform or process the result after execute() completes.
        Return the potentially modified result.

        Args:
            result: The result returned from execute()

        Returns:
            The final result (can be transformed)
        """
        return result

    @abstractmethod
    def execute(self) -> ResultT:
        """
        Execute command business logic.

        Override this method to implement command behavior.
        Return the result value on success.
        """
        pass

    def commit_transaction(self) -> None:
        """Commit database transaction"""
        pass  # Transaction commits on context exit

    def rollback_transaction(self) -> None:
        """Rollback database transaction"""
        if self._transaction:
            self._transaction.mark_failed()

    # ==================== Execution Flow ====================

    def run_instance(self) -> "CommandOutcome[ResultT]":
        """
        Run this command instance through full execution flow.

        Returns CommandOutcome with result or errors.
        """
        from foobara_py.core.outcome import CommandOutcome

        # Initialize callback executor
        if self._callback_registry:
            self._callback_executor = CallbackExecutor(self._callback_registry, self)

        try:
            # Phase 1: Open transaction
            self._execute_phase(
                CommandState.OPENING_TRANSACTION,
                CallbackPhase.OPEN_TRANSACTION,
                self.open_transaction,
            )
            if self._errors.has_errors():
                return self._fail()

            try:
                # Phase 2: Cast and validate inputs
                self._execute_phase(
                    CommandState.CASTING_AND_VALIDATING_INPUTS,
                    CallbackPhase.CAST_AND_VALIDATE_INPUTS,
                    self.cast_and_validate_inputs,
                )
                if self._errors.has_errors():
                    return self._fail()

                # Phase 3: Load records
                self._execute_phase(
                    CommandState.LOADING_RECORDS, CallbackPhase.LOAD_RECORDS, self.load_records
                )
                if self._errors.has_errors():
                    return self._fail()

                # Phase 4: Validate records
                self._execute_phase(
                    CommandState.VALIDATING_RECORDS,
                    CallbackPhase.VALIDATE_RECORDS,
                    self.validate_records,
                )
                if self._errors.has_errors():
                    return self._fail()

                # Phase 5: Validate
                self._execute_phase(CommandState.VALIDATING, CallbackPhase.VALIDATE, self.validate)
                if self._errors.has_errors():
                    return self._fail()

                # Phase 6: Execute
                self._state_machine.transition_to(CommandState.EXECUTING)
                try:
                    # Call before_execute hook if defined
                    if hasattr(self, 'before_execute') and callable(getattr(self, 'before_execute', None)):
                        before_method = getattr(self.__class__, 'before_execute', None)
                        # Only call if it's a user-defined method (not inherited from Command base)
                        if before_method is not None and before_method is not Command.before_execute:
                            self.before_execute()
                            if self._errors.has_errors():
                                return self._fail()

                    if self._callback_executor:
                        self._result = self._callback_executor.execute_phase(
                            CallbackPhase.EXECUTE, self.execute
                        )
                    else:
                        self._result = self.execute()

                    # Call after_execute hook if defined
                    if hasattr(self, 'after_execute') and callable(getattr(self, 'after_execute', None)):
                        after_method = getattr(self.__class__, 'after_execute', None)
                        # Only call if it's a user-defined method (not inherited from Command base)
                        if after_method is not None and after_method is not Command.after_execute:
                            self._result = self.after_execute(self._result)
                except Halt:
                    return self._fail()
                except Exception as e:
                    self.add_error(
                        FoobaraError.runtime_error(
                            Symbols.EXECUTION_ERROR, str(e), exception_type=type(e).__name__
                        )
                    )
                    return self._fail()

                if self._errors.has_errors():
                    return self._fail()

                # Phase 7: Commit transaction
                self._execute_phase(
                    CommandState.COMMITTING_TRANSACTION,
                    CallbackPhase.COMMIT_TRANSACTION,
                    self.commit_transaction,
                )

                # Success!
                self._state_machine.transition_to(CommandState.SUCCEEDED)
                return CommandOutcome.from_result(self._result)

            except Halt:
                return self._fail()

            finally:
                # Exit transaction context
                if self._transaction:
                    self._transaction.__exit__(None, None, None)

        except Exception as e:
            # Unhandled exception - error state
            self._state_machine.error()
            self.rollback_transaction()
            if self._transaction:
                self._transaction.__exit__(type(e), e, e.__traceback__)
            raise

    def _execute_phase(
        self, state: CommandState, callback_phase: CallbackPhase, action: Callable[[], None]
    ) -> None:
        """Execute a phase with state transition and callbacks"""
        self._state_machine.transition_to(state)
        try:
            if self._callback_executor:
                self._callback_executor.execute_phase(callback_phase, action)
            else:
                action()
        except Halt:
            raise

    def _fail(self) -> "CommandOutcome[ResultT]":
        """Transition to failed state and return failure outcome"""
        from foobara_py.core.outcome import CommandOutcome

        self._state_machine.fail()
        self.rollback_transaction()
        return CommandOutcome.from_errors(*self._errors.all())

    # ==================== Class Methods ====================

    @classmethod
    def run(cls, **inputs) -> "CommandOutcome[ResultT]":
        """Create and run command with given inputs"""
        instance = cls(**inputs)
        return instance.run_instance()

    @classmethod
    def manifest(cls) -> dict:
        """Generate command manifest for discovery/documentation"""
        return {
            "name": cls.full_name(),
            "description": cls.description(),
            "organization": cls._organization,
            "domain": cls._domain,
            "depends_on": list(cls._depends_on),
            "inputs_type": {"type": "attributes", "schema": cls.inputs_schema()},
            "result_type": {"type": str(cls.result_type())},
            "possible_errors": cls._possible_errors,
        }

    # ==================== Configuration Decorators ====================

    @classmethod
    def depends_on(cls, *domains: str) -> None:
        """Declare domain dependencies"""
        cls._depends_on = tuple(domains)

    @classmethod
    def possible_error(
        cls, symbol: str, message: str = None, context: Dict[str, Any] = None
    ) -> None:
        """Declare a possible error"""
        cls._possible_errors[symbol] = {
            "symbol": symbol,
            "message": message,
            "context": context or {},
        }

    @classmethod
    def possible_errors(cls) -> List[Dict[str, Any]]:
        """
        Get all declared possible errors for this command.

        Returns:
            List of error dicts with symbol and message
        """
        return [{"symbol": symbol, "message": details.get("message")} for symbol, details in cls._possible_errors.items()]

    @classmethod
    def reflect(cls) -> "CommandManifest":
        """
        Get comprehensive reflection metadata for this command.

        Returns a CommandManifest object with complete introspection data including:
        - Command name and fully qualified name
        - Input and result schemas (JSON Schema)
        - Domain and organization
        - Possible errors
        - Whether command is async
        - Tags and description

        Returns:
            CommandManifest: Complete command metadata

        Example:
            >>> reflection = MyCommand.reflect()
            >>> print(reflection.full_name)
            "MyOrg::MyDomain::MyCommand"
            >>> print(reflection.inputs_schema)
            {"type": "object", "properties": {...}}
        """
        from foobara_py.manifest.command_manifest import CommandManifest

        return CommandManifest.from_command(cls)


# Import here to avoid circular dependency
from foobara_py.core.outcome import CommandOutcome

# ==================== Async Command ====================


class AsyncCommand(ABC, Generic[InputT, ResultT], metaclass=CommandMeta):
    """
    Async version of Command for I/O-bound operations.

    Same features as Command but with async execute().
    """

    _domain: ClassVar[Optional[str]] = None
    _organization: ClassVar[Optional[str]] = None
    _description: ClassVar[Optional[str]] = None
    _depends_on: ClassVar[Tuple[str, ...]] = ()
    _possible_errors: ClassVar[Dict[str, Dict]] = {}
    _transaction_config: ClassVar[TransactionConfig] = TransactionConfig(enabled=False)
    _callback_registry: ClassVar[Optional[CallbackRegistry]] = None
    _cached_inputs_type: ClassVar[Optional[Type[BaseModel]]] = None
    _cached_result_type: ClassVar[Optional[Type]] = None

    __slots__ = (
        "_raw_inputs",
        "_inputs",
        "_errors",
        "_result",
        "_outcome",
        "_state_machine",
        "_subcommand_runtime_path",
        "_loaded_records",
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
        self._raw_inputs: Dict[str, Any] = inputs
        self._inputs: Optional[InputT] = None
        self._errors: ErrorCollection = ErrorCollection()
        self._result: Optional[ResultT] = None
        self._outcome: Optional[CommandOutcome[ResultT]] = None
        self._state_machine: CommandStateMachine = CommandStateMachine()
        self._subcommand_runtime_path: Tuple[str, ...] = _runtime_path
        self._loaded_records: Dict[str, Any] = {}

    @property
    def inputs(self) -> InputT:
        if self._inputs is None:
            raise ValueError("Inputs not yet validated")
        return self._inputs

    @property
    def errors(self) -> ErrorCollection:
        return self._errors

    @classmethod
    def inputs_type(cls) -> Type[InputT]:
        if cls._cached_inputs_type is not None:
            return cls._cached_inputs_type

        for base in getattr(cls, "__orig_bases__", []):
            origin = get_origin(base)
            if origin is AsyncCommand or (
                isinstance(origin, type) and issubclass(origin, AsyncCommand)
            ):
                args = get_args(base)
                if args and len(args) >= 1:
                    inputs_cls = args[0]
                    if isinstance(inputs_cls, type) and issubclass(inputs_cls, BaseModel):
                        cls._cached_inputs_type = inputs_cls
                        return inputs_cls

        raise TypeError(f"Could not determine inputs type for {cls.__name__}")

    @classmethod
    def result_type(cls) -> Type[ResultT]:
        if cls._cached_result_type is not None:
            return cls._cached_result_type

        for base in getattr(cls, "__orig_bases__", []):
            origin = get_origin(base)
            if origin is AsyncCommand or (
                isinstance(origin, type) and issubclass(origin, AsyncCommand)
            ):
                args = get_args(base)
                if args and len(args) >= 2:
                    cls._cached_result_type = args[1]
                    return args[1]

        cls._cached_result_type = Any
        return Any

    @classmethod
    def inputs_schema(cls) -> dict:
        return cls.inputs_type().model_json_schema()

    @classmethod
    def full_name(cls) -> str:
        parts = []
        if cls._organization:
            parts.append(cls._organization)
        if cls._domain:
            parts.append(cls._domain)
        parts.append(cls.__name__)
        return "::".join(parts)

    @classmethod
    def description(cls) -> str:
        if cls._description:
            return cls._description
        return cls.__doc__ or ""

    @classmethod
    def possible_errors(cls) -> List[Dict[str, Any]]:
        """
        Get all declared possible errors for this command.

        Returns:
            List of error dicts with symbol and message
        """
        return [{"symbol": symbol, "message": details.get("message")} for symbol, details in cls._possible_errors.items()]

    def add_error(self, error: FoobaraError) -> None:
        if self._subcommand_runtime_path:
            error = error.with_runtime_path_prefix(*self._subcommand_runtime_path)
        self._errors.add(error)

    def add_input_error(
        self, path: Union[List[str], Tuple[str, ...]], symbol: str, message: str, **context
    ) -> None:
        self.add_error(FoobaraError.data_error(symbol, path, message, **context))

    def add_runtime_error(self, symbol: str, message: str, halt: bool = True, **context) -> None:
        self.add_error(FoobaraError.runtime_error(symbol, message, **context))
        if halt:
            raise Halt()

    def validate_inputs(self) -> bool:
        try:
            inputs_class = self.inputs_type()
            self._inputs = inputs_class(**self._raw_inputs)
            return True
        except ValidationError as e:
            for error in e.errors():
                path = tuple(str(p) for p in error["loc"])
                self.add_error(
                    FoobaraError(
                        category="data",
                        symbol=error["type"],
                        path=path,
                        message=error["msg"],
                        context={"input": error.get("input")},
                    )
                )
            return False

    async def before_execute(self) -> None:
        """
        Async lifecycle hook called before execute().

        Override to add logic that runs before the main execute() method.
        Add errors via add_error() to prevent execute() from running.
        """
        pass

    async def after_execute(self, result: ResultT) -> ResultT:
        """
        Async lifecycle hook called after execute().

        Override to transform or process the result after execute() completes.
        Return the potentially modified result.

        Args:
            result: The result returned from execute()

        Returns:
            The final result (can be transformed)
        """
        return result

    @abstractmethod
    async def execute(self) -> ResultT:
        """Async execute method - override this"""
        pass

    async def run_instance(self) -> CommandOutcome[ResultT]:
        """Run async command instance"""
        self._state_machine.transition_to(CommandState.CASTING_AND_VALIDATING_INPUTS)

        if not self.validate_inputs():
            self._state_machine.fail()
            return CommandOutcome.from_errors(*self._errors.all())

        self._state_machine.transition_to(CommandState.EXECUTING)
        try:
            # Call before_execute hook if defined
            if hasattr(self, 'before_execute') and callable(getattr(self, 'before_execute', None)):
                before_method = getattr(self.__class__, 'before_execute', None)
                # Only call if it's a user-defined method (not inherited from AsyncCommand base)
                if before_method is not None and before_method is not AsyncCommand.before_execute:
                    await self.before_execute()
                    if self._errors.has_errors():
                        self._state_machine.fail()
                        return CommandOutcome.from_errors(*self._errors.all())

            self._result = await self.execute()

            # Call after_execute hook if defined
            if hasattr(self, 'after_execute') and callable(getattr(self, 'after_execute', None)):
                after_method = getattr(self.__class__, 'after_execute', None)
                # Only call if it's a user-defined method (not inherited from AsyncCommand base)
                if after_method is not None and after_method is not AsyncCommand.after_execute:
                    self._result = await self.after_execute(self._result)
        except Halt:
            self._state_machine.fail()
            return CommandOutcome.from_errors(*self._errors.all())
        except Exception as e:
            self.add_error(
                FoobaraError.runtime_error(
                    Symbols.EXECUTION_ERROR, str(e), exception_type=type(e).__name__
                )
            )
            self._state_machine.fail()
            return CommandOutcome.from_errors(*self._errors.all())

        if self._errors.has_errors():
            self._state_machine.fail()
            return CommandOutcome.from_errors(*self._errors.all())

        self._state_machine.succeed()
        return CommandOutcome.from_result(self._result)

    @classmethod
    async def run(cls, **inputs) -> CommandOutcome[ResultT]:
        """Create and run async command"""
        instance = cls(**inputs)
        return await instance.run_instance()

    @classmethod
    def manifest(cls) -> dict:
        return {
            "name": cls.full_name(),
            "description": cls.description(),
            "organization": cls._organization,
            "domain": cls._domain,
            "inputs_type": {"type": "attributes", "schema": cls.inputs_schema()},
            "result_type": {"type": str(cls.result_type())},
            "async": True,
        }

    @classmethod
    def reflect(cls) -> "CommandManifest":
        """
        Get comprehensive reflection metadata for this command.

        Returns a CommandManifest object with complete introspection data including:
        - Command name and fully qualified name
        - Input and result schemas (JSON Schema)
        - Domain and organization
        - Possible errors
        - Whether command is async
        - Tags and description

        Returns:
            CommandManifest: Complete command metadata

        Example:
            >>> reflection = MyCommand.reflect()
            >>> print(reflection.full_name)
            "MyOrg::MyDomain::MyCommand"
            >>> print(reflection.inputs_schema)
            {"type": "object", "properties": {...}}
        """
        from foobara_py.manifest.command_manifest import CommandManifest

        return CommandManifest.from_command(cls)


# ==================== Decorators ====================


def command(
    domain: str = None,
    organization: str = None,
    description: str = None,
    depends_on: Tuple[str, ...] = (),
):
    """
    Decorator for configuring commands.

    Usage:
        @command(domain="Users", organization="MyApp")
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                ...
    """

    def decorator(cls):
        if domain:
            cls._domain = domain
        if organization:
            cls._organization = organization
        if description:
            cls._description = description
        if depends_on:
            cls._depends_on = depends_on
        return cls

    return decorator


def async_command(
    domain: str = None,
    organization: str = None,
    description: str = None,
    depends_on: Tuple[str, ...] = (),
):
    """Decorator for configuring async commands"""

    def decorator(cls):
        if domain:
            cls._domain = domain
        if organization:
            cls._organization = organization
        if description:
            cls._description = description
        if depends_on:
            cls._depends_on = depends_on
        return cls

    return decorator


# ------------------------------------------------------------------------------
# SimpleCommand and AsyncSimpleCommand (from V1, maintained for compatibility)
# ------------------------------------------------------------------------------


class SimpleCommand(Generic[ResultT]):
    """
    Simplified command for functions (decorator-based).

    Usage:
        @simple_command
        def add_numbers(a: int, b: int) -> int:
            return a + b

        outcome = add_numbers.run(a=1, b=2)
        result = outcome.unwrap()  # 3
    """

    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__

        # Extract type hints
        self._hints = get_type_hints(func)
        self._return_type = self._hints.pop("return", Any)

        # Build inputs model dynamically
        from pydantic import create_model

        sig = inspect.signature(func)
        fields = {}
        for param_name, param in sig.parameters.items():
            param_type = self._hints.get(param_name, Any)
            if param.default is inspect.Parameter.empty:
                fields[param_name] = (param_type, ...)
            else:
                fields[param_name] = (param_type, param.default)

        self._inputs_model = create_model(f"{func.__name__}Inputs", **fields)

    def inputs_schema(self) -> dict:
        """Get JSON Schema for inputs"""
        return self._inputs_model.model_json_schema()

    def run(self, **inputs) -> CommandOutcome[ResultT]:
        """Run the command with given inputs"""
        from pydantic import ValidationError

        from foobara_py.core.errors import DataError, ErrorCollection

        errors = ErrorCollection()

        # Validate inputs
        try:
            validated = self._inputs_model(**inputs)
        except ValidationError as e:
            for error in e.errors():
                path = [str(p) for p in error["loc"]]
                errors.add_error(
                    DataError(
                        category="data", symbol=error["type"], path=path, message=error["msg"]
                    )
                )
            return CommandOutcome.from_errors(*errors.all())

        # Execute function
        try:
            result = self.func(**validated.model_dump())
            return CommandOutcome.from_result(result)
        except Exception as e:
            return CommandOutcome.from_errors(
                DataError.runtime_error(symbol="execution_error", message=str(e))
            )

    def __call__(self, **inputs) -> ResultT:
        """Direct call returns result or raises"""
        outcome = self.run(**inputs)
        return outcome.unwrap()


def simple_command(func):
    """Decorator to create SimpleCommand from function"""
    return SimpleCommand(func)


class AsyncSimpleCommand(Generic[ResultT]):
    """
    Simplified async command for async functions (decorator-based).

    Usage:
        @async_simple_command
        async def fetch_user(user_id: int) -> User:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"/users/{user_id}") as resp:
                    return User(**(await resp.json()))

        outcome = await fetch_user.run(user_id=123)
        result = outcome.unwrap()
    """

    def __init__(self, func):
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"async_simple_command requires an async function, "
                f"got {type(func).__name__}. Use @simple_command for sync functions."
            )
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__

        # Extract type hints
        self._hints = get_type_hints(func)
        self._return_type = self._hints.pop("return", Any)

        # Build inputs model dynamically
        from pydantic import create_model

        sig = inspect.signature(func)
        fields = {}
        for param_name, param in sig.parameters.items():
            param_type = self._hints.get(param_name, Any)
            if param.default is inspect.Parameter.empty:
                fields[param_name] = (param_type, ...)
            else:
                fields[param_name] = (param_type, param.default)

        self._inputs_model = create_model(f"{func.__name__}Inputs", **fields)

    def inputs_schema(self) -> dict:
        """Get JSON Schema for inputs"""
        return self._inputs_model.model_json_schema()

    async def run(self, **inputs) -> CommandOutcome[ResultT]:
        """Run the async command with given inputs"""
        from pydantic import ValidationError

        from foobara_py.core.errors import DataError, ErrorCollection

        errors = ErrorCollection()

        # Validate inputs
        try:
            validated = self._inputs_model(**inputs)
        except ValidationError as e:
            for error in e.errors():
                path = [str(p) for p in error["loc"]]
                errors.add_error(
                    DataError(
                        category="data", symbol=error["type"], path=path, message=error["msg"]
                    )
                )
            return CommandOutcome.from_errors(*errors.all())

        # Execute async function
        try:
            result = await self.func(**validated.model_dump())
            return CommandOutcome.from_result(result)
        except Exception as e:
            return CommandOutcome.from_errors(
                DataError.runtime_error(symbol="execution_error", message=str(e))
            )

    async def __call__(self, **inputs) -> ResultT:
        """Direct call returns result or raises"""
        outcome = await self.run(**inputs)
        return outcome.unwrap()


def async_simple_command(func):
    """Decorator to create AsyncSimpleCommand from async function"""
    return AsyncSimpleCommand(func)
