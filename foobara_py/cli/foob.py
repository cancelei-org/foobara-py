"""
foob - Foobara Python CLI tool.

Main CLI application providing commands for:
- Project creation
- Code generation (commands, domains, entities, types)
- Running Foobara commands
- Interactive console
"""

from pathlib import Path
from typing import List, Optional

import typer
from typing_extensions import Annotated

# Main app
app = typer.Typer(
    name="foob",
    help="Foobara Python CLI - scaffolding and development tools",
    no_args_is_help=True,
)


# ==================== New Command ====================


@app.command("new")
def new_project(
    name: Annotated[str, typer.Argument(help="Project name")],
    path: Annotated[Optional[Path], typer.Option("--path", "-p", help="Output directory")] = None,
    template: Annotated[str, typer.Option("--template", "-t", help="Project template")] = "basic",
    python_version: Annotated[str, typer.Option("--python", help="Python version")] = "3.11",
    docker: Annotated[bool, typer.Option("--docker", help="Include Dockerfile")] = False,
    ci: Annotated[bool, typer.Option("--ci", help="Include CI workflow")] = False,
    no_makefile: Annotated[bool, typer.Option("--no-makefile", help="Skip Makefile")] = False,
):
    """
    Create a new Foobara Python project.

    Templates: basic, api, web, full

    Examples:
        foob new myapp
        foob new myapp --template api --docker --ci
        foob new myapp -p /projects -t full
    """
    from foobara_py.generators import generate_project

    output_dir = path or Path.cwd()

    typer.echo(f"Creating project '{name}' with template '{template}'...")

    try:
        files = generate_project(
            name=name,
            output_dir=output_dir,
            template=template,
            python_version=python_version,
            include_docker=docker,
            include_ci=ci,
            include_makefile=not no_makefile,
        )

        typer.echo(f"✓ Created {len(files)} files")
        typer.echo(f"\nProject created at: {output_dir / name.lower().replace('-', '_')}")
        typer.echo("\nNext steps:")
        typer.echo(f"  cd {name.lower().replace('-', '_')}")
        typer.echo("  pip install -e '.[dev]'")
        typer.echo("  make test")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# ==================== Generate Commands ====================

generate_app = typer.Typer(
    name="generate",
    help="Code generation commands",
    no_args_is_help=True,
)
app.add_typer(generate_app, name="generate")

# Alias 'g' for generate
app.add_typer(generate_app, name="g", hidden=True)


@generate_app.command("command")
def generate_command_cmd(
    name: Annotated[str, typer.Argument(help="Command name (e.g., CreateUser)")],
    domain: Annotated[Optional[str], typer.Option("--domain", "-d", help="Domain name")] = None,
    organization: Annotated[Optional[str], typer.Option("--org", help="Organization name")] = None,
    inputs: Annotated[
        Optional[List[str]], typer.Option("--input", "-i", help="Input field (name:type)")
    ] = None,
    result: Annotated[Optional[str], typer.Option("--result", "-r", help="Result type")] = None,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path(
        "commands"
    ),
    no_tests: Annotated[bool, typer.Option("--no-tests", help="Skip test generation")] = False,
):
    """
    Generate a new Foobara command.

    Examples:
        foob generate command CreateUser
        foob generate command CreateUser -d Users -i email:str -i name:str -r User
        foob g command ProcessPayment --domain Billing --result PaymentResult
    """
    from foobara_py.generators import generate_command

    # Parse inputs
    parsed_inputs = []
    if inputs:
        for inp in inputs:
            if ":" in inp:
                field_name, field_type = inp.split(":", 1)
                parsed_inputs.append({"name": field_name, "type": field_type})
            else:
                parsed_inputs.append({"name": inp, "type": "str"})

    typer.echo(f"Generating command '{name}'...")

    try:
        files = generate_command(
            name=name,
            output_dir=output,
            domain=domain,
            organization=organization,
            inputs=parsed_inputs if parsed_inputs else None,
            result_type=result,
            generate_tests=not no_tests,
        )

        typer.echo(f"✓ Created {len(files)} files:")
        for f in files:
            typer.echo(f"  - {f}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@generate_app.command("domain")
def generate_domain_cmd(
    name: Annotated[str, typer.Argument(help="Domain name (e.g., Users)")],
    organization: Annotated[Optional[str], typer.Option("--org", help="Organization name")] = None,
    dependencies: Annotated[
        Optional[List[str]], typer.Option("--dep", "-d", help="Domain dependency")
    ] = None,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path(
        "domains"
    ),
    no_commands: Annotated[bool, typer.Option("--no-commands", help="Skip commands dir")] = False,
    no_types: Annotated[bool, typer.Option("--no-types", help="Skip types dir")] = False,
    no_entities: Annotated[bool, typer.Option("--no-entities", help="Skip entities dir")] = False,
):
    """
    Generate a new Foobara domain.

    Examples:
        foob generate domain Users
        foob generate domain Orders --dep Users --dep Products
        foob g domain Analytics --org MyCompany
    """
    from foobara_py.generators import generate_domain

    typer.echo(f"Generating domain '{name}'...")

    try:
        files = generate_domain(
            name=name,
            output_dir=output,
            organization=organization,
            dependencies=dependencies,
            generate_commands_dir=not no_commands,
            generate_types_dir=not no_types,
            generate_entities_dir=not no_entities,
        )

        typer.echo(f"✓ Created {len(files)} files:")
        for f in files:
            typer.echo(f"  - {f}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@generate_app.command("entity")
def generate_entity_cmd(
    name: Annotated[str, typer.Argument(help="Entity name (e.g., User)")],
    fields: Annotated[
        Optional[List[str]], typer.Option("--field", "-f", help="Field (name:type)")
    ] = None,
    primary_key: Annotated[str, typer.Option("--pk", help="Primary key field")] = "id",
    domain: Annotated[Optional[str], typer.Option("--domain", "-d", help="Domain name")] = None,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path(
        "entities"
    ),
    no_tests: Annotated[bool, typer.Option("--no-tests", help="Skip test generation")] = False,
):
    """
    Generate a new Foobara entity.

    Examples:
        foob generate entity User -f id:int -f email:str -f name:str
        foob generate entity Product --pk product_id -f product_id:str -f name:str -f price:float
        foob g entity Order -d Orders -f id:int -f total:float
    """
    from foobara_py.generators import generate_type

    # Parse fields
    parsed_fields = []
    if fields:
        for field in fields:
            if ":" in field:
                field_name, field_type = field.split(":", 1)
                parsed_fields.append({"name": field_name, "type": field_type})
            else:
                parsed_fields.append({"name": field, "type": "str"})
    else:
        # Default fields if none provided
        parsed_fields = [
            {"name": "id", "type": "int"},
        ]

    typer.echo(f"Generating entity '{name}'...")

    try:
        files = generate_type(
            name=name,
            output_dir=output,
            kind="entity",
            fields=parsed_fields,
            primary_key=primary_key,
            domain=domain,
            generate_tests=not no_tests,
        )

        typer.echo(f"✓ Created {len(files)} files:")
        for f in files:
            typer.echo(f"  - {f}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@generate_app.command("model")
def generate_model_cmd(
    name: Annotated[str, typer.Argument(help="Model name (e.g., Address)")],
    fields: Annotated[
        Optional[List[str]], typer.Option("--field", "-f", help="Field (name:type)")
    ] = None,
    mutable: Annotated[bool, typer.Option("--mutable", help="Make model mutable")] = False,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path(
        "models"
    ),
    no_tests: Annotated[bool, typer.Option("--no-tests", help="Skip test generation")] = False,
):
    """
    Generate a new Foobara model (value object).

    Examples:
        foob generate model Address -f street:str -f city:str -f postal_code:str
        foob generate model Settings --mutable -f theme:str -f notifications:bool
        foob g model Money -f amount:float -f currency:str
    """
    from foobara_py.generators import generate_type

    # Parse fields
    parsed_fields = []
    if fields:
        for field in fields:
            if ":" in field:
                field_name, field_type = field.split(":", 1)
                parsed_fields.append({"name": field_name, "type": field_type})
            else:
                parsed_fields.append({"name": field, "type": "str"})

    typer.echo(f"Generating model '{name}'...")

    try:
        files = generate_type(
            name=name,
            output_dir=output,
            kind="model",
            fields=parsed_fields,
            mutable=mutable,
            generate_tests=not no_tests,
        )

        typer.echo(f"✓ Created {len(files)} files:")
        for f in files:
            typer.echo(f"  - {f}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@generate_app.command("crud")
def generate_crud_cmd(
    entity: Annotated[str, typer.Argument(help="Entity name (e.g., User)")],
    entity_module: Annotated[str, typer.Option("--module", "-m", help="Entity module path")] = None,
    fields: Annotated[
        Optional[List[str]], typer.Option("--field", "-f", help="Field (name:type)")
    ] = None,
    primary_key: Annotated[str, typer.Option("--pk", help="Primary key field")] = "id",
    operations: Annotated[
        Optional[List[str]], typer.Option("--op", help="Operations to generate")
    ] = None,
    domain: Annotated[Optional[str], typer.Option("--domain", "-d", help="Domain name")] = None,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path(
        "commands"
    ),
    no_tests: Annotated[bool, typer.Option("--no-tests", help="Skip test generation")] = False,
):
    """
    Generate CRUD commands for an entity.

    Operations: create, read, update, delete, list (default: all)

    Examples:
        foob generate crud User -f id:int -f email:str -f name:str
        foob generate crud Product --op create --op read --op list
        foob g crud Order -d Orders -m myapp.entities.order -f id:int -f total:float
    """
    from foobara_py.generators import generate_crud

    # Parse fields
    parsed_fields = []
    if fields:
        for field in fields:
            if ":" in field:
                field_name, field_type = field.split(":", 1)
                parsed_fields.append({"name": field_name, "type": field_type})
            else:
                parsed_fields.append({"name": field, "type": "str"})
    else:
        parsed_fields = [
            {"name": "id", "type": "int"},
        ]

    # Default module if not provided
    module = entity_module or f"entities.{entity.lower()}"

    typer.echo(f"Generating CRUD commands for '{entity}'...")

    try:
        files = generate_crud(
            entity_name=entity,
            entity_module=module,
            fields=parsed_fields,
            output_dir=output,
            primary_key=primary_key,
            operations=operations,
            domain=domain,
            generate_tests=not no_tests,
        )

        typer.echo(f"✓ Created {len(files)} files:")
        for f in files:
            typer.echo(f"  - {f}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# ==================== Console Command ====================


@app.command("console")
def console():
    """
    Start interactive Python console with Foobara loaded.

    Example:
        foob console
    """
    import code

    # Import Foobara components
    from foobara_py import Command, Domain, Outcome
    from foobara_py.core.registry import CommandRegistry
    from foobara_py.persistence.entity import EntityBase, Model

    banner = """
Foobara Python Console
======================
Available:
  - Command, Domain, Outcome
  - EntityBase, Model
  - CommandRegistry

Type help(Command) for documentation.
"""

    local_vars = {
        "Command": Command,
        "Domain": Domain,
        "Outcome": Outcome,
        "EntityBase": EntityBase,
        "Model": Model,
        "CommandRegistry": CommandRegistry,
    }

    code.interact(banner=banner, local=local_vars)


# ==================== Version Command ====================


@app.command("version")
def version():
    """Show foob version."""
    try:
        from foobara_py import __version__

        typer.echo(f"foob (foobara-py) version {__version__}")
    except ImportError:
        typer.echo("foob (foobara-py) version unknown")


# ==================== Main ====================


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
