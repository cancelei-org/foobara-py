"""
⚠️  DEPRECATED V1 IMPLEMENTATION ⚠️

This file is deprecated as of v0.3.0 and will be removed in v0.4.0.

DO NOT USE THIS FILE. Use the current implementation instead:
    from foobara_py import MCPConnector, register_command_with_mcp

---

MCP (Model Context Protocol) Connector for foobara-py (LEGACY V1)

Exposes foobara-py commands as MCP tools, enabling integration with
AI assistants like Claude, GPT, and others that support MCP.

Based on analysis of foobara-mcp-connector Ruby gem.
"""

import warnings

warnings.warn(
    "foobara_py._deprecated.connectors.mcp_v1 is deprecated and will be removed in v0.4.0. "
    "Use 'from foobara_py import MCPConnector' instead.",
    DeprecationWarning,
    stacklevel=2,
)

import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from foobara_py.core.command import Command
from foobara_py.core.outcome import CommandOutcome
from foobara_py.core.registry import CommandRegistry
from foobara_py.domain.domain import Domain, Organization


class JsonRpcError(Enum):
    """Standard JSON-RPC 2.0 error codes"""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class MCPSession:
    """MCP protocol session state"""

    protocol_version: str = "2024-11-05"
    initialized: bool = False
    client_info: dict = field(default_factory=dict)
    capabilities: dict = field(default_factory=dict)


@dataclass
class MCPResource:
    """
    MCP Resource definition.

    Resources are read-only data sources that MCP clients can access.
    Use resources to expose entities, configurations, or other data.

    Usage:
        connector.add_resource(MCPResource(
            uri="foobara://users/{id}",
            name="User",
            description="User entity",
            mime_type="application/json",
            entity_class=User
        ))
    """

    uri: str  # URI template, e.g., "foobara://users/{id}"
    name: str
    description: str = ""
    mime_type: str = "application/json"
    entity_class: Optional[Type] = None  # Optional entity class for auto-loading
    loader: Optional[Any] = None  # Custom loader function


class MCPConnector:
    """
    MCP Connector for exposing foobara-py commands as MCP tools.

    Implements JSON-RPC 2.0 protocol with MCP-specific methods:
    - initialize: Protocol handshake
    - tools/list: List available commands with JSON schemas
    - tools/call: Execute a command

    Usage:
        from foobara_py.connectors import MCPConnector

        connector = MCPConnector(
            name="MyService",
            version="1.0.0"
        )

        # Register commands
        connector.connect(CreateUser)
        connector.connect(users_domain)  # All commands in domain

        # Run stdio server
        connector.run_stdio()
    """

    SUPPORTED_VERSIONS = ["2024-11-05", "2025-03-26"]

    def __init__(
        self,
        name: str = "foobara-py",
        version: str = "0.1.0",
        instructions: str = None,
        capture_unknown_error: bool = True,
    ):
        self.name = name
        self.version = version
        self.instructions = instructions
        self.capture_unknown_error = capture_unknown_error

        self._registry = CommandRegistry(name)
        self._session: Optional[MCPSession] = None
        self._resources: Dict[str, MCPResource] = {}  # URI -> Resource

    def connect(self, target: Union[Type[Command], Domain, Organization]) -> None:
        """
        Connect a command, domain, or organization to expose via MCP.

        Args:
            target: Command class, Domain, or Organization to expose
        """
        if isinstance(target, type) and issubclass(target, Command):
            self._registry.register(target)
        elif isinstance(target, Domain):
            for cmd in target.list_commands():
                self._registry.register(cmd)
        elif isinstance(target, Organization):
            for domain in target.list_domains():
                for cmd in domain.list_commands():
                    self._registry.register(cmd)
        else:
            raise TypeError(f"Cannot connect {type(target)}")

    def add_resource(self, resource: MCPResource) -> "MCPConnector":
        """
        Add a resource to expose via MCP.

        Resources are read-only data sources that MCP clients can access.

        Args:
            resource: MCPResource definition

        Returns:
            Self for chaining

        Example:
            connector.add_resource(MCPResource(
                uri="foobara://users/{id}",
                name="User",
                description="User entity",
                entity_class=User
            ))
        """
        self._resources[resource.uri] = resource
        return self

    def add_entity_resource(
        self, entity_class: Type, uri_prefix: str = "foobara://", description: str = None
    ) -> "MCPConnector":
        """
        Convenience method to add an entity as a resource.

        Creates a resource that exposes the entity via its primary key.

        Args:
            entity_class: Entity class to expose
            uri_prefix: URI prefix (default: "foobara://")
            description: Optional description

        Returns:
            Self for chaining

        Example:
            connector.add_entity_resource(User)
            # Creates resource at foobara://user/{id}
        """
        name = entity_class.__name__
        uri = f"{uri_prefix}{name.lower()}/{{id}}"

        resource = MCPResource(
            uri=uri,
            name=name,
            description=description or f"{name} entity",
            mime_type="application/json",
            entity_class=entity_class,
        )
        return self.add_resource(resource)

    def run(self, json_string: str) -> Optional[str]:
        """
        Process a JSON-RPC request and return response.

        Args:
            json_string: Raw JSON-RPC request string

        Returns:
            JSON-RPC response string, or None for notifications
        """
        # Parse JSON
        try:
            request = json.loads(json_string)
        except json.JSONDecodeError as e:
            return self._error_response(None, JsonRpcError.PARSE_ERROR.value, f"Invalid JSON: {e}")

        # Handle batch requests
        if isinstance(request, list):
            if not request:
                return self._error_response(
                    None, JsonRpcError.INVALID_REQUEST.value, "Empty batch request"
                )
            responses = []
            for req in request:
                response = self._handle_request(req)
                if response:  # Skip None (notifications)
                    responses.append(json.loads(response))
            return json.dumps(responses) if responses else None

        return self._handle_request(request)

    def _handle_request(self, request: dict) -> Optional[str]:
        """Handle a single JSON-RPC request"""
        # Validate structure
        if not isinstance(request, dict):
            return self._error_response(
                None, JsonRpcError.INVALID_REQUEST.value, "Request must be object"
            )

        # Check version
        if request.get("jsonrpc") != "2.0":
            return self._error_response(
                request.get("id"), JsonRpcError.INVALID_REQUEST.value, "Invalid JSON-RPC version"
            )

        method = request.get("method")
        if not method:
            return self._error_response(
                request.get("id"), JsonRpcError.INVALID_REQUEST.value, "Missing method"
            )

        params = request.get("params", {})
        request_id = request.get("id")

        # Notifications have no id and return None
        is_notification = request_id is None

        # Route to handler
        try:
            result = self._dispatch(method, params)

            if is_notification:
                return None

            return self._success_response(request_id, result)

        except Exception as e:
            if is_notification:
                return None

            if self.capture_unknown_error:
                return self._error_response(request_id, JsonRpcError.INTERNAL_ERROR.value, str(e))
            raise

    def _dispatch(self, method: str, params: dict) -> Any:
        """Dispatch method to appropriate handler"""
        if method == "initialize":
            return self._handle_initialize(params)
        elif method == "tools/list":
            return self._handle_tools_list(params)
        elif method == "tools/call":
            return self._handle_tools_call(params)
        elif method == "resources/list":
            return self._handle_resources_list(params)
        elif method == "resources/read":
            return self._handle_resources_read(params)
        elif method == "ping":
            return {}
        elif method.startswith("notifications/"):
            return None  # Notifications are ignored
        else:
            raise ValueError(f"Unknown method: {method}")

    def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request"""
        client_version = params.get("protocolVersion", "2024-11-05")

        # Negotiate version (use highest supported <= client version)
        negotiated = "2024-11-05"
        for version in self.SUPPORTED_VERSIONS:
            if version <= client_version:
                negotiated = version

        self._session = MCPSession(
            protocol_version=negotiated,
            initialized=True,
            client_info=params.get("clientInfo", {}),
            capabilities=params.get("capabilities", {}),
        )

        capabilities = {"tools": {"listChanged": False}}

        # Add resources capability if resources are registered
        if self._resources:
            capabilities["resources"] = {"listChanged": False}

        response = {
            "protocolVersion": negotiated,
            "capabilities": capabilities,
            "serverInfo": {"name": self.name, "version": self.version},
        }

        if self.instructions:
            response["instructions"] = self.instructions

        return response

    def _handle_tools_list(self, params: dict) -> dict:
        """Handle tools/list request"""
        return {"tools": self._registry.list_tools()}

    def _handle_tools_call(self, params: dict) -> dict:
        """Handle tools/call request"""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if not name:
            raise ValueError("Missing tool name")

        if not isinstance(arguments, dict):
            raise ValueError("Arguments must be object, not array")

        # Execute command
        outcome = self._registry.execute(name, arguments)

        # Format result
        if outcome.is_success():
            result = outcome.result
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
        else:
            # Format errors
            errors = outcome.to_dict()["errors"]
            return {
                "content": [{"type": "text", "text": json.dumps({"errors": errors}, default=str)}],
                "isError": True,
            }

    def _handle_resources_list(self, params: dict) -> dict:
        """Handle resources/list request"""
        resources = []
        for uri, resource in self._resources.items():
            resources.append(
                {
                    "uri": uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mime_type,
                }
            )
        return {"resources": resources}

    def _handle_resources_read(self, params: dict) -> dict:
        """Handle resources/read request"""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Missing resource URI")

        # Find matching resource (exact match or template match)
        resource = self._resources.get(uri)

        if not resource:
            # Try template matching for URIs like "foobara://user/123"
            resource, uri_params = self._match_resource_template(uri)
        else:
            uri_params = {}

        if not resource:
            raise ValueError(f"Resource not found: {uri}")

        # Load the resource content
        content = self._load_resource(resource, uri_params)

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": resource.mime_type,
                    "text": json.dumps(content, default=str)
                    if not isinstance(content, str)
                    else content,
                }
            ]
        }

    def _match_resource_template(self, uri: str) -> tuple:
        """
        Match a URI against registered resource templates.

        Returns (MCPResource, dict) where dict contains extracted parameters.
        Example: "foobara://user/123" matches "foobara://user/{id}" → ({id: "123"})
        """
        import re

        for template_uri, resource in self._resources.items():
            # Convert template to regex: {param} → (?P<param>[^/]+)
            pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template_uri)
            pattern = f"^{pattern}$"

            match = re.match(pattern, uri)
            if match:
                return resource, match.groupdict()

        return None, {}

    def _load_resource(self, resource: MCPResource, params: dict) -> Any:
        """
        Load resource content using custom loader or entity loading.
        """
        # Use custom loader if provided
        if resource.loader:
            return resource.loader(params)

        # Use entity class for automatic loading
        if resource.entity_class:
            # Get the primary key from params (typically 'id')
            pk = params.get("id")
            if pk is None:
                # Try to find any single param
                if len(params) == 1:
                    pk = list(params.values())[0]

            if pk is not None:
                # Import here to avoid circular imports
                from foobara_py.persistence.repository import RepositoryRegistry

                # Try to convert pk to int if it's a numeric string
                try:
                    pk = int(pk)
                except (ValueError, TypeError):
                    pass  # Keep original type

                repo = RepositoryRegistry.get(resource.entity_class)
                if repo:
                    entity = repo.find(resource.entity_class, pk)
                    if entity:
                        if hasattr(entity, "model_dump"):
                            return entity.model_dump()
                        return entity.__dict__
                    raise ValueError(f"{resource.name} not found with id: {pk}")

            raise ValueError(f"Cannot load {resource.name}: no primary key in URI")

        # No loader or entity class - return empty resource
        return {"uri": resource.uri, "name": resource.name}

    def _success_response(self, request_id: Any, result: Any) -> str:
        """Build success response"""
        return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, default=str)

    def _error_response(self, request_id: Any, code: int, message: str, data: Any = None) -> str:
        """Build error response"""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data

        return json.dumps({"jsonrpc": "2.0", "id": request_id, "error": error}, default=str)

    def run_stdio(self, io_in=None, io_out=None, io_err=None) -> None:
        """
        Run MCP server on stdin/stdout.

        This is the main entry point for running as an MCP server.
        Reads JSON-RPC requests from stdin, writes responses to stdout.
        """
        io_in = io_in or sys.stdin
        io_out = io_out or sys.stdout
        io_err = io_err or sys.stderr

        for line in io_in:
            line = line.strip()
            if not line:
                continue

            try:
                response = self.run(line)
                if response:
                    io_out.write(response + "\n")
                    io_out.flush()
            except Exception as e:
                io_err.write(f"Error: {e}\n")
                io_err.flush()


def create_mcp_server(
    name: str = "foobara-py",
    version: str = "0.1.0",
    commands: List[Type[Command]] = None,
    domains: List[Domain] = None,
) -> MCPConnector:
    """
    Convenience function to create and configure MCP server.

    Usage:
        server = create_mcp_server(
            name="MyService",
            commands=[CreateUser, UpdateUser],
            domains=[billing_domain]
        )
        server.run_stdio()
    """
    connector = MCPConnector(name=name, version=version)

    if commands:
        for cmd in commands:
            connector.connect(cmd)

    if domains:
        for domain in domains:
            connector.connect(domain)

    return connector
