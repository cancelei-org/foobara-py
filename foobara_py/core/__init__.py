"""Core components: Command, Outcome, Errors"""

from foobara_py.core.command import (
    AsyncCommand,
    AsyncSimpleCommand,
    Command,
    SimpleCommand,
    async_command,
    async_simple_command,
    command,
    simple_command,
)
from foobara_py.core.errors import DataError, ErrorCollection, ErrorSymbols
from foobara_py.core.outcome import CommandOutcome, Failure, Outcome, Success
from foobara_py.core.registry import CommandRegistry, get_default_registry, register

__all__ = [
    "Outcome",
    "Success",
    "Failure",
    "CommandOutcome",
    "Command",
    "command",
    "SimpleCommand",
    "simple_command",
    "AsyncCommand",
    "async_command",
    "AsyncSimpleCommand",
    "async_simple_command",
    "DataError",
    "ErrorCollection",
    "ErrorSymbols",
    "CommandRegistry",
    "get_default_registry",
    "register",
]
