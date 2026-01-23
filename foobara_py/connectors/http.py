"""
FastAPI HTTP Connector for foobara-py.

Exposes commands as HTTP endpoints following REST conventions.
Similar to Ruby Foobara's HTTP connector.

Features:
- Automatic route generation from commands
- JSON request/response serialization
- OpenAPI schema generation
- Error handling with proper HTTP status codes
- Command manifest endpoint
- Authentication middleware support

Usage:
    from fastapi import FastAPI
    from foobara_py.connectors.http import HTTPConnector

    app = FastAPI()
    connector = HTTPConnector(app)

    # Register commands
    connector.register(CreateUser)
    connector.register(GetUser)

    # Or register a domain
    connector.register_domain(users_domain)

    # Run with: uvicorn myapp:app
"""

import json
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type, TypeVar, Union

from foobara_py.core.command import AsyncCommand, Command
from foobara_py.core.outcome import CommandOutcome
from foobara_py.domain.domain import Domain, Organization

logger = logging.getLogger(__name__)


class HTTPStatus(IntEnum):
    """Common HTTP status codes"""

    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500


@dataclass(slots=True)
class RouteConfig:
    """Configuration for a command route"""

    path: str
    method: str = "POST"
    tags: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    description: Optional[str] = None
    operation_id: Optional[str] = None
    deprecated: bool = False
    include_in_schema: bool = True


@dataclass(slots=True)
class AuthConfig:
    """Authentication configuration"""

    enabled: bool = False
    dependency: Optional[Callable] = None
    scopes: List[str] = field(default_factory=list)


class CommandRoute:
    """
    Wrapper for a command exposed as an HTTP route.

    Handles request parsing, command execution, and response formatting.
    """

    __slots__ = ("command_class", "config", "auth_config")

    def __init__(
        self,
        command_class: Type[Command],
        config: Optional[RouteConfig] = None,
        auth_config: Optional[AuthConfig] = None,
    ):
        self.command_class = command_class
        self.config = config or self._default_config(command_class)
        self.auth_config = auth_config

    @staticmethod
    def _default_config(command_class: Type[Command]) -> RouteConfig:
        """Generate default route config from command"""
        name = command_class.full_name()
        # Convert CamelCase to kebab-case for URL
        path = "/" + "/".join(part.lower() for part in name.split("::"))

        # Get domain as tag if available
        tags = []
        if hasattr(command_class, "_domain") and command_class._domain:
            domain = command_class._domain
            # _domain can be a Domain object or a string
            domain_name = domain.name if hasattr(domain, "name") else str(domain)
            tags.append(domain_name)

        return RouteConfig(
            path=path,
            method="POST",
            tags=tags,
            summary=command_class.description() or name,
            description=command_class.__doc__,
            operation_id=name.replace("::", "_"),
        )

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the command and return response dict"""
        try:
            outcome = self.command_class.run(**inputs)
            return self._format_response(outcome)
        except Exception as e:
            logger.exception(f"Error executing {self.command_class.full_name()}")
            return {"success": False, "errors": [{"message": str(e), "symbol": "internal_error"}]}

    async def execute_async(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute async command and return response dict"""
        try:
            if issubclass(self.command_class, AsyncCommand):
                outcome = await self.command_class.run_async(**inputs)
            else:
                outcome = self.command_class.run(**inputs)
            return self._format_response(outcome)
        except Exception as e:
            logger.exception(f"Error executing {self.command_class.full_name()}")
            return {"success": False, "errors": [{"message": str(e), "symbol": "internal_error"}]}

    def _format_response(self, outcome: CommandOutcome) -> Dict[str, Any]:
        """Format command outcome as HTTP response"""
        if outcome.is_success():
            result = outcome.unwrap()
            # Handle Pydantic models
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            elif hasattr(result, "__dict__"):
                result = result.__dict__

            return {"success": True, "result": result}
        else:
            errors = []
            for error in outcome.errors:
                err_dict = {"symbol": getattr(error, "symbol", "error"), "message": str(error)}
                if hasattr(error, "path") and error.path:
                    err_dict["path"] = error.path
                if hasattr(error, "context") and error.context:
                    err_dict["context"] = error.context
                errors.append(err_dict)

            return {"success": False, "errors": errors}


class HTTPConnector:
    """
    FastAPI HTTP Connector for exposing commands as REST endpoints.

    Automatically generates routes from registered commands.

    Usage:
        from fastapi import FastAPI
        from foobara_py.connectors.http import HTTPConnector

        app = FastAPI()
        connector = HTTPConnector(app)

        # Register individual commands
        connector.register(CreateUser)

        # Register all commands from a domain
        connector.register_domain(users_domain)

        # Custom route configuration
        connector.register(
            CreateUser,
            config=RouteConfig(path="/users", method="POST", tags=["Users"])
        )

        # With authentication
        connector.register(
            DeleteUser,
            auth_config=AuthConfig(enabled=True, dependency=get_current_user)
        )

    The connector adds the following endpoints:
        - POST /commands/{command_name} - Execute command
        - GET /manifest - List all available commands
        - GET /manifest/{command_name} - Get specific command info
        - GET /health - Health check endpoint
    """

    __slots__ = (
        "_app",
        "_routes",
        "_prefix",
        "_auth_config",
        "_middleware",
        "_manifest_enabled",
        "_health_enabled",
    )

    def __init__(
        self,
        app: Any = None,  # FastAPI instance (Any to avoid hard dependency)
        prefix: str = "",
        auth_config: Optional[AuthConfig] = None,
        manifest_enabled: bool = True,
        health_enabled: bool = True,
    ):
        """
        Initialize HTTP connector.

        Args:
            app: FastAPI application instance
            prefix: URL prefix for all routes (e.g., "/api/v1")
            auth_config: Default authentication config for all routes
            manifest_enabled: Enable /manifest endpoint
            health_enabled: Enable /health endpoint
        """
        self._app = app
        self._routes: Dict[str, CommandRoute] = {}
        self._prefix = prefix.rstrip("/") if prefix else ""
        self._auth_config = auth_config
        self._middleware: List[Callable] = []
        self._manifest_enabled = manifest_enabled
        self._health_enabled = health_enabled

        if app is not None:
            self._setup_builtin_routes()

    def register(
        self,
        command_class: Type[Command],
        config: Optional[RouteConfig] = None,
        auth_config: Optional[AuthConfig] = None,
    ) -> "HTTPConnector":
        """
        Register a command as an HTTP endpoint.

        Args:
            command_class: Command class to register
            config: Optional route configuration
            auth_config: Optional authentication configuration

        Returns:
            Self for chaining
        """
        # Use provided auth config, fall back to connector default
        effective_auth = auth_config or self._auth_config

        route = CommandRoute(command_class, config, effective_auth)
        name = command_class.full_name()
        self._routes[name] = route

        if self._app is not None:
            self._add_route(route)

        logger.debug(f"Registered command: {name} at {route.config.path}")
        return self

    def register_domain(
        self, domain: Domain, auth_config: Optional[AuthConfig] = None
    ) -> "HTTPConnector":
        """
        Register all commands from a domain.

        Args:
            domain: Domain containing commands to register
            auth_config: Optional auth config for all domain commands

        Returns:
            Self for chaining
        """
        # Access internal _commands dict
        commands = getattr(domain, "_commands", {})
        for command_class in commands.values():
            self.register(command_class, auth_config=auth_config)

        logger.debug(f"Registered domain: {domain.name} with {len(commands)} commands")
        return self

    def register_organization(
        self, org: Organization, auth_config: Optional[AuthConfig] = None
    ) -> "HTTPConnector":
        """
        Register all commands from all domains in an organization.

        Args:
            org: Organization containing domains to register
            auth_config: Optional auth config for all commands

        Returns:
            Self for chaining
        """
        # Use list_domains() method or access internal _domains
        domains = (
            org.list_domains()
            if hasattr(org, "list_domains")
            else getattr(org, "_domains", {}).values()
        )
        for domain in domains:
            self.register_domain(domain, auth_config=auth_config)

        logger.debug(f"Registered organization: {org.name}")
        return self

    def add_middleware(self, middleware: Callable) -> "HTTPConnector":
        """
        Add middleware function to process requests/responses.

        Args:
            middleware: Middleware function

        Returns:
            Self for chaining
        """
        self._middleware.append(middleware)
        return self

    def _setup_builtin_routes(self) -> None:
        """Setup built-in routes (manifest, health)"""
        if self._manifest_enabled:
            self._add_manifest_routes()

        if self._health_enabled:
            self._add_health_route()

    def _add_manifest_routes(self) -> None:
        """Add manifest endpoints"""
        try:
            from fastapi import APIRouter
            from fastapi.responses import JSONResponse

            router = APIRouter(prefix=self._prefix, tags=["Manifest"])

            @router.get("/manifest")
            async def get_manifest():
                """Get manifest of all available commands"""
                return JSONResponse(content=self.get_manifest())

            @router.get("/manifest/{command_name:path}")
            async def get_command_manifest(command_name: str):
                """Get manifest for a specific command"""
                # Replace slashes with :: for full name lookup
                full_name = command_name.replace("/", "::")
                manifest = self.get_command_manifest(full_name)
                if manifest is None:
                    return JSONResponse(
                        status_code=HTTPStatus.NOT_FOUND,
                        content={"error": f"Command not found: {command_name}"},
                    )
                return JSONResponse(content=manifest)

            self._app.include_router(router)

        except ImportError:
            logger.warning("FastAPI not installed, skipping manifest routes")

    def _add_health_route(self) -> None:
        """Add health check endpoint"""
        try:
            from fastapi import APIRouter
            from fastapi.responses import JSONResponse

            router = APIRouter(prefix=self._prefix, tags=["Health"])

            @router.get("/health")
            async def health_check():
                """Health check endpoint"""
                return JSONResponse(
                    content={"status": "healthy", "commands_registered": len(self._routes)}
                )

            self._app.include_router(router)

        except ImportError:
            logger.warning("FastAPI not installed, skipping health route")

    def _add_route(self, route: CommandRoute) -> None:
        """Add a command route to the FastAPI app"""
        try:
            from fastapi import APIRouter, Depends
            from fastapi.responses import JSONResponse
            from pydantic import BaseModel

            config = route.config
            path = f"{self._prefix}{config.path}"

            # Create request model from command inputs
            inputs_type = route.command_class.inputs_type()

            # Build dependencies list
            dependencies = []
            if route.auth_config and route.auth_config.enabled and route.auth_config.dependency:
                dependencies.append(Depends(route.auth_config.dependency))

            # Create the endpoint handler
            if issubclass(route.command_class, AsyncCommand):

                async def handler(inputs: inputs_type, _route=route) -> JSONResponse:
                    result = await _route.execute_async(inputs.model_dump())
                    status = HTTPStatus.OK if result["success"] else HTTPStatus.UNPROCESSABLE_ENTITY
                    return JSONResponse(content=result, status_code=status)
            else:

                async def handler(inputs: inputs_type, _route=route) -> JSONResponse:
                    result = _route.execute(inputs.model_dump())
                    status = HTTPStatus.OK if result["success"] else HTTPStatus.UNPROCESSABLE_ENTITY
                    return JSONResponse(content=result, status_code=status)

            # Add route based on method
            method = config.method.upper()
            route_kwargs = {
                "path": path,
                "response_class": JSONResponse,
                "summary": config.summary,
                "description": config.description,
                "operation_id": config.operation_id,
                "tags": config.tags or None,
                "deprecated": config.deprecated,
                "include_in_schema": config.include_in_schema,
                "dependencies": dependencies or None,
            }

            if method == "POST":
                self._app.post(**route_kwargs)(handler)
            elif method == "GET":
                self._app.get(**route_kwargs)(handler)
            elif method == "PUT":
                self._app.put(**route_kwargs)(handler)
            elif method == "DELETE":
                self._app.delete(**route_kwargs)(handler)
            elif method == "PATCH":
                self._app.patch(**route_kwargs)(handler)
            else:
                self._app.api_route(methods=[method], **route_kwargs)(handler)

        except ImportError:
            logger.warning("FastAPI not installed, cannot add route")

    def get_manifest(self) -> Dict[str, Any]:
        """
        Generate manifest of all registered commands.

        Returns:
            Dict with command metadata for API discovery
        """
        commands = {}
        for name, route in self._routes.items():
            cmd = route.command_class
            commands[name] = {
                "name": name,
                "path": f"{self._prefix}{route.config.path}",
                "method": route.config.method,
                "description": cmd.description() or "",
                "inputs_schema": cmd.inputs_schema(),
                "tags": route.config.tags,
                "deprecated": route.config.deprecated,
            }

        return {
            "version": "1.0",
            "commands": commands,
            "count": len(commands),
            "prefix": self._prefix,
        }

    def get_command_manifest(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get manifest for a specific command.

        Args:
            name: Command full name

        Returns:
            Command manifest dict or None if not found
        """
        route = self._routes.get(name)
        if not route:
            return None

        cmd = route.command_class
        return {
            "name": name,
            "path": f"{self._prefix}{route.config.path}",
            "method": route.config.method,
            "description": cmd.description() or "",
            "inputs_schema": cmd.inputs_schema(),
            "result_schema": getattr(cmd, "result_schema", lambda: None)(),
            "tags": route.config.tags,
            "deprecated": route.config.deprecated,
            "possible_errors": getattr(cmd, "possible_errors", lambda: [])(),
        }

    def execute(self, command_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command by name.

        Useful for testing or programmatic access.

        Args:
            command_name: Full command name
            inputs: Command inputs

        Returns:
            Response dict with success/result or success/errors
        """
        route = self._routes.get(command_name)
        if not route:
            return {
                "success": False,
                "errors": [
                    {"message": f"Command not found: {command_name}", "symbol": "not_found"}
                ],
            }
        return route.execute(inputs)

    async def execute_async(self, command_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command asynchronously by name.

        Args:
            command_name: Full command name
            inputs: Command inputs

        Returns:
            Response dict
        """
        route = self._routes.get(command_name)
        if not route:
            return {
                "success": False,
                "errors": [
                    {"message": f"Command not found: {command_name}", "symbol": "not_found"}
                ],
            }
        return await route.execute_async(inputs)

    @property
    def routes(self) -> Dict[str, CommandRoute]:
        """Get all registered routes"""
        return self._routes.copy()

    def __len__(self) -> int:
        return len(self._routes)

    def __contains__(self, name: str) -> bool:
        return name in self._routes


def create_http_app(
    commands: Optional[List[Type[Command]]] = None,
    domains: Optional[List[Domain]] = None,
    title: str = "Foobara API",
    version: str = "1.0.0",
    prefix: str = "",
    **fastapi_kwargs,
) -> Any:
    """
    Create a FastAPI app with commands pre-registered.

    Convenience function for quick API setup.

    Args:
        commands: List of command classes to register
        domains: List of domains to register
        title: API title for OpenAPI
        version: API version
        prefix: URL prefix
        **fastapi_kwargs: Additional FastAPI constructor arguments

    Returns:
        Configured FastAPI application

    Example:
        app = create_http_app(
            commands=[CreateUser, GetUser],
            title="User API",
            version="1.0.0"
        )
    """
    try:
        from fastapi import FastAPI
    except ImportError:
        raise ImportError(
            "FastAPI is required for HTTP connector. Install with: pip install fastapi"
        )

    app = FastAPI(title=title, version=version, **fastapi_kwargs)
    connector = HTTPConnector(app, prefix=prefix)

    if commands:
        for cmd in commands:
            connector.register(cmd)

    if domains:
        for domain in domains:
            connector.register_domain(domain)

    return app
