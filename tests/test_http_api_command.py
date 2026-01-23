"""Tests for HTTP API Command"""

import pytest
from pydantic import BaseModel

try:
    import httpx
    from foobara_py.apis import (
        HTTPAPICommand,
        HTTPMethod,
        HTTPError,
        AuthenticationError,
        NotFoundError,
        RateLimitError,
        ServerError
    )
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@pytest.mark.skipif(not HTTPX_AVAILABLE, reason="httpx not installed")
class TestHTTPAPICommand:
    """Test HTTPAPICommand base class"""

    def test_simple_get_request(self, httpx_mock):
        """Should make a simple GET request"""

        # Define command
        class GetUserInputs(BaseModel):
            user_id: int

        class UserResult(BaseModel):
            id: int
            name: str
            email: str

        class GetUserCommand(HTTPAPICommand[GetUserInputs, UserResult]):
            base_url = "https://api.example.com"

            def endpoint(self) -> str:
                return f"/users/{self.inputs.user_id}"

            def method(self) -> HTTPMethod:
                return HTTPMethod.GET

            async def parse_response(self, response: httpx.Response) -> UserResult:
                data = response.json()
                return UserResult(**data)

        # Mock response
        httpx_mock.add_response(
            url="https://api.example.com/users/123",
            json={"id": 123, "name": "John Doe", "email": "john@example.com"}
        )

        # Run command
        import asyncio
        outcome = asyncio.run(GetUserCommand.run(user_id=123))

        assert outcome.is_success()
        assert outcome.result.id == 123
        assert outcome.result.name == "John Doe"
        assert outcome.result.email == "john@example.com"

    def test_post_request_with_body(self, httpx_mock):
        """Should make POST request with JSON body"""

        class CreateUserInputs(BaseModel):
            name: str
            email: str

        class UserResult(BaseModel):
            id: int
            name: str
            email: str

        class CreateUserCommand(HTTPAPICommand[CreateUserInputs, UserResult]):
            base_url = "https://api.example.com"

            def endpoint(self) -> str:
                return "/users"

            def method(self) -> HTTPMethod:
                return HTTPMethod.POST

            def request_body(self):
                return {
                    "name": self.inputs.name,
                    "email": self.inputs.email
                }

            async def parse_response(self, response: httpx.Response) -> UserResult:
                data = response.json()
                return UserResult(**data)

        # Mock response
        httpx_mock.add_response(
            url="https://api.example.com/users",
            json={"id": 456, "name": "Jane Smith", "email": "jane@example.com"}
        )

        # Run command
        import asyncio
        outcome = asyncio.run(CreateUserCommand.run(
            name="Jane Smith",
            email="jane@example.com"
        ))

        assert outcome.is_success()
        assert outcome.result.id == 456
        assert outcome.result.name == "Jane Smith"

    def test_request_with_query_params(self, httpx_mock):
        """Should add query parameters"""

        class ListUsersInputs(BaseModel):
            page: int = 1
            limit: int = 10

        class ListUsersResult(BaseModel):
            users: list

        class ListUsersCommand(HTTPAPICommand[ListUsersInputs, ListUsersResult]):
            base_url = "https://api.example.com"

            def endpoint(self) -> str:
                return "/users"

            def query_params(self):
                return {
                    "page": self.inputs.page,
                    "limit": self.inputs.limit
                }

            async def parse_response(self, response: httpx.Response) -> ListUsersResult:
                return ListUsersResult(users=response.json())

        # Mock response
        httpx_mock.add_response(
            url="https://api.example.com/users?page=2&limit=20",
            json=[{"id": 1}, {"id": 2}]
        )

        # Run command
        import asyncio
        outcome = asyncio.run(ListUsersCommand.run(page=2, limit=20))

        assert outcome.is_success()
        assert len(outcome.result.users) == 2

    def test_request_with_custom_headers(self, httpx_mock):
        """Should add custom headers"""

        class AuthenticatedCommandInputs(BaseModel):
            pass

        class AuthenticatedCommandResult(BaseModel):
            data: str

        class AuthenticatedCommand(HTTPAPICommand[AuthenticatedCommandInputs, AuthenticatedCommandResult]):
            base_url = "https://api.example.com"
            api_token = "secret-token"

            def endpoint(self) -> str:
                return "/protected"

            def headers(self):
                return {
                    "Authorization": f"Bearer {self.api_token}",
                    "X-Custom-Header": "value"
                }

            async def parse_response(self, response: httpx.Response) -> AuthenticatedCommandResult:
                return AuthenticatedCommandResult(data=response.json()["data"])

        # Mock response
        httpx_mock.add_response(
            url="https://api.example.com/protected",
            json={"data": "secret"}
        )

        # Run command
        import asyncio
        outcome = asyncio.run(AuthenticatedCommand.run())

        assert outcome.is_success()
        assert outcome.result.data == "secret"

    def test_404_error_handling(self, httpx_mock):
        """Should handle 404 errors"""

        class GetUserInputs(BaseModel):
            user_id: int

        class UserResult(BaseModel):
            id: int
            name: str

        class GetUserCommand(HTTPAPICommand[GetUserInputs, UserResult]):
            base_url = "https://api.example.com"

            def endpoint(self) -> str:
                return f"/users/{self.inputs.user_id}"

            async def parse_response(self, response: httpx.Response) -> UserResult:
                return UserResult(**response.json())

        # Mock 404 response
        httpx_mock.add_response(
            url="https://api.example.com/users/999",
            status_code=404,
            json={"message": "User not found"}
        )

        # Run command
        import asyncio
        outcome = asyncio.run(GetUserCommand.run(user_id=999))

        assert outcome.is_failure()
        assert any("not_found" in error.symbol for error in outcome.errors)

    def test_401_authentication_error(self, httpx_mock):
        """Should handle 401 authentication errors"""

        class ProtectedInputs(BaseModel):
            pass

        class ProtectedResult(BaseModel):
            data: str

        class ProtectedCommand(HTTPAPICommand[ProtectedInputs, ProtectedResult]):
            base_url = "https://api.example.com"

            def endpoint(self) -> str:
                return "/protected"

            async def parse_response(self, response: httpx.Response) -> ProtectedResult:
                return ProtectedResult(data=response.json()["data"])

        # Mock 401 response
        httpx_mock.add_response(
            url="https://api.example.com/protected",
            status_code=401,
            json={"message": "Unauthorized"}
        )

        # Run command
        import asyncio
        outcome = asyncio.run(ProtectedCommand.run())

        assert outcome.is_failure()
        assert any("authentication_failed" in error.symbol for error in outcome.errors)

    def test_429_rate_limit_error(self, httpx_mock):
        """Should handle 429 rate limit errors"""

        class APIInputs(BaseModel):
            pass

        class APIResult(BaseModel):
            data: str

        class APICommand(HTTPAPICommand[APIInputs, APIResult]):
            base_url = "https://api.example.com"

            def endpoint(self) -> str:
                return "/data"

            async def parse_response(self, response: httpx.Response) -> APIResult:
                return APIResult(data=response.json()["data"])

        # Mock 429 response
        httpx_mock.add_response(
            url="https://api.example.com/data",
            status_code=429,
            json={"message": "Rate limit exceeded"}
        )

        # Run command
        import asyncio
        outcome = asyncio.run(APICommand.run())

        assert outcome.is_failure()
        assert any("rate_limit_exceeded" in error.symbol for error in outcome.errors)

    def test_500_server_error(self, httpx_mock):
        """Should handle 500 server errors"""

        class APIInputs(BaseModel):
            pass

        class APIResult(BaseModel):
            data: str

        class APICommand(HTTPAPICommand[APIInputs, APIResult]):
            base_url = "https://api.example.com"
            max_retries = 1  # Disable retries for test

            def endpoint(self) -> str:
                return "/data"

            async def parse_response(self, response: httpx.Response) -> APIResult:
                return APIResult(data=response.json()["data"])

        # Mock 500 response
        httpx_mock.add_response(
            url="https://api.example.com/data",
            status_code=500,
            json={"message": "Internal server error"}
        )

        # Run command
        import asyncio
        outcome = asyncio.run(APICommand.run())

        assert outcome.is_failure()
        assert any("external_service_error" in error.symbol for error in outcome.errors)

    def test_retry_logic(self, httpx_mock):
        """Should retry on retryable errors"""

        class APIInputs(BaseModel):
            pass

        class APIResult(BaseModel):
            data: str

        class APICommand(HTTPAPICommand[APIInputs, APIResult]):
            base_url = "https://api.example.com"
            max_retries = 3
            retry_delay = 0.01  # Fast retries for testing

            def endpoint(self) -> str:
                return "/data"

            async def parse_response(self, response: httpx.Response) -> APIResult:
                return APIResult(data=response.json()["data"])

        # Mock responses - first two fail, third succeeds
        httpx_mock.add_response(
            url="https://api.example.com/data",
            status_code=500,
            json={"message": "Server error"}
        )
        httpx_mock.add_response(
            url="https://api.example.com/data",
            status_code=500,
            json={"message": "Server error"}
        )
        httpx_mock.add_response(
            url="https://api.example.com/data",
            status_code=200,
            json={"data": "success"}
        )

        # Run command
        import asyncio
        outcome = asyncio.run(APICommand.run())

        # Should succeed after retries
        assert outcome.is_success()
        assert outcome.result.data == "success"


@pytest.fixture
def httpx_mock(monkeypatch):
    """Fixture to provide httpx mock using monkeypatching"""
    import httpx
    from unittest.mock import AsyncMock, MagicMock

    # Track responses to return
    responses = []
    response_index = [0]  # Use list to allow mutation in closure

    async def mock_request(method, url, **kwargs):
        """Mock httpx request"""
        # Find matching response
        if response_index[0] < len(responses):
            resp_config = responses[response_index[0]]
            response_index[0] += 1
        elif responses:
            # Use last response if we run out
            resp_config = responses[-1]
        else:
            # No responses configured - return error
            raise httpx.ConnectError("No mock response configured")

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = resp_config.get("status_code", 200)
        mock_response.json.return_value = resp_config.get("json", {})
        mock_response.text = str(resp_config.get("json", ""))

        return mock_response

    # Mock AsyncClient
    class MockAsyncClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request(self, method, url, **kwargs):
            return await mock_request(method, url, **kwargs)

    # Replace AsyncClient with mock
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    # Create mock object for test to configure
    class HTTPXMock:
        def add_response(self, url, json=None, status_code=200):
            responses.append({
                "url": url,
                "json": json,
                "status_code": status_code
            })

    return HTTPXMock()
