"""
Entity lifecycle callbacks for Foobara Python.

Provides hooks into entity lifecycle events similar to ActiveRecord callbacks:
- before_validation, after_validation
- before_create, after_create
- before_save, after_save
- before_update, after_update
- before_delete, after_delete

Usage:
    class User(EntityBase):
        name: str
        created_at: Optional[datetime] = None

        @before_create
        def set_created_at(self):
            self.created_at = datetime.now()

        @after_save
        def send_notification(self):
            notify_user_updated(self.email)

        @before_delete
        def cleanup_associations(self):
            # Clean up related data
            Post.delete_by(user_id=self.id)
"""

import threading
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List

if TYPE_CHECKING:
    from foobara_py.persistence.entity import EntityBase


class EntityLifecycle(str, Enum):
    """Entity lifecycle events"""

    # Validation callbacks
    BEFORE_VALIDATION = "before_validation"
    AFTER_VALIDATION = "after_validation"

    # Create callbacks (first save only)
    BEFORE_CREATE = "before_create"
    AFTER_CREATE = "after_create"

    # Save callbacks (all saves)
    BEFORE_SAVE = "before_save"
    AFTER_SAVE = "after_save"

    # Update callbacks (subsequent saves)
    BEFORE_UPDATE = "before_update"
    AFTER_UPDATE = "after_update"

    # Delete callbacks
    BEFORE_DELETE = "before_delete"
    AFTER_DELETE = "after_delete"


class EntityCallbackRegistry:
    """
    Registry for entity callbacks.

    Manages callbacks per entity class using a class-level registry.
    """

    _registry: Dict[type, Dict[EntityLifecycle, List[Callable]]] = {}
    _lock = threading.Lock()

    @classmethod
    def register(cls, entity_class: type, lifecycle: EntityLifecycle, callback: Callable) -> None:
        """Register a callback for an entity class and lifecycle event"""
        with cls._lock:
            if entity_class not in cls._registry:
                cls._registry[entity_class] = {}

            if lifecycle not in cls._registry[entity_class]:
                cls._registry[entity_class][lifecycle] = []

            cls._registry[entity_class][lifecycle].append(callback)

    @classmethod
    def get_callbacks(cls, entity_class: type, lifecycle: EntityLifecycle) -> List[Callable]:
        """Get all callbacks for an entity class and lifecycle event"""
        with cls._lock:
            if entity_class not in cls._registry:
                return []
            return cls._registry[entity_class].get(lifecycle, []).copy()

    @classmethod
    def run_callbacks(cls, entity: "EntityBase", lifecycle: EntityLifecycle) -> None:
        """Run all callbacks for an entity instance and lifecycle event"""
        entity_class = type(entity)
        callbacks = cls.get_callbacks(entity_class, lifecycle)

        for callback in callbacks:
            callback(entity)

    @classmethod
    def clear(cls, entity_class: type = None) -> None:
        """Clear all callbacks (for testing)"""
        with cls._lock:
            if entity_class:
                cls._registry.pop(entity_class, None)
            else:
                cls._registry.clear()


# Decorator factories for each lifecycle event


def before_validation(method: Callable) -> Callable:
    """
    Mark method as before_validation callback.

    Called before Pydantic validation.

    Usage:
        @before_validation
        def normalize_email(self):
            if self.email:
                self.email = self.email.lower().strip()
    """
    method._entity_callback = EntityLifecycle.BEFORE_VALIDATION
    return method


def after_validation(method: Callable) -> Callable:
    """
    Mark method as after_validation callback.

    Called after Pydantic validation succeeds.

    Usage:
        @after_validation
        def verify_email_format(self):
            assert "@" in self.email, "Invalid email format"
    """
    method._entity_callback = EntityLifecycle.AFTER_VALIDATION
    return method


def before_create(method: Callable) -> Callable:
    """
    Mark method as before_create callback.

    Called before entity is created (first save only).

    Usage:
        @before_create
        def set_timestamps(self):
            self.created_at = datetime.now()
            self.updated_at = datetime.now()
    """
    method._entity_callback = EntityLifecycle.BEFORE_CREATE
    return method


def after_create(method: Callable) -> Callable:
    """
    Mark method as after_create callback.

    Called after entity is created (first save only).

    Usage:
        @after_create
        def send_welcome_email(self):
            send_email(self.email, "Welcome!")
    """
    method._entity_callback = EntityLifecycle.AFTER_CREATE
    return method


def before_save(method: Callable) -> Callable:
    """
    Mark method as before_save callback.

    Called before every save (create and update).

    Usage:
        @before_save
        def update_timestamp(self):
            self.updated_at = datetime.now()
    """
    method._entity_callback = EntityLifecycle.BEFORE_SAVE
    return method


def after_save(method: Callable) -> Callable:
    """
    Mark method as after_save callback.

    Called after every save (create and update).

    Usage:
        @after_save
        def clear_cache(self):
            cache.delete(f"user:{self.id}")
    """
    method._entity_callback = EntityLifecycle.AFTER_SAVE
    return method


def before_update(method: Callable) -> Callable:
    """
    Mark method as before_update callback.

    Called before entity is updated (subsequent saves only).

    Usage:
        @before_update
        def track_changes(self):
            if self.is_dirty:
                log_changes(self.dirty_attributes)
    """
    method._entity_callback = EntityLifecycle.BEFORE_UPDATE
    return method


def after_update(method: Callable) -> Callable:
    """
    Mark method as after_update callback.

    Called after entity is updated (subsequent saves only).

    Usage:
        @after_update
        def notify_watchers(self):
            notify_subscribers(self.id, "updated")
    """
    method._entity_callback = EntityLifecycle.AFTER_UPDATE
    return method


def before_delete(method: Callable) -> Callable:
    """
    Mark method as before_delete callback.

    Called before entity is deleted.

    Usage:
        @before_delete
        def archive_data(self):
            ArchiveService.archive(self)
    """
    method._entity_callback = EntityLifecycle.BEFORE_DELETE
    return method


def after_delete(method: Callable) -> Callable:
    """
    Mark method as after_delete callback.

    Called after entity is deleted.

    Usage:
        @after_delete
        def cleanup_files(self):
            remove_user_files(self.id)
    """
    method._entity_callback = EntityLifecycle.AFTER_DELETE
    return method


def register_entity_callbacks(entity_class: type) -> None:
    """
    Register all callback methods from an entity class.

    This is called automatically by EntityMeta during class creation.
    It scans for methods with _entity_callback attribute and registers them.
    """
    for attr_name in dir(entity_class):
        try:
            attr = getattr(entity_class, attr_name)
            if hasattr(attr, "_entity_callback"):
                lifecycle = attr._entity_callback
                EntityCallbackRegistry.register(entity_class, lifecycle, attr)
        except AttributeError:
            # Skip attributes that can't be accessed
            pass
