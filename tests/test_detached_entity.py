"""Tests for DetachedEntity"""

import pytest
from pydantic import ValidationError
from foobara_py.persistence import DetachedEntity, detached_entity


# Test entities
class RemoteUser(DetachedEntity):
    """User entity from remote system"""
    _primary_key_field = 'id'
    _source_system = 'external-api'

    id: int
    name: str
    email: str


@detached_entity(primary_key='user_id', source_system='partner-api')
class PartnerUser(DetachedEntity):
    """User from partner system with custom config"""
    user_id: int
    username: str
    active: bool


class RemotePost(DetachedEntity):
    """Post entity from remote system"""
    _primary_key_field = 'id'

    id: int
    title: str
    content: str
    author_id: int


class TestDetachedEntityBasics:
    """Test basic DetachedEntity functionality"""

    def test_create_detached_entity(self):
        """Should create detached entity"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")

        assert user.id == 1
        assert user.name == "John Doe"
        assert user.email == "john@example.com"

    def test_primary_key(self):
        """Should access primary key"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")

        assert user.primary_key == 1

    def test_source_system_class_level(self):
        """Should track source system from class definition"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")

        assert user.source_system == 'external-api'

    def test_from_remote(self):
        """Should create from remote data"""
        data = {
            'id': 1,
            'name': 'John Doe',
            'email': 'john@example.com'
        }

        user = RemoteUser.from_remote(data, source='api.example.com')

        assert user.id == 1
        assert user.name == "John Doe"
        assert user.source_system == 'api.example.com'  # Instance source overrides class

    def test_from_remote_without_class_source(self):
        """Should use instance source when class has none"""
        data = {
            'id': 1,
            'title': 'Test Post',
            'content': 'Content',
            'author_id': 1
        }

        post = RemotePost.from_remote(data, source='blog.example.com')

        assert post.source_system == 'blog.example.com'


class TestDetachedEntityImmutability:
    """Test immutability of detached entities"""

    def test_immutable_fields(self):
        """Should not allow field modification"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")

        with pytest.raises(ValidationError):
            user.name = "Jane Doe"

    def test_frozen_model(self):
        """Should be frozen"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")

        # Pydantic frozen models raise ValidationError on assignment
        with pytest.raises(ValidationError):
            user.email = "jane@example.com"


class TestDetachedEntityComparison:
    """Test equality and hashing"""

    def test_equality_same_pk(self):
        """Should be equal if same class and primary key"""
        user1 = RemoteUser(id=1, name="John Doe", email="john@example.com")
        user2 = RemoteUser(id=1, name="Jane Doe", email="jane@example.com")

        assert user1 == user2  # Same id, different data

    def test_equality_different_pk(self):
        """Should not be equal if different primary key"""
        user1 = RemoteUser(id=1, name="John Doe", email="john@example.com")
        user2 = RemoteUser(id=2, name="John Doe", email="john@example.com")

        assert user1 != user2

    def test_equality_different_class(self):
        """Should not be equal if different class"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")
        post = RemotePost(id=1, title="Post", content="Content", author_id=1)

        assert user != post

    def test_hashable(self):
        """Should be hashable for use in sets/dicts"""
        user1 = RemoteUser(id=1, name="John Doe", email="john@example.com")
        user2 = RemoteUser(id=1, name="Jane Doe", email="jane@example.com")
        user3 = RemoteUser(id=2, name="Bob Smith", email="bob@example.com")

        # Can be used in sets
        user_set = {user1, user2, user3}
        assert len(user_set) == 2  # user1 and user2 have same hash (same id)

        # Can be dict keys
        user_dict = {
            user1: "first",
            user2: "second",  # Overwrites first (same key)
            user3: "third"
        }
        assert len(user_dict) == 2


class TestDetachedEntitySerialization:
    """Test serialization methods"""

    def test_to_dict(self):
        """Should convert to dictionary"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")
        data = user.to_dict()

        assert data == {
            'id': 1,
            'name': 'John Doe',
            'email': 'john@example.com'
        }

    def test_to_json(self):
        """Should convert to JSON string"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")
        json_str = user.to_json()

        assert '"id":1' in json_str or '"id": 1' in json_str
        assert '"name":"John Doe"' in json_str or '"name": "John Doe"' in json_str


class TestDetachedEntityPersistenceBlocking:
    """Test that persistence operations are blocked"""

    def test_save_blocked(self):
        """Should not allow save"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")

        with pytest.raises(NotImplementedError, match="cannot be saved"):
            user.save()

    def test_delete_blocked(self):
        """Should not allow delete"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")

        with pytest.raises(NotImplementedError, match="cannot be deleted"):
            user.delete()

    def test_reload_blocked(self):
        """Should not allow reload"""
        user = RemoteUser(id=1, name="John Doe", email="john@example.com")

        with pytest.raises(NotImplementedError, match="cannot be reloaded"):
            user.reload()

    def test_create_blocked(self):
        """Should not allow create"""
        with pytest.raises(NotImplementedError, match="Use from_remote"):
            RemoteUser.create(id=1, name="John Doe", email="john@example.com")

    def test_find_blocked(self):
        """Should not allow find"""
        with pytest.raises(NotImplementedError, match="cannot be found"):
            RemoteUser.find(1)

    def test_find_all_blocked(self):
        """Should not allow find_all"""
        with pytest.raises(NotImplementedError, match="cannot be queried"):
            RemoteUser.find_all()


class TestDetachedEntityDecorator:
    """Test @detached_entity decorator"""

    def test_decorator_primary_key(self):
        """Should set custom primary key via decorator"""
        user = PartnerUser(user_id=1, username="john", active=True)

        assert user.primary_key == 1

    def test_decorator_source_system(self):
        """Should set source system via decorator"""
        user = PartnerUser(user_id=1, username="john", active=True)

        assert user.source_system == 'partner-api'

    def test_decorator_immutable(self):
        """Should still be immutable with decorator"""
        user = PartnerUser(user_id=1, username="john", active=True)

        with pytest.raises(ValidationError):
            user.username = "jane"


class TestDetachedEntityRealWorld:
    """Test real-world usage scenarios"""

    def test_remote_api_data(self):
        """Should handle data from remote API"""
        # Simulate API response
        api_response = {
            'id': 42,
            'name': 'External User',
            'email': 'external@example.com'
        }

        user = RemoteUser.from_remote(api_response, source='api.partner.com')

        assert user.id == 42
        assert user.source_system == 'api.partner.com'
        assert isinstance(user, DetachedEntity)

    def test_multiple_sources(self):
        """Should distinguish entities from different sources"""
        user1 = RemoteUser.from_remote(
            {'id': 1, 'name': 'User A', 'email': 'a@example.com'},
            source='system-a'
        )
        user2 = RemoteUser.from_remote(
            {'id': 1, 'name': 'User B', 'email': 'b@example.com'},
            source='system-b'
        )

        # Same primary key but different sources
        assert user1 == user2  # Equal by pk
        assert user1.source_system != user2.source_system
        assert user1.source_system == 'system-a'
        assert user2.source_system == 'system-b'

    def test_caching_use_case(self):
        """Should work well for caching remote data"""
        # Fetch from remote system
        remote_data = {'id': 1, 'name': 'John', 'email': 'john@example.com'}
        user = RemoteUser.from_remote(remote_data, source='cache')

        # Use as cache key
        cache = {}
        cache[user] = {'last_accessed': '2025-01-20'}

        # Retrieve from cache
        lookup = RemoteUser(id=1, name="Different Name", email="diff@example.com")
        assert lookup in cache  # Found by primary key

    def test_validation_still_works(self):
        """Should still validate data types"""
        with pytest.raises(ValidationError):
            # Invalid email type
            RemoteUser(id="not-an-int", name="John", email="john@example.com")

    def test_extra_fields_forbidden(self):
        """Should forbid extra fields"""
        with pytest.raises(ValidationError):
            RemoteUser(
                id=1,
                name="John",
                email="john@example.com",
                extra_field="not allowed"
            )
