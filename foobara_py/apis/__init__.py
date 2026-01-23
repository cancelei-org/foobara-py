"""
HTTP API integration for Foobara Python.

Provides base classes for wrapping external HTTP APIs as commands.
"""

from foobara_py.apis.http_api_command import (
    AuthenticationError,
    HTTPAPICommand,
    HTTPError,
    HTTPMethod,
    NotFoundError,
    RateLimitError,
    ServerError,
)

__all__ = [
    "HTTPAPICommand",
    "HTTPMethod",
    "HTTPError",
    "RateLimitError",
    "AuthenticationError",
    "NotFoundError",
    "ServerError",
]
