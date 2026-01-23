"""Tests for Remote Imports System"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pydantic import BaseModel

from foobara_py.remote import (
    RemoteCommand,
    AsyncRemoteCommand,
    RemoteCommandError,
    ConnectionError,
    RemoteImporter,
    RemoteNamespace,
    RemoteImportError,
    ManifestFetchError,
    CommandNotFoundError,
    import_remote,
    ManifestCache,
    FileManifestCache,
    CacheEntry,
    get_manifest_cache,
    set_manifest_cache,
)


class TestManifestCache:
    """Test ManifestCache"""

    def test_create_cache(self):
        """Should create cache with default settings"""
        cache = ManifestCache()
        assert cache.ttl_seconds == 300
        assert cache.max_entries == 100
        assert cache.size == 0

    def test_cache_set_and_get(self):
        """Should store and retrieve manifest data"""
        cache = ManifestCache()
        data = {"commands": [{"name": "Test", "full_name": "Test"}]}

        cache.set("https://example.com/manifest", data)

        result = cache.get("https://example.com/manifest")
        assert result == data

    def test_cache_miss(self):
        """Should return None for cache miss"""
        cache = ManifestCache()
        assert cache.get("https://unknown.com/manifest") is None

    def test_cache_expiration(self):
        """Should expire entries after TTL"""
        cache = ManifestCache(ttl_seconds=1)
        data = {"commands": []}

        cache.set("https://example.com/manifest", data)

        # Manually expire the entry
        key = cache._cache_key("https://example.com/manifest")
        cache._entries[key].expires_at = datetime.now() - timedelta(seconds=1)

        assert cache.get("https://example.com/manifest") is None

    def test_cache_entry_properties(self):
        """Should track cache entry properties"""
        cache = ManifestCache(ttl_seconds=60)
        data = {"test": "data"}

        entry = cache.set("https://example.com/manifest", data, etag="abc123")

        assert entry.data == data
        assert entry.etag == "abc123"
        assert entry.url == "https://example.com/manifest"
        assert not entry.is_expired
        assert entry.age_seconds < 1

    def test_cache_invalidate(self):
        """Should remove entry on invalidate"""
        cache = ManifestCache()
        cache.set("https://example.com/manifest", {"data": "test"})

        assert cache.invalidate("https://example.com/manifest") is True
        assert cache.get("https://example.com/manifest") is None
        assert cache.invalidate("https://example.com/manifest") is False

    def test_cache_clear(self):
        """Should clear all entries"""
        cache = ManifestCache()
        cache.set("https://a.com/manifest", {"a": 1})
        cache.set("https://b.com/manifest", {"b": 2})

        count = cache.clear()

        assert count == 2
        assert cache.size == 0

    def test_cache_eviction(self):
        """Should evict oldest entry when at capacity"""
        cache = ManifestCache(max_entries=2)

        cache.set("https://a.com/manifest", {"a": 1})
        cache.set("https://b.com/manifest", {"b": 2})
        cache.set("https://c.com/manifest", {"c": 3})

        assert cache.size == 2
        assert cache.get("https://a.com/manifest") is None  # Evicted
        assert cache.get("https://b.com/manifest") is not None
        assert cache.get("https://c.com/manifest") is not None

    def test_cache_stats(self):
        """Should report cache statistics"""
        cache = ManifestCache(ttl_seconds=60, max_entries=50)
        cache.set("https://a.com/manifest", {"a": 1})

        stats = cache.stats()

        assert stats["total_entries"] == 1
        assert stats["valid_entries"] == 1
        assert stats["expired_entries"] == 0
        assert stats["max_entries"] == 50
        assert stats["ttl_seconds"] == 60

    def test_cleanup_expired(self):
        """Should cleanup expired entries"""
        cache = ManifestCache(ttl_seconds=1)
        cache.set("https://a.com/manifest", {"a": 1})
        cache.set("https://b.com/manifest", {"b": 2})

        # Expire first entry
        key = cache._cache_key("https://a.com/manifest")
        cache._entries[key].expires_at = datetime.now() - timedelta(seconds=1)

        removed = cache.cleanup_expired()

        assert removed == 1
        assert cache.size == 1


class TestRemoteCommand:
    """Test RemoteCommand"""

    def test_create_remote_command_class(self):
        """Should create RemoteCommand subclass"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://example.com"
            _command_name = "Test::TestCommand"
            _description = "A test command"

        assert TestCommand._remote_url == "https://example.com"
        assert TestCommand._command_name == "Test::TestCommand"
        assert TestCommand.full_name() == "Test::TestCommand"

    def test_inputs_type_extraction(self):
        """Should extract inputs type from generic"""
        class MyInputs(BaseModel):
            value: str

        class MyCommand(RemoteCommand[MyInputs, str]):
            _remote_url = "https://example.com"
            _command_name = "MyCommand"

        assert MyCommand.inputs_type() == MyInputs

    def test_inputs_schema(self):
        """Should generate inputs schema"""
        class TestInputs(BaseModel):
            name: str
            age: int = 0

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://example.com"
            _command_name = "Test"

        schema = TestCommand.inputs_schema()
        assert "properties" in schema
        assert "name" in schema["properties"]

    def test_validate_inputs(self):
        """Should validate inputs"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://example.com"
            _command_name = "Test"

        cmd = TestCommand(name="John")
        assert cmd.validate_inputs() is True
        assert cmd.inputs.name == "John"

    def test_manifest_generation(self):
        """Should generate command manifest"""
        class TestInputs(BaseModel):
            value: str

        class TestCommand(RemoteCommand[TestInputs, str]):
            _remote_url = "https://example.com"
            _command_name = "Test::TestCommand"
            _domain = "Test"

        manifest = TestCommand.manifest()

        assert manifest["name"] == "Test::TestCommand"
        assert manifest["domain"] == "Test"
        assert manifest["is_remote"] is True
        assert manifest["remote_url"] == "https://example.com"

    @patch("httpx.Client")
    def test_execute_success(self, mock_client_class):
        """Should execute remote command successfully"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://example.com"
            _command_name = "CreateUser"

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"id": 1, "name": "John"}}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        cmd = TestCommand(name="John")
        cmd.validate_inputs()
        result = cmd.execute()

        assert result == {"id": 1, "name": "John"}

    @patch("httpx.Client")
    def test_execute_error_response(self, mock_client_class):
        """Should handle error response"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://example.com"
            _command_name = "CreateUser"

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {"message": "Invalid input"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        cmd = TestCommand(name="John")
        cmd.validate_inputs()

        with pytest.raises(RemoteCommandError) as exc_info:
            cmd.execute()

        assert exc_info.value.status_code == 400

    @patch("httpx.Client")
    def test_run_returns_outcome(self, mock_client_class):
        """Should return CommandOutcome from run()"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _remote_url = "https://example.com"
            _command_name = "Test"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"success": True}}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        outcome = TestCommand.run(name="Test")

        assert outcome.is_success()
        assert outcome.unwrap() == {"success": True}

    def test_missing_remote_url(self):
        """Should error when remote URL not configured"""
        class TestInputs(BaseModel):
            name: str

        class TestCommand(RemoteCommand[TestInputs, dict]):
            _command_name = "Test"
            # _remote_url not set

        cmd = TestCommand(name="Test")
        cmd.validate_inputs()

        with pytest.raises(RemoteCommandError) as exc_info:
            cmd.execute()

        assert "not configured" in str(exc_info.value)


class TestRemoteImporter:
    """Test RemoteImporter"""

    def test_create_importer(self):
        """Should create importer with manifest URL"""
        importer = RemoteImporter("https://api.example.com/manifest")

        assert importer.manifest_url == "https://api.example.com/manifest"
        assert importer.base_url == "https://api.example.com"

    def test_base_url_derivation(self):
        """Should derive base URL from manifest URL"""
        importer1 = RemoteImporter("https://api.example.com/manifest")
        assert importer1.base_url == "https://api.example.com"

        # For nested paths, strips /manifest suffix
        importer2 = RemoteImporter("https://api.example.com/api/v1/manifest")
        assert importer2.base_url == "https://api.example.com/api/v1"

    @patch("httpx.Client")
    def test_fetch_manifest(self, mock_client_class):
        """Should fetch and parse manifest"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "version": "1.0",
            "commands": [
                {
                    "name": "CreateUser",
                    "full_name": "Users::CreateUser",
                    "inputs_schema": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"]
                    }
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        importer = RemoteImporter("https://api.example.com/manifest")
        manifest = importer.manifest

        assert manifest.command_count == 1
        assert manifest.commands[0].name == "CreateUser"

    @patch("httpx.Client")
    def test_list_commands(self, mock_client_class):
        """Should list available commands"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {"name": "CreateUser", "full_name": "Users::CreateUser"},
                {"name": "DeleteUser", "full_name": "Users::DeleteUser"},
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Use fresh cache to avoid cross-test pollution
        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        commands = importer.list_commands()

        assert "Users::CreateUser" in commands
        assert "Users::DeleteUser" in commands

    @patch("httpx.Client")
    def test_import_command(self, mock_client_class):
        """Should import command from manifest"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {
                    "name": "CreateUser",
                    "full_name": "Users::CreateUser",
                    "description": "Create a new user",
                    "domain": "Users",
                    "inputs_schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"}
                        },
                        "required": ["name", "email"]
                    }
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Use fresh cache to avoid cross-test pollution
        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        CreateUser = importer.import_command("Users::CreateUser")

        assert CreateUser.__name__ == "CreateUser"
        assert CreateUser._remote_url == "https://api.example.com"
        assert CreateUser._command_name == "Users::CreateUser"
        assert CreateUser._domain == "Users"

    @patch("httpx.Client")
    def test_import_command_not_found(self, mock_client_class):
        """Should raise error for unknown command"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"commands": []}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        importer = RemoteImporter("https://api.example.com/manifest")

        with pytest.raises(CommandNotFoundError):
            importer.import_command("Unknown::Command")

    @patch("httpx.Client")
    def test_import_all_commands(self, mock_client_class):
        """Should import all commands from manifest"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {"name": "CreateUser", "full_name": "Users::CreateUser"},
                {"name": "UpdateUser", "full_name": "Users::UpdateUser"},
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Use fresh cache to avoid cross-test pollution
        cache = ManifestCache()
        importer = RemoteImporter("https://api.example.com/manifest", cache=cache)
        commands = importer.import_all()

        assert "Users::CreateUser" in commands
        assert "Users::UpdateUser" in commands
        # Short names should also be available
        assert "CreateUser" in commands
        assert "UpdateUser" in commands

    @patch("httpx.Client")
    def test_as_namespace(self, mock_client_class):
        """Should create namespace with commands as attributes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {"name": "CreateUser", "full_name": "Users::CreateUser"},
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        importer = RemoteImporter("https://api.example.com/manifest")
        remote = importer.as_namespace()

        assert hasattr(remote, "CreateUser")
        assert remote.CreateUser._command_name == "Users::CreateUser"

    @patch("httpx.Client")
    def test_manifest_caching(self, mock_client_class):
        """Should cache manifest to avoid repeated fetches"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"etag": "abc123"}
        mock_response.json.return_value = {
            "commands": [{"name": "Test", "full_name": "Test"}]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        cache = ManifestCache()
        importer = RemoteImporter(
            "https://api.example.com/manifest",
            cache=cache
        )

        # First access
        _ = importer.manifest
        # Second access should use cache
        _ = importer.manifest

        # Should only make one HTTP call
        assert mock_client.__enter__.return_value.get.call_count == 1

    def test_fetch_manifest_connection_error(self):
        """Should handle connection errors gracefully"""
        import httpx

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            # httpx.ConnectError requires a message argument
            mock_client.__enter__.return_value.get.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            mock_client_class.return_value = mock_client

            # Use a fresh cache to avoid cached manifests
            cache = ManifestCache()
            importer = RemoteImporter("https://api.example.com/manifest", cache=cache)

            with pytest.raises(ManifestFetchError) as exc_info:
                _ = importer.manifest

            assert "Failed to connect" in str(exc_info.value)


class TestRemoteNamespace:
    """Test RemoteNamespace"""

    def test_namespace_attribute_access(self):
        """Should access commands via attributes"""
        class MockCommand:
            _command_name = "Test::CreateUser"

        commands = {
            "Test::CreateUser": MockCommand,
            "CreateUser": MockCommand,
        }

        importer = Mock()
        importer.manifest = Mock()

        namespace = RemoteNamespace(commands, importer)

        assert namespace.CreateUser == MockCommand

    def test_namespace_getattr_fallback(self):
        """Should find command by partial name"""
        class MockCommand:
            _command_name = "Users::CreateUser"

        commands = {"Users::CreateUser": MockCommand}

        importer = Mock()
        namespace = RemoteNamespace(commands, importer)

        # Should find even though we didn't register short name
        result = namespace.__getattr__("CreateUser")
        assert result == MockCommand

    def test_namespace_unknown_command(self):
        """Should raise AttributeError for unknown command"""
        importer = Mock()
        namespace = RemoteNamespace({}, importer)

        with pytest.raises(AttributeError):
            _ = namespace.UnknownCommand

    def test_namespace_list_commands(self):
        """Should list available commands"""
        commands = {
            "A::Create": Mock(),
            "B::Delete": Mock(),
        }

        importer = Mock()
        namespace = RemoteNamespace(commands, importer)

        assert set(namespace.list_commands()) == {"A::Create", "B::Delete"}


class TestImportRemoteFunction:
    """Test import_remote convenience function"""

    @patch("httpx.Client")
    def test_import_specific_command(self, mock_client_class):
        """Should import specific command"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {"name": "TestCommand", "full_name": "TestCommand"}
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Use fresh cache
        cache = ManifestCache()
        cmd = import_remote(
            "https://api.example.com/manifest",
            "TestCommand",
            cache=cache
        )

        assert cmd._command_name == "TestCommand"

    @patch("httpx.Client")
    def test_import_all_commands(self, mock_client_class):
        """Should import all commands when no name specified"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [
                {"name": "CommandA", "full_name": "CommandA"},
                {"name": "CommandB", "full_name": "CommandB"},
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Use fresh cache
        cache = ManifestCache()
        commands = import_remote("https://api.example.com/manifest", cache=cache)

        assert isinstance(commands, dict)
        assert "CommandA" in commands
        assert "CommandB" in commands


class TestAsyncRemoteCommand:
    """Test AsyncRemoteCommand"""

    def test_create_async_command(self):
        """Should create async remote command"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://example.com"
            _command_name = "Test"

        assert TestAsyncCommand._remote_url == "https://example.com"
        assert TestAsyncCommand.full_name() == "Test"

    @pytest.mark.asyncio
    async def test_async_run(self):
        """Should run async command"""
        class TestInputs(BaseModel):
            name: str

        class TestAsyncCommand(AsyncRemoteCommand[TestInputs, dict]):
            _remote_url = "https://example.com"
            _command_name = "Test"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"ok": True}}

            mock_client = MagicMock()
            mock_client.__aenter__.return_value.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            outcome = await TestAsyncCommand.run(name="Test")

            assert outcome.is_success()


class TestGlobalCache:
    """Test global cache management"""

    def test_get_default_cache(self):
        """Should return default cache"""
        cache = get_manifest_cache()
        assert isinstance(cache, ManifestCache)

    def test_set_default_cache(self):
        """Should set custom default cache"""
        custom_cache = ManifestCache(ttl_seconds=600)
        set_manifest_cache(custom_cache)

        cache = get_manifest_cache()
        assert cache.ttl_seconds == 600

        # Reset to default
        set_manifest_cache(ManifestCache())


class TestImportEntity:
    """Test entity import as DetachedEntity"""

    @patch("httpx.Client")
    def test_import_entity(self, mock_client_class):
        """Should import entity as DetachedEntity"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "commands": [],
            "entities": [
                {
                    "name": "User",
                    "full_name": "User",
                    "primary_key_field": "id",
                    "fields": {
                        "id": {"type": "int", "required": True},
                        "name": {"type": "str", "required": True},
                        "email": {"type": "str", "required": True},
                    }
                }
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        importer = RemoteImporter("https://api.example.com/manifest")

        # Need to add entity to manifest
        from foobara_py.manifest import EntityManifest
        importer._manifest = importer._fetch_manifest()
        importer._manifest.entities = [
            EntityManifest(
                name="User",
                full_name="User",
                primary_key_field="id",
                fields={
                    "id": {"type": "int", "required": True},
                    "name": {"type": "str", "required": True},
                }
            )
        ]

        User = importer.import_entity("User")

        assert User.__name__ == "User"
        assert User._primary_key_field == "id"
        assert User._source_system == "https://api.example.com"
