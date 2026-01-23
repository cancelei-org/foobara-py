"""
WebSocket Connector for Foobara commands.

Provides real-time bidirectional communication for command execution,
streaming results, and subscriptions.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type

from pydantic import BaseModel

from foobara_py.core.command import AsyncCommand, Command
from foobara_py.core.registry import CommandRegistry


class WebSocketMessageType(Enum):
    """WebSocket message types."""

    # Client -> Server
    EXECUTE = "execute"  # Execute a command
    SUBSCRIBE = "subscribe"  # Subscribe to command results
    UNSUBSCRIBE = "unsubscribe"  # Unsubscribe from results
    PING = "ping"  # Keep-alive ping

    # Server -> Client
    RESULT = "result"  # Command result
    ERROR = "error"  # Error message
    STREAM = "stream"  # Streaming data
    SUBSCRIBED = "subscribed"  # Subscription confirmed
    UNSUBSCRIBED = "unsubscribed"  # Unsubscription confirmed
    PONG = "pong"  # Keep-alive pong


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""

    type: WebSocketMessageType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    subscription_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            "type": self.type.value,
            "id": self.id,
        }
        if self.command:
            data["command"] = self.command
        if self.inputs:
            data["inputs"] = self.inputs
        if self.result is not None:
            data["result"] = self.result
        if self.error:
            data["error"] = self.error
        if self.subscription_id:
            data["subscription_id"] = self.subscription_id
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebSocketMessage":
        """Create from dictionary."""
        return cls(
            type=WebSocketMessageType(data["type"]),
            id=data.get("id", str(uuid.uuid4())),
            command=data.get("command"),
            inputs=data.get("inputs"),
            result=data.get("result"),
            error=data.get("error"),
            subscription_id=data.get("subscription_id"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class WebSocketConfig:
    """Configuration for WebSocket connector."""

    # Connection settings
    ping_interval: float = 30.0  # Seconds between pings
    ping_timeout: float = 10.0  # Seconds to wait for pong
    max_message_size: int = 1024 * 1024  # 1MB max message

    # Execution settings
    allow_concurrent_commands: bool = True
    max_concurrent_commands: int = 10

    # Subscription settings
    enable_subscriptions: bool = True
    max_subscriptions_per_connection: int = 100

    # Security
    require_auth: bool = False
    auth_timeout: float = 30.0  # Seconds to authenticate


class Subscription:
    """Represents a command subscription."""

    def __init__(
        self,
        subscription_id: str,
        command_name: str,
        inputs: Dict[str, Any],
        interval: float = 1.0,
    ):
        self.subscription_id = subscription_id
        self.command_name = command_name
        self.inputs = inputs
        self.interval = interval
        self.active = True
        self._task: Optional[asyncio.Task] = None

    def cancel(self):
        """Cancel the subscription."""
        self.active = False
        if self._task and not self._task.done():
            self._task.cancel()


class WebSocketConnection:
    """Represents a WebSocket connection."""

    def __init__(
        self,
        connection_id: str,
        send_func: Callable[[str], Any],
        config: WebSocketConfig,
    ):
        self.connection_id = connection_id
        self.send = send_func
        self.config = config
        self.authenticated = not config.require_auth
        self.user: Optional[Dict[str, Any]] = None
        self.subscriptions: Dict[str, Subscription] = {}
        self._pending_commands: Set[str] = set()

    async def send_message(self, message: WebSocketMessage):
        """Send a message to the client."""
        await self.send(message.to_json())

    async def send_error(self, message_id: str, error: str):
        """Send an error message."""
        msg = WebSocketMessage(
            type=WebSocketMessageType.ERROR,
            id=message_id,
            error=error,
        )
        await self.send_message(msg)

    async def send_result(self, message_id: str, result: Any):
        """Send a result message."""
        msg = WebSocketMessage(
            type=WebSocketMessageType.RESULT,
            id=message_id,
            result=result,
        )
        await self.send_message(msg)

    def add_subscription(self, subscription: Subscription):
        """Add a subscription."""
        if len(self.subscriptions) >= self.config.max_subscriptions_per_connection:
            raise ValueError("Max subscriptions reached")
        self.subscriptions[subscription.subscription_id] = subscription

    def remove_subscription(self, subscription_id: str):
        """Remove a subscription."""
        if subscription_id in self.subscriptions:
            self.subscriptions[subscription_id].cancel()
            del self.subscriptions[subscription_id]

    def close(self):
        """Close the connection and cleanup."""
        for sub in self.subscriptions.values():
            sub.cancel()
        self.subscriptions.clear()


class WebSocketConnector:
    """WebSocket connector for Foobara commands.

    Provides real-time command execution over WebSocket connections.

    Example usage with FastAPI:

        from fastapi import FastAPI, WebSocket
        from foobara_py.connectors.websocket import WebSocketConnector

        app = FastAPI()
        connector = WebSocketConnector(registry)

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            connection = await connector.connect(
                connection_id=str(uuid.uuid4()),
                send_func=websocket.send_text,
            )
            try:
                while True:
                    data = await websocket.receive_text()
                    await connector.handle_message(connection, data)
            except Exception:
                await connector.disconnect(connection)
    """

    def __init__(
        self,
        registry: Optional[CommandRegistry] = None,
        config: Optional[WebSocketConfig] = None,
    ):
        """Initialize the WebSocket connector.

        Args:
            registry: Command registry to use.
            config: WebSocket configuration.
        """
        self.registry = registry or CommandRegistry()
        self.config = config or WebSocketConfig()
        self._connections: Dict[str, WebSocketConnection] = {}

    async def connect(
        self,
        connection_id: str,
        send_func: Callable[[str], Any],
    ) -> WebSocketConnection:
        """Register a new WebSocket connection.

        Args:
            connection_id: Unique connection identifier.
            send_func: Async function to send messages to client.

        Returns:
            WebSocketConnection instance.
        """
        connection = WebSocketConnection(connection_id, send_func, self.config)
        self._connections[connection_id] = connection
        return connection

    async def disconnect(self, connection: WebSocketConnection):
        """Disconnect and cleanup a connection.

        Args:
            connection: Connection to disconnect.
        """
        connection.close()
        if connection.connection_id in self._connections:
            del self._connections[connection.connection_id]

    async def handle_message(
        self,
        connection: WebSocketConnection,
        raw_message: str,
    ):
        """Handle an incoming WebSocket message.

        Args:
            connection: The connection that received the message.
            raw_message: Raw JSON message string.
        """
        try:
            message = WebSocketMessage.from_json(raw_message)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            await connection.send_error("unknown", f"Invalid message format: {e}")
            return

        # Route message by type
        handlers = {
            WebSocketMessageType.EXECUTE: self._handle_execute,
            WebSocketMessageType.SUBSCRIBE: self._handle_subscribe,
            WebSocketMessageType.UNSUBSCRIBE: self._handle_unsubscribe,
            WebSocketMessageType.PING: self._handle_ping,
        }

        handler = handlers.get(message.type)
        if handler:
            await handler(connection, message)
        else:
            await connection.send_error(message.id, f"Unknown message type: {message.type}")

    async def _handle_execute(
        self,
        connection: WebSocketConnection,
        message: WebSocketMessage,
    ):
        """Handle command execution request."""
        if not connection.authenticated:
            await connection.send_error(message.id, "Authentication required")
            return

        if not message.command:
            await connection.send_error(message.id, "Command name required")
            return

        # Check concurrent command limit
        if not self.config.allow_concurrent_commands:
            if connection._pending_commands:
                await connection.send_error(message.id, "Concurrent commands not allowed")
                return
        elif len(connection._pending_commands) >= self.config.max_concurrent_commands:
            await connection.send_error(message.id, "Max concurrent commands reached")
            return

        # Get command class
        command_class = self.registry.get(message.command)
        if not command_class:
            await connection.send_error(message.id, f"Command not found: {message.command}")
            return

        # Execute command
        connection._pending_commands.add(message.id)
        try:
            inputs = message.inputs or {}

            if issubclass(command_class, AsyncCommand):
                outcome = await command_class.run_async(**inputs)
            else:
                # Run sync command in thread pool
                loop = asyncio.get_event_loop()
                outcome = await loop.run_in_executor(
                    None,
                    lambda: command_class.run(**inputs)
                )

            if outcome.is_success():
                result = outcome.result
                if isinstance(result, BaseModel):
                    result = result.model_dump()
                await connection.send_result(message.id, result)
            else:
                errors = [
                    {
                        "key": str(getattr(err, "symbol", "error")),
                        "message": str(err),
                        "path": getattr(err, "path", None),
                    }
                    for err in (outcome.errors or [])
                ]
                await connection.send_error(message.id, json.dumps(errors))

        except Exception as e:
            await connection.send_error(message.id, str(e))
        finally:
            connection._pending_commands.discard(message.id)

    async def _handle_subscribe(
        self,
        connection: WebSocketConnection,
        message: WebSocketMessage,
    ):
        """Handle subscription request."""
        if not self.config.enable_subscriptions:
            await connection.send_error(message.id, "Subscriptions not enabled")
            return

        if not connection.authenticated:
            await connection.send_error(message.id, "Authentication required")
            return

        if not message.command:
            await connection.send_error(message.id, "Command name required")
            return

        # Verify command exists
        command_class = self.registry.get(message.command)
        if not command_class:
            await connection.send_error(message.id, f"Command not found: {message.command}")
            return

        # Create subscription
        subscription_id = str(uuid.uuid4())
        subscription = Subscription(
            subscription_id=subscription_id,
            command_name=message.command,
            inputs=message.inputs or {},
        )

        try:
            connection.add_subscription(subscription)
        except ValueError as e:
            await connection.send_error(message.id, str(e))
            return

        # Start subscription task
        subscription._task = asyncio.create_task(
            self._run_subscription(connection, subscription, command_class)
        )

        # Confirm subscription
        await connection.send_message(WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBED,
            id=message.id,
            subscription_id=subscription_id,
        ))

    async def _run_subscription(
        self,
        connection: WebSocketConnection,
        subscription: Subscription,
        command_class: Type[Command],
    ):
        """Run a subscription loop."""
        while subscription.active:
            try:
                # Execute command
                if issubclass(command_class, AsyncCommand):
                    outcome = await command_class.run_async(**subscription.inputs)
                else:
                    loop = asyncio.get_event_loop()
                    outcome = await loop.run_in_executor(
                        None,
                        lambda: command_class.run(**subscription.inputs)
                    )

                if outcome.is_success():
                    result = outcome.result
                    if isinstance(result, BaseModel):
                        result = result.model_dump()

                    await connection.send_message(WebSocketMessage(
                        type=WebSocketMessageType.STREAM,
                        subscription_id=subscription.subscription_id,
                        result=result,
                    ))

                await asyncio.sleep(subscription.interval)

            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue subscription
                await asyncio.sleep(subscription.interval)

    async def _handle_unsubscribe(
        self,
        connection: WebSocketConnection,
        message: WebSocketMessage,
    ):
        """Handle unsubscription request."""
        if not message.subscription_id:
            await connection.send_error(message.id, "Subscription ID required")
            return

        if message.subscription_id not in connection.subscriptions:
            await connection.send_error(message.id, "Subscription not found")
            return

        connection.remove_subscription(message.subscription_id)

        await connection.send_message(WebSocketMessage(
            type=WebSocketMessageType.UNSUBSCRIBED,
            id=message.id,
            subscription_id=message.subscription_id,
        ))

    async def _handle_ping(
        self,
        connection: WebSocketConnection,
        message: WebSocketMessage,
    ):
        """Handle ping message."""
        await connection.send_message(WebSocketMessage(
            type=WebSocketMessageType.PONG,
            id=message.id,
        ))

    def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Get a connection by ID."""
        return self._connections.get(connection_id)

    def get_all_connections(self) -> List[WebSocketConnection]:
        """Get all active connections."""
        return list(self._connections.values())

    async def broadcast(self, message: WebSocketMessage):
        """Broadcast a message to all connections.

        Args:
            message: Message to broadcast.
        """
        for connection in self._connections.values():
            try:
                await connection.send_message(message)
            except Exception:
                pass  # Connection may be closed


def create_fastapi_websocket_handler(
    connector: WebSocketConnector,
) -> Callable:
    """Create a FastAPI WebSocket handler.

    Args:
        connector: WebSocket connector instance.

    Returns:
        Async function that can be used as FastAPI WebSocket endpoint.

    Example:
        connector = WebSocketConnector(registry)
        handler = create_fastapi_websocket_handler(connector)

        @app.websocket("/ws")
        async def ws_endpoint(websocket: WebSocket):
            await handler(websocket)
    """
    async def handler(websocket):
        """FastAPI WebSocket handler."""
        await websocket.accept()

        connection_id = str(uuid.uuid4())
        connection = await connector.connect(
            connection_id=connection_id,
            send_func=websocket.send_text,
        )

        try:
            while True:
                data = await websocket.receive_text()
                await connector.handle_message(connection, data)
        except Exception:
            pass
        finally:
            await connector.disconnect(connection)

    return handler


def create_starlette_websocket_handler(
    connector: WebSocketConnector,
) -> Callable:
    """Create a Starlette WebSocket handler.

    Args:
        connector: WebSocket connector instance.

    Returns:
        Async function for Starlette WebSocket endpoint.
    """
    return create_fastapi_websocket_handler(connector)
