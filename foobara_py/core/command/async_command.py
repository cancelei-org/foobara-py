"""
AsyncCommand - Async version of Command for I/O-bound operations.

Same features as Command but with async execute().
Uses simplified execution flow (no transactions by default).
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Generic, List, Optional, Tuple, Type, TypeVar, get_args, get_origin

from pydantic import BaseModel, ValidationError

from foobara_py.core.callbacks import CallbackRegistry
from foobara_py.core.errors import ErrorCollection, FoobaraError, Symbols
from foobara_py.core.outcome import CommandOutcome
from foobara_py.core.state_machine import CommandState, CommandStateMachine, Halt
from foobara_py.core.transactions import TransactionConfig

from .base import CommandMeta

InputT = TypeVar("InputT", bound=BaseModel)
ResultT = TypeVar("ResultT")


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
        """Normalize _possible_errors format."""
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
        """Get all declared possible errors for this command."""
        return [
            {"symbol": symbol, "message": details.get("message")}
            for symbol, details in cls._possible_errors.items()
        ]

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
        """Async lifecycle hook called before execute()."""
        pass

    async def after_execute(self, result: ResultT) -> ResultT:
        """Async lifecycle hook called after execute()."""
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
        """Get comprehensive reflection metadata for this command."""
        from foobara_py.manifest.command_manifest import CommandManifest

        return CommandManifest.from_command(cls)


# Add missing import
from typing import Union
