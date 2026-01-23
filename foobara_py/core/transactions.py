"""
Transaction management for command execution.

Provides pluggable transaction support similar to Ruby Foobara.
Supports multiple transaction backends (SQLAlchemy, custom, etc.)
"""

import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any, Callable, ContextManager, List, Optional, Protocol


class TransactionHandler(Protocol):
    """Protocol for transaction handlers"""

    def begin(self) -> None:
        """Begin a transaction"""
        ...

    def commit(self) -> None:
        """Commit the transaction"""
        ...

    def rollback(self) -> None:
        """Rollback the transaction"""
        ...


class NoOpTransactionHandler:
    """No-op transaction handler for commands without persistence"""

    __slots__ = ()

    def begin(self) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class TransactionContext:
    """
    Transaction context manager for command execution.

    Supports nested transactions via savepoints.
    Thread-safe using thread-local storage.
    """

    __slots__ = ("_handler", "_depth", "_failed")

    def __init__(self, handler: Optional[TransactionHandler] = None):
        self._handler = handler or NoOpTransactionHandler()
        self._depth = 0
        self._failed = False

    def __enter__(self) -> "TransactionContext":
        if self._depth == 0:
            self._handler.begin()
            self._failed = False
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._depth -= 1

        if exc_type is not None:
            self._failed = True

        if self._depth == 0:
            if self._failed:
                self._handler.rollback()
            else:
                self._handler.commit()

        return False  # Don't suppress exceptions

    def mark_failed(self) -> None:
        """Mark transaction as failed (will rollback on exit)"""
        self._failed = True

    @property
    def is_active(self) -> bool:
        """Check if in active transaction"""
        return self._depth > 0


# Thread-local storage for current transaction
_thread_local = threading.local()


def get_current_transaction() -> Optional[TransactionContext]:
    """Get current thread's transaction context"""
    return getattr(_thread_local, "transaction", None)


def set_current_transaction(ctx: Optional[TransactionContext]) -> None:
    """Set current thread's transaction context"""
    _thread_local.transaction = ctx


@contextmanager
def transaction(handler: Optional[TransactionHandler] = None):
    """
    Context manager for running code in a transaction.

    Usage:
        with transaction(my_db_handler):
            # Code runs in transaction
            create_user(...)
            update_balance(...)
    """
    ctx = TransactionContext(handler)
    previous = get_current_transaction()
    set_current_transaction(ctx)
    try:
        with ctx:
            yield ctx
    finally:
        set_current_transaction(previous)


# SQLAlchemy transaction handler (optional dependency)


class SQLAlchemyTransactionHandler:
    """
    Transaction handler for SQLAlchemy sessions.

    Usage:
        from sqlalchemy.orm import Session
        handler = SQLAlchemyTransactionHandler(session)

        with transaction(handler):
            # Queries run in transaction
            pass
    """

    __slots__ = ("_session", "_savepoint")

    def __init__(self, session: Any):  # Any to avoid hard SQLAlchemy dependency
        self._session = session
        self._savepoint = None

    def begin(self) -> None:
        """Begin transaction or savepoint"""
        if self._session.in_transaction():
            self._savepoint = self._session.begin_nested()
        else:
            self._session.begin()

    def commit(self) -> None:
        """Commit transaction or savepoint"""
        if self._savepoint:
            self._savepoint.commit()
            self._savepoint = None
        else:
            self._session.commit()

    def rollback(self) -> None:
        """Rollback transaction or savepoint"""
        if self._savepoint:
            self._savepoint.rollback()
            self._savepoint = None
        else:
            self._session.rollback()


# Transaction configuration for commands


@dataclass(slots=True)
class TransactionConfig:
    """Configuration for command transaction behavior"""

    enabled: bool = True
    handler_factory: Optional[Callable[[], TransactionHandler]] = None
    auto_detect: bool = True  # Auto-detect transaction from context

    @classmethod
    def disabled(cls) -> "TransactionConfig":
        """Create config with transactions disabled"""
        return cls(enabled=False)

    @classmethod
    def with_handler(cls, factory: Callable[[], TransactionHandler]) -> "TransactionConfig":
        """Create config with specific handler factory"""
        return cls(enabled=True, handler_factory=factory)


# Global transaction registry for auto-detection


class TransactionRegistry:
    """
    Registry for transaction handlers.

    Commands can auto-detect which handler to use based on registered handlers.
    """

    _handlers: List[Callable[[], Optional[TransactionHandler]]] = []
    _lock = threading.Lock()

    @classmethod
    def register(cls, detector: Callable[[], Optional[TransactionHandler]]) -> None:
        """
        Register a transaction handler detector.

        The detector should return a handler if it can provide one,
        or None if it cannot (e.g., no active database session).
        """
        with cls._lock:
            cls._handlers.append(detector)

    @classmethod
    def detect(cls) -> Optional[TransactionHandler]:
        """Try to detect an appropriate transaction handler"""
        with cls._lock:
            for detector in cls._handlers:
                handler = detector()
                if handler is not None:
                    return handler
        return None

    @classmethod
    def clear(cls) -> None:
        """Clear all registered handlers"""
        with cls._lock:
            cls._handlers.clear()
