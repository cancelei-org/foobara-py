"""
Command module - Backward compatible exports.

This module maintains 100% backward compatibility with the old monolithic command.py
by re-exporting all public APIs.

The implementation is now split into modular concerns:
- foobara_py/core/command/concerns/ - Individual concern modules
- foobara_py/core/command/base.py - Main Command class
- foobara_py/core/command/async_command.py - AsyncCommand implementation
- foobara_py/core/command/simple.py - SimpleCommand and decorators
- foobara_py/core/command/decorators.py - @command, @async_command

For backward compatibility, all imports that worked with:
    from foobara_py.core.command import Command, command, ...

Will continue to work unchanged.
"""

# Core Command class
from .base import Command, CommandMeta

# Async Command (import from separate module when created)
from .async_command import AsyncCommand

# Simple Commands (import from separate module when created)
from .simple import AsyncSimpleCommand, SimpleCommand, async_simple_command, simple_command

# Decorators
from .decorators import async_command, command

# Import CommandOutcome for backward compatibility
from foobara_py.core.outcome import CommandOutcome

# Re-export everything for backward compatibility
__all__ = [
    "Command",
    "CommandMeta",
    "AsyncCommand",
    "SimpleCommand",
    "AsyncSimpleCommand",
    "command",
    "async_command",
    "simple_command",
    "async_simple_command",
    "CommandOutcome",
]
