"""
Project generator for Foobara Python.

Generates complete Foobara project structures with different templates.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from foobara_py.generators.files_generator import FilesGenerator

ProjectTemplate = Literal["basic", "api", "web", "full"]


class ProjectGenerator(FilesGenerator):
    """
    Generator for complete Foobara Python projects.

    Creates project structures with:
    - pyproject.toml with dependencies
    - Package structure with domains, commands, entities
    - Test setup with pytest
    - Optional Docker and CI configuration

    Templates:
    - basic: Minimal project with core Foobara setup
    - api: Adds HTTP connector and API server setup
    - web: Adds web framework integration
    - full: Complete setup with all features

    Usage:
        generator = ProjectGenerator(
            name="MyApp",
            template="api",
            python_version="3.11",
            include_docker=True,
            include_ci=True
        )

        files = generator.generate(output_dir=Path("."))

    This creates:
        myapp/
        ├── pyproject.toml
        ├── README.md
        ├── myapp/
        │   ├── __init__.py
        │   ├── domains/
        │   │   └── __init__.py
        │   ├── commands/
        │   │   └── __init__.py
        │   └── entities/
        │       └── __init__.py
        ├── tests/
        │   ├── __init__.py
        │   └── conftest.py
        ├── Dockerfile (optional)
        └── .github/workflows/ci.yml (optional)
    """

    def __init__(
        self,
        name: str,
        template: ProjectTemplate = "basic",
        python_version: str = "3.11",
        description: Optional[str] = None,
        author: Optional[str] = None,
        include_docker: bool = False,
        include_ci: bool = False,
        include_makefile: bool = True,
    ):
        """
        Initialize project generator.

        Args:
            name: Project name (e.g., "MyApp", "user-service")
            template: Project template type
            python_version: Python version requirement
            description: Project description
            author: Author name/email
            include_docker: Generate Dockerfile
            include_ci: Generate GitHub Actions CI workflow
            include_makefile: Generate Makefile with common commands
        """
        super().__init__()

        self.name = name
        self.template = template
        self.python_version = python_version
        self.description = description
        self.author = author
        self.include_docker = include_docker
        self.include_ci = include_ci
        self.include_makefile = include_makefile

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate project files.

        Args:
            output_dir: Base directory to generate project in
            **kwargs: Additional options

        Returns:
            List of generated file paths
        """
        files = []

        # Prepare context
        context = self._build_context()

        # Project root directory
        project_dir = output_dir / self._to_snake_case(self.name)

        # Core project files
        files.extend(self._generate_core_files(project_dir, context))

        # Package structure
        files.extend(self._generate_package_structure(project_dir, context))

        # Test structure
        files.extend(self._generate_test_structure(project_dir, context))

        # Template-specific files
        if self.template in ("api", "full"):
            files.extend(self._generate_api_files(project_dir, context))

        if self.template in ("web", "full"):
            files.extend(self._generate_web_files(project_dir, context))

        # Optional files
        if self.include_docker:
            files.append(self._generate_dockerfile(project_dir, context))

        if self.include_ci:
            files.append(self._generate_ci_workflow(project_dir, context))

        if self.include_makefile:
            files.append(self._generate_makefile(project_dir, context))

        return files

    def _build_context(self) -> Dict[str, Any]:
        """Build template context."""
        snake_name = self._to_snake_case(self.name)
        return {
            "project_name": self.name,
            "package_name": snake_name,
            "template": self.template,
            "python_version": self.python_version,
            "description": self.description or f"{self.name} - A Foobara Python application",
            "author": self.author or "",
            "include_docker": self.include_docker,
            "include_ci": self.include_ci,
            "is_api": self.template in ("api", "full"),
            "is_web": self.template in ("web", "full"),
            "is_full": self.template == "full",
        }

    def _generate_core_files(self, project_dir: Path, context: Dict[str, Any]) -> List[Path]:
        """Generate core project files."""
        files = []

        # pyproject.toml
        files.append(
            self.create_from_template(
                template_name="project_pyproject.toml.j2",
                output_path=project_dir / "pyproject.toml",
                context=context,
            )
        )

        # README.md
        files.append(
            self.create_from_template(
                template_name="project_readme.md.j2",
                output_path=project_dir / "README.md",
                context=context,
            )
        )

        # .gitignore
        files.append(
            self.create_from_template(
                template_name="project_gitignore.j2",
                output_path=project_dir / ".gitignore",
                context=context,
            )
        )

        return files

    def _generate_package_structure(self, project_dir: Path, context: Dict[str, Any]) -> List[Path]:
        """Generate main package structure."""
        files = []
        pkg_dir = project_dir / context["package_name"]

        # Main __init__.py
        files.append(
            self.create_from_template(
                template_name="project_init.py.j2",
                output_path=pkg_dir / "__init__.py",
                context=context,
            )
        )

        # Domains directory
        files.append(
            self.create_from_template(
                template_name="project_domains_init.py.j2",
                output_path=pkg_dir / "domains" / "__init__.py",
                context=context,
            )
        )

        # Commands directory
        files.append(
            self.create_from_template(
                template_name="project_commands_init.py.j2",
                output_path=pkg_dir / "commands" / "__init__.py",
                context=context,
            )
        )

        # Entities directory
        files.append(
            self.create_from_template(
                template_name="project_entities_init.py.j2",
                output_path=pkg_dir / "entities" / "__init__.py",
                context=context,
            )
        )

        return files

    def _generate_test_structure(self, project_dir: Path, context: Dict[str, Any]) -> List[Path]:
        """Generate test structure."""
        files = []
        tests_dir = project_dir / "tests"

        # tests/__init__.py
        files.append(
            self.create_file(
                output_path=tests_dir / "__init__.py",
                content="",
            )
        )

        # conftest.py
        files.append(
            self.create_from_template(
                template_name="project_conftest.py.j2",
                output_path=tests_dir / "conftest.py",
                context=context,
            )
        )

        return files

    def _generate_api_files(self, project_dir: Path, context: Dict[str, Any]) -> List[Path]:
        """Generate API-specific files."""
        files = []
        pkg_dir = project_dir / context["package_name"]

        # API server module
        files.append(
            self.create_from_template(
                template_name="project_server.py.j2",
                output_path=pkg_dir / "server.py",
                context=context,
            )
        )

        return files

    def _generate_web_files(self, project_dir: Path, context: Dict[str, Any]) -> List[Path]:
        """Generate web-specific files."""
        # Placeholder for web template files
        return []

    def _generate_dockerfile(self, project_dir: Path, context: Dict[str, Any]) -> Path:
        """Generate Dockerfile."""
        return self.create_from_template(
            template_name="project_dockerfile.j2",
            output_path=project_dir / "Dockerfile",
            context=context,
        )

    def _generate_ci_workflow(self, project_dir: Path, context: Dict[str, Any]) -> Path:
        """Generate CI workflow."""
        return self.create_from_template(
            template_name="project_ci.yml.j2",
            output_path=project_dir / ".github" / "workflows" / "ci.yml",
            context=context,
        )

    def _generate_makefile(self, project_dir: Path, context: Dict[str, Any]) -> Path:
        """Generate Makefile."""
        return self.create_from_template(
            template_name="project_makefile.j2",
            output_path=project_dir / "Makefile",
            context=context,
        )


def generate_project(
    name: str,
    output_dir: Path,
    template: ProjectTemplate = "basic",
    python_version: str = "3.11",
    description: Optional[str] = None,
    author: Optional[str] = None,
    include_docker: bool = False,
    include_ci: bool = False,
    include_makefile: bool = True,
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate a Foobara project.

    Args:
        name: Project name
        output_dir: Output directory
        template: Project template ("basic", "api", "web", "full")
        python_version: Python version requirement
        description: Project description
        author: Author name/email
        include_docker: Generate Dockerfile
        include_ci: Generate GitHub Actions CI
        include_makefile: Generate Makefile
        **kwargs: Additional options

    Returns:
        List of generated file paths

    Example:
        files = generate_project(
            name="UserService",
            output_dir=Path("."),
            template="api",
            python_version="3.11",
            include_docker=True,
            include_ci=True
        )
    """
    generator = ProjectGenerator(
        name=name,
        template=template,
        python_version=python_version,
        description=description,
        author=author,
        include_docker=include_docker,
        include_ci=include_ci,
        include_makefile=include_makefile,
    )

    return generator.generate(output_dir, **kwargs)
