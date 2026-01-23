"""Tests for WebSocket Connector."""

import asyncio
import json

import pytest
from pydantic import BaseModel

from foobara_py import Command
from foobara_py.core.registry import CommandRegistry
from foobara_py.connectors.websocket import (
    Subscription,
    WebSocketConfig,
    WebSocketConnection,
    WebSocketConnector,
    WebSocketMessage,
    WebSocketMessageType,
    create_fastapi_websocket_handler,
)


# Test models and commands
class EchoInputs(BaseModel):
    message: str


class EchoResult(BaseModel):
    echoed: str


class EchoCommand(Command[EchoInputs, EchoResult]):
    """Echo a message back."""

    Inputs = EchoInputs
    Result = EchoResult

    def execute(self) -> EchoResult:
        return EchoResult(echoed=self.inputs.message)


class CounterInputs(BaseModel):
    start: int = 0


class CounterResult(BaseModel):
    count: int


_counter = 0


class CounterCommand(Command[CounterInputs, CounterResult]):
    """Return an incrementing counter."""

    Inputs = CounterInputs
    Result = CounterResult

    def execute(self) -> CounterResult:
        global _counter
        _counter += 1
        return CounterResult(count=_counter)


class FailingCommand(Command):
    """A command that always fails."""

    def execute(self):
        raise ValueError("Intentional failure")


class TestWebSocketMessage:
    """Tests for WebSocketMessage class."""

    def test_create_message(self):
        msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            command="EchoCommand",
            inputs={"message": "hello"},
        )
        assert msg.type == WebSocketMessageType.EXECUTE
        assert msg.command == "EchoCommand"
        assert msg.inputs == {"message": "hello"}

    def test_to_dict(self):
        msg = WebSocketMessage(
            type=WebSocketMessageType.RESULT,
            id="test-123",
            result={"data": "value"},
        )
        d = msg.to_dict()
        assert d["type"] == "result"
        assert d["id"] == "test-123"
        assert d["result"] == {"data": "value"}

    def test_to_json(self):
        msg = WebSocketMessage(
            type=WebSocketMessageType.PING,
            id="ping-1",
        )
        json_str = msg.to_json()
        assert '"type": "ping"' in json_str
        assert '"id": "ping-1"' in json_str

    def test_from_dict(self):
        data = {
            "type": "execute",
            "id": "msg-1",
            "command": "TestCommand",
            "inputs": {"key": "value"},
        }
        msg = WebSocketMessage.from_dict(data)
        assert msg.type == WebSocketMessageType.EXECUTE
        assert msg.id == "msg-1"
        assert msg.command == "TestCommand"

    def test_from_json(self):
        json_str = '{"type": "ping", "id": "ping-2"}'
        msg = WebSocketMessage.from_json(json_str)
        assert msg.type == WebSocketMessageType.PING
        assert msg.id == "ping-2"


class TestWebSocketConfig:
    """Tests for WebSocket configuration."""

    def test_default_config(self):
        config = WebSocketConfig()
        assert config.ping_interval == 30.0
        assert config.max_message_size == 1024 * 1024
        assert config.enable_subscriptions is True
        assert config.require_auth is False

    def test_custom_config(self):
        config = WebSocketConfig(
            ping_interval=10.0,
            require_auth=True,
            max_concurrent_commands=5,
        )
        assert config.ping_interval == 10.0
        assert config.require_auth is True
        assert config.max_concurrent_commands == 5


class TestSubscription:
    """Tests for Subscription class."""

    def test_create_subscription(self):
        sub = Subscription(
            subscription_id="sub-1",
            command_name="TestCommand",
            inputs={"key": "value"},
            interval=2.0,
        )
        assert sub.subscription_id == "sub-1"
        assert sub.command_name == "TestCommand"
        assert sub.interval == 2.0
        assert sub.active is True

    def test_cancel_subscription(self):
        sub = Subscription(
            subscription_id="sub-2",
            command_name="TestCommand",
            inputs={},
        )
        sub.cancel()
        assert sub.active is False


class TestWebSocketConnection:
    """Tests for WebSocketConnection class."""

    @pytest.fixture
    def messages(self):
        """Capture sent messages."""
        return []

    @pytest.fixture
    def connection(self, messages):
        """Create a test connection."""
        async def send(msg):
            messages.append(msg)

        config = WebSocketConfig()
        return WebSocketConnection("conn-1", send, config)

    @pytest.mark.asyncio
    async def test_send_message(self, connection, messages):
        msg = WebSocketMessage(type=WebSocketMessageType.PONG, id="test")
        await connection.send_message(msg)
        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "pong"

    @pytest.mark.asyncio
    async def test_send_error(self, connection, messages):
        await connection.send_error("msg-1", "Something went wrong")
        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"
        assert data["error"] == "Something went wrong"

    @pytest.mark.asyncio
    async def test_send_result(self, connection, messages):
        await connection.send_result("msg-2", {"data": "result"})
        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "result"
        assert data["result"] == {"data": "result"}

    def test_add_subscription(self, connection):
        sub = Subscription("sub-1", "TestCommand", {})
        connection.add_subscription(sub)
        assert "sub-1" in connection.subscriptions

    def test_remove_subscription(self, connection):
        sub = Subscription("sub-1", "TestCommand", {})
        connection.add_subscription(sub)
        connection.remove_subscription("sub-1")
        assert "sub-1" not in connection.subscriptions

    def test_max_subscriptions(self, connection):
        connection.config.max_subscriptions_per_connection = 2
        connection.add_subscription(Subscription("sub-1", "Cmd", {}))
        connection.add_subscription(Subscription("sub-2", "Cmd", {}))
        with pytest.raises(ValueError, match="Max subscriptions"):
            connection.add_subscription(Subscription("sub-3", "Cmd", {}))


class TestWebSocketConnector:
    """Tests for WebSocketConnector class."""

    @pytest.fixture
    def registry(self):
        """Create a command registry."""
        reg = CommandRegistry()
        reg.register(EchoCommand)
        reg.register(CounterCommand)
        reg.register(FailingCommand)
        return reg

    @pytest.fixture
    def connector(self, registry):
        """Create a connector instance."""
        return WebSocketConnector(registry)

    @pytest.fixture
    def messages(self):
        """Capture sent messages."""
        return []

    @pytest.mark.asyncio
    async def test_connect(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        assert connection.connection_id == "conn-1"
        assert "conn-1" in connector._connections

    @pytest.mark.asyncio
    async def test_disconnect(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        await connector.disconnect(connection)
        assert "conn-1" not in connector._connections

    @pytest.mark.asyncio
    async def test_handle_ping(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        ping_msg = WebSocketMessage(type=WebSocketMessageType.PING, id="ping-1")
        await connector.handle_message(connection, ping_msg.to_json())

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "pong"
        assert data["id"] == "ping-1"

    @pytest.mark.asyncio
    async def test_handle_execute(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        exec_msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            id="exec-1",
            command="EchoCommand",
            inputs={"message": "hello"},
        )
        await connector.handle_message(connection, exec_msg.to_json())

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "result"
        assert data["result"]["echoed"] == "hello"

    @pytest.mark.asyncio
    async def test_handle_execute_command_not_found(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        exec_msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            id="exec-2",
            command="NonExistentCommand",
            inputs={},
        )
        await connector.handle_message(connection, exec_msg.to_json())

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"
        assert "not found" in data["error"]

    @pytest.mark.asyncio
    async def test_handle_execute_missing_command(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        exec_msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            id="exec-3",
        )
        await connector.handle_message(connection, exec_msg.to_json())

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"
        assert "required" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        await connector.handle_message(connection, "not valid json")

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"

    @pytest.mark.asyncio
    async def test_handle_subscribe(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        sub_msg = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE,
            id="sub-1",
            command="CounterCommand",
            inputs={"start": 0},
        )
        await connector.handle_message(connection, sub_msg.to_json())

        # Wait a bit for subscription confirmation
        await asyncio.sleep(0.1)

        # Should have subscribed message
        assert len(messages) >= 1
        data = json.loads(messages[0])
        assert data["type"] == "subscribed"
        assert "subscription_id" in data

        # Cleanup
        for sub in list(connection.subscriptions.values()):
            sub.cancel()

    @pytest.mark.asyncio
    async def test_handle_unsubscribe(self, connector, messages):
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)

        # First subscribe
        sub_msg = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE,
            id="sub-1",
            command="CounterCommand",
            inputs={},
        )
        await connector.handle_message(connection, sub_msg.to_json())
        await asyncio.sleep(0.1)

        # Get subscription ID from response
        sub_response = json.loads(messages[0])
        subscription_id = sub_response["subscription_id"]

        messages.clear()

        # Now unsubscribe
        unsub_msg = WebSocketMessage(
            type=WebSocketMessageType.UNSUBSCRIBE,
            id="unsub-1",
            subscription_id=subscription_id,
        )
        await connector.handle_message(connection, unsub_msg.to_json())

        assert len(messages) >= 1
        data = json.loads(messages[0])
        assert data["type"] == "unsubscribed"

    @pytest.mark.asyncio
    async def test_broadcast(self, connector, messages):
        messages1 = []
        messages2 = []

        async def send1(msg):
            messages1.append(msg)

        async def send2(msg):
            messages2.append(msg)

        await connector.connect("conn-1", send1)
        await connector.connect("conn-2", send2)

        await connector.broadcast(WebSocketMessage(
            type=WebSocketMessageType.STREAM,
            result={"data": "broadcast"},
        ))

        assert len(messages1) == 1
        assert len(messages2) == 1


class TestWebSocketWithAuth:
    """Tests for WebSocket with authentication enabled."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(EchoCommand)
        return reg

    @pytest.fixture
    def connector(self, registry):
        config = WebSocketConfig(require_auth=True)
        return WebSocketConnector(registry, config)

    @pytest.mark.asyncio
    async def test_execute_without_auth(self, connector):
        messages = []

        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        exec_msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            id="exec-1",
            command="EchoCommand",
            inputs={"message": "hello"},
        )
        await connector.handle_message(connection, exec_msg.to_json())

        data = json.loads(messages[0])
        assert data["type"] == "error"
        assert "Authentication" in data["error"]

    @pytest.mark.asyncio
    async def test_execute_with_auth(self, connector):
        messages = []

        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        connection.authenticated = True  # Simulate authentication

        exec_msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            id="exec-1",
            command="EchoCommand",
            inputs={"message": "hello"},
        )
        await connector.handle_message(connection, exec_msg.to_json())

        data = json.loads(messages[0])
        assert data["type"] == "result"


class TestConcurrencyLimits:
    """Tests for concurrency limits."""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(EchoCommand)
        return reg

    @pytest.mark.asyncio
    async def test_no_concurrent_commands(self, registry):
        config = WebSocketConfig(allow_concurrent_commands=False)
        connector = WebSocketConnector(registry, config)
        messages = []

        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        connection._pending_commands.add("existing-cmd")

        exec_msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            id="exec-1",
            command="EchoCommand",
            inputs={"message": "hello"},
        )
        await connector.handle_message(connection, exec_msg.to_json())

        data = json.loads(messages[0])
        assert data["type"] == "error"
        assert "concurrent" in data["error"].lower()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_create_fastapi_handler(self):
        registry = CommandRegistry()
        connector = WebSocketConnector(registry)
        handler = create_fastapi_websocket_handler(connector)
        assert callable(handler)
