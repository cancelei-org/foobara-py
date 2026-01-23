"""
Foobara Python CLI tools.

Provides the `foob` command-line interface for:
- Creating new projects
- Generating commands, domains, entities, types
- Running commands
- Interactive console
"""

from foobara_py.cli.foob import app, main

__all__ = ["app", "main"]
