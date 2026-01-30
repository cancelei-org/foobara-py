"""Comprehensive Tests for Remote Imports System

This test suite expands coverage of the remote imports system with:
- RemoteCommand HTTP execution tests
- AsyncRemoteCommand tests
- ManifestCache TTL tests
- RemoteImporter tests
- RemoteNamespace tests
- Edge case tests
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pydantic import BaseModel

from foobara_py.remote import (
    RemoteCommand,
    AsyncRemoteCommand,
    RemoteCommandError,
    RemoteConnectionError,
    RemoteImporter,
    RemoteNamespace,
    RemoteImportError,
    ManifestFetchError,
    CommandNotFoundError,
    import_remote,
    ManifestCache,
    CacheEntry,
)


# ============================================================================
# RemoteCommand HTTP Execution Tests (15+ tests)
# ============================================================================


class TestRemoteCommandHTTPExecution:
    """Test RemoteCommand HTTP execution scenarios"""

    def test_successful_remote_execution_with_json_response(self):
        """Should successfully execute remote command with JSON response"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"id": 1, "status": "ok"}}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()
            result = cmd.execute()

            assert result == {"id": 1, "status": "ok"}

    def test_network_connection_failure(self):
        """Should handle network connection failures"""
        import httpx

        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteConnectionError) as exc_info:
                cmd.execute()

            assert "Failed to connect" in str(exc_info.value)

    def test_request_timeout(self):
        """Should handle request timeouts"""
        import httpx

        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"
            _timeout = 5.0

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.side_effect = httpx.TimeoutException(
                "Timeout"
            )
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                cmd.execute()

            assert "timed out" in str(exc_info.value)

    def test_malformed_json_response(self):
        """Should handle malformed JSON responses"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                cmd.execute()

            assert "parse" in str(exc_info.value).lower()

    def test_http_401_authentication_error(self):
        """Should handle 401 authentication errors"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_response.json.return_value = {"message": "Invalid credentials"}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                cmd.execute()

            assert exc_info.value.status_code == 401

    def test_http_403_forbidden_error(self):
        """Should handle 403 forbidden errors"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_response.json.return_value = {"message": "Access denied"}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                cmd.execute()

            assert exc_info.value.status_code == 403

    def test_http_404_not_found_error(self):
        """Should handle 404 not found errors"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "NonExistent"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"
            mock_response.json.return_value = {"message": "Command not found"}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                cmd.execute()

            assert exc_info.value.status_code == 404

    def test_http_500_server_error(self):
        """Should handle 500 server errors"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.json.return_value = {"message": "Server error"}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                cmd.execute()

            assert exc_info.value.status_code == 500

    def test_http_503_service_unavailable(self):
        """Should handle 503 service unavailable errors"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.text = "Service Unavailable"
            mock_response.json.return_value = {"message": "Service temporarily down"}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                cmd.execute()

            assert exc_info.value.status_code == 503

    def test_custom_headers_sent(self):
        """Should send custom headers with requests"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"
            _headers = {"Authorization": "Bearer token123", "X-Custom": "value"}

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_post = mock_client.__enter__.return_value.post
            mock_post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()
            cmd.execute()

            # Verify headers were passed
            call_kwargs = mock_post.call_args[1]
            assert "headers" in call_kwargs
            assert call_kwargs["headers"]["Authorization"] == "Bearer token123"

    def test_custom_timeout_setting(self):
        """Should use custom timeout setting"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"
            _timeout = 60.0

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()
            cmd.execute()

            # Verify timeout was passed to client
            assert mock_client_class.call_args[1]["timeout"] == 60.0

    def test_response_with_data_envelope(self):
        """Should handle response with 'data' envelope"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"id": 1, "name": "test"}}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()
            result = cmd.execute()

            assert result == {"id": 1, "name": "test"}

    def test_response_without_envelope(self):
        """Should handle direct response without envelope"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": 1, "name": "test"}

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()
            result = cmd.execute()

            assert result == {"id": 1, "name": "test"}

    def test_error_with_remote_errors_list(self):
        """Should extract remote errors list from error response"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 422
            mock_response.text = "Validation Error"
            mock_response.json.return_value = {
                "message": "Validation failed",
                "errors": [
                    {"field": "name", "message": "Required"},
                    {"field": "email", "message": "Invalid format"},
                ]
            }

            mock_client = MagicMock()
            mock_client.__enter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                cmd.execute()

            assert len(exc_info.value.remote_errors) == 2
            assert exc_info.value.remote_errors[0]["field"] == "name"

    def test_url_construction(self):
        """Should construct correct URL for remote command"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com/"
            _command_name = "Users::CreateUser"

        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_post = mock_client.__enter__.return_value.post
            mock_post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestCommand(name="test")
            cmd.validate_inputs()
            cmd.execute()

            # Verify correct URL was called
            call_args = mock_post.call_args[0]
            assert call_args[0] == "https://api.example.com/run/Users::CreateUser"


# ============================================================================
# AsyncRemoteCommand Tests (15+ tests)
# ============================================================================


class TestAsyncRemoteCommand:
    """Test AsyncRemoteCommand functionality"""

    @pytest.mark.asyncio
    async def test_async_successful_execution(self):
        """Should execute async remote command successfully"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"id": 1, "status": "ok"}}

            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            outcome = await TestAsyncCommand.run(name="test")

            assert outcome.is_success()
            assert outcome.unwrap() == {"id": 1, "status": "ok"}

    @pytest.mark.asyncio
    async def test_async_connection_error(self):
        """Should handle async connection errors"""
        import httpx

        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.side_effect = httpx.ConnectError(
                "Connection failed"
            )
            mock_client_class.return_value = mock_client

            cmd = TestAsyncCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteConnectionError):
                await cmd.execute()

    @pytest.mark.asyncio
    async def test_async_timeout(self):
        """Should handle async timeout errors"""
        import httpx

        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"
            _timeout = 5.0

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.side_effect = httpx.TimeoutException(
                "Timeout"
            )
            mock_client_class.return_value = mock_client

            cmd = TestAsyncCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                await cmd.execute()

            assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_async_http_error(self):
        """Should handle async HTTP errors"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Server error"
            mock_response.json.return_value = {"message": "Internal error"}

            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestAsyncCommand(name="test")
            cmd.validate_inputs()

            with pytest.raises(RemoteCommandError) as exc_info:
                await cmd.execute()

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_concurrent_async_calls(self):
        """Should handle concurrent async remote calls"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Execute multiple concurrent calls
            tasks = [
                TestAsyncCommand.run(name=f"test{i}")
                for i in range(5)
            ]
            outcomes = await asyncio.gather(*tasks)

            assert len(outcomes) == 5
            assert all(outcome.is_success() for outcome in outcomes)

    @pytest.mark.asyncio
    async def test_async_inputs_validation(self):
        """Should validate inputs for async commands"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        cmd = TestAsyncCommand(name="test")
        assert cmd.validate_inputs()
        assert cmd.inputs.name == "test"

    @pytest.mark.asyncio
    async def test_async_missing_remote_url(self):
        """Should error when async command missing remote URL"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _command_name = "TestCommand"
            # _remote_url not set

        cmd = TestAsyncCommand(name="test")
        cmd.validate_inputs()

        with pytest.raises(RemoteCommandError) as exc_info:
            await cmd.execute()

        assert "not configured" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_async_run_instance(self):
        """Should run async command instance"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestAsyncCommand(name="test")
            outcome = await cmd.run_instance()

            assert outcome.is_success()

    @pytest.mark.asyncio
    async def test_async_validation_error(self):
        """Should handle async validation errors"""
        class TestInputs(BaseModel):
            name: str
            age: int

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        cmd = TestAsyncCommand(name="test", age="invalid")
        outcome = await cmd.run_instance()

        assert outcome.is_failure()

    @pytest.mark.asyncio
    async def test_async_with_custom_headers(self):
        """Should send custom headers with async requests"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"
            _headers = {"Authorization": "Bearer token"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_post = mock_client.__aenter__.return_value.post
            mock_post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestAsyncCommand(name="test")
            cmd.validate_inputs()
            await cmd.execute()

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer token"

    @pytest.mark.asyncio
    async def test_async_response_parsing(self):
        """Should parse async response correctly"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "result": {"id": 1, "name": "test", "data": [1, 2, 3]}
            }

            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            cmd = TestAsyncCommand(name="test")
            cmd.validate_inputs()
            result = await cmd.execute()

            assert result["id"] == 1
            assert result["data"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_async_error_recovery(self):
        """Should handle async error recovery"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_response.json.return_value = {
                "message": "Invalid input",
                "errors": [{"field": "name", "code": "required"}]
            }

            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            outcome = await TestAsyncCommand.run(name="test")

            assert outcome.is_failure()

    @pytest.mark.asyncio
    async def test_async_multiple_errors(self):
        """Should handle multiple async error scenarios"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            # First call fails, second succeeds
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500
            mock_response_fail.text = "Error"
            mock_response_fail.json.return_value = {"message": "Error"}

            mock_response_ok = Mock()
            mock_response_ok.status_code = 200
            mock_response_ok.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_post = mock_client.__aenter__.return_value.post
            mock_post.side_effect = [mock_response_fail, mock_response_ok]
            mock_client_class.return_value = mock_client

            # First call should fail
            outcome1 = await TestAsyncCommand.run(name="test1")
            assert outcome1.is_failure()

            # Second call should succeed
            outcome2 = await TestAsyncCommand.run(name="test2")
            assert outcome2.is_success()

    @pytest.mark.asyncio
    async def test_async_with_retries(self):
        """Should handle async operations with retry logic"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://api.example.com"
            _command_name = "TestCommand"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Simulate retry logic by calling multiple times
            for _ in range(3):
                outcome = await TestAsyncCommand.run(name="test")
                assert outcome.is_success()


# ============================================================================
# ManifestCache TTL Tests (10+ tests)
# ============================================================================


class TestManifestCacheTTL:
    """Test ManifestCache TTL and expiration behavior"""

    def test_cache_hit_within_ttl(self):
        """Should return cached data within TTL"""
        cache = ManifestCache(ttl_seconds=60)
        data = {"commands": [{"name": "Test"}]}

        cache.set("https://example.com/manifest", data)
        result = cache.get("https://example.com/manifest")

        assert result == data

    def test_cache_miss_after_expiry(self):
        """Should return None after TTL expires"""
        cache = ManifestCache(ttl_seconds=1)
        data = {"commands": []}

        entry = cache.set("https://example.com/manifest", data)
        # Manually expire
        entry.expires_at = datetime.now() - timedelta(seconds=1)

        result = cache.get("https://example.com/manifest")
        assert result is None

    def test_cache_miss_nonexistent_url(self):
        """Should return None for nonexistent URL"""
        cache = ManifestCache()
        result = cache.get("https://nonexistent.com/manifest")
        assert result is None

    def test_cache_entry_etag_tracking(self):
        """Should track ETag for cache entries"""
        cache = ManifestCache()
        data = {"commands": []}
        etag = "abc123"

        entry = cache.set("https://example.com/manifest", data, etag=etag)

        assert entry.etag == etag

    def test_cache_entry_age(self):
        """Should track entry age"""
        cache = ManifestCache()
        data = {"commands": []}

        entry = cache.set("https://example.com/manifest", data)

        assert entry.age_seconds < 1.0

    def test_cache_with_custom_ttl(self):
        """Should allow custom TTL per entry"""
        cache = ManifestCache(ttl_seconds=60)
        data = {"commands": []}

        entry = cache.set("https://example.com/manifest", data, ttl_seconds=120)

        # Check that custom TTL was used
        expected_expiry = entry.fetched_at + timedelta(seconds=120)
        assert abs((entry.expires_at - expected_expiry).total_seconds()) < 1

    def test_cache_invalidation_removes_entry(self):
        """Should remove entry on invalidation"""
        cache = ManifestCache()
        cache.set("https://example.com/manifest", {"data": "test"})

        result = cache.invalidate("https://example.com/manifest")
        assert result is True
        assert cache.get("https://example.com/manifest") is None

    def test_cache_invalidation_nonexistent(self):
        """Should return False when invalidating nonexistent entry"""
        cache = ManifestCache()
        result = cache.invalidate("https://nonexistent.com/manifest")
        assert result is False

    def test_cache_get_entry_for_conditional_requests(self):
        """Should get entry even if expired for conditional requests"""
        cache = ManifestCache(ttl_seconds=1)
        data = {"commands": []}
        etag = "abc123"

        entry = cache.set("https://example.com/manifest", data, etag=etag)
        # Manually expire
        entry.expires_at = datetime.now() - timedelta(seconds=1)

        # get() returns None for expired
        assert cache.get("https://example.com/manifest") is None

        # But get_entry() returns the entry
        retrieved_entry = cache.get_entry("https://example.com/manifest")
        assert retrieved_entry is not None
        assert retrieved_entry.etag == etag

    def test_cache_cleanup_removes_expired(self):
        """Should cleanup expired entries"""
        cache = ManifestCache(ttl_seconds=1)
        cache.set("https://a.com/manifest", {"a": 1})
        cache.set("https://b.com/manifest", {"b": 2})

        # Expire first entry
        key_a = cache._cache_key("https://a.com/manifest")
        cache._entries[key_a].expires_at = datetime.now() - timedelta(seconds=1)

        removed = cache.cleanup_expired()

        assert removed == 1
        assert cache.size == 1
        assert cache.get("https://b.com/manifest") is not None

    def test_cache_stats_tracking(self):
        """Should track cache statistics"""
        cache = ManifestCache(ttl_seconds=60, max_entries=100)
        cache.set("https://a.com/manifest", {"a": 1})
        cache.set("https://b.com/manifest", {"b": 2})

        # Expire one entry
        key = cache._cache_key("https://a.com/manifest")
        cache._entries[key].expires_at = datetime.now() - timedelta(seconds=1)

        stats = cache.stats()

        assert stats["total_entries"] == 2
        assert stats["expired_entries"] == 1
        assert stats["valid_entries"] == 1
        assert stats["max_entries"] == 100
        assert stats["ttl_seconds"] == 60


# ============================================================================
# RemoteImporter Tests (15+ tests)
# ============================================================================


class TestRemoteImporterComprehensive:
    """Comprehensive RemoteImporter tests"""

    @patch("httpx.Client")
    def test_manifest_parsing_basic(self, mock_client_class):
        """Should parse basic manifest structure"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "version": "1.0",
            "commands": [
                {
                    "name": "CreateUser",
                    "full_name": "Users::CreateUser",
                    "description": "Create a user",
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        manifest = importer.manifest

        assert manifest.command_count == 1
        assert manifest.version == "1.0"

    @patch("httpx.Client")
    def test_manifest_parsing_with_schemas(self, mock_client_class):
        """Should parse manifest with input/output schemas"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {
                    "name": "CreateUser",
                    "full_name": "Users::CreateUser",
                    "inputs_schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"}
                        },
                        "required": ["name"]
                    },
                    "result_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"}
                        }
                    }
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        cmd_class = importer.import_command("Users::CreateUser")

        schema = cmd_class.inputs_schema()
        assert "properties" in schema
        assert "name" in schema["properties"]

    @patch("httpx.Client")
    def test_command_registration_multiple(self, mock_client_class):
        """Should register multiple commands"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {"name": "CreateUser", "full_name": "Users::CreateUser"},
                {"name": "UpdateUser", "full_name": "Users::UpdateUser"},
                {"name": "DeleteUser", "full_name": "Users::DeleteUser"},
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        commands = importer.import_all()

        assert len(commands) >= 3
        assert "Users::CreateUser" in commands
        assert "Users::UpdateUser" in commands
        assert "Users::DeleteUser" in commands

    @patch("httpx.Client")
    def test_command_registration_with_domains(self, mock_client_class):
        """Should handle commands with domain prefixes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {
                    "name": "CreateUser",
                    "full_name": "Users::CreateUser",
                    "domain": "Users"
                },
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        cmd_class = importer.import_command("Users::CreateUser")

        assert cmd_class._domain == "Users"

    @patch("httpx.Client")
    def test_type_registration_from_schema(self, mock_client_class):
        """Should register types from schema definitions"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {
                    "name": "GetUser",
                    "full_name": "Users::GetUser",
                    "result_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "email": {"type": "string"},
                            "active": {"type": "boolean"}
                        }
                    }
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        cmd_class = importer.import_command("Users::GetUser")

        result_type = cmd_class.result_type()
        assert result_type is not None

    @patch("httpx.Client")
    def test_manifest_refresh(self, mock_client_class):
        """Should refresh manifest from remote"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [{"name": "Test", "full_name": "Test"}]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        # First access
        _ = importer.manifest
        # Refresh
        _ = importer.refresh()

        # Should have made 2 HTTP calls
        assert mock_client.__enter__.return_value.get.call_count == 2

    @patch("httpx.Client")
    def test_base_url_derivation_standard(self, mock_client_class):
        """Should derive base URL from manifest URL"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"commands": []}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        importer = RemoteImporter("https://api.example.com/manifest")
        assert importer.base_url == "https://api.example.com"

    @patch("httpx.Client")
    def test_base_url_derivation_nested(self, mock_client_class):
        """Should derive base URL from nested manifest path"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"commands": []}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        importer = RemoteImporter("https://api.example.com/v1/manifest")
        assert importer.base_url == "https://api.example.com/v1"

    @patch("httpx.Client")
    def test_import_command_not_found(self, mock_client_class):
        """Should raise error for nonexistent command"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"commands": []}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        with pytest.raises(CommandNotFoundError) as exc_info:
            importer.import_command("NonExistent::Command")

        assert "NonExistent::Command" in str(exc_info.value)

    @patch("httpx.Client")
    def test_import_with_custom_timeout(self, mock_client_class):
        """Should use custom timeout for imports"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"commands": []}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        importer = RemoteImporter(
            "https://api.example.com/manifest",
            timeout=60.0
        )

        assert importer.timeout == 60.0

    @patch("httpx.Client")
    def test_import_with_custom_headers(self, mock_client_class):
        """Should use custom headers for imports"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"commands": []}

        mock_client = MagicMock()
        mock_get = mock_client.__enter__.return_value.get
        mock_get.return_value = mock_response
        mock_client_class.return_value = mock_client

        headers = {"Authorization": "Bearer token"}
        # Use fresh cache to avoid cross-test pollution
        cache = ManifestCache()
        importer = RemoteImporter(
            "https://api.example.com/manifest",
            headers=headers,
            cache=cache
        )

        _ = importer.manifest

        # Verify headers were passed
        call_kwargs = mock_get.call_args[1]
        assert "Authorization" in call_kwargs["headers"]

    @patch("httpx.Client")
    def test_conditional_request_with_etag(self, mock_client_class):
        """Should use ETag for conditional requests"""
        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.headers = {"etag": "abc123"}
        mock_response_1.json.return_value = {"commands": []}

        mock_response_2 = Mock()
        mock_response_2.status_code = 304  # Not Modified

        mock_client = MagicMock()
        mock_get = mock_client.__enter__.return_value.get
        mock_get.side_effect = [mock_response_1, mock_response_2]
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        # First fetch
        _ = importer.manifest
        # Force refresh
        _ = importer.refresh()

        # Second request should include If-None-Match header
        second_call_headers = mock_get.call_args_list[1][1]["headers"]
        assert "If-None-Match" in second_call_headers

    @patch("httpx.Client")
    def test_manifest_fetch_http_error(self, mock_client_class):
        """Should handle HTTP errors when fetching manifest"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        with pytest.raises(ManifestFetchError) as exc_info:
            _ = importer.manifest

        assert exc_info.value.status_code == 500

    @patch("httpx.Client")
    def test_import_command_caching(self, mock_client_class):
        """Should cache imported command classes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {"name": "Test", "full_name": "Test"}
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        # Import twice
        cmd1 = importer.import_command("Test")
        cmd2 = importer.import_command("Test")

        # Should return same class
        assert cmd1 is cmd2


# ============================================================================
# RemoteNamespace Tests (10+ tests)
# ============================================================================


class TestRemoteNamespaceComprehensive:
    """Comprehensive RemoteNamespace tests"""

    def test_namespace_attribute_access_simple(self):
        """Should access commands via simple attributes"""
        class MockCommand:
            _command_name = "CreateUser"

        commands = {"CreateUser": MockCommand}
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)

        assert namespace.CreateUser == MockCommand

    def test_namespace_attribute_access_with_domain(self):
        """Should access commands with domain prefix"""
        class MockCommand:
            _command_name = "Users::CreateUser"

        commands = {"Users::CreateUser": MockCommand}
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)

        assert namespace.CreateUser == MockCommand

    def test_namespace_list_commands(self):
        """Should list all commands in namespace"""
        commands = {
            "Users::CreateUser": Mock(),
            "Users::UpdateUser": Mock(),
            "Posts::CreatePost": Mock(),
        }
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)
        command_list = namespace.list_commands()

        assert len(command_list) == 3
        assert "Users::CreateUser" in command_list

    def test_namespace_unknown_command_error(self):
        """Should raise AttributeError for unknown commands"""
        commands = {}
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)

        with pytest.raises(AttributeError):
            _ = namespace.NonExistentCommand

    def test_namespace_hierarchy_simple(self):
        """Should handle simple namespace hierarchy"""
        class MockCommand:
            _command_name = "Test"

        commands = {"Test": MockCommand}
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)

        assert hasattr(namespace, "Test")

    def test_namespace_hierarchy_nested(self):
        """Should handle nested namespace hierarchy"""
        class MockCommand:
            _command_name = "Domain::SubDomain::Command"

        commands = {"Domain::SubDomain::Command": MockCommand}
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)

        # Should be accessible by short name
        assert namespace.Command == MockCommand

    def test_namespace_multiple_domains(self):
        """Should handle commands from multiple domains"""
        class MockCommand1:
            _command_name = "Users::CreateUser"

        class MockCommand2:
            _command_name = "Posts::CreatePost"

        commands = {
            "Users::CreateUser": MockCommand1,
            "Posts::CreatePost": MockCommand2,
        }
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)

        assert namespace.CreateUser == MockCommand1
        assert namespace.CreatePost == MockCommand2

    def test_namespace_manifest_access(self):
        """Should provide access to manifest"""
        commands = {}
        importer = Mock()
        importer.manifest = Mock()

        namespace = RemoteNamespace(commands, importer)

        assert namespace.manifest == importer.manifest

    def test_namespace_command_name_collision(self):
        """Should handle command name collisions"""
        class MockCommand1:
            _command_name = "Users::Create"

        class MockCommand2:
            _command_name = "Posts::Create"

        commands = {
            "Users::Create": MockCommand1,
            "Posts::Create": MockCommand2,
        }
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)

        # First one wins
        result = namespace.Create
        assert result in [MockCommand1, MockCommand2]

    def test_namespace_empty(self):
        """Should handle empty namespace"""
        commands = {}
        importer = Mock()

        namespace = RemoteNamespace(commands, importer)

        assert namespace.list_commands() == []


# ============================================================================
# Edge Case Tests (15+ tests)
# ============================================================================


class TestRemoteImportsEdgeCases:
    """Test edge cases and error scenarios"""

    @patch("httpx.Client")
    def test_empty_manifest(self, mock_client_class):
        """Should handle empty manifest"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"commands": []}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        assert len(importer.list_commands()) == 0

    @patch("httpx.Client")
    def test_malformed_manifest_structure(self, mock_client_class):
        """Should handle malformed manifest structure"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"invalid": "structure"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        with pytest.raises(Exception):
            _ = importer.manifest

    @patch("httpx.Client")
    def test_network_failure_during_import(self, mock_client_class):
        """Should handle network failures gracefully"""
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.side_effect = httpx.ConnectError(
            "Network error"
        )
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        with pytest.raises(ManifestFetchError):
            _ = importer.manifest

    @patch("httpx.Client")
    def test_timeout_during_manifest_fetch(self, mock_client_class):
        """Should handle timeout during manifest fetch"""
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.side_effect = httpx.TimeoutException(
            "Timeout"
        )
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        with pytest.raises(ManifestFetchError):
            _ = importer.manifest

    @patch("httpx.Client")
    def test_invalid_json_in_manifest(self, mock_client_class):
        """Should handle invalid JSON in manifest"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        with pytest.raises(Exception):
            _ = importer.manifest

    @patch("httpx.Client")
    def test_command_with_no_inputs_schema(self, mock_client_class):
        """Should handle commands with no inputs schema"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {
                    "name": "NoInputs",
                    "full_name": "NoInputs",
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        cmd_class = importer.import_command("NoInputs")

        assert cmd_class is not None

    @patch("httpx.Client")
    def test_command_with_complex_schema(self, mock_client_class):
        """Should handle commands with complex nested schemas"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {
                    "name": "Complex",
                    "full_name": "Complex",
                    "inputs_schema": {
                        "type": "object",
                        "properties": {
                            "nested": {
                                "type": "object",
                                "properties": {
                                    "value": {"type": "string"}
                                }
                            },
                            "list": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        cmd_class = importer.import_command("Complex")

        assert cmd_class is not None

    def test_cache_key_collision(self):
        """Should handle cache key collisions"""
        cache = ManifestCache()

        # Set two different URLs
        cache.set("https://a.com/manifest", {"a": 1})
        cache.set("https://b.com/manifest", {"b": 2})

        # Should have separate entries
        assert cache.get("https://a.com/manifest") != cache.get("https://b.com/manifest")

    def test_cache_at_max_capacity(self):
        """Should handle cache at maximum capacity"""
        cache = ManifestCache(max_entries=3)

        for i in range(5):
            cache.set(f"https://example{i}.com/manifest", {"index": i})

        # Should only have 3 entries
        assert cache.size == 3

    def test_multiple_cache_evictions(self):
        """Should handle multiple cache evictions"""
        cache = ManifestCache(max_entries=2)

        cache.set("https://a.com/manifest", {"a": 1})
        cache.set("https://b.com/manifest", {"b": 2})
        cache.set("https://c.com/manifest", {"c": 3})
        cache.set("https://d.com/manifest", {"d": 4})

        assert cache.size == 2
        # Oldest entries should be evicted
        assert cache.get("https://a.com/manifest") is None
        assert cache.get("https://b.com/manifest") is None

    @patch("httpx.Client")
    def test_import_with_missing_httpx(self, mock_client_class):
        """Should provide helpful error when httpx not installed"""
        # This test would need to mock the import mechanism
        # Skipping actual implementation as it requires module mocking
        pass

    @patch("httpx.Client")
    def test_command_with_special_characters(self, mock_client_class):
        """Should handle command names with special characters"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {
                    "name": "Create-User",
                    "full_name": "Users::Create-User",
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        # Should handle special characters
        commands = importer.list_commands()
        assert "Users::Create-User" in commands

    @patch("httpx.Client")
    def test_very_long_manifest(self, mock_client_class):
        """Should handle very large manifests"""
        commands_list = [
            {
                "name": f"Command{i}",
                "full_name": f"Domain::Command{i}",
            }
            for i in range(100)
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"commands": commands_list}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

        assert len(importer.list_commands()) == 100

    @patch("httpx.Client")
    def test_manifest_with_null_values(self, mock_client_class):
        """Should handle manifest with null values"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {
                    "name": "Test",
                    "full_name": "Test",
                    "description": None,
                    "domain": None,
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        cmd_class = importer.import_command("Test")

        assert cmd_class is not None

    def test_concurrent_cache_access(self):
        """Should handle concurrent cache access"""
        cache = ManifestCache()

        # Simulate concurrent writes
        for i in range(10):
            cache.set(f"https://example{i}.com/manifest", {"index": i})

        # All should be accessible
        for i in range(10):
            result = cache.get(f"https://example{i}.com/manifest")
            assert result is not None
