"""
Remote imports for Foobara services.

This module enables importing commands and types from remote Foobara services.
Remote commands are proxies that call the remote service via HTTP while
maintaining the same interface as local commands.

Usage:
    from foobara_py.remote import RemoteImporter, import_remote

    # Method 1: Using RemoteImporter
    importer = RemoteImporter("https://api.example.com/manifest")

    # Import a specific command
    CreateUser = importer.import_command("Users::CreateUser")
    outcome = CreateUser.run(name="John", email="john@example.com")

    # Import all commands
    commands = importer.import_all()

    # Use as namespace
    remote = importer.as_namespace()
    outcome = remote.CreateUser.run(name="John", email="john@example.com")

    # Method 2: Using import_remote shortcut
    CreateUser = import_remote(
        "https://api.example.com/manifest",
        "Users::CreateUser"
    )

    # Method 3: Import entities as DetachedEntity
    User = importer.import_entity("User")
    user = User.from_remote({"id": 1, "name": "John"}, source="api.example.com")
"""

from foobara_py.remote.cache import (
    CacheEntry,
    FileManifestCache,
    ManifestCache,
    get_manifest_cache,
    set_manifest_cache,
)
from foobara_py.remote.importer import (
    CommandNotFoundError,
    ManifestFetchError,
    RemoteImporter,
    RemoteImportError,
    RemoteNamespace,
    import_remote,
)
from foobara_py.remote.remote_command import (
    AsyncRemoteCommand,
    RemoteCommand,
    RemoteCommandError,
    RemoteConnectionError,
)

__all__ = [
    # Remote commands
    "RemoteCommand",
    "AsyncRemoteCommand",
    "RemoteCommandError",
    "RemoteConnectionError",
    # Importer
    "RemoteImporter",
    "RemoteNamespace",
    "RemoteImportError",
    "ManifestFetchError",
    "CommandNotFoundError",
    "import_remote",
    # Cache
    "ManifestCache",
    "FileManifestCache",
    "CacheEntry",
    "get_manifest_cache",
    "set_manifest_cache",
]
