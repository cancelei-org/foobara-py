"""Tests for entity associations"""

import pytest
from typing import Optional, List

from foobara_py.persistence import (
    EntityBase,
    has_many,
    belongs_to,
    has_one,
    InMemoryRepository,
    RepositoryRegistry,
    EagerLoader
)


# Test entities with associations
class User(EntityBase):
    """User entity with has_many and has_one associations"""
    _primary_key_field = 'id'

    id: int
    name: str
    email: str

    # Associations defined in class body (no type annotation)
    posts = has_many("Post", foreign_key="user_id")
    profile = has_one("Profile", foreign_key="user_id")


class Post(EntityBase):
    """Post entity with belongs_to association"""
    _primary_key_field = 'id'

    id: int
    title: str
    content: str
    user_id: Optional[int] = None

    # Association defined in class body (no type annotation)
    user = belongs_to(User, foreign_key="user_id")


class Profile(EntityBase):
    """Profile entity with belongs_to association"""
    _primary_key_field = 'id'

    id: int
    bio: str
    user_id: int

    # Association defined in class body (no type annotation)
    user = belongs_to(User, foreign_key="user_id")


class TestHasManyAssociation:
    """Test has_many associations"""

    def setup_method(self):
        """Setup repositories"""
        RepositoryRegistry.clear()

        # Create repositories
        self.user_repo = InMemoryRepository()
        self.post_repo = InMemoryRepository()

        # Register repositories
        User._repository = self.user_repo
        Post._repository = self.post_repo

        RepositoryRegistry.register(User, self.user_repo)
        RepositoryRegistry.register(Post, self.post_repo)

    def test_has_many_basic(self):
        """Should load associated entities"""
        # Create user
        user = User(id=1, name="John", email="john@example.com")
        self.user_repo.save(user)

        # Create posts
        post1 = Post(id=10, title="Post 1", content="Content 1", user_id=1)
        post2 = Post(id=20, title="Post 2", content="Content 2", user_id=1)
        self.post_repo.save(post1)
        self.post_repo.save(post2)

        # Load user and access posts
        loaded_user = self.user_repo.find(User, 1)
        posts = loaded_user.posts

        assert len(posts) == 2
        assert posts[0].title in ["Post 1", "Post 2"]
        assert posts[1].title in ["Post 1", "Post 2"]

    def test_has_many_empty(self):
        """Should return empty list when no associations"""
        user = User(id=1, name="John", email="john@example.com")
        self.user_repo.save(user)

        loaded_user = self.user_repo.find(User, 1)
        posts = loaded_user.posts

        assert posts == []

    def test_has_many_caching(self):
        """Should cache loaded associations"""
        user = User(id=1, name="John", email="john@example.com")
        self.user_repo.save(user)

        post1 = Post(id=10, title="Post 1", content="Content 1", user_id=1)
        self.post_repo.save(post1)

        loaded_user = self.user_repo.find(User, 1)

        # First access
        posts1 = loaded_user.posts

        # Second access should return cached value
        posts2 = loaded_user.posts

        assert posts1 is posts2  # Same object (cached)


class TestBelongsToAssociation:
    """Test belongs_to associations"""

    def setup_method(self):
        """Setup repositories"""
        RepositoryRegistry.clear()

        self.user_repo = InMemoryRepository()
        self.post_repo = InMemoryRepository()

        User._repository = self.user_repo
        Post._repository = self.post_repo

        RepositoryRegistry.register(User, self.user_repo)
        RepositoryRegistry.register(Post, self.post_repo)

    def test_belongs_to_basic(self):
        """Should load associated entity"""
        # Create user
        user = User(id=1, name="John", email="john@example.com")
        self.user_repo.save(user)

        # Create post
        post = Post(id=10, title="Post 1", content="Content 1", user_id=1)
        self.post_repo.save(post)

        # Load post and access user
        loaded_post = self.post_repo.find(Post, 10)
        loaded_user = loaded_post.user

        assert loaded_user is not None
        assert loaded_user.id == 1
        assert loaded_user.name == "John"

    def test_belongs_to_null(self):
        """Should return None when foreign key is None"""
        post = Post(id=10, title="Post 1", content="Content 1", user_id=None)
        self.post_repo.save(post)

        loaded_post = self.post_repo.find(Post, 10)
        user = loaded_post.user

        assert user is None

    def test_belongs_to_caching(self):
        """Should cache loaded association"""
        user = User(id=1, name="John", email="john@example.com")
        self.user_repo.save(user)

        post = Post(id=10, title="Post 1", content="Content 1", user_id=1)
        self.post_repo.save(post)

        loaded_post = self.post_repo.find(Post, 10)

        # First access
        user1 = loaded_post.user

        # Second access should return cached value
        user2 = loaded_post.user

        assert user1 is user2  # Same object (cached)


class TestHasOneAssociation:
    """Test has_one associations"""

    def setup_method(self):
        """Setup repositories"""
        RepositoryRegistry.clear()

        self.user_repo = InMemoryRepository()
        self.profile_repo = InMemoryRepository()

        User._repository = self.user_repo
        Profile._repository = self.profile_repo

        RepositoryRegistry.register(User, self.user_repo)
        RepositoryRegistry.register(Profile, self.profile_repo)

    def test_has_one_basic(self):
        """Should load associated entity"""
        # Create user
        user = User(id=1, name="John", email="john@example.com")
        self.user_repo.save(user)

        # Create profile
        profile = Profile(id=100, bio="Developer", user_id=1)
        self.profile_repo.save(profile)

        # Load user and access profile
        loaded_user = self.user_repo.find(User, 1)
        loaded_profile = loaded_user.profile

        assert loaded_profile is not None
        assert loaded_profile.id == 100
        assert loaded_profile.bio == "Developer"

    def test_has_one_null(self):
        """Should return None when no association"""
        user = User(id=1, name="John", email="john@example.com")
        self.user_repo.save(user)

        loaded_user = self.user_repo.find(User, 1)
        profile = loaded_user.profile

        assert profile is None

    def test_has_one_caching(self):
        """Should cache loaded association"""
        user = User(id=1, name="John", email="john@example.com")
        self.user_repo.save(user)

        profile = Profile(id=100, bio="Developer", user_id=1)
        self.profile_repo.save(profile)

        loaded_user = self.user_repo.find(User, 1)

        # First access
        profile1 = loaded_user.profile

        # Second access should return cached value
        profile2 = loaded_user.profile

        assert profile1 is profile2  # Same object (cached)


class TestEagerLoading:
    """Test eager loading to avoid N+1 queries"""

    def setup_method(self):
        """Setup repositories"""
        RepositoryRegistry.clear()

        self.user_repo = InMemoryRepository()
        self.post_repo = InMemoryRepository()
        self.profile_repo = InMemoryRepository()

        User._repository = self.user_repo
        Post._repository = self.post_repo
        Profile._repository = self.profile_repo

        RepositoryRegistry.register(User, self.user_repo)
        RepositoryRegistry.register(Post, self.post_repo)
        RepositoryRegistry.register(Profile, self.profile_repo)

    def test_eager_load_has_many(self):
        """Should eager load has_many associations"""
        # Create users
        user1 = User(id=1, name="John", email="john@example.com")
        user2 = User(id=2, name="Jane", email="jane@example.com")
        self.user_repo.save(user1)
        self.user_repo.save(user2)

        # Create posts
        post1 = Post(id=10, title="Post 1", content="Content 1", user_id=1)
        post2 = Post(id=20, title="Post 2", content="Content 2", user_id=1)
        post3 = Post(id=30, title="Post 3", content="Content 3", user_id=2)
        self.post_repo.save(post1)
        self.post_repo.save(post2)
        self.post_repo.save(post3)

        # Load all users
        users = self.user_repo.find_all(User)

        # Eager load posts
        EagerLoader.load(users, "posts")

        # Access posts (should be cached)
        assert len(users[0].posts) == 2
        assert len(users[1].posts) == 1

    def test_eager_load_belongs_to(self):
        """Should eager load belongs_to associations"""
        # Create users
        user1 = User(id=1, name="John", email="john@example.com")
        user2 = User(id=2, name="Jane", email="jane@example.com")
        self.user_repo.save(user1)
        self.user_repo.save(user2)

        # Create posts
        post1 = Post(id=10, title="Post 1", content="Content 1", user_id=1)
        post2 = Post(id=20, title="Post 2", content="Content 2", user_id=2)
        self.post_repo.save(post1)
        self.post_repo.save(post2)

        # Load all posts
        posts = self.post_repo.find_all(Post)

        # Eager load users
        EagerLoader.load(posts, "user")

        # Access users (should be cached)
        assert posts[0].user.name in ["John", "Jane"]
        assert posts[1].user.name in ["John", "Jane"]

    def test_eager_load_has_one(self):
        """Should eager load has_one associations"""
        # Create users
        user1 = User(id=1, name="John", email="john@example.com")
        user2 = User(id=2, name="Jane", email="jane@example.com")
        self.user_repo.save(user1)
        self.user_repo.save(user2)

        # Create profiles
        profile1 = Profile(id=100, bio="Developer", user_id=1)
        profile2 = Profile(id=200, bio="Designer", user_id=2)
        self.profile_repo.save(profile1)
        self.profile_repo.save(profile2)

        # Load all users
        users = self.user_repo.find_all(User)

        # Eager load profiles
        EagerLoader.load(users, "profile")

        # Access profiles (should be cached)
        assert users[0].profile.bio in ["Developer", "Designer"]
        assert users[1].profile.bio in ["Developer", "Designer"]
