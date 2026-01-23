"""
Code generators for Foobara Python.

Provides tools for scaffolding commands, domains, types, and other Foobara components.
"""

from foobara_py.generators.autocrud_generator import (
    AutoCRUDGenerator,
    generate_crud,
)
from foobara_py.generators.cli_connector_generator import (
    CLIConnectorGenerator,
    generate_cli_connector,
)
from foobara_py.generators.command_generator import (
    CommandGenerator,
    generate_command,
)
from foobara_py.generators.domain_generator import (
    DomainGenerator,
    generate_domain,
)
from foobara_py.generators.domain_mapper_generator import (
    DomainMapperGenerator,
    generate_domain_mapper,
)
from foobara_py.generators.files_generator import (
    FileExistsError,
    FilesGenerator,
    GeneratorError,
    TemplateNotFoundError,
)
from foobara_py.generators.organization_generator import (
    OrganizationGenerator,
    generate_organization,
)
from foobara_py.generators.project_generator import (
    ProjectGenerator,
    generate_project,
)
from foobara_py.generators.remote_imports_generator import (
    RemoteImportsGenerator,
    generate_remote_imports,
)
from foobara_py.generators.type_generator import (
    TypeGenerator,
    generate_type,
)

__all__ = [
    "FilesGenerator",
    "GeneratorError",
    "TemplateNotFoundError",
    "FileExistsError",
    "CommandGenerator",
    "generate_command",
    "TypeGenerator",
    "generate_type",
    "DomainGenerator",
    "generate_domain",
    "AutoCRUDGenerator",
    "generate_crud",
    "ProjectGenerator",
    "generate_project",
    "DomainMapperGenerator",
    "generate_domain_mapper",
    "OrganizationGenerator",
    "generate_organization",
    "CLIConnectorGenerator",
    "generate_cli_connector",
    "RemoteImportsGenerator",
    "generate_remote_imports",
]
