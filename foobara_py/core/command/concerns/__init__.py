"""
Command concerns - modular mixins for Command class.

This module provides a concern-based architecture for the Command class,
splitting functionality into focused, testable mixins (~100-150 LOC each).

Architecture inspired by Ruby Foobara's command concerns pattern.
"""

from .types_concern import TypesConcern
from .naming_concern import NamingConcern
from .errors_concern import ErrorsConcern
from .inputs_concern import InputsConcern
from .validation_concern import ValidationConcern
from .execution_concern import ExecutionConcern
from .subcommand_concern import SubcommandConcern
from .transaction_concern import TransactionConcern
from .state_concern import StateConcern
from .metadata_concern import MetadataConcern
from .callbacks_concern import CallbacksConcern

__all__ = [
    "TypesConcern",
    "NamingConcern",
    "ErrorsConcern",
    "InputsConcern",
    "ValidationConcern",
    "ExecutionConcern",
    "SubcommandConcern",
    "TransactionConcern",
    "StateConcern",
    "MetadataConcern",
    "CallbacksConcern",
]
