"""
CLI Connector generator for Foobara Python.

Generates CLI entry point scripts that connect commands to the command line using Typer.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from foobara_py.generators.files_generator import FilesGenerator


class CLIConnectorGenerator(FilesGenerator):
    """
    Generator for Foobara CLI connector scripts.

    Creates CLI entry point scripts that:
    - Import necessary commands/domains/organizations
    - Configure the CLI connector
    - Register commands
    - Run the CLI application

    Usage:
        generator = CLIConnectorGenerator(
            app_name="MyApp",
            commands=["CreateUser", "ListUsers"],
            import_commands=[
                "from myapp.commands import CreateUser, ListUsers"
            ],
            cli_name="myapp",
            description="MyApp command-line interface"
        )

        files = generator.generate(output_dir=Path("myapp/bin"))
    """

    def __init__(
        self,
        app_name: Optional[str] = None,
        commands: Optional[List[str]] = None,
        domains: Optional[List[str]] = None,
        organizations: Optional[List[str]] = None,
        import_commands: Optional[List[str]] = None,
        import_domains: Optional[List[str]] = None,
        import_organizations: Optional[List[str]] = None,
        cli_name: Optional[str] = None,
        description: Optional[str] = None,
        help_text: Optional[str] = None,
        output_format: str = "JSON",
        levels_up: int = 0,
        filename: str = "cli.py",
    ):
        """
        Initialize CLI connector generator.

        Args:
            app_name: Application name for the CLI
            commands: List of command class names to register
            domains: List of domain variable names to register
            organizations: List of organization variable names to register
            import_commands: List of import statements for commands
            import_domains: List of import statements for domains
            import_organizations: List of import statements for organizations
            cli_name: CLI command name (e.g., "myapp" for `myapp command-name`)
            description: CLI description for docstring
            help_text: Help text shown when running --help
            output_format: Default output format (JSON, TABLE, PLAIN)
            levels_up: Number of parent directories to traverse to find project root
            filename: Output filename (default: "cli.py")
        """
        super().__init__()

        self.app_name = app_name
        self.commands = commands or []
        self.domains = domains or []
        self.organizations = organizations or []
        self.import_commands = import_commands or []
        self.import_domains = import_domains or []
        self.import_organizations = import_organizations or []
        self.cli_name = cli_name or "foobara"
        self.description = description
        self.help_text = help_text
        self.output_format = output_format
        self.levels_up = levels_up
        self.filename = filename

    def generate(self, output_dir: Path, **kwargs) -> List[Path]:
        """
        Generate CLI connector script.

        Args:
            output_dir: Directory to generate files in
            **kwargs: Additional options

        Returns:
            List of generated file paths
        """
        context = self._build_context()
        cli_file = self._generate_cli_file(output_dir, context)

        # Make the file executable
        cli_file.chmod(0o755)

        return [cli_file]

    def _build_context(self) -> Dict[str, Any]:
        """Build template context from generator configuration."""
        return {
            "app_name": self.app_name,
            "commands": self.commands,
            "domains": self.domains,
            "organizations": self.organizations,
            "import_commands": self.import_commands,
            "import_domains": self.import_domains,
            "import_organizations": self.import_organizations,
            "cli_name": self.cli_name,
            "description": self.description,
            "help_text": self.help_text,
            "output_format": self.output_format,
            "levels_up": self.levels_up,
        }

    def _generate_cli_file(self, output_dir: Path, context: Dict[str, Any]) -> Path:
        """Generate the CLI connector script file."""
        output_path = output_dir / self.filename

        return self.create_from_template(
            template_name="cli_connector.py.j2",
            output_path=output_path,
            context=context,
        )


def generate_cli_connector(
    output_dir: Path,
    app_name: Optional[str] = None,
    commands: Optional[List[str]] = None,
    domains: Optional[List[str]] = None,
    organizations: Optional[List[str]] = None,
    import_commands: Optional[List[str]] = None,
    import_domains: Optional[List[str]] = None,
    import_organizations: Optional[List[str]] = None,
    cli_name: Optional[str] = None,
    description: Optional[str] = None,
    help_text: Optional[str] = None,
    output_format: str = "JSON",
    levels_up: int = 0,
    filename: str = "cli.py",
    **kwargs,
) -> List[Path]:
    """
    Convenience function to generate a CLI connector script.

    Args:
        output_dir: Output directory
        app_name: Application name
        commands: List of command class names
        domains: List of domain variable names
        organizations: List of organization variable names
        import_commands: Import statements for commands
        import_domains: Import statements for domains
        import_organizations: Import statements for organizations
        cli_name: CLI command name
        description: CLI description
        help_text: Help text for --help
        output_format: Default output format
        levels_up: Parent directories to project root
        filename: Output filename
        **kwargs: Additional options

    Returns:
        List of generated file paths

    Example:
        files = generate_cli_connector(
            output_dir=Path("myapp/bin"),
            app_name="MyApp",
            commands=["CreateUser", "ListUsers"],
            import_commands=["from myapp.commands import CreateUser, ListUsers"],
            cli_name="myapp",
            levels_up=1
        )
    """
    generator = CLIConnectorGenerator(
        app_name=app_name,
        commands=commands,
        domains=domains,
        organizations=organizations,
        import_commands=import_commands,
        import_domains=import_domains,
        import_organizations=import_organizations,
        cli_name=cli_name,
        description=description,
        help_text=help_text,
        output_format=output_format,
        levels_up=levels_up,
        filename=filename,
    )

    return generator.generate(output_dir, **kwargs)
