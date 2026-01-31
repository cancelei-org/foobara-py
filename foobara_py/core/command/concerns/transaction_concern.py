"""
TransactionConcern - Database transaction management.

Handles:
- Opening transactions
- Committing transactions
- Rolling back on errors
- Transaction handler detection and registration

Pattern: Ruby Foobara's Transactions concern
"""

from typing import ClassVar, Optional

from foobara_py.core.transactions import (
    TransactionConfig,
    TransactionContext,
    TransactionRegistry,
)


class TransactionConcern:
    """Mixin for transaction management."""

    # Class-level configuration
    _transaction_config: ClassVar[TransactionConfig] = TransactionConfig()

    # Instance attributes (defined in __slots__ in Command)
    _transaction: Optional[TransactionContext]

    def open_transaction(self) -> None:
        """
        Open database transaction.

        Override for custom transaction behavior.
        By default, uses the configured transaction handler or auto-detects.
        """
        if self._transaction_config.enabled:
            handler = None
            if self._transaction_config.handler_factory:
                handler = self._transaction_config.handler_factory()
            elif self._transaction_config.auto_detect:
                handler = TransactionRegistry.detect()

            if handler:
                self._transaction = TransactionContext(handler)
                self._transaction.__enter__()

    def commit_transaction(self) -> None:
        """
        Commit database transaction.

        Transaction commits automatically on context exit.
        Override for custom commit behavior.
        """
        pass  # Transaction commits on context exit

    def rollback_transaction(self) -> None:
        """
        Rollback database transaction.

        Marks transaction as failed, causing rollback on context exit.
        """
        if self._transaction:
            self._transaction.mark_failed()
