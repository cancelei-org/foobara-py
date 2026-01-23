"""
Base class for file generators with template support.

Provides scaffolding for code generation using Jinja2 templates.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2

from foobara_py.util.case_conversion import (
    to_camel_case,
    to_kebab_case,
    to_pascal_case,
    to_snake_case,
)


class GeneratorError(Exception):
    """Base exception for generator errors."""

    pass


class TemplateNotFoundError(GeneratorError):
    """Raised when a template file cannot be found."""

    pass


class FileExistsError(GeneratorError):
    """Raised when attempting to create a file that already exists."""

    pass


class FilesGenerator(ABC):
    """
    Base class for code generators with template support.

    Provides infrastructure for:
    - Loading Jinja2 templates
    - Rendering templates with context data
    - Creating files and directories
    - Managing template paths

    Usage:
        class CommandGenerator(FilesGenerator):
            def __init__(self, name: str, domain: str = ""):
                super().__init__()
                self.name = name
                self.domain = domain

            def generate(self, output_dir: Path) -> List[Path]:
                context = {
                    "command_name": self.name,
                    "domain_name": self.domain,
                }

                files = []
                files.append(self.create_from_template(
                    template_name="command.py.j2",
                    output_path=output_dir / f"{self.name.lower()}.py",
                    context=context
                ))

                return files
    """

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        autoescape: bool = False,
        trim_blocks: bool = True,
        lstrip_blocks: bool = True,
    ):
        """
        Initialize the generator.

        Args:
            template_dir: Directory containing Jinja2 templates (defaults to ./templates relative to class)
            autoescape: Enable Jinja2 autoescaping (default: False for code generation)
            trim_blocks: Strip trailing newlines after blocks
            lstrip_blocks: Strip leading spaces before blocks
        """
        self._template_dir = template_dir or self._default_template_dir()
        self._jinja_env = self._create_jinja_env(
            autoescape=autoescape,
            trim_blocks=trim_blocks,
            lstrip_blocks=lstrip_blocks,
        )

    def _default_template_dir(self) -> Path:
        """
        Get default template directory.

        Defaults to ./templates relative to the generator class file.

        Returns:
            Path to template directory
        """
        import inspect

        class_file = Path(inspect.getfile(self.__class__))
        return class_file.parent / "templates"

    def _create_jinja_env(
        self,
        autoescape: bool,
        trim_blocks: bool,
        lstrip_blocks: bool,
    ) -> jinja2.Environment:
        """
        Create and configure Jinja2 environment.

        Args:
            autoescape: Enable autoescaping
            trim_blocks: Strip trailing newlines after blocks
            lstrip_blocks: Strip leading spaces before blocks

        Returns:
            Configured Jinja2 environment
        """
        loader = jinja2.FileSystemLoader(str(self._template_dir))

        env = jinja2.Environment(
            loader=loader,
            autoescape=autoescape,
            trim_blocks=trim_blocks,
            lstrip_blocks=lstrip_blocks,
            keep_trailing_newline=True,  # Preserve final newline
        )

        # Add custom filters
        env.filters["snake_case"] = to_snake_case
        env.filters["pascal_case"] = to_pascal_case
        env.filters["camel_case"] = to_camel_case
        env.filters["kebab_case"] = to_kebab_case

        return env

    @abstractmethod
    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate files.

        Subclasses must implement this method to define what files to generate.

        Args:
            output_dir: Directory to generate files in
            **kwargs: Additional generation options

        Returns:
            List of generated file paths

        Raises:
            GeneratorError: If generation fails
        """
        pass

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a template with given context.

        Args:
            template_name: Name of template file
            context: Dictionary of variables for template

        Returns:
            Rendered template content

        Raises:
            TemplateNotFoundError: If template doesn't exist
        """
        try:
            template = self._jinja_env.get_template(template_name)
            return template.render(**context)
        except jinja2.TemplateNotFound as e:
            raise TemplateNotFoundError(
                f"Template '{template_name}' not found in {self._template_dir}"
            ) from e

    def create_from_template(
        self,
        template_name: str,
        output_path: Path,
        context: Dict[str, Any],
        overwrite: bool = False,
    ) -> Path:
        """
        Render template and write to file.

        Args:
            template_name: Name of template file
            output_path: Path to write rendered content
            context: Dictionary of variables for template
            overwrite: Whether to overwrite existing files

        Returns:
            Path to created file

        Raises:
            TemplateNotFoundError: If template doesn't exist
            FileExistsError: If file exists and overwrite=False
        """
        # Check if file exists
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {output_path}")

        # Render template
        content = self.render_template(template_name, context)

        # Create parent directories
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        output_path.write_text(content, encoding="utf-8")

        return output_path

    def create_file(
        self,
        output_path: Path,
        content: str,
        overwrite: bool = False,
    ) -> Path:
        """
        Create a file with given content (no template).

        Args:
            output_path: Path to write content
            content: File content
            overwrite: Whether to overwrite existing files

        Returns:
            Path to created file

        Raises:
            FileExistsError: If file exists and overwrite=False
        """
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {output_path}")

        # Create parent directories
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        output_path.write_text(content, encoding="utf-8")

        return output_path

    def create_directory(self, dir_path: Path, exist_ok: bool = True) -> Path:
        """
        Create a directory.

        Args:
            dir_path: Path to create
            exist_ok: Don't raise error if directory exists

        Returns:
            Path to created directory

        Raises:
            GeneratorError: If directory creation fails
        """
        try:
            dir_path.mkdir(parents=True, exist_ok=exist_ok)
            return dir_path
        except Exception as e:
            raise GeneratorError(f"Failed to create directory {dir_path}: {e}") from e

    # String transformation utilities - delegate to module-level functions
    @staticmethod
    def _to_snake_case(text: str) -> str:
        """Convert to snake_case (delegates to case_conversion module)"""
        return to_snake_case(text)

    @staticmethod
    def _to_pascal_case(text: str) -> str:
        """Convert to PascalCase (delegates to case_conversion module)"""
        return to_pascal_case(text)

    @staticmethod
    def _to_camel_case(text: str) -> str:
        """Convert to camelCase (delegates to case_conversion module)"""
        return to_camel_case(text)

    @staticmethod
    def _to_kebab_case(text: str) -> str:
        """Convert to kebab-case (delegates to case_conversion module)"""
        return to_kebab_case(text)
