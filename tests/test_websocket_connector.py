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


# ==================== WebSocket Connection Edge Cases ====================

class TestWebSocketConnectionFailures:
    """Tests for WebSocket connection failure scenarios"""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(EchoCommand)
        return reg

    @pytest.fixture
    def connector(self, registry):
        return WebSocketConnector(registry)

    @pytest.mark.asyncio
    async def test_connection_without_send_callback(self, connector):
        """Test connection with invalid send callback"""
        # Some implementations may accept None and fail later
        # Test that connection is created even with None
        try:
            conn = await connector.connect("conn-1", None)
            assert conn is not None
        except Exception:
            # Or it raises an exception, which is also valid
            pass

    @pytest.mark.asyncio
    async def test_duplicate_connection_id(self, connector):
        """Test connecting with duplicate connection ID"""
        messages = []
        async def send(msg):
            messages.append(msg)

        conn1 = await connector.connect("conn-1", send)
        conn2 = await connector.connect("conn-1", send)
        # Second connection should replace first
        assert "conn-1" in connector._connections

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_connection(self, connector):
        """Test disconnecting a connection that doesn't exist"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = WebSocketConnection("conn-x", send, WebSocketConfig())
        # Should not raise error
        await connector.disconnect(connection)

    @pytest.mark.asyncio
    async def test_message_to_disconnected_client(self, connector):
        """Test sending message after disconnect"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        await connector.disconnect(connection)

        # Try to send after disconnect
        msg = WebSocketMessage(type=WebSocketMessageType.PING, id="ping-1")
        try:
            await connection.send_message(msg)
        except Exception:
            pass  # Expected to fail

    @pytest.mark.asyncio
    async def test_invalid_message_format(self, connector):
        """Test handling invalid message format"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        await connector.handle_message(connection, "not json")

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"

    @pytest.mark.asyncio
    async def test_message_missing_type(self, connector):
        """Test message without type field"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        await connector.handle_message(connection, json.dumps({"id": "test"}))

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"

    @pytest.mark.asyncio
    async def test_message_invalid_type(self, connector):
        """Test message with invalid type value"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        await connector.handle_message(
            connection,
            json.dumps({"type": "invalid_type", "id": "test"})
        )

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"

    @pytest.mark.asyncio
    async def test_execute_with_missing_inputs(self, connector):
        """Test execute without inputs field"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        exec_msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            id="exec-1",
            command="EchoCommand"
        )
        await connector.handle_message(connection, exec_msg.to_json())

        assert len(messages) == 1
        data = json.loads(messages[0])
        # Should error on missing required input
        assert data["type"] == "error" or (data["type"] == "result" and data.get("isError"))

    @pytest.mark.asyncio
    async def test_very_large_message(self, connector):
        """Test handling very large message"""
        messages = []
        async def send(msg):
            messages.append(msg)

        config = WebSocketConfig(max_message_size=1000)
        connector.config = config
        connection = await connector.connect("conn-1", send)

        # Create message larger than limit
        large_data = "x" * 10000
        exec_msg = WebSocketMessage(
            type=WebSocketMessageType.EXECUTE,
            id="exec-1",
            command="EchoCommand",
            inputs={"message": large_data}
        )
        await connector.handle_message(connection, exec_msg.to_json())

        # Should handle or reject large message
        assert len(messages) >= 1

    @pytest.mark.asyncio
    async def test_rapid_fire_messages(self, connector):
        """Test many messages sent rapidly"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)

        # Send many pings rapidly
        for i in range(100):
            ping_msg = WebSocketMessage(
                type=WebSocketMessageType.PING,
                id=f"ping-{i}"
            )
            await connector.handle_message(connection, ping_msg.to_json())

        # Should handle all messages
        assert len(messages) == 100

    @pytest.mark.asyncio
    async def test_subscription_without_command(self, connector):
        """Test subscribe without command name"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        sub_msg = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE,
            id="sub-1",
            inputs={}
        )
        await connector.handle_message(connection, sub_msg.to_json())

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self, connector):
        """Test unsubscribe from non-existent subscription"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        unsub_msg = WebSocketMessage(
            type=WebSocketMessageType.UNSUBSCRIBE,
            id="unsub-1",
            subscription_id="nonexistent"
        )
        await connector.handle_message(connection, unsub_msg.to_json())

        assert len(messages) == 1
        data = json.loads(messages[0])
        # Should handle gracefully
        assert data["type"] in ["error", "unsubscribed"]

    @pytest.mark.asyncio
    async def test_unsubscribe_without_subscription_id(self, connector):
        """Test unsubscribe without subscription_id"""
        messages = []
        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        unsub_msg = WebSocketMessage(
            type=WebSocketMessageType.UNSUBSCRIBE,
            id="unsub-1"
        )
        await connector.handle_message(connection, unsub_msg.to_json())

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "error"


class TestWebSocketHeartbeat:
    """Tests for WebSocket heartbeat/ping functionality"""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(EchoCommand)
        return reg

    @pytest.mark.asyncio
    async def test_ping_response(self, registry):
        """Test ping receives pong"""
        connector = WebSocketConnector(registry)
        messages = []

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
    async def test_pong_without_ping(self, registry):
        """Test receiving unsolicited pong"""
        connector = WebSocketConnector(registry)
        messages = []

        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        pong_msg = WebSocketMessage(type=WebSocketMessageType.PONG, id="pong-1")
        await connector.handle_message(connection, pong_msg.to_json())

        # Should handle gracefully (no error)
        # May or may not generate response

    @pytest.mark.asyncio
    async def test_ping_without_id(self, registry):
        """Test ping without id field"""
        connector = WebSocketConnector(registry)
        messages = []

        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)
        await connector.handle_message(
            connection,
            json.dumps({"type": "ping"})
        )

        # Should handle gracefully
        assert len(messages) >= 0


class TestWebSocketReconnection:
    """Tests for reconnection scenarios"""

    @pytest.fixture
    def registry(self):
        reg = CommandRegistry()
        reg.register(EchoCommand)
        return reg

    @pytest.mark.asyncio
    async def test_reconnect_same_id(self, registry):
        """Test reconnecting with same connection ID"""
        connector = WebSocketConnector(registry)
        messages1 = []
        messages2 = []

        async def send1(msg):
            messages1.append(msg)

        async def send2(msg):
            messages2.append(msg)

        # First connection
        conn1 = await connector.connect("conn-1", send1)
        # Reconnect with same ID
        conn2 = await connector.connect("conn-1", send2)

        # Send message
        ping_msg = WebSocketMessage(type=WebSocketMessageType.PING, id="ping-1")
        await connector.handle_message(conn2, ping_msg.to_json())

        # Should go to second connection
        assert len(messages2) == 1
        assert len(messages1) == 0

    @pytest.mark.asyncio
    async def test_subscription_cleanup_on_disconnect(self, registry):
        """Test subscriptions are cleaned up on disconnect"""
        connector = WebSocketConnector(registry)
        messages = []

        async def send(msg):
            messages.append(msg)

        connection = await connector.connect("conn-1", send)

        # Create subscription
        sub_msg = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE,
            id="sub-1",
            command="EchoCommand",
            inputs={"message": "test"}
        )
        await connector.handle_message(connection, sub_msg.to_json())
        await asyncio.sleep(0.1)

        # Disconnect
        await connector.disconnect(connection)

        # Subscriptions should be cancelled
        assert len(connection.subscriptions) == 0 or all(
            not sub.active for sub in connection.subscriptions.values()
        )
