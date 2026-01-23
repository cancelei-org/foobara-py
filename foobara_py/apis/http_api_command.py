"""
HTTP API Command base class for wrapping external HTTP APIs.

Provides a foundation for creating commands that interact with external
HTTP APIs with automatic error handling, retry logic, and auth support.
"""

import asyncio
import time
from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

try:
    import httpx
except ImportError:
    httpx = None

from pydantic import BaseModel

from foobara_py.core.command import AsyncCommand
from foobara_py.core.errors import Symbols

# Type variables for generic command
InputT = TypeVar("InputT", bound=BaseModel)
ResultT = TypeVar("ResultT")


class HTTPMethod(str, Enum):
    """HTTP methods"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class HTTPError(Exception):
    """Base HTTP error"""

    def __init__(self, message: str, status_code: int = None, response: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(HTTPError):
    """Rate limit exceeded"""

    pass


class AuthenticationError(HTTPError):
    """Authentication failed"""

    pass


class NotFoundError(HTTPError):
    """Resource not found"""

    pass


class ServerError(HTTPError):
    """Server error (5xx)"""

    pass


class HTTPAPICommand(Generic[InputT, ResultT], AsyncCommand[InputT, ResultT]):
    """
    Base class for HTTP API client commands.

    Provides a structured way to wrap external HTTP APIs with:
    - Automatic error handling and status code mapping
    - Retry logic with exponential backoff
    - Custom headers and authentication
    - Request/response transformation

    Subclasses must implement:
    - endpoint(): Return the API endpoint URL
    - method(): Return the HTTP method
    - parse_response(): Parse response into result type

    Optionally override:
    - request_body(): Return request body
    - query_params(): Return query parameters
    - headers(): Return custom headers
    - should_retry(): Custom retry logic
    - handle_error(): Custom error handling

    Usage:
        class GetUserInputs(BaseModel):
            user_id: int

        class GetUserResult(BaseModel):
            id: int
            name: str
            email: str

        class GetUser(HTTPAPICommand[GetUserInputs, GetUserResult]):
            base_url = "https://api.example.com"

            def endpoint(self) -> str:
                return f"/users/{self.inputs.user_id}"

            def method(self) -> HTTPMethod:
                return HTTPMethod.GET

            async def parse_response(self, response: httpx.Response) -> GetUserResult:
                data = response.json()
                return GetUserResult(**data)

        # Use it
        outcome = await GetUser.run(user_id=123)
        if outcome.is_success():
            print(outcome.result.name)
    """

    # Class-level configuration
    base_url: str = ""
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0  # Initial delay in seconds
    retry_backoff: float = 2.0  # Exponential backoff multiplier

    def __init__(self, **inputs):
        """Initialize HTTP API command"""
        if httpx is None:
            raise ImportError(
                "httpx is required for HTTPAPICommand. Install with: pip install httpx"
            )
        super().__init__(**inputs)
        self._client: Optional[httpx.AsyncClient] = None

    # ==================== Abstract Methods ====================

    @abstractmethod
    def endpoint(self) -> str:
        """
        Return the API endpoint path.

        Should return the path portion of the URL (without base_url).

        Example:
            return f"/users/{self.inputs.user_id}"
        """
        pass

    def method(self) -> HTTPMethod:
        """
        Return the HTTP method.

        Defaults to GET. Override for other methods.

        Example:
            return HTTPMethod.POST
        """
        return HTTPMethod.GET

    @abstractmethod
    async def parse_response(self, response: "httpx.Response") -> ResultT:
        """
        Parse HTTP response into result type.

        This method is called after successful HTTP request.
        Transform the response data into your result type.

        Args:
            response: httpx Response object

        Returns:
            Parsed result of type ResultT

        Example:
            async def parse_response(self, response):
                data = response.json()
                return UserResult(**data)
        """
        pass

    # ==================== Optional Override Methods ====================

    def request_body(self) -> Optional[Union[Dict[str, Any], str, bytes]]:
        """
        Return request body for POST/PUT/PATCH.

        Defaults to None. Override to send body data.

        Returns:
            Dict for JSON, str for text, bytes for binary, or None

        Example:
            def request_body(self):
                return {"name": self.inputs.name, "email": self.inputs.email}
        """
        return None

    def query_params(self) -> Dict[str, Any]:
        """
        Return query parameters.

        Defaults to empty dict. Override to add query params.

        Returns:
            Dict of query parameters

        Example:
            def query_params(self):
                return {"page": self.inputs.page, "limit": 20}
        """
        return {}

    def headers(self) -> Dict[str, str]:
        """
        Return custom headers.

        Defaults to empty dict. Override to add custom headers.

        Returns:
            Dict of headers

        Example:
            def headers(self):
                return {"Authorization": f"Bearer {self.get_token()}"}
        """
        return {}

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determine if request should be retried.

        Defaults to retrying on connection errors and 5xx status codes.
        Override for custom retry logic.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (1-based)

        Returns:
            True if should retry, False otherwise

        Example:
            def should_retry(self, error, attempt):
                # Only retry on 503
                if isinstance(error, HTTPError) and error.status_code == 503:
                    return attempt < self.max_retries
                return False
        """
        if attempt >= self.max_retries:
            return False

        # Retry on connection errors
        if isinstance(error, (httpx.ConnectError, httpx.TimeoutException)):
            return True

        # Retry on 5xx errors (but not rate limits)
        if isinstance(error, ServerError) and not isinstance(error, RateLimitError):
            return True

        return False

    async def handle_error(self, response: "httpx.Response") -> None:
        """
        Handle HTTP error responses.

        Override for custom error handling. Default implementation
        maps status codes to appropriate Foobara errors.

        Args:
            response: HTTP response with error status

        Raises:
            HTTPError or subclass
        """
        status = response.status_code
        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
        except Exception:
            message = response.text or f"HTTP {status}"

        # Map status codes to error types
        if status == 401:
            raise AuthenticationError(message, status, response)
        elif status == 404:
            raise NotFoundError(message, status, response)
        elif status == 429:
            raise RateLimitError(message, status, response)
        elif status >= 500:
            raise ServerError(message, status, response)
        else:
            raise HTTPError(message, status, response)

    # ==================== Execution ====================

    async def execute(self) -> ResultT:
        """
        Execute HTTP request with retry logic.

        This method is called by AsyncCommand.run_instance().
        It handles retries, error mapping, and response parsing.
        """
        # Build full URL
        url = self.base_url + self.endpoint()

        # Prepare request
        method = self.method().value
        params = self.query_params()
        request_headers = self.headers()
        body = self.request_body()

        # Retry loop
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    # Make request
                    if body is not None:
                        if isinstance(body, dict):
                            response = await client.request(
                                method, url, params=params, headers=request_headers, json=body
                            )
                        else:
                            response = await client.request(
                                method, url, params=params, headers=request_headers, content=body
                            )
                    else:
                        response = await client.request(
                            method, url, params=params, headers=request_headers
                        )

                    # Check for errors
                    if response.status_code >= 400:
                        await self.handle_error(response)

                    # Parse and return response
                    return await self.parse_response(response)

            except Exception as e:
                last_error = e

                # Check if should retry
                if self.should_retry(e, attempt):
                    # Calculate delay with exponential backoff
                    delay = self.retry_delay * (self.retry_backoff ** (attempt - 1))
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Don't retry - break and handle error
                    break

        # If we get here, all retries failed
        self._map_exception_to_error(last_error)
        return None  # Unreachable, but makes type checker happy

    def _map_exception_to_error(self, error: Exception) -> None:
        """Map HTTP exceptions to Foobara errors"""
        if isinstance(error, AuthenticationError):
            self.add_runtime_error(
                Symbols.AUTHENTICATION_FAILED, str(error), halt=True, status_code=error.status_code
            )
        elif isinstance(error, NotFoundError):
            self.add_runtime_error(
                Symbols.NOT_FOUND, str(error), halt=True, status_code=error.status_code
            )
        elif isinstance(error, RateLimitError):
            self.add_runtime_error(
                Symbols.RATE_LIMIT_EXCEEDED, str(error), halt=True, status_code=error.status_code
            )
        elif isinstance(error, ServerError):
            self.add_runtime_error(
                Symbols.EXTERNAL_SERVICE_ERROR,
                f"Server error: {error}",
                halt=True,
                status_code=error.status_code,
            )
        elif isinstance(error, httpx.TimeoutException):
            self.add_runtime_error(Symbols.TIMEOUT, "Request timed out", halt=True)
        elif isinstance(error, httpx.ConnectError):
            self.add_runtime_error(
                Symbols.CONNECTION_FAILED, f"Connection failed: {error}", halt=True
            )
        else:
            self.add_runtime_error(Symbols.EXTERNAL_SERVICE_ERROR, str(error), halt=True)
