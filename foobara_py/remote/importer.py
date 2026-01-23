"""
Remote imports for Foobara services.

Allows importing commands and types from remote Foobara services
by fetching their manifest and dynamically creating local proxy classes.
"""

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

from foobara_py.manifest.command_manifest import CommandManifest
from foobara_py.manifest.root_manifest import RootManifest
from foobara_py.persistence.detached_entity import DetachedEntity
from foobara_py.remote.cache import ManifestCache, get_manifest_cache
from foobara_py.remote.remote_command import (
    AsyncRemoteCommand,
    RemoteCommand,
    RemoteCommandError,
)


class RemoteImportError(Exception):
    """Error during remote import."""

    pass


class ManifestFetchError(RemoteImportError):
    """Failed to fetch remote manifest."""

    def __init__(self, message: str, url: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class CommandNotFoundError(RemoteImportError):
    """Command not found in remote manifest."""

    def __init__(self, command_name: str, manifest_url: str):
        super().__init__(f"Command '{command_name}' not found in manifest at {manifest_url}")
        self.command_name = command_name
        self.manifest_url = manifest_url


class RemoteImporter:
    """
    Import commands and types from a remote Foobara service.

    RemoteImporter fetches the manifest from a remote service and
    dynamically creates local proxy classes that call the remote service.

    Usage:
        # Create importer from manifest URL
        importer = RemoteImporter("https://api.example.com/manifest")

        # Import a specific command
        CreateUser = importer.import_command("Users::CreateUser")

        # Run it like a local command
        outcome = CreateUser.run(name="John", email="john@example.com")
        if outcome.is_success():
            user = outcome.unwrap()

        # Import all commands
        commands = importer.import_all()
        for name, cmd_class in commands.items():
            print(f"Imported: {name}")

        # Import as a namespace
        remote = importer.as_namespace()
        outcome = remote.CreateUser.run(name="John", email="john@example.com")
    """

    def __init__(
        self,
        manifest_url: str,
        cache: Optional[ManifestCache] = None,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize remote importer.

        Args:
            manifest_url: URL to the remote manifest endpoint.
            cache: Optional manifest cache (uses default if not provided).
            timeout: HTTP request timeout in seconds.
            headers: Optional HTTP headers for requests.
        """
        self.manifest_url = manifest_url
        self.cache = cache or get_manifest_cache()
        self.timeout = timeout
        self.headers = headers or {}

        # Derive base URL from manifest URL
        # e.g., "https://api.example.com/manifest" -> "https://api.example.com"
        if manifest_url.endswith("/manifest"):
            self.base_url = manifest_url[:-9]
        else:
            # Try to extract base from URL
            from urllib.parse import urlparse

            parsed = urlparse(manifest_url)
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"

        self._manifest: Optional[RootManifest] = None
        self._imported_commands: Dict[str, Type[RemoteCommand]] = {}
        self._imported_types: Dict[str, Type[BaseModel]] = {}

    def _fetch_manifest(self, force_refresh: bool = False) -> RootManifest:
        """
        Fetch and parse the remote manifest.

        Args:
            force_refresh: Force refresh even if cached.

        Returns:
            RootManifest parsed from remote service.

        Raises:
            ManifestFetchError: If manifest cannot be fetched.
        """
        # Check cache first
        if not force_refresh:
            cached_data = self.cache.get(self.manifest_url)
            if cached_data is not None:
                return self._parse_manifest(cached_data)

        # Fetch from remote
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for remote imports. "
                "Install it with: pip install foobara-py[http]"
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                # Check for conditional request support
                cache_entry = self.cache.get_entry(self.manifest_url)
                request_headers = dict(self.headers)

                if cache_entry and cache_entry.etag:
                    request_headers["If-None-Match"] = cache_entry.etag

                response = client.get(self.manifest_url, headers=request_headers)

                # Handle 304 Not Modified
                if response.status_code == 304 and cache_entry:
                    return self._parse_manifest(cache_entry.data)

                if response.status_code >= 400:
                    raise ManifestFetchError(
                        f"HTTP {response.status_code}: {response.text}",
                        url=self.manifest_url,
                        status_code=response.status_code,
                    )

                data = response.json()

                # Cache the response
                etag = response.headers.get("etag")
                self.cache.set(self.manifest_url, data, etag=etag)

                return self._parse_manifest(data)

        except httpx.ConnectError as e:
            raise ManifestFetchError(
                f"Failed to connect to {self.manifest_url}: {e}",
                url=self.manifest_url,
            )
        except httpx.TimeoutException:
            raise ManifestFetchError(
                f"Request timed out after {self.timeout}s",
                url=self.manifest_url,
            )

    def _parse_manifest(self, data: Dict[str, Any]) -> RootManifest:
        """Parse manifest data into RootManifest."""
        # Handle different manifest formats
        if "commands" in data and isinstance(data["commands"], list):
            # Already in expected format
            commands = [CommandManifest(**cmd) for cmd in data["commands"]]
            return RootManifest(
                commands=commands,
                command_count=len(commands),
                version=data.get("version", "1.0"),
                foobara_version=data.get("foobara_version", "unknown"),
            )

        # Try to parse directly
        return RootManifest.model_validate(data)

    def _schema_to_model(
        self,
        schema: Optional[Dict[str, Any]],
        name: str = "DynamicModel",
    ) -> Type[BaseModel]:
        """
        Convert JSON Schema to Pydantic model.

        Args:
            schema: JSON Schema dict.
            name: Model class name.

        Returns:
            Dynamically created Pydantic model class.
        """
        if not schema:
            return create_model(name)

        # Extract properties and required fields
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        # Build field definitions
        fields: Dict[str, Any] = {}
        for field_name, field_schema in properties.items():
            field_type = self._schema_type_to_python(field_schema)
            is_required = field_name in required

            if is_required:
                fields[field_name] = (field_type, ...)
            else:
                default = field_schema.get("default")
                fields[field_name] = (Optional[field_type], default)

        return create_model(name, **fields)

    def _schema_type_to_python(self, schema: Dict[str, Any]) -> type:
        """Convert JSON Schema type to Python type."""
        json_type = schema.get("type", "string")

        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        if json_type == "array":
            items_schema = schema.get("items", {})
            items_type = self._schema_type_to_python(items_schema)
            return List[items_type]

        return type_map.get(json_type, Any)

    @property
    def manifest(self) -> RootManifest:
        """Get the remote manifest (fetched on first access)."""
        if self._manifest is None:
            self._manifest = self._fetch_manifest()
        return self._manifest

    def refresh(self) -> RootManifest:
        """Force refresh the manifest from remote."""
        self._manifest = self._fetch_manifest(force_refresh=True)
        return self._manifest

    def list_commands(self) -> List[str]:
        """List all available command names."""
        return [cmd.full_name for cmd in self.manifest.commands]

    def import_command(
        self,
        command_name: str,
        async_mode: bool = False,
    ) -> Type[RemoteCommand]:
        """
        Import a single command from the remote service.

        Args:
            command_name: Name or full name of the command.
            async_mode: If True, create AsyncRemoteCommand instead.

        Returns:
            RemoteCommand subclass that calls the remote service.

        Raises:
            CommandNotFoundError: If command not found in manifest.
        """
        # Check if already imported
        cache_key = f"{command_name}:{'async' if async_mode else 'sync'}"
        if cache_key in self._imported_commands:
            return self._imported_commands[cache_key]

        # Find command in manifest
        cmd_manifest = self.manifest.find_command(command_name)
        if cmd_manifest is None:
            raise CommandNotFoundError(command_name, self.manifest_url)

        # Create input model from schema
        inputs_model = self._schema_to_model(
            cmd_manifest.inputs_schema, f"{cmd_manifest.name}Inputs"
        )

        # Create result model from schema (if available)
        result_model: type = Any
        if cmd_manifest.result_schema:
            result_model = self._schema_to_model(
                cmd_manifest.result_schema, f"{cmd_manifest.name}Result"
            )

        # Choose base class - use non-generic form to avoid type() MRO issues
        base_class = AsyncRemoteCommand if async_mode else RemoteCommand

        # Create RemoteCommand subclass without generic parameters
        # We store type info as class attributes instead
        command_class = type(
            cmd_manifest.name,
            (base_class,),
            {
                "_remote_url": self.base_url,
                "_command_name": cmd_manifest.full_name,
                "_timeout": self.timeout,
                "_headers": self.headers,
                "_description": cmd_manifest.description or "",
                "_domain": cmd_manifest.domain,
                "_organization": cmd_manifest.organization,
                "__doc__": cmd_manifest.description or f"Remote command: {cmd_manifest.full_name}",
                # Store type info for inputs_type() and result_type() methods
                "_inputs_model": inputs_model,
                "_result_model": result_model,
            },
        )

        # Override inputs_type and result_type to return stored models
        def inputs_type_override(cls=command_class, model=inputs_model):
            return model

        def result_type_override(cls=command_class, model=result_model):
            return model

        command_class.inputs_type = classmethod(lambda cls: inputs_model)
        command_class.result_type = classmethod(lambda cls: result_model)

        # Cache for reuse
        self._imported_commands[cache_key] = command_class

        return command_class

    def import_all(
        self,
        async_mode: bool = False,
    ) -> Dict[str, Type[RemoteCommand]]:
        """
        Import all commands from the remote service.

        Args:
            async_mode: If True, create AsyncRemoteCommand classes.

        Returns:
            Dict mapping command names to RemoteCommand classes.
        """
        commands = {}
        for cmd_manifest in self.manifest.commands:
            try:
                cmd_class = self.import_command(cmd_manifest.full_name, async_mode)
                commands[cmd_manifest.full_name] = cmd_class
                # Also add short name if unique
                if cmd_manifest.name not in commands:
                    commands[cmd_manifest.name] = cmd_class
            except Exception:
                # Skip commands that fail to import
                pass

        return commands

    def import_entity(self, entity_name: str) -> Type[DetachedEntity]:
        """
        Import an entity type as a DetachedEntity.

        Entities from remote services cannot be persisted locally,
        so they are represented as DetachedEntity instances.

        Args:
            entity_name: Name of the entity to import.

        Returns:
            DetachedEntity subclass.

        Raises:
            RemoteImportError: If entity not found.
        """
        # Check if already imported
        if entity_name in self._imported_types:
            entity_class = self._imported_types[entity_name]
            if issubclass(entity_class, DetachedEntity):
                return entity_class

        # Find entity in manifest
        entity_manifest = self.manifest.find_entity(entity_name)
        if entity_manifest is None:
            raise RemoteImportError(f"Entity '{entity_name}' not found in manifest")

        # Build field definitions from schema or fields dict
        fields: Dict[str, Any] = {}

        if entity_manifest.fields:
            for field_name, field_info in entity_manifest.fields.items():
                field_type_str = field_info.get("type", "str")
                field_type = self._type_string_to_python(field_type_str)
                is_required = field_info.get("required", True)

                if is_required:
                    fields[field_name] = (field_type, ...)
                else:
                    fields[field_name] = (Optional[field_type], None)

        elif entity_manifest.json_schema:
            return self._schema_to_detached_entity(
                entity_manifest.json_schema,
                entity_name,
                entity_manifest.primary_key_field,
            )

        # Create DetachedEntity subclass
        entity_class = create_model(entity_name, __base__=DetachedEntity, **fields)

        # Set metadata
        entity_class._primary_key_field = entity_manifest.primary_key_field
        entity_class._source_system = self.base_url

        # Cache
        self._imported_types[entity_name] = entity_class

        return entity_class

    def _schema_to_detached_entity(
        self,
        schema: Dict[str, Any],
        name: str,
        primary_key_field: str = "id",
    ) -> Type[DetachedEntity]:
        """Convert JSON Schema to DetachedEntity subclass."""
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        fields: Dict[str, Any] = {}
        for field_name, field_schema in properties.items():
            field_type = self._schema_type_to_python(field_schema)
            is_required = field_name in required

            if is_required:
                fields[field_name] = (field_type, ...)
            else:
                default = field_schema.get("default")
                fields[field_name] = (Optional[field_type], default)

        entity_class = create_model(name, __base__=DetachedEntity, **fields)

        entity_class._primary_key_field = primary_key_field
        entity_class._source_system = self.base_url

        return entity_class

    def _type_string_to_python(self, type_str: str) -> type:
        """Convert type string to Python type."""
        type_map = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": float,
            "number": float,
            "bool": bool,
            "boolean": bool,
            "list": list,
            "dict": dict,
            "any": Any,
        }
        # Handle parameterized types like "List[str]"
        base_type = type_str.lower().split("[")[0]
        return type_map.get(base_type, str)

    def as_namespace(self, async_mode: bool = False) -> "RemoteNamespace":
        """
        Create a namespace object with all commands as attributes.

        Usage:
            remote = importer.as_namespace()
            outcome = remote.CreateUser.run(name="John", email="john@example.com")

        Args:
            async_mode: If True, create async command classes.

        Returns:
            RemoteNamespace with commands as attributes.
        """
        commands = self.import_all(async_mode=async_mode)
        return RemoteNamespace(commands, self)


class RemoteNamespace:
    """
    Namespace object providing attribute access to remote commands.

    Created by RemoteImporter.as_namespace().
    """

    def __init__(
        self,
        commands: Dict[str, Type[RemoteCommand]],
        importer: RemoteImporter,
    ):
        self._commands = commands
        self._importer = importer

        # Set commands as attributes
        for name, cmd_class in commands.items():
            # Use simple name (without domain prefix) as attribute
            attr_name = name.split("::")[-1]
            if not hasattr(self, attr_name):
                setattr(self, attr_name, cmd_class)

    def __getattr__(self, name: str) -> Type[RemoteCommand]:
        """Get command by name."""
        # Try exact match
        if name in self._commands:
            return self._commands[name]

        # Try to find by simple name
        for full_name, cmd_class in self._commands.items():
            if full_name.endswith(f"::{name}") or full_name == name:
                return cmd_class

        raise AttributeError(f"Command '{name}' not found in remote namespace")

    def list_commands(self) -> List[str]:
        """List available commands."""
        return list(self._commands.keys())

    @property
    def manifest(self) -> RootManifest:
        """Get the remote manifest."""
        return self._importer.manifest


def import_remote(
    manifest_url: str,
    command_name: Optional[str] = None,
    **kwargs,
) -> Type[RemoteCommand] | Dict[str, Type[RemoteCommand]]:
    """
    Convenience function to import from a remote service.

    Args:
        manifest_url: URL to the remote manifest.
        command_name: Optional specific command to import.
        **kwargs: Additional arguments for RemoteImporter.

    Returns:
        If command_name provided: Single RemoteCommand class.
        Otherwise: Dict of all commands.

    Usage:
        # Import specific command
        CreateUser = import_remote(
            "https://api.example.com/manifest",
            "Users::CreateUser"
        )

        # Import all commands
        commands = import_remote("https://api.example.com/manifest")
    """
    importer = RemoteImporter(manifest_url, **kwargs)

    if command_name:
        return importer.import_command(command_name)

    return importer.import_all()
