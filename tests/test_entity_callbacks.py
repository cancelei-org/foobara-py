"""Tests for entity lifecycle callbacks"""

import pytest
from datetime import datetime
from typing import Optional, List
from foobara_py.persistence import (
    EntityBase,
    InMemoryRepository,
    RepositoryRegistry,
    EntityCallbackRegistry,
    before_create,
    after_create,
    before_save,
    after_save,
    before_update,
    after_update,
    before_delete,
    after_delete,
)


# Track callback execution
callback_log = []


def reset_callback_log():
    """Reset the callback log"""
    global callback_log
    callback_log = []


class TestEntityCallbacks:
    """Test entity lifecycle callbacks"""

    def setup_method(self):
        """Setup repositories and clear state"""
        reset_callback_log()
        RepositoryRegistry.clear()
        EntityCallbackRegistry.clear()

        self.repo = InMemoryRepository()
        RepositoryRegistry.set_default(self.repo)

    def teardown_method(self):
        """Cleanup"""
        reset_callback_log()
        EntityCallbackRegistry.clear()

    def test_before_create_callback(self):
        """Should run before_create callback on first save"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str
            created_at: Optional[datetime] = None

            @before_create
            def set_created_at(self):
                self.created_at = datetime.now()
                callback_log.append('before_create')

        User._repository = self.repo

        user = User(name="John")
        assert user.created_at is None

        user.save()

        assert user.created_at is not None
        assert 'before_create' in callback_log

    def test_after_create_callback(self):
        """Should run after_create callback on first save"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @after_create
            def send_welcome(self):
                callback_log.append(f'welcome:{self.name}')

        User._repository = self.repo

        user = User(name="John")
        user.save()

        assert 'welcome:John' in callback_log

    def test_before_save_callback(self):
        """Should run before_save callback on every save"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str
            updated_at: Optional[datetime] = None

            @before_save
            def update_timestamp(self):
                self.updated_at = datetime.now()
                callback_log.append('before_save')

        User._repository = self.repo

        user = User(name="John")
        user.save()
        assert callback_log.count('before_save') == 1

        user.name = "Jane"
        user.save()
        assert callback_log.count('before_save') == 2

    def test_after_save_callback(self):
        """Should run after_save callback on every save"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @after_save
            def clear_cache(self):
                callback_log.append('cache_cleared')

        User._repository = self.repo

        user = User(name="John")
        user.save()
        assert 'cache_cleared' in callback_log

        reset_callback_log()
        user.name = "Jane"
        user.save()
        assert 'cache_cleared' in callback_log

    def test_before_update_callback(self):
        """Should run before_update callback on subsequent saves"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @before_update
            def log_update(self):
                callback_log.append('before_update')

        User._repository = self.repo

        user = User(name="John")
        user.save()
        assert 'before_update' not in callback_log  # Not on create

        user.name = "Jane"
        user.save()
        assert 'before_update' in callback_log  # On update

    def test_after_update_callback(self):
        """Should run after_update callback on subsequent saves"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @after_update
            def notify_watchers(self):
                callback_log.append('notified')

        User._repository = self.repo

        user = User(name="John")
        user.save()
        assert 'notified' not in callback_log  # Not on create

        user.name = "Jane"
        user.save()
        assert 'notified' in callback_log  # On update

    def test_before_delete_callback(self):
        """Should run before_delete callback"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @before_delete
            def cleanup(self):
                callback_log.append(f'cleanup:{self.id}')

        User._repository = self.repo

        user = User(name="John")
        user.save()

        user.delete()
        assert f'cleanup:{user.id}' in callback_log

    def test_after_delete_callback(self):
        """Should run after_delete callback"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @after_delete
            def log_deletion(self):
                callback_log.append(f'deleted:{self.id}')

        User._repository = self.repo

        user = User(name="John")
        user.save()

        user.delete()
        assert f'deleted:{user.id}' in callback_log

    def test_multiple_callbacks_same_lifecycle(self):
        """Should run multiple callbacks for same lifecycle event"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @before_create
            def callback_one(self):
                callback_log.append('callback_1')

            @before_create
            def callback_two(self):
                callback_log.append('callback_2')

        User._repository = self.repo

        user = User(name="John")
        user.save()

        assert 'callback_1' in callback_log
        assert 'callback_2' in callback_log

    def test_callback_order(self):
        """Should run callbacks in correct order"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @before_save
            def before_save_cb(self):
                callback_log.append('before_save')

            @before_create
            def before_create_cb(self):
                callback_log.append('before_create')

            @after_create
            def after_create_cb(self):
                callback_log.append('after_create')

            @after_save
            def after_save_cb(self):
                callback_log.append('after_save')

        User._repository = self.repo

        user = User(name="John")
        user.save()

        # Order: before_save, before_create, after_create, after_save
        assert callback_log == [
            'before_save',
            'before_create',
            'after_create',
            'after_save'
        ]

    def test_update_callback_order(self):
        """Should run update callbacks in correct order"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @before_save
            def before_save_cb(self):
                callback_log.append('before_save')

            @before_update
            def before_update_cb(self):
                callback_log.append('before_update')

            @after_update
            def after_update_cb(self):
                callback_log.append('after_update')

            @after_save
            def after_save_cb(self):
                callback_log.append('after_save')

        User._repository = self.repo

        user = User(name="John")
        user.save()
        reset_callback_log()

        user.name = "Jane"
        user.save()

        # Order: before_save, before_update, after_update, after_save
        assert callback_log == [
            'before_save',
            'before_update',
            'after_update',
            'after_save'
        ]

    def test_delete_callback_order(self):
        """Should run delete callbacks in correct order"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @before_delete
            def before_delete_cb(self):
                callback_log.append('before_delete')

            @after_delete
            def after_delete_cb(self):
                callback_log.append('after_delete')

        User._repository = self.repo

        user = User(name="John")
        user.save()
        reset_callback_log()

        user.delete()

        # Order: before_delete, after_delete
        assert callback_log == ['before_delete', 'after_delete']


class TestRealWorldScenarios:
    """Test real-world callback use cases"""

    def setup_method(self):
        """Setup repositories"""
        reset_callback_log()
        RepositoryRegistry.clear()
        EntityCallbackRegistry.clear()
        self.repo = InMemoryRepository()

    def teardown_method(self):
        """Cleanup"""
        reset_callback_log()
        EntityCallbackRegistry.clear()

    def test_timestamp_tracking(self):
        """Should track created_at and updated_at timestamps"""

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str
            created_at: Optional[datetime] = None
            updated_at: Optional[datetime] = None

            @before_create
            def set_created_at(self):
                self.created_at = datetime.now()

            @before_save
            def set_updated_at(self):
                self.updated_at = datetime.now()

        User._repository = self.repo

        user = User(name="John")
        user.save()

        assert user.created_at is not None
        assert user.updated_at is not None

        created_at = user.created_at
        updated_at = user.updated_at

        # Update user
        import time
        time.sleep(0.01)  # Small delay
        user.name = "Jane"
        user.save()

        # created_at should not change, updated_at should
        assert user.created_at == created_at
        assert user.updated_at > updated_at

    def test_audit_trail(self):
        """Should create audit trail via callbacks"""
        audit_trail = []

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @after_create
            def log_creation(self):
                audit_trail.append({
                    'action': 'create',
                    'entity': 'User',
                    'id': self.id,
                    'name': self.name
                })

            @after_update
            def log_update(self):
                audit_trail.append({
                    'action': 'update',
                    'entity': 'User',
                    'id': self.id,
                    'name': self.name
                })

            @after_delete
            def log_deletion(self):
                audit_trail.append({
                    'action': 'delete',
                    'entity': 'User',
                    'id': self.id
                })

        User._repository = self.repo

        user = User(name="John")
        user.save()
        assert len(audit_trail) == 1
        assert audit_trail[0]['action'] == 'create'

        user.name = "Jane"
        user.save()
        assert len(audit_trail) == 2
        assert audit_trail[1]['action'] == 'update'

        user.delete()
        assert len(audit_trail) == 3
        assert audit_trail[2]['action'] == 'delete'

    def test_cache_invalidation(self):
        """Should invalidate cache on save/delete"""
        cache = {}

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @after_save
            def invalidate_cache(self):
                cache_key = f"user:{self.id}"
                if cache_key in cache:
                    del cache[cache_key]

            @after_delete
            def remove_from_cache(self):
                cache_key = f"user:{self.id}"
                cache.pop(cache_key, None)

        User._repository = self.repo

        user = User(name="John")
        user.save()

        # Simulate cache entry
        cache[f"user:{user.id}"] = {"name": "John"}

        user.name = "Jane"
        user.save()

        # Cache should be invalidated
        assert f"user:{user.id}" not in cache

    def test_dependent_cleanup(self):
        """Should cleanup dependent data on delete"""
        deleted_posts = []

        class Post(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            user_id: int
            title: str

        class User(EntityBase):
            _primary_key_field = 'id'
            id: Optional[int] = None
            name: str

            @before_delete
            def cleanup_posts(self):
                # In real scenario, would delete from repository
                deleted_posts.append(f"cleanup_posts_for_user:{self.id}")

        User._repository = self.repo
        Post._repository = self.repo

        user = User(name="John")
        user.save()

        post = Post(user_id=user.id, title="Test Post")
        post.save()

        user.delete()

        assert f"cleanup_posts_for_user:{user.id}" in deleted_posts
