"""
Typer CLI Connector for foobara-py.

Exposes commands as CLI commands using Typer.
Similar to Ruby Foobara's CLI connector.

Features:
- Automatic CLI command generation from Foobara commands
- Input prompting for required fields
- Multiple output formats (table, JSON, plain)
- Automatic help generation from command metadata
- Domain/organization grouping as command groups

Usage:
    from foobara_py.connectors.cli import CLIConnector, create_cli_app

    # Create CLI app
    cli = CLIConnector()

    # Register commands
    cli.register(CreateUser)
    cli.register(ListUsers)

    # Or register a domain
    cli.register_domain(users_domain)

    # Run CLI
    cli.run()

    # Or use convenience function
    app = create_cli_app(commands=[CreateUser, ListUsers])
    app()
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from foobara_py.core.command import AsyncCommand, Command
from foobara_py.core.outcome import CommandOutcome
from foobara_py.domain.domain import Domain, Organization

logger = logging.getLogger(__name__)


class OutputFormat(str, Enum):
    """Output format options"""

    JSON = "json"
    TABLE = "table"
    PLAIN = "plain"


@dataclass(slots=True)
class CLIConfig:
    """Configuration for CLI command"""

    name: Optional[str] = None
    help: Optional[str] = None
    hidden: bool = False
    deprecated: bool = False
    rich_help_panel: Optional[str] = None


@dataclass(slots=True)
class CLIAppConfig:
    """Configuration for CLI application"""

    name: str = "foobara"
    help: Optional[str] = None
    add_completion: bool = True
    no_args_is_help: bool = True
    pretty_exceptions_enable: bool = True
    pretty_exceptions_short: bool = True
    default_output_format: OutputFormat = OutputFormat.JSON


class CommandCLI:
    """
    Wrapper for a command exposed as CLI command.

    Handles argument parsing, command execution, and output formatting.
    """

    __slots__ = ("command_class", "config", "output_format")

    def __init__(
        self,
        command_class: Type[Command],
        config: Optional[CLIConfig] = None,
        output_format: OutputFormat = OutputFormat.JSON,
    ):
        self.command_class = command_class
        self.config = config or self._default_config(command_class)
        self.output_format = output_format

    @staticmethod
    def _default_config(command_class: Type[Command]) -> CLIConfig:
        """Generate default CLI config from command"""
        name = command_class.full_name()
        # Convert CamelCase/:: to kebab-case
        cli_name = name.replace("::", "-").lower()
        # Convert camelCase to kebab-case
        result = []
        for char in cli_name:
            if char.isupper():
                result.append("-")
                result.append(char.lower())
            else:
                result.append(char)
        cli_name = "".join(result).strip("-")

        return CLIConfig(name=cli_name, help=command_class.description() or command_class.__doc__)

    def execute(self, **inputs: Any) -> Any:
        """Execute the command and return result"""
        outcome = self.command_class.run(**inputs)
        return self._format_output(outcome)

    def _format_output(self, outcome: CommandOutcome) -> str:
        """Format command outcome for CLI output"""
        if outcome.is_success():
            result = outcome.unwrap()
            return self._format_result(result)
        else:
            return self._format_errors(outcome.errors)

    def _format_result(self, result: Any) -> str:
        """Format successful result"""
        if self.output_format == OutputFormat.JSON:
            return self._to_json(result)
        elif self.output_format == OutputFormat.TABLE:
            return self._to_table(result)
        else:  # PLAIN
            return self._to_plain(result)

    def _format_errors(self, errors: List[Any]) -> str:
        """Format errors for CLI output"""
        if self.output_format == OutputFormat.JSON:
            error_list = []
            for e in errors:
                error_list.append({"symbol": getattr(e, "symbol", "error"), "message": str(e)})
            return json.dumps({"success": False, "errors": error_list}, indent=2)
        else:
            lines = ["Error:"]
            for e in errors:
                lines.append(f"  - {e}")
            return "\n".join(lines)

    def _to_json(self, result: Any) -> str:
        """Convert result to JSON string"""
        if hasattr(result, "model_dump"):
            data = result.model_dump()
        elif hasattr(result, "__dict__"):
            data = result.__dict__
        elif isinstance(result, (list, dict)):
            data = result
        else:
            data = result

        return json.dumps({"success": True, "result": data}, indent=2)

    def _to_table(self, result: Any) -> str:
        """Convert result to table format"""
        try:
            from io import StringIO

            from rich.console import Console
            from rich.table import Table

            console = Console(file=StringIO(), force_terminal=True)
            table = Table()

            # Handle list of items
            if isinstance(result, list) and result:
                first = result[0]
                if hasattr(first, "model_dump"):
                    keys = list(first.model_dump().keys())
                elif hasattr(first, "__dict__"):
                    keys = list(first.__dict__.keys())
                else:
                    return self._to_plain(result)

                for key in keys:
                    table.add_column(key.replace("_", " ").title())

                for item in result:
                    if hasattr(item, "model_dump"):
                        row = item.model_dump()
                    else:
                        row = item.__dict__
                    table.add_row(*[str(row.get(k, "")) for k in keys])

            # Handle single item
            elif hasattr(result, "model_dump"):
                data = result.model_dump()
                table.add_column("Field")
                table.add_column("Value")
                for k, v in data.items():
                    table.add_row(k.replace("_", " ").title(), str(v))

            elif hasattr(result, "__dict__"):
                table.add_column("Field")
                table.add_column("Value")
                for k, v in result.__dict__.items():
                    table.add_row(k.replace("_", " ").title(), str(v))

            else:
                return self._to_plain(result)

            console.print(table)
            return console.file.getvalue()

        except ImportError:
            # Fallback if rich not installed
            return self._to_plain(result)

    def _to_plain(self, result: Any) -> str:
        """Convert result to plain text"""
        if hasattr(result, "model_dump"):
            lines = []
            for k, v in result.model_dump().items():
                lines.append(f"{k}: {v}")
            return "\n".join(lines)
        elif isinstance(result, list):
            return "\n".join(str(item) for item in result)
        else:
            return str(result)

    def get_typer_params(self) -> List[Dict[str, Any]]:
        """Get Typer parameter definitions from command inputs"""
        inputs_type = self.command_class.inputs_type()
        params = []

        for field_name, field_info in inputs_type.model_fields.items():
            param = self._field_to_param(field_name, field_info)
            params.append(param)

        return params

    def _field_to_param(self, name: str, field_info: Any) -> Dict[str, Any]:
        """Convert Pydantic field to Typer parameter"""
        annotation = field_info.annotation
        is_required = field_info.is_required()
        default = field_info.default if not is_required else ...

        # Get the base type
        origin = get_origin(annotation)
        if origin is Union:
            args = get_args(annotation)
            # Handle Optional[X] = Union[X, None]
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                annotation = non_none[0]

        return {
            "name": name,
            "annotation": annotation,
            "default": default,
            "help": field_info.description or f"The {name.replace('_', ' ')}",
            "required": is_required,
        }


class CLIConnector:
    """
    Typer CLI Connector for exposing commands as CLI commands.

    Features:
    - Automatic command registration
    - Domain grouping as command groups
    - Multiple output formats
    - Input validation through Pydantic

    Usage:
        cli = CLIConnector()
        cli.register(CreateUser)
        cli.register_domain(users_domain)
        cli.run()
    """

    __slots__ = ("_app", "_commands", "_groups", "_config", "_output_format")

    def __init__(
        self,
        app: Any = None,  # Typer instance
        config: Optional[CLIAppConfig] = None,
        output_format: OutputFormat = OutputFormat.JSON,
    ):
        """
        Initialize CLI connector.

        Args:
            app: Optional Typer application instance
            config: CLI application configuration
            output_format: Default output format
        """
        self._config = config or CLIAppConfig()
        self._output_format = output_format
        self._commands: Dict[str, CommandCLI] = {}
        self._groups: Dict[str, Any] = {}  # Domain -> Typer group

        if app is None:
            self._app = self._create_app()
        else:
            self._app = app

        self._add_global_options()

    def _create_app(self) -> Any:
        """Create Typer application"""
        try:
            import typer

            app = typer.Typer(
                name=self._config.name,
                help=self._config.help or "Foobara CLI",
                add_completion=self._config.add_completion,
                no_args_is_help=self._config.no_args_is_help,
                pretty_exceptions_enable=self._config.pretty_exceptions_enable,
                pretty_exceptions_short=self._config.pretty_exceptions_short,
            )
            return app

        except ImportError:
            raise ImportError(
                "Typer is required for CLI connector. Install with: pip install typer[all]"
            )

    def _add_global_options(self) -> None:
        """Add global CLI options and built-in commands"""
        try:
            import typer

            @self._app.callback()
            def main(
                output: OutputFormat = typer.Option(
                    self._output_format, "--output", "-o", help="Output format"
                ),
                verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
            ):
                """Foobara CLI - Run commands from the command line."""
                pass

            # Add built-in manifest command
            @self._app.command(name="manifest", help="List all available commands")
            def manifest_cmd(
                format: OutputFormat = typer.Option(
                    OutputFormat.JSON, "--format", "-f", help="Output format for manifest"
                ),
            ):
                """Show manifest of all registered commands."""
                manifest = self.get_manifest()
                if format == OutputFormat.JSON:
                    typer.echo(json.dumps(manifest, indent=2))
                else:
                    typer.echo("Available Commands:")
                    typer.echo("-" * 40)
                    for name, info in manifest["commands"].items():
                        desc = info.get("description", "")[:50]
                        typer.echo(f"  {name}")
                        if desc:
                            typer.echo(f"    {desc}")

        except ImportError:
            pass

    def register(
        self, command_class: Type[Command], config: Optional[CLIConfig] = None
    ) -> "CLIConnector":
        """
        Register a command as CLI command.

        Args:
            command_class: Command class to register
            config: Optional CLI configuration

        Returns:
            Self for chaining
        """
        cmd_cli = CommandCLI(command_class, config, self._output_format)
        name = command_class.full_name()
        self._commands[name] = cmd_cli

        self._add_command(cmd_cli)

        logger.debug(f"Registered CLI command: {name} as {cmd_cli.config.name}")
        return self

    def register_domain(self, domain: Domain, group_name: Optional[str] = None) -> "CLIConnector":
        """
        Register all commands from a domain.

        Commands are grouped under a subcommand matching the domain name.

        Args:
            domain: Domain containing commands
            group_name: Optional override for group name

        Returns:
            Self for chaining
        """
        try:
            import typer

            # Create domain group
            name = group_name or domain.name.lower().replace(" ", "-")

            if name not in self._groups:
                group = typer.Typer(name=name, help=f"{domain.name} commands")
                self._groups[name] = group
                self._app.add_typer(group)

            group = self._groups[name]

            # Register commands in group
            commands = getattr(domain, "_commands", {})
            for command_class in commands.values():
                cmd_cli = CommandCLI(command_class, output_format=self._output_format)
                full_name = command_class.full_name()
                self._commands[full_name] = cmd_cli
                self._add_command_to_group(cmd_cli, group)

            logger.debug(f"Registered domain: {domain.name} with {len(commands)} commands")
            return self

        except ImportError:
            raise ImportError("Typer is required for CLI connector")

    def register_organization(self, org: Organization) -> "CLIConnector":
        """
        Register all domains from an organization.

        Args:
            org: Organization containing domains

        Returns:
            Self for chaining
        """
        domains = (
            org.list_domains()
            if hasattr(org, "list_domains")
            else getattr(org, "_domains", {}).values()
        )
        for domain in domains:
            self.register_domain(domain)

        logger.debug(f"Registered organization: {org.name}")
        return self

    def _add_command(self, cmd_cli: CommandCLI) -> None:
        """Add command to the main app"""
        try:
            import typer

            inputs_type = cmd_cli.command_class.inputs_type()

            # Build the command function dynamically
            def make_handler(cli: CommandCLI):
                def handler(**kwargs):
                    try:
                        output = cli.execute(**kwargs)
                        typer.echo(output)
                    except Exception as e:
                        typer.echo(f"Error: {e}", err=True)
                        raise typer.Exit(1)

                return handler

            handler = make_handler(cmd_cli)

            # Add Typer decorations for parameters
            for param in cmd_cli.get_typer_params():
                if param["required"]:
                    handler.__annotations__[param["name"]] = param["annotation"]
                else:
                    default = param["default"]
                    if default is None:
                        default = typer.Option(None, help=param["help"])
                    handler.__annotations__[param["name"]] = param["annotation"]

            # Register with Typer
            self._app.command(
                name=cmd_cli.config.name,
                help=cmd_cli.config.help,
                hidden=cmd_cli.config.hidden,
                deprecated=cmd_cli.config.deprecated,
            )(handler)

        except ImportError:
            pass

    def _add_command_to_group(self, cmd_cli: CommandCLI, group: Any) -> None:
        """Add command to a group (Typer instance)"""
        try:
            import typer

            def make_handler(cli: CommandCLI):
                def handler(**kwargs):
                    try:
                        output = cli.execute(**kwargs)
                        typer.echo(output)
                    except Exception as e:
                        typer.echo(f"Error: {e}", err=True)
                        raise typer.Exit(1)

                return handler

            handler = make_handler(cmd_cli)

            # Add type annotations for parameters
            for param in cmd_cli.get_typer_params():
                handler.__annotations__[param["name"]] = param["annotation"]

            # Use simple command name within group
            simple_name = cmd_cli.command_class.__name__.lower()
            # Convert CamelCase to kebab-case
            result = []
            for char in simple_name:
                if char.isupper() and result:
                    result.append("-")
                result.append(char.lower())
            simple_name = "".join(result)

            group.command(name=simple_name, help=cmd_cli.config.help)(handler)

        except ImportError:
            pass

    def run(self, args: Optional[List[str]] = None) -> None:
        """
        Run the CLI application.

        Args:
            args: Command line arguments (defaults to sys.argv)
        """
        if args:
            sys.argv[1:] = args
        self._app()

    def execute(self, command_name: str, **inputs: Any) -> str:
        """
        Execute a command programmatically.

        Args:
            command_name: Full command name
            inputs: Command inputs

        Returns:
            Formatted output string
        """
        cmd_cli = self._commands.get(command_name)
        if not cmd_cli:
            return json.dumps(
                {"success": False, "errors": [{"message": f"Command not found: {command_name}"}]}
            )
        return cmd_cli.execute(**inputs)

    def get_manifest(self) -> Dict[str, Any]:
        """
        Generate manifest of all registered CLI commands.

        Returns:
            Dict with command metadata for CLI discovery
        """
        commands = {}
        for name, cmd_cli in self._commands.items():
            cmd = cmd_cli.command_class
            commands[name] = {
                "cli_name": cmd_cli.config.name,
                "description": cmd.description() or "",
                "inputs_schema": cmd.inputs_schema(),
            }

            # Add possible errors if defined
            if hasattr(cmd, "possible_errors"):
                errors = cmd.possible_errors()
                if errors:
                    commands[name]["possible_errors"] = errors

        return {"app_name": self._config.name, "commands": commands, "count": len(commands)}

    @property
    def app(self) -> Any:
        """Get the underlying Typer app"""
        return self._app

    @property
    def commands(self) -> Dict[str, CommandCLI]:
        """Get all registered commands"""
        return self._commands.copy()

    def __len__(self) -> int:
        return len(self._commands)

    def __contains__(self, name: str) -> bool:
        return name in self._commands


def create_cli_app(
    commands: Optional[List[Type[Command]]] = None,
    domains: Optional[List[Domain]] = None,
    name: str = "foobara",
    help: Optional[str] = None,
    output_format: OutputFormat = OutputFormat.JSON,
    **typer_kwargs,
) -> Any:
    """
    Create a Typer CLI app with commands pre-registered.

    Convenience function for quick CLI setup.

    Args:
        commands: List of command classes to register
        domains: List of domains to register
        name: CLI app name
        help: CLI app help text
        output_format: Default output format
        **typer_kwargs: Additional Typer constructor arguments

    Returns:
        Configured Typer application

    Example:
        app = create_cli_app(
            commands=[CreateUser, ListUsers],
            name="myapp"
        )

        if __name__ == "__main__":
            app()
    """
    config = CLIAppConfig(name=name, help=help)
    connector = CLIConnector(config=config, output_format=output_format)

    if commands:
        for cmd in commands:
            connector.register(cmd)

    if domains:
        for domain in domains:
            connector.register_domain(domain)

    return connector.app
