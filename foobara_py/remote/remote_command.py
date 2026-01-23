"""
Remote command for calling remote Foobara services.

RemoteCommand is a proxy that calls commands on remote Foobara services
via HTTP, maintaining the same interface as local commands.
"""

from abc import ABC
from typing import Any, ClassVar, Dict, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

from foobara_py.core.errors import FoobaraError as BaseFoobaraError
from foobara_py.core.outcome import CommandOutcome

InputT = TypeVar("InputT", bound=BaseModel)
ResultT = TypeVar("ResultT")


class RemoteCommandError(Exception):
    """Error during remote command execution."""

    def __init__(
        self,
        message: str,
        symbol: str = "remote_command_error",
        status_code: Optional[int] = None,
        remote_errors: Optional[list] = None,
    ):
        super().__init__(message)
        self.message = message
        self.symbol = symbol
        self.category = "runtime"
        self.status_code = status_code
        self.remote_errors = remote_errors or []

    def __str__(self) -> str:
        return self.message


class RemoteConnectionError(RemoteCommandError):
    """Failed to connect to remote service."""

    def __init__(self, message: str, url: str):
        super().__init__(message=message, symbol="connection_error")
        self.url = url


# Alias for backward compatibility
ConnectionError = RemoteConnectionError


class RemoteCommand(ABC, Generic[InputT, ResultT]):
    """
    Proxy command that calls a remote Foobara service.

    RemoteCommand maintains the same interface as local Command classes
    but executes via HTTP calls to a remote Foobara service.

    Usage:
        # Create via RemoteImporter (recommended)
        importer = RemoteImporter("https://api.example.com/manifest")
        CreateUser = importer.import_command("CreateUser")

        # Or define manually
        class CreateUser(RemoteCommand[CreateUserInputs, User]):
            _remote_url = "https://api.example.com"
            _command_name = "Users::CreateUser"

            # InputT and ResultT are auto-generated from manifest

        # Run like a local command
        outcome = CreateUser.run(name="John", email="john@example.com")
    """

    # Class-level configuration (set by RemoteImporter)
    _remote_url: ClassVar[str] = ""
    _command_name: ClassVar[str] = ""
    _timeout: ClassVar[float] = 30.0
    _headers: ClassVar[Dict[str, str]] = {}

    # Metadata from manifest
    _description: ClassVar[str] = ""
    _domain: ClassVar[Optional[str]] = None
    _organization: ClassVar[Optional[str]] = None

    def __init__(self, **inputs: Any):
        """Initialize with inputs."""
        self._raw_inputs = inputs
        self._inputs: Optional[InputT] = None
        self._result: Optional[ResultT] = None

    @property
    def inputs(self) -> InputT:
        """Get validated inputs."""
        if self._inputs is None:
            raise ValueError("Inputs not yet validated")
        return self._inputs

    @classmethod
    def inputs_type(cls) -> Type[InputT]:
        """Get the inputs Pydantic model class."""
        # Check for dynamically set _inputs_model first (from RemoteImporter)
        if hasattr(cls, "_inputs_model") and cls._inputs_model is not None:
            return cls._inputs_model
        # Fall back to generic type extraction
        for base in getattr(cls, "__orig_bases__", []):
            if hasattr(base, "__args__") and len(base.__args__) >= 1:
                inputs_class = base.__args__[0]
                if isinstance(inputs_class, type) and issubclass(inputs_class, BaseModel):
                    return inputs_class
        raise TypeError(f"Could not determine inputs type for {cls.__name__}")

    @classmethod
    def result_type(cls) -> Type[ResultT]:
        """Get the result type."""
        # Check for dynamically set _result_model first (from RemoteImporter)
        if hasattr(cls, "_result_model") and cls._result_model is not None:
            return cls._result_model
        # Fall back to generic type extraction
        for base in getattr(cls, "__orig_bases__", []):
            if hasattr(base, "__args__") and len(base.__args__) >= 2:
                return base.__args__[1]
        return Any

    @classmethod
    def full_name(cls) -> str:
        """Get full command name."""
        return cls._command_name or cls.__name__

    @classmethod
    def description(cls) -> str:
        """Get command description."""
        return cls._description or cls.__doc__ or ""

    @classmethod
    def inputs_schema(cls) -> dict:
        """Get JSON Schema for inputs."""
        try:
            return cls.inputs_type().model_json_schema()
        except TypeError:
            return {}

    def validate_inputs(self) -> bool:
        """Validate inputs using the inputs model."""
        try:
            inputs_class = self.inputs_type()
            self._inputs = inputs_class(**self._raw_inputs)
            return True
        except Exception:
            return False

    def execute(self) -> ResultT:
        """
        Execute the remote command via HTTP.

        Makes a POST request to the remote service's run endpoint.
        """
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for remote commands. "
                "Install it with: pip install foobara-py[http]"
            )

        if not self._remote_url:
            raise RemoteCommandError("Remote URL not configured", symbol="configuration_error")

        if not self._command_name:
            raise RemoteCommandError("Command name not configured", symbol="configuration_error")

        # Build request URL
        url = f"{self._remote_url.rstrip('/')}/run/{self._command_name}"

        # Prepare request body
        body = self._inputs.model_dump() if self._inputs else self._raw_inputs

        # Make request
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    url,
                    json=body,
                    headers=self._headers,
                )
        except httpx.ConnectError as e:
            raise RemoteConnectionError(f"Failed to connect to remote service: {e}", url=url)
        except httpx.TimeoutException as e:
            raise RemoteCommandError(
                f"Request timed out after {self._timeout}s: {e}", symbol="timeout_error"
            )

        # Parse response
        return self._parse_response(response)

    def _parse_response(self, response: Any) -> ResultT:
        """Parse HTTP response into result type."""
        if response.status_code >= 400:
            # Try to extract error details from response
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                message = error_data.get("message", response.text)
            except Exception:
                errors = []
                message = response.text

            raise RemoteCommandError(
                message=message,
                symbol="remote_error",
                status_code=response.status_code,
                remote_errors=errors,
            )

        # Parse successful response
        try:
            data = response.json()
        except Exception as e:
            raise RemoteCommandError(f"Failed to parse response: {e}", symbol="parse_error")

        # Extract result from response envelope
        if isinstance(data, dict):
            # Foobara response format: {"outcome": "success", "result": {...}}
            if "result" in data:
                data = data["result"]
            elif "data" in data:
                data = data["data"]

        # Convert to result type if it's a model
        result_type = self.result_type()
        if result_type and result_type != Any:
            if isinstance(result_type, type) and issubclass(result_type, BaseModel):
                return result_type.model_validate(data)

        return data

    def run_instance(self) -> CommandOutcome[ResultT]:
        """
        Run this command instance and return outcome.

        Matches the interface of local Command.run_instance().
        """
        # Validate inputs first
        if not self.validate_inputs():
            return CommandOutcome.from_errors(
                BaseFoobaraError(
                    category="data", symbol="validation_error", message="Input validation failed"
                )
            )

        # Execute remote call
        try:
            result = self.execute()
            return CommandOutcome.from_result(result)
        except RemoteCommandError as e:
            return CommandOutcome.from_errors(e)
        except Exception as e:
            return CommandOutcome.from_errors(
                BaseFoobaraError(category="runtime", symbol="execution_error", message=str(e))
            )

    @classmethod
    def run(cls, **inputs: Any) -> CommandOutcome[ResultT]:
        """
        Class method to create and run command.

        Matches the interface of local Command.run().

        Example:
            outcome = CreateUser.run(name="John", email="john@example.com")
        """
        instance = cls(**inputs)
        return instance.run_instance()

    @classmethod
    def manifest(cls) -> dict:
        """Generate command manifest."""
        return {
            "name": cls.full_name(),
            "description": cls.description(),
            "organization": cls._organization,
            "domain": cls._domain,
            "remote_url": cls._remote_url,
            "inputs_type": {"type": "attributes", "schema": cls.inputs_schema()},
            "result_type": {"type": str(cls.result_type())},
            "is_remote": True,
        }


class AsyncRemoteCommand(ABC, Generic[InputT, ResultT]):
    """
    Async version of RemoteCommand.

    Uses async HTTP client for non-blocking remote calls.
    """

    _remote_url: ClassVar[str] = ""
    _command_name: ClassVar[str] = ""
    _timeout: ClassVar[float] = 30.0
    _headers: ClassVar[Dict[str, str]] = {}

    _description: ClassVar[str] = ""
    _domain: ClassVar[Optional[str]] = None
    _organization: ClassVar[Optional[str]] = None

    def __init__(self, **inputs: Any):
        self._raw_inputs = inputs
        self._inputs: Optional[InputT] = None
        self._result: Optional[ResultT] = None

    @property
    def inputs(self) -> InputT:
        if self._inputs is None:
            raise ValueError("Inputs not yet validated")
        return self._inputs

    @classmethod
    def inputs_type(cls) -> Type[InputT]:
        for base in getattr(cls, "__orig_bases__", []):
            if hasattr(base, "__args__") and len(base.__args__) >= 1:
                inputs_class = base.__args__[0]
                if isinstance(inputs_class, type) and issubclass(inputs_class, BaseModel):
                    return inputs_class
        raise TypeError(f"Could not determine inputs type for {cls.__name__}")

    @classmethod
    def result_type(cls) -> Type[ResultT]:
        for base in getattr(cls, "__orig_bases__", []):
            if hasattr(base, "__args__") and len(base.__args__) >= 2:
                return base.__args__[1]
        return Any

    @classmethod
    def full_name(cls) -> str:
        return cls._command_name or cls.__name__

    @classmethod
    def description(cls) -> str:
        return cls._description or cls.__doc__ or ""

    @classmethod
    def inputs_schema(cls) -> dict:
        try:
            return cls.inputs_type().model_json_schema()
        except TypeError:
            return {}

    def validate_inputs(self) -> bool:
        try:
            inputs_class = self.inputs_type()
            self._inputs = inputs_class(**self._raw_inputs)
            return True
        except Exception:
            return False

    async def execute(self) -> ResultT:
        """Execute the remote command via async HTTP."""
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for remote commands. "
                "Install it with: pip install foobara-py[http]"
            )

        if not self._remote_url or not self._command_name:
            raise RemoteCommandError(
                "Remote URL or command name not configured", symbol="configuration_error"
            )

        url = f"{self._remote_url.rstrip('/')}/run/{self._command_name}"
        body = self._inputs.model_dump() if self._inputs else self._raw_inputs

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    json=body,
                    headers=self._headers,
                )
        except httpx.ConnectError as e:
            raise RemoteConnectionError(f"Failed to connect: {e}", url=url)
        except httpx.TimeoutException as e:
            raise RemoteCommandError(f"Request timed out: {e}", symbol="timeout_error")

        return self._parse_response(response)

    def _parse_response(self, response: Any) -> ResultT:
        """Parse HTTP response into result type."""
        if response.status_code >= 400:
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                message = error_data.get("message", response.text)
            except Exception:
                errors = []
                message = response.text

            raise RemoteCommandError(
                message=message,
                symbol="remote_error",
                status_code=response.status_code,
                remote_errors=errors,
            )

        try:
            data = response.json()
        except Exception as e:
            raise RemoteCommandError(f"Failed to parse response: {e}", symbol="parse_error")

        if isinstance(data, dict):
            if "result" in data:
                data = data["result"]
            elif "data" in data:
                data = data["data"]

        result_type = self.result_type()
        if result_type and result_type != Any:
            if isinstance(result_type, type) and issubclass(result_type, BaseModel):
                return result_type.model_validate(data)

        return data

    async def run_instance(self) -> CommandOutcome[ResultT]:
        """Run this async command instance and return outcome."""
        if not self.validate_inputs():
            return CommandOutcome.from_errors(
                BaseFoobaraError(
                    category="data", symbol="validation_error", message="Input validation failed"
                )
            )

        try:
            result = await self.execute()
            return CommandOutcome.from_result(result)
        except RemoteCommandError as e:
            return CommandOutcome.from_errors(e)
        except Exception as e:
            return CommandOutcome.from_errors(
                BaseFoobaraError(category="runtime", symbol="execution_error", message=str(e))
            )

    @classmethod
    async def run(cls, **inputs: Any) -> CommandOutcome[ResultT]:
        """Class method to create and run async command."""
        instance = cls(**inputs)
        return await instance.run_instance()
