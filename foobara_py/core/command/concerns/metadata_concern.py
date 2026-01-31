"""
MetadataConcern - Command metadata, manifest, and reflection.

Handles:
- Manifest generation for discovery/documentation
- Reflection metadata
- Domain dependencies declaration
- Possible errors declaration

Pattern: Ruby Foobara's Reflection and Description concerns
"""

from typing import Any, ClassVar, Dict, List, Tuple


class MetadataConcern:
    """Mixin for command metadata and reflection."""

    # Class-level configuration
    _depends_on: ClassVar[Tuple[str, ...]] = ()
    _possible_errors: ClassVar[Dict[str, Dict]] = {}

    @classmethod
    def depends_on(cls, *domains: str) -> None:
        """
        Declare domain dependencies.

        Args:
            *domains: Domain names this command depends on
        """
        cls._depends_on = tuple(domains)

    @classmethod
    def manifest(cls) -> dict:
        """
        Generate command manifest for discovery/documentation.

        Returns:
            Manifest dict with command metadata
        """
        return {
            "name": cls.full_name(),
            "description": cls.description(),
            "organization": cls._organization,
            "domain": cls._domain,
            "depends_on": list(cls._depends_on),
            "inputs_type": {"type": "attributes", "schema": cls.inputs_schema()},
            "result_type": {"type": str(cls.result_type())},
            "possible_errors": cls._possible_errors,
        }

    @classmethod
    def reflect(cls) -> "CommandManifest":
        """
        Get comprehensive reflection metadata for this command.

        Returns a CommandManifest object with complete introspection data including:
        - Command name and fully qualified name
        - Input and result schemas (JSON Schema)
        - Domain and organization
        - Possible errors
        - Whether command is async
        - Tags and description

        Returns:
            CommandManifest: Complete command metadata

        Example:
            >>> reflection = MyCommand.reflect()
            >>> print(reflection.full_name)
            "MyOrg::MyDomain::MyCommand"
            >>> print(reflection.inputs_schema)
            {"type": "object", "properties": {...}}
        """
        from foobara_py.manifest.command_manifest import CommandManifest

        return CommandManifest.from_command(cls)
