"""
⚠️  DEPRECATED V1 IMPLEMENTATION ⚠️

This file is deprecated as of v0.3.0 and will be removed in v0.4.0.

DO NOT USE THIS FILE. Use the current implementation instead:
    from foobara_py import Command

The public API has always used V2 (now current) implementations.

---

Command base class for foobara-py (LEGACY V1)

Provides the core Command pattern implementation with:
- Pydantic-based input validation
- Outcome-based result handling
- Domain/organization registration
- JSON Schema generation for MCP integration
"""

import warnings

warnings.warn(
    "foobara_py._deprecated.core.command_v1 is deprecated and will be removed in v0.4.0. "
    "Use 'from foobara_py import Command' instead.",
    DeprecationWarning,
    stacklevel=2,
)

import asyncio
import inspect
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Coroutine, Dict, Generic, List, Optional, Type, TypeVar, get_type_hints

from pydantic import BaseModel, ValidationError

from foobara_py.core.errors import DataError, ErrorCollection
from foobara_py.core.outcome import CommandOutcome

InputT = TypeVar("InputT", bound=BaseModel)
ResultT = TypeVar("ResultT")


class Command(ABC, Generic[InputT, ResultT]):
    """
    Base command class inspired by Foobara::Command.

    Commands encapsulate business logic with:
    - Typed inputs (validated via Pydantic)
    - Structured outcomes (Success/Failure)
    - Self-documenting (JSON Schema generation)
    - Registerable in domains

    Usage:
        class CreateUserInputs(BaseModel):
            name: str
            email: str
            age: int = None

        class User(BaseModel):
            id: int
            name: str
            email: str

        class CreateUser(Command[CreateUserInputs, User]):
            '''Create a new user account'''

            def execute(self) -> User:
                # Business logic here
                return User(id=1, name=self.inputs.name, email=self.inputs.email)

        # Run the command
        outcome = CreateUser.run(name="John", email="john@example.com")
        if outcome.is_success():
            user = outcome.unwrap()
    """

    # Class-level configuration
    _domain: Optional[str] = None
    _organization: Optional[str] = None
    _description: Optional[str] = None
    _loads: List[Any] = []  # Entity load specifications (LoadSpec objects)
    _possible_errors: List[tuple] = []  # List of (symbol, message) tuples

    def __init__(self, **inputs):
        """Initialize command with inputs"""
        self._raw_inputs = inputs
        self._inputs: Optional[InputT] = None
        self._errors = ErrorCollection()
        self._result: Optional[ResultT] = None
        self._outcome: Optional[CommandOutcome[ResultT]] = None
        self._loaded_entities: Dict[str, Any] = {}  # Loaded entities storage

    @property
    def inputs(self) -> InputT:
        """Get validated inputs"""
        if self._inputs is None:
            raise ValueError("Inputs not yet validated. Call validate_inputs() first.")
        return self._inputs

    @property
    def errors(self) -> ErrorCollection:
        """Get error collection"""
        return self._errors

    @classmethod
    def inputs_type(cls) -> Type[InputT]:
        """Get the inputs Pydantic model class"""
        # Extract from Generic type parameters
        for base in cls.__orig_bases__:
            if hasattr(base, "__args__") and len(base.__args__) >= 1:
                inputs_class = base.__args__[0]
                if isinstance(inputs_class, type) and issubclass(inputs_class, BaseModel):
                    return inputs_class
        raise TypeError(f"Could not determine inputs type for {cls.__name__}")

    @classmethod
    def result_type(cls) -> Type[ResultT]:
        """Get the result type"""
        for base in cls.__orig_bases__:
            if hasattr(base, "__args__") and len(base.__args__) >= 2:
                return base.__args__[1]
        return Any

    @classmethod
    def inputs_schema(cls) -> dict:
        """Get JSON Schema for inputs (for MCP integration)"""
        return cls.inputs_type().model_json_schema()

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
    def description(cls) -> str:
        """Get command description from docstring or explicit setting"""
        if cls._description:
            return cls._description
        return cls.__doc__ or ""

    def validate_inputs(self) -> bool:
        """
        Validate raw inputs using Pydantic model.

        Returns True if valid, False if errors occurred.
        Errors are added to self.errors collection.
        """
        try:
            inputs_class = self.inputs_type()
            self._inputs = inputs_class(**self._raw_inputs)
            return True
        except ValidationError as e:
            # Convert Pydantic errors to foobara-py errors
            for error in e.errors():
                path = [str(p) for p in error["loc"]]
                data_error = DataError(
                    category="data",
                    symbol=error["type"],
                    path=path,
                    message=error["msg"],
                    context={"input": error.get("input")},
                )
                self._errors.add_error(data_error)
            return False

    def add_error(self, error: DataError) -> None:
        """Add an error during execution"""
        self._errors.add_error(error)

    def add_input_error(self, path: List[str], symbol: str, message: str) -> None:
        """Convenience method to add input validation error"""
        self.add_error(DataError.data_error(symbol, path, message))

    def add_runtime_error(self, symbol: str, message: str) -> None:
        """Convenience method to add runtime error"""
        self.add_error(DataError.runtime_error(symbol, message))

    # ==================== Lifecycle Hooks ====================

    def before_execute(self) -> None:
        """
        Called before execute().

        Override this method to implement pre-execution logic such as:
        - Authorization checks
        - Resource acquisition
        - Logging/auditing

        Example:
            def before_execute(self) -> None:
                if not self.current_user.can_create_users():
                    self.add_runtime_error('unauthorized', 'Not authorized')
        """
        pass

    def after_execute(self, result: ResultT) -> ResultT:
        """
        Called after execute() with the result.

        Override this method to implement post-execution logic such as:
        - Result transformation
        - Cleanup
        - Event emission

        Args:
            result: The result from execute()

        Returns:
            The (possibly transformed) result

        Example:
            def after_execute(self, result: User) -> User:
                send_welcome_email(result.email)
                return result
        """
        return result

    # ==================== Entity Loading ====================

    def _load_entities(self) -> bool:
        """
        Load entities declared in _loads specification.

        Returns True if all required entities loaded successfully.
        Loaded entities are accessible via self.<into_name>.

        Example:
            class UpdateUser(Command[...]):
                _loads = [
                    load(User, from_input='user_id', into='user')
                ]

                def execute(self):
                    self.user.name = self.inputs.name  # self.user loaded automatically
        """
        loads = getattr(self.__class__, "_loads", [])
        if not loads:
            return True

        for spec in loads:
            # Get the primary key from inputs
            pk = getattr(self.inputs, spec.from_input, None)

            if pk is None:
                if spec.required:
                    self.add_error(
                        DataError(
                            category="data",
                            symbol="missing_required",
                            path=[spec.from_input],
                            message=f"Missing required input: {spec.from_input}",
                        )
                    )
                    return False
                continue

            # Load the entity
            try:
                entity = spec.entity_class.find(pk)
            except Exception as e:
                self.add_error(
                    DataError.runtime_error(
                        symbol="entity_load_error",
                        message=f"Failed to load {spec.entity_class.__name__}: {e}",
                    )
                )
                return False

            if entity is None:
                if spec.required:
                    self.add_error(
                        DataError(
                            category="data",
                            symbol="not_found",
                            path=[spec.from_input],
                            message=f"{spec.entity_class.__name__} with id={pk} not found",
                        )
                    )
                    return False
                continue

            # Store loaded entity
            self._loaded_entities[spec.into] = entity

        return True

    def __getattr__(self, name: str) -> Any:
        """Allow access to loaded entities via attribute access"""
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
        if "_loaded_entities" in self.__dict__ and name in self._loaded_entities:
            return self._loaded_entities[name]
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    # ==================== Subcommand Support ====================

    def run_subcommand(self, command_class: Type["Command"], **inputs) -> Any:
        """
        Run another command within this command.

        Errors from the subcommand are propagated to this command.
        Returns the result on success, None on failure.

        Example:
            def execute(self):
                # Run validation as subcommand
                validation_result = self.run_subcommand(
                    ValidateEmail,
                    email=self.inputs.email
                )
                if validation_result is None:
                    return None  # Errors already added

                return User(email=self.inputs.email)
        """
        outcome = command_class.run(**inputs)

        if outcome.is_failure():
            # Propagate errors with subcommand context
            for error in outcome.errors:
                # Add context about which subcommand failed
                context = getattr(error, "context", {}) or {}
                context["subcommand"] = command_class.full_name()
                self.add_error(
                    DataError(
                        category=getattr(error, "category", "runtime"),
                        symbol=getattr(error, "symbol", "subcommand_error"),
                        path=getattr(error, "path", []),
                        message=str(error),
                        context=context,
                    )
                )
            return None

        return outcome.unwrap()

    # ==================== Possible Errors ====================

    @classmethod
    def possible_errors(cls) -> List[Dict[str, str]]:
        """
        Get list of possible errors this command may raise.

        Returns list of dicts with 'symbol' and 'message' keys.
        Used for documentation and API schema generation.

        Example:
            class CreateUser(Command[...]):
                _possible_errors = [
                    ('email_taken', 'Email address is already in use'),
                    ('invalid_domain', 'Email domain is not allowed'),
                ]
        """
        errors = getattr(cls, "_possible_errors", [])
        return [{"symbol": symbol, "message": message} for symbol, message in errors]

    @abstractmethod
    def execute(self) -> ResultT:
        """
        Execute command business logic.

        Override this method to implement command behavior.
        Can raise exceptions or add errors via add_error().
        Return the result value on success.
        """
        pass

    def _run_execute(self) -> Optional[ResultT]:
        """Internal execute wrapper with error handling"""
        try:
            return self.execute()
        except Exception as e:
            self.add_error(
                DataError.runtime_error(
                    symbol="execution_error", message=str(e), exception_type=type(e).__name__
                )
            )
            return None

    def run_instance(self) -> CommandOutcome[ResultT]:
        """
        Run this command instance and return outcome.

        Execution flow:
        1. Validate inputs (cast and validate)
        2. Load entities (if _loads specified)
        3. Run before_execute hook
        4. Execute business logic
        5. Run after_execute hook
        6. Return Success or Failure outcome
        """
        # Step 1: Validate inputs
        if not self.validate_inputs():
            return CommandOutcome.from_errors(*self._errors.all())

        # Step 2: Load entities
        if not self._load_entities():
            return CommandOutcome.from_errors(*self._errors.all())

        # Step 3: Before execute hook
        try:
            self.before_execute()
        except Exception as e:
            self.add_error(
                DataError.runtime_error(
                    symbol="before_execute_error", message=str(e), exception_type=type(e).__name__
                )
            )

        # Check for errors from before_execute
        if self._errors.has_errors():
            return CommandOutcome.from_errors(*self._errors.all())

        # Step 4: Execute
        result = self._run_execute()

        # Step 5: Return early on errors
        if self._errors.has_errors():
            return CommandOutcome.from_errors(*self._errors.all())

        # Step 6: After execute hook
        try:
            result = self.after_execute(result)
        except Exception as e:
            self.add_error(
                DataError.runtime_error(
                    symbol="after_execute_error", message=str(e), exception_type=type(e).__name__
                )
            )
            return CommandOutcome.from_errors(*self._errors.all())

        return CommandOutcome.from_result(result)

    @classmethod
    def run(cls, **inputs) -> CommandOutcome[ResultT]:
        """
        Class method to create and run command.

        Example:
            outcome = CreateUser.run(name="John", email="john@example.com")
        """
        instance = cls(**inputs)
        return instance.run_instance()

    @classmethod
    def manifest(cls) -> dict:
        """
        Generate command manifest for discovery/documentation.

        Similar to Foobara's foobara_manifest.
        """
        manifest = {
            "name": cls.full_name(),
            "description": cls.description(),
            "organization": cls._organization,
            "domain": cls._domain,
            "inputs_type": {"type": "attributes", "schema": cls.inputs_schema()},
            "result_type": {"type": str(cls.result_type())},
        }

        # Add possible errors if defined
        errors = cls.possible_errors()
        if errors:
            manifest["possible_errors"] = errors

        return manifest


def command(domain: str = None, organization: str = None, description: str = None):
    """
    Decorator for registering commands with a domain.

    Usage:
        @command(domain="Users", organization="MyApp")
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                ...
    """

    def decorator(cls):
        cls._domain = domain
        cls._organization = organization
        if description:
            cls._description = description
        return cls

    return decorator


class AsyncCommand(ABC, Generic[InputT, ResultT]):
    """
    Async base command class for async/await operations.

    Commands encapsulate business logic with:
    - Typed inputs (validated via Pydantic)
    - Structured outcomes (Success/Failure)
    - Async execution support for I/O-bound operations
    - Self-documenting (JSON Schema generation)
    - Registerable in domains

    Usage:
        class FetchUserInputs(BaseModel):
            user_id: int

        class User(BaseModel):
            id: int
            name: str
            email: str

        class FetchUser(AsyncCommand[FetchUserInputs, User]):
            '''Fetch a user from external API'''

            async def execute(self) -> User:
                # Async business logic here
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"/users/{self.inputs.user_id}") as resp:
                        data = await resp.json()
                        return User(**data)

        # Run the command (returns a coroutine)
        outcome = await FetchUser.run(user_id=123)
        if outcome.is_success():
            user = outcome.unwrap()
    """

    # Class-level configuration
    _domain: Optional[str] = None
    _organization: Optional[str] = None
    _description: Optional[str] = None
    _loads: List[Any] = []  # Entity load specifications (LoadSpec objects)
    _possible_errors: List[tuple] = []  # List of (symbol, message) tuples

    def __init__(self, **inputs):
        """Initialize command with inputs"""
        self._raw_inputs = inputs
        self._inputs: Optional[InputT] = None
        self._errors = ErrorCollection()
        self._result: Optional[ResultT] = None
        self._outcome: Optional[CommandOutcome[ResultT]] = None
        self._loaded_entities: Dict[str, Any] = {}  # Loaded entities storage

    @property
    def inputs(self) -> InputT:
        """Get validated inputs"""
        if self._inputs is None:
            raise ValueError("Inputs not yet validated. Call validate_inputs() first.")
        return self._inputs

    @property
    def errors(self) -> ErrorCollection:
        """Get error collection"""
        return self._errors

    @classmethod
    def inputs_type(cls) -> Type[InputT]:
        """Get the inputs Pydantic model class"""
        for base in cls.__orig_bases__:
            if hasattr(base, "__args__") and len(base.__args__) >= 1:
                inputs_class = base.__args__[0]
                if isinstance(inputs_class, type) and issubclass(inputs_class, BaseModel):
                    return inputs_class
        raise TypeError(f"Could not determine inputs type for {cls.__name__}")

    @classmethod
    def result_type(cls) -> Type[ResultT]:
        """Get the result type"""
        for base in cls.__orig_bases__:
            if hasattr(base, "__args__") and len(base.__args__) >= 2:
                return base.__args__[1]
        return Any

    @classmethod
    def inputs_schema(cls) -> dict:
        """Get JSON Schema for inputs (for MCP integration)"""
        return cls.inputs_type().model_json_schema()

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
    def description(cls) -> str:
        """Get command description from docstring or explicit setting"""
        if cls._description:
            return cls._description
        return cls.__doc__ or ""

    def validate_inputs(self) -> bool:
        """
        Validate raw inputs using Pydantic model.

        Returns True if valid, False if errors occurred.
        Errors are added to self.errors collection.
        """
        try:
            inputs_class = self.inputs_type()
            self._inputs = inputs_class(**self._raw_inputs)
            return True
        except ValidationError as e:
            for error in e.errors():
                path = [str(p) for p in error["loc"]]
                data_error = DataError(
                    category="data",
                    symbol=error["type"],
                    path=path,
                    message=error["msg"],
                    context={"input": error.get("input")},
                )
                self._errors.add_error(data_error)
            return False

    def add_error(self, error: DataError) -> None:
        """Add an error during execution"""
        self._errors.add_error(error)

    def add_input_error(self, path: List[str], symbol: str, message: str) -> None:
        """Convenience method to add input validation error"""
        self.add_error(DataError.data_error(symbol, path, message))

    def add_runtime_error(self, symbol: str, message: str) -> None:
        """Convenience method to add runtime error"""
        self.add_error(DataError.runtime_error(symbol, message))

    # ==================== Lifecycle Hooks ====================

    async def before_execute(self) -> None:
        """Called before execute(). Override for pre-execution logic."""
        pass

    async def after_execute(self, result: ResultT) -> ResultT:
        """Called after execute(). Override for post-execution logic."""
        return result

    # ==================== Entity Loading ====================

    def _load_entities(self) -> bool:
        """Load entities declared in _loads specification (sync for now)."""
        loads = getattr(self.__class__, "_loads", [])
        if not loads:
            return True

        for spec in loads:
            pk = getattr(self.inputs, spec.from_input, None)
            if pk is None:
                if spec.required:
                    self.add_error(
                        DataError(
                            category="data",
                            symbol="missing_required",
                            path=[spec.from_input],
                            message=f"Missing required input: {spec.from_input}",
                        )
                    )
                    return False
                continue

            try:
                entity = spec.entity_class.find(pk)
            except Exception as e:
                self.add_error(
                    DataError.runtime_error(
                        symbol="entity_load_error",
                        message=f"Failed to load {spec.entity_class.__name__}: {e}",
                    )
                )
                return False

            if entity is None:
                if spec.required:
                    self.add_error(
                        DataError(
                            category="data",
                            symbol="not_found",
                            path=[spec.from_input],
                            message=f"{spec.entity_class.__name__} with id={pk} not found",
                        )
                    )
                    return False
                continue

            self._loaded_entities[spec.into] = entity

        return True

    def __getattr__(self, name: str) -> Any:
        """Allow access to loaded entities via attribute access"""
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
        if "_loaded_entities" in self.__dict__ and name in self._loaded_entities:
            return self._loaded_entities[name]
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    # ==================== Subcommand Support ====================

    async def run_subcommand(self, command_class: Type["AsyncCommand"], **inputs) -> Any:
        """Run another async command within this command."""
        outcome = await command_class.run(**inputs)

        if outcome.is_failure():
            for error in outcome.errors:
                context = getattr(error, "context", {}) or {}
                context["subcommand"] = command_class.full_name()
                self.add_error(
                    DataError(
                        category=getattr(error, "category", "runtime"),
                        symbol=getattr(error, "symbol", "subcommand_error"),
                        path=getattr(error, "path", []),
                        message=str(error),
                        context=context,
                    )
                )
            return None

        return outcome.unwrap()

    # ==================== Possible Errors ====================

    @classmethod
    def possible_errors(cls) -> List[Dict[str, str]]:
        """Get list of possible errors this command may raise."""
        errors = getattr(cls, "_possible_errors", [])
        return [{"symbol": symbol, "message": message} for symbol, message in errors]

    @abstractmethod
    async def execute(self) -> ResultT:
        """
        Execute async command business logic.

        Override this method to implement command behavior.
        Can raise exceptions or add errors via add_error().
        Return the result value on success.
        """
        pass

    async def _run_execute(self) -> Optional[ResultT]:
        """Internal async execute wrapper with error handling"""
        try:
            return await self.execute()
        except Exception as e:
            self.add_error(
                DataError.runtime_error(
                    symbol="execution_error", message=str(e), exception_type=type(e).__name__
                )
            )
            return None

    async def run_instance(self) -> CommandOutcome[ResultT]:
        """
        Run this async command instance and return outcome.

        Execution flow:
        1. Validate inputs (cast and validate)
        2. Load entities (if _loads specified)
        3. Run before_execute hook
        4. Execute async business logic
        5. Run after_execute hook
        6. Return Success or Failure outcome
        """
        # Step 1: Validate inputs (sync - Pydantic validation is synchronous)
        if not self.validate_inputs():
            return CommandOutcome.from_errors(*self._errors.all())

        # Step 2: Load entities
        if not self._load_entities():
            return CommandOutcome.from_errors(*self._errors.all())

        # Step 3: Before execute hook
        try:
            await self.before_execute()
        except Exception as e:
            self.add_error(
                DataError.runtime_error(
                    symbol="before_execute_error", message=str(e), exception_type=type(e).__name__
                )
            )

        if self._errors.has_errors():
            return CommandOutcome.from_errors(*self._errors.all())

        # Step 4: Execute async
        result = await self._run_execute()

        # Step 5: Return early on errors
        if self._errors.has_errors():
            return CommandOutcome.from_errors(*self._errors.all())

        # Step 6: After execute hook
        try:
            result = await self.after_execute(result)
        except Exception as e:
            self.add_error(
                DataError.runtime_error(
                    symbol="after_execute_error", message=str(e), exception_type=type(e).__name__
                )
            )
            return CommandOutcome.from_errors(*self._errors.all())

        return CommandOutcome.from_result(result)

    @classmethod
    async def run(cls, **inputs) -> CommandOutcome[ResultT]:
        """
        Class method to create and run async command.

        Example:
            outcome = await FetchUser.run(user_id=123)
        """
        instance = cls(**inputs)
        return await instance.run_instance()

    @classmethod
    def manifest(cls) -> dict:
        """
        Generate command manifest for discovery/documentation.

        Similar to Foobara's foobara_manifest.
        """
        manifest = {
            "name": cls.full_name(),
            "description": cls.description(),
            "organization": cls._organization,
            "domain": cls._domain,
            "inputs_type": {"type": "attributes", "schema": cls.inputs_schema()},
            "result_type": {"type": str(cls.result_type())},
            "async": True,
        }

        # Add possible errors if defined
        errors = cls.possible_errors()
        if errors:
            manifest["possible_errors"] = errors

        return manifest


def async_command(domain: str = None, organization: str = None, description: str = None):
    """
    Decorator for registering async commands with a domain.

    Usage:
        @async_command(domain="Users", organization="MyApp")
        class FetchUser(AsyncCommand[FetchUserInputs, User]):
            async def execute(self) -> User:
                ...
    """

    def decorator(cls):
        cls._domain = domain
        cls._organization = organization
        if description:
            cls._description = description
        return cls

    return decorator


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
