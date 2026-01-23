"""
Enhanced MCP Connector with full Ruby Foobara parity.

Features:
- Full batch request support (JSON-RPC 2.0 compliant)
- Notification handling
- Ping support
- Session management with capabilities
- Enhanced error handling
- Resource and prompt support (MCP spec)
- High-performance JSON processing
"""

import json
import sys
from dataclasses import dataclass, field
from enum import IntEnum
from io import StringIO
from typing import Any, Callable, Dict, List, Optional, Type, Union

from foobara_py.core.command import AsyncCommand, Command
from foobara_py.core.outcome import CommandOutcome
from foobara_py.domain.domain import Domain, Organization


class JsonRpcErrorCode(IntEnum):
    """Standard JSON-RPC 2.0 error codes"""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific error codes
    UNAUTHENTICATED = 401
    NOT_ALLOWED = 403
    NOT_FOUND = 404


# Backward compatibility alias (V1 used JsonRpcError, V2 uses JsonRpcErrorCode)
JsonRpcError = JsonRpcErrorCode


@dataclass(slots=True)
class MCPSession:
    """MCP protocol session state with full capabilities tracking"""

    protocol_version: str = "2024-11-05"
    initialized: bool = False
    client_info: Dict[str, Any] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    request_count: int = 0


class CommandRegistry:
    """
    High-performance command registry for MCP.

    Uses dict for O(1) lookups and maintains insertion order.
    """

    __slots__ = ("_commands", "_name")

    def __init__(self, name: str = "default"):
        self._name = name
        self._commands: Dict[str, Type[Command]] = {}

    def register(self, command_class: Type[Command]) -> None:
        """Register a command class"""
        name = command_class.full_name()
        self._commands[name] = command_class

    def get(self, name: str) -> Optional[Type[Command]]:
        """Get command by full name"""
        return self._commands.get(name)

    def execute(self, name: str, inputs: Dict[str, Any]) -> CommandOutcome:
        """Execute command by name"""
        cmd_class = self.get(name)
        if not cmd_class:
            raise KeyError(f"Command not found: {name}")
        return cmd_class.run(**inputs)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Generate MCP tools list"""
        return [
            {
                "name": cmd.full_name(),
                "description": cmd.description(),
                "inputSchema": cmd.inputs_schema(),
            }
            for cmd in self._commands.values()
        ]

    def __len__(self) -> int:
        return len(self._commands)

    def __contains__(self, name: str) -> bool:
        return name in self._commands


class MCPConnector:
    """
    High-performance MCP Connector with full protocol support.

    Implements JSON-RPC 2.0 with MCP extensions:
    - Batch requests (arrays of requests)
    - Notifications (requests without id)
    - Full method routing
    - Session management
    - Error handling with proper codes

    Usage:
        connector = MCPConnector(
            name="MyService",
            version="1.0.0",
            instructions="Available commands for user management"
        )

        connector.connect(CreateUser)
        connector.connect(users_domain)

        # Run as MCP server
        connector.run_stdio()
    """

    SUPPORTED_VERSIONS = ("2024-11-05", "2025-03-26")

    __slots__ = (
        "name",
        "version",
        "instructions",
        "capture_unknown_error",
        "_registry",
        "_session",
        "_resources",
        "_prompts",
    )

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
        self._resources: Dict[str, Dict[str, Any]] = {}
        self._prompts: Dict[str, Dict[str, Any]] = {}

    # ==================== Connection ====================

    def connect(self, target: Union[Type[Command], Domain, Organization]) -> "MCPConnector":
        """
        Connect a command, domain, or organization to expose via MCP.

        Returns self for chaining.
        """
        if isinstance(target, type) and issubclass(target, (Command, AsyncCommand)):
            self._registry.register(target)
        elif isinstance(target, Domain):
            for cmd in target.list_commands():
                self._registry.register(cmd)
        elif isinstance(target, Organization):
            for domain in target.list_domains():
                for cmd in domain.list_commands():
                    self._registry.register(cmd)
        else:
            raise TypeError(f"Cannot connect {type(target).__name__}")
        return self

    def connect_all(self, *targets) -> "MCPConnector":
        """Connect multiple targets"""
        for target in targets:
            self.connect(target)
        return self

    # ==================== Resource Registration ====================

    def add_resource(
        self, uri: str, name: str, description: str = None, mime_type: str = "text/plain"
    ) -> "MCPConnector":
        """Register a resource"""
        self._resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "mimeType": mime_type,
        }
        return self

    # ==================== Prompt Registration ====================

    def add_prompt(
        self, name: str, description: str = None, arguments: List[Dict[str, Any]] = None
    ) -> "MCPConnector":
        """Register a prompt template"""
        self._prompts[name] = {
            "name": name,
            "description": description,
            "arguments": arguments or [],
        }
        return self

    # ==================== Request Processing ====================

    def run(self, json_string: str) -> Optional[str]:
        """
        Process JSON-RPC request(s) and return response(s).

        Handles both single requests and batch requests (arrays).
        Returns None for pure notifications.
        """
        # Parse JSON
        try:
            request = json.loads(json_string)
        except json.JSONDecodeError as e:
            return self._error_response(None, JsonRpcErrorCode.PARSE_ERROR, f"Invalid JSON: {e}")

        # Handle batch requests
        if isinstance(request, list):
            return self._handle_batch(request)

        # Handle single request
        return self._handle_single(request)

    def _handle_batch(self, requests: List[Any]) -> Optional[str]:
        """
        Handle batch requests (JSON-RPC 2.0 batch).

        Returns array of responses, excluding notifications.
        Returns None if all requests are notifications.
        """
        if not requests:
            return self._error_response(
                None, JsonRpcErrorCode.INVALID_REQUEST, "Empty batch request"
            )

        responses = []
        for req in requests:
            response = self._handle_single(req)
            if response is not None:
                # Parse response to include in batch array
                responses.append(json.loads(response))

        if not responses:
            return None  # All were notifications

        return json.dumps(responses, separators=(",", ":"))

    def _handle_single(self, request: Any) -> Optional[str]:
        """Handle a single JSON-RPC request"""
        # Validate structure
        if not isinstance(request, dict):
            return self._error_response(
                None, JsonRpcErrorCode.INVALID_REQUEST, "Request must be an object"
            )

        # Check JSON-RPC version
        if request.get("jsonrpc") != "2.0":
            return self._error_response(
                request.get("id"),
                JsonRpcErrorCode.INVALID_REQUEST,
                "Invalid or missing jsonrpc version",
            )

        method = request.get("method")
        if not method or not isinstance(method, str):
            return self._error_response(
                request.get("id"), JsonRpcErrorCode.INVALID_REQUEST, "Missing or invalid method"
            )

        params = request.get("params", {})
        request_id = request.get("id")

        # Track session metrics
        if self._session:
            self._session.request_count += 1

        # Notifications have no id
        is_notification = request_id is None

        try:
            result = self._dispatch(method, params)

            if is_notification:
                return None

            return self._success_response(request_id, result)

        except KeyError as e:
            if is_notification:
                return None
            return self._error_response(request_id, JsonRpcErrorCode.NOT_FOUND, str(e))
        except ValueError as e:
            if is_notification:
                return None
            return self._error_response(request_id, JsonRpcErrorCode.INVALID_PARAMS, str(e))
        except Exception as e:
            if is_notification:
                return None
            if self.capture_unknown_error:
                return self._error_response(request_id, JsonRpcErrorCode.INTERNAL_ERROR, str(e))
            raise

    # ==================== Method Dispatch ====================

    def _dispatch(self, method: str, params: Dict[str, Any]) -> Any:
        """Route method to appropriate handler"""
        # MCP lifecycle
        if method == "initialize":
            return self._handle_initialize(params)
        elif method == "initialized":
            return None  # Notification acknowledgment

        # Tools
        elif method == "tools/list":
            return self._handle_tools_list(params)
        elif method == "tools/call":
            return self._handle_tools_call(params)

        # Resources
        elif method == "resources/list":
            return self._handle_resources_list(params)
        elif method == "resources/read":
            return self._handle_resources_read(params)

        # Prompts
        elif method == "prompts/list":
            return self._handle_prompts_list(params)
        elif method == "prompts/get":
            return self._handle_prompts_get(params)

        # Utility
        elif method == "ping":
            return {}

        # Notifications (no response)
        elif method.startswith("notifications/"):
            return None

        else:
            raise ValueError(f"Unknown method: {method}")

    # ==================== Handler Methods ====================

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request (MCP handshake)"""
        client_version = params.get("protocolVersion", "2024-11-05")

        # Negotiate version (use highest supported <= client version)
        negotiated = self.SUPPORTED_VERSIONS[0]
        for version in self.SUPPORTED_VERSIONS:
            if version <= client_version:
                negotiated = version

        self._session = MCPSession(
            protocol_version=negotiated,
            initialized=True,
            client_info=params.get("clientInfo", {}),
            capabilities=params.get("capabilities", {}),
        )

        response = {
            "protocolVersion": negotiated,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {"name": self.name, "version": self.version},
        }

        if self.instructions:
            response["instructions"] = self.instructions

        return response

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request"""
        cursor = params.get("cursor")
        # TODO: Implement pagination with cursor if needed
        return {"tools": self._registry.list_tools()}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if not name:
            raise ValueError("Missing tool name")

        if not isinstance(arguments, dict):
            raise ValueError("Arguments must be an object")

        # Execute command
        outcome = self._registry.execute(name, arguments)

        # Format response
        if outcome.is_success():
            result = outcome.result
            # Handle Pydantic models
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            return {
                "content": [
                    {"type": "text", "text": json.dumps(result, default=str, separators=(",", ":"))}
                ]
            }
        else:
            # Format errors
            errors = [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in outcome.errors]
            return {
                "content": [
                    {"type": "text", "text": json.dumps({"errors": errors}, separators=(",", ":"))}
                ],
                "isError": True,
            }

    def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request"""
        return {"resources": list(self._resources.values())}

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request"""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Missing resource URI")

        resource = self._resources.get(uri)
        if not resource:
            raise KeyError(f"Resource not found: {uri}")

        # Generate content based on URI pattern
        content_text = self._generate_resource_content(uri, resource)

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": resource.get("mimeType", "text/plain"),
                    "text": content_text,
                }
            ]
        }

    def _generate_resource_content(self, uri: str, resource: Dict[str, Any]) -> str:
        """
        Generate content for a resource based on its URI.

        Supports:
        - command://CommandName - Returns command manifest as JSON
        - domain://DomainName - Returns domain manifest as JSON
        - manifest://full - Returns complete manifest as JSON
        """
        import json

        if uri.startswith("command://"):
            # Extract command name and return its manifest
            command_name = uri.replace("command://", "")
            command_class = self._get_command_by_name(command_name)
            if command_class:
                manifest = command_class.reflect()
                return json.dumps(manifest.to_dict(), indent=2)
            return json.dumps({"error": f"Command not found: {command_name}"})

        elif uri.startswith("domain://"):
            # Extract domain name and return its manifest
            domain_name = uri.replace("domain://", "")
            from foobara_py.domain.domain import Domain

            domain = Domain._registry.get(domain_name)
            if domain:
                from foobara_py.manifest.domain_manifest import DomainManifest

                manifest = DomainManifest.from_domain(domain)
                return json.dumps(manifest.to_dict(), indent=2)
            return json.dumps({"error": f"Domain not found: {domain_name}"})

        elif uri.startswith("manifest://"):
            # Return complete manifest
            from foobara_py.manifest.root_manifest import RootManifest

            manifest = RootManifest()
            # Add all registered commands
            for cmd_class in self._registry._commands.values():
                manifest.add_command(cmd_class)
            return json.dumps(manifest.to_dict(), indent=2)

        else:
            # Default: return resource description
            return resource.get("description", "No content available")

    def _get_command_by_name(self, name: str):
        """Get command class by name from registered commands"""
        for cmd_class in self._registry._commands.values():
            if cmd_class.__name__ == name or cmd_class.full_command_symbol() == name:
                return cmd_class
        return None

    def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request"""
        return {"prompts": list(self._prompts.values())}

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request"""
        name = params.get("name")
        if not name:
            raise ValueError("Missing prompt name")

        prompt = self._prompts.get(name)
        if not prompt:
            raise KeyError(f"Prompt not found: {name}")

        # Get arguments provided by client
        arguments = params.get("arguments", {})

        # Render prompt messages with arguments
        messages = self._render_prompt_messages(name, prompt, arguments)

        return {"description": prompt.get("description"), "messages": messages}

    def _render_prompt_messages(
        self, name: str, prompt: Dict[str, Any], arguments: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Render prompt template messages with provided arguments.

        Supports:
        - command_help prompts: Generate help for a command
        - domain_overview prompts: Generate domain overview
        - Custom prompts with template field
        """
        import json

        # Handle built-in prompt types
        if name == "command_help":
            command_name = arguments.get("command_name")
            if not command_name:
                return [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": "Please provide a command_name argument",
                        },
                    }
                ]

            command_class = self._get_command_by_name(command_name)
            if not command_class:
                return [
                    {
                        "role": "user",
                        "content": {"type": "text", "text": f"Command not found: {command_name}"},
                    }
                ]

            # Generate helpful prompt about the command
            manifest = command_class.reflect()
            content = f"""# {manifest.full_name}

{manifest.description or "No description available"}

## Inputs
```json
{json.dumps(manifest.inputs_schema, indent=2) if manifest.inputs_schema else "No inputs"}
```

## Result
```json
{json.dumps(manifest.result_schema, indent=2) if manifest.result_schema else "Unknown result type"}
```

## Domain
{manifest.domain or "Global"}

## Organization
{manifest.organization or "None"}
"""
            if manifest.possible_errors:
                content += f"\n## Possible Errors\n" + "\n".join(
                    f"- {err}" for err in manifest.possible_errors
                )

            return [{"role": "user", "content": {"type": "text", "text": content}}]

        elif name == "domain_overview":
            domain_name = arguments.get("domain_name")
            if not domain_name:
                return [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": "Please provide a domain_name argument",
                        },
                    }
                ]

            from foobara_py.domain.domain import Domain

            domain = Domain._registry.get(domain_name)
            if not domain:
                return [
                    {
                        "role": "user",
                        "content": {"type": "text", "text": f"Domain not found: {domain_name}"},
                    }
                ]

            from foobara_py.manifest.domain_manifest import DomainManifest

            manifest = DomainManifest.from_domain(domain)

            content = f"""# {manifest.full_name}

{manifest.description or "No description available"}

## Statistics
- Commands: {manifest.command_count}
- Types: {manifest.type_count}
- Entities: {manifest.entity_count}

## Dependencies
{", ".join(manifest.dependencies) if manifest.dependencies else "None"}

## Commands
{chr(10).join(f"- {cmd}" for cmd in manifest.command_names)}
"""
            return [{"role": "user", "content": {"type": "text", "text": content}}]

        # Handle custom prompts with template
        elif "template" in prompt:
            # Simple template substitution
            template = prompt["template"]
            rendered = template
            for key, value in arguments.items():
                rendered = rendered.replace(f"{{{key}}}", str(value))

            return [{"role": "user", "content": {"type": "text", "text": rendered}}]

        # Default: return description as message
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": prompt.get("description", "No prompt content available"),
                },
            }
        ]

    # ==================== Response Building ====================

    def _success_response(self, request_id: Any, result: Any) -> str:
        """Build JSON-RPC success response"""
        response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        return json.dumps(response, default=str, separators=(",", ":"))

    def _error_response(self, request_id: Any, code: int, message: str, data: Any = None) -> str:
        """Build JSON-RPC error response"""
        error = {"code": int(code), "message": message}
        if data is not None:
            error["data"] = data

        response = {"jsonrpc": "2.0", "id": request_id, "error": error}
        return json.dumps(response, default=str, separators=(",", ":"))

    # ==================== Server Runners ====================

    def run_stdio(self, io_in=None, io_out=None, io_err=None) -> None:
        """
        Run MCP server on stdin/stdout.

        This is the main entry point for running as an MCP server.
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

    def run_once(self, request: str) -> Optional[str]:
        """Process a single request (for testing)"""
        return self.run(request)


# ==================== Convenience Functions ====================


def create_mcp_server(
    name: str = "foobara-py",
    version: str = "0.1.0",
    instructions: str = None,
    commands: List[Type[Command]] = None,
    domains: List[Domain] = None,
    organizations: List[Organization] = None,
) -> MCPConnector:
    """
    Create and configure an MCP server.

    Usage:
        server = create_mcp_server(
            name="MyService",
            commands=[CreateUser, UpdateUser],
            domains=[billing_domain]
        )
        server.run_stdio()
    """
    connector = MCPConnector(name=name, version=version, instructions=instructions)

    if commands:
        for cmd in commands:
            connector.connect(cmd)

    if domains:
        for domain in domains:
            connector.connect(domain)

    if organizations:
        for org in organizations:
            connector.connect(org)

    return connector
