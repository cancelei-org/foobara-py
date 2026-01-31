#!/usr/bin/env python3
"""
Ruby DSL to Pydantic Converter

Automates the conversion of Foobara Ruby commands to Python/Pydantic format.
Target: 90% automation of the porting process.

Usage:
    python -m tools.ruby_to_python_converter --input path/to/ruby_command.rb --output path/to/python_command.py
    python -m tools.ruby_to_python_converter --input path/to/ruby_command.rb  # prints to stdout
    python -m tools.ruby_to_python_converter --batch path/to/commands_dir/
"""

import re
import sys
import argparse
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
import json


# =============================================================================
# Type Mappings
# =============================================================================

TYPE_MAPPING = {
    # Primitive types
    "string": "str",
    "integer": "int",
    "float": "float",
    "boolean": "bool",
    "number": "float",

    # Collection types
    "array": "list",
    "hash": "dict",
    "associative_array": "dict",

    # Special types
    "email": "EmailStr",
    "url": "HttpUrl",
    "datetime": "datetime",
    "date": "date",
    "time": "time",
    "uuid": "UUID",

    # Duck types
    "duck": "Any",

    # Complex types
    "attributes": "BaseModel",
    "model": "BaseModel",
    "entity": "Any",  # Entity needs to be defined per domain
    "associative_array": "Dict[str, Any]",
}

# Pydantic imports needed for special types
IMPORT_REQUIREMENTS = {
    "EmailStr": "from pydantic import EmailStr",
    "HttpUrl": "from pydantic import HttpUrl",
    "UUID": "from uuid import UUID",
    "datetime": "from datetime import datetime",
    "date": "from datetime import date",
    "time": "from datetime import time",
    "Any": "from typing import Any",
    "Optional": "from typing import Optional",
    "List": "from typing import List",
    "Dict": "from typing import Dict",
    "Annotated": "from typing import Annotated",
    "Field": "from pydantic import Field",
    "BaseModel": "from pydantic import BaseModel",
    "field_validator": "from pydantic import field_validator",
}


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class FieldDefinition:
    """Represents a single input field definition"""
    name: str
    type: str
    required: bool = False
    default: Optional[Any] = None
    min: Optional[float] = None
    max: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    one_of: Optional[List[Any]] = None
    element_type: Optional[str] = None
    validators: List[str] = field(default_factory=list)
    description: Optional[str] = None

    def to_python_type(self) -> str:
        """Convert to Python type annotation"""
        base_type = TYPE_MAPPING.get(self.type, self.type)

        # Handle array types
        if self.type == "array" and self.element_type:
            element_type = TYPE_MAPPING.get(self.element_type, self.element_type)
            base_type = f"List[{element_type}]"

        # Handle hash types
        if self.type == "hash":
            base_type = "Dict[str, Any]"

        # Handle one_of as Literal
        if self.one_of:
            values = ", ".join(repr(v) for v in self.one_of)
            base_type = f"Literal[{values}]"

        # Handle constraints with Annotated
        if self.has_field_constraints():
            constraints = self._build_field_constraints()
            base_type = f"Annotated[{base_type}, {constraints}]"

        # Handle optional
        if not self.required:
            base_type = f"Optional[{base_type}]"

        return base_type

    def has_field_constraints(self) -> bool:
        """Check if field has Pydantic Field constraints"""
        return any([
            self.min is not None,
            self.max is not None,
            self.min_length is not None,
            self.max_length is not None,
            self.pattern is not None,
            self.description is not None
        ])

    def _build_field_constraints(self) -> str:
        """Build Field() constructor arguments"""
        constraints = []

        if self.min is not None:
            constraints.append(f"ge={self.min}")
        if self.max is not None:
            constraints.append(f"le={self.max}")
        if self.min_length is not None:
            constraints.append(f"min_length={self.min_length}")
        if self.max_length is not None:
            constraints.append(f"max_length={self.max_length}")
        if self.pattern is not None:
            constraints.append(f"regex={self.pattern!r}")
        if self.description is not None:
            constraints.append(f"description={self.description!r}")

        return f"Field({', '.join(constraints)})"

    def get_default_value(self) -> str:
        """Get the default value string"""
        if self.default is not None:
            if isinstance(self.default, str):
                return repr(self.default)
            return str(self.default)
        if self.required:
            return "..."
        return "None"


@dataclass
class CommandDefinition:
    """Represents a complete command definition"""
    class_name: str
    inputs: List[FieldDefinition] = field(default_factory=list)
    result_type: Optional[str] = None
    description: Optional[str] = None
    module_path: Optional[str] = None
    parent_class: str = "Foobara::Command"
    methods: List[str] = field(default_factory=list)
    callbacks: List[str] = field(default_factory=list)


# =============================================================================
# Parser
# =============================================================================

class RubyDSLParser:
    """Parses Ruby Foobara command DSL"""

    def __init__(self, ruby_code: str):
        self.ruby_code = ruby_code
        self.lines = ruby_code.split('\n')

    def parse(self) -> CommandDefinition:
        """Parse the complete Ruby command"""
        cmd = CommandDefinition(
            class_name=self._extract_class_name(),
            inputs=self._extract_inputs(),
            result_type=self._extract_result_type(),
            description=self._extract_description(),
            module_path=self._extract_module_path(),
            methods=self._extract_methods()
        )
        return cmd

    def _extract_class_name(self) -> str:
        """Extract the command class name"""
        # Look for: class ClassName < ParentClass
        match = re.search(r'class\s+(\w+)\s*<', self.ruby_code)
        if match:
            return match.group(1)

        # Look for stub_class definitions
        match = re.search(r'stub_class\([:\'](\w+)', self.ruby_code)
        if match:
            return match.group(1)

        return "UnknownCommand"

    def _extract_module_path(self) -> Optional[str]:
        """Extract module namespace"""
        modules = []
        for line in self.lines:
            match = re.match(r'\s*module\s+(\w+)', line)
            if match:
                modules.append(match.group(1))
        return "::".join(modules) if modules else None

    def _extract_description(self) -> Optional[str]:
        """Extract command description from comments"""
        # Look for comments before class definition
        description_lines = []
        in_comment_block = False

        for line in self.lines:
            if re.match(r'\s*#', line):
                comment = re.sub(r'^\s*#\s?', '', line)
                description_lines.append(comment)
                in_comment_block = True
            elif in_comment_block and re.match(r'\s*class\s+', line):
                break
            elif in_comment_block:
                break

        return ' '.join(description_lines).strip() if description_lines else None

    def _extract_inputs(self) -> List[FieldDefinition]:
        """Extract input definitions from inputs do...end block"""
        inputs = []

        # Pattern 1: inputs do...end block
        inputs_block = self._extract_block('inputs')
        if inputs_block:
            inputs.extend(self._parse_inputs_block(inputs_block))

        # Pattern 2: inputs type: :attributes, element_type_declarations: {...}
        match = re.search(
            r'inputs\s+type:\s*:(\w+),?\s*element_type_declarations:\s*\{([^}]+)\}',
            self.ruby_code,
            re.DOTALL
        )
        if match:
            inputs.extend(self._parse_element_type_declarations(match.group(2)))

        # Pattern 3: inputs key: :type syntax
        match = re.search(r'inputs\s+([^d\n][^\n]*)', self.ruby_code)
        if match and not inputs:
            inputs.extend(self._parse_inline_inputs(match.group(1)))

        # Pattern 4: add_inputs block
        add_inputs_block = self._extract_block('add_inputs')
        if add_inputs_block:
            inputs.extend(self._parse_inputs_block(add_inputs_block))

        return inputs

    def _extract_block(self, block_name: str) -> Optional[str]:
        """Extract a do...end block by name"""
        pattern = rf'{block_name}\s+do\s*\n(.*?)\n\s*end'
        match = re.search(pattern, self.ruby_code, re.DOTALL)
        return match.group(1) if match else None

    def _parse_inputs_block(self, block: str) -> List[FieldDefinition]:
        """Parse inputs from a do...end block"""
        inputs = []
        lines = block.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            field_def = self._parse_input_line(line)
            if field_def:
                inputs.append(field_def)

        return inputs

    def _parse_input_line(self, line: str) -> Optional[FieldDefinition]:
        """Parse a single input field definition line"""
        # Pattern: field_name :type, option: value, ...
        # Examples:
        #   name :string, :required
        #   age :integer, min: 0, max: 150
        #   email :email
        #   who :string, default: "World"

        # Extract field name and type
        match = re.match(r'(\w+)\s+:(\w+)(.*)', line)
        if not match:
            return None

        field_name = match.group(1)
        field_type = match.group(2)
        options_str = match.group(3)

        field = FieldDefinition(name=field_name, type=field_type)

        # Parse options
        if ':required' in options_str:
            field.required = True

        # Extract key-value options
        # Special handling for arrays (one_of: [...])
        # First, handle array values
        array_pattern = r'(\w+):\s*(\[[^\]]+\])'
        for key, value in re.findall(array_pattern, options_str):
            if key == 'one_of':
                field.one_of = self._parse_array(value)

        # Then handle simple key-value pairs
        kv_pattern = r'(\w+):\s*([^\[,]+?)(?=,|\s|$)'
        for key, value in re.findall(kv_pattern, options_str):
            value = value.strip()

            if key == 'default':
                field.default = self._parse_value(value)
            elif key == 'min':
                field.min = float(value)
            elif key == 'max':
                field.max = float(value)
            elif key == 'min_length':
                field.min_length = int(value)
            elif key == 'max_length':
                field.max_length = int(value)
            elif key == 'pattern':
                field.pattern = value.strip('"\'/')
            elif key == 'element_type':
                field.element_type = value.strip(':')

        return field

    def _parse_element_type_declarations(self, declarations: str) -> List[FieldDefinition]:
        """Parse element_type_declarations hash"""
        inputs = []

        # Parse key: :type pairs
        pattern = r'(\w+):\s*:(\w+)'
        for name, type_name in re.findall(pattern, declarations):
            inputs.append(FieldDefinition(
                name=name,
                type=type_name,
                required=False
            ))

        return inputs

    def _parse_inline_inputs(self, inline: str) -> List[FieldDefinition]:
        """Parse inline inputs definition (key: :type, ...)"""
        inputs = []

        # Parse key: :type pairs
        pattern = r'(\w+):\s*:(\w+)'
        for name, type_name in re.findall(pattern, inline):
            inputs.append(FieldDefinition(
                name=name,
                type=type_name,
                required=False
            ))

        return inputs

    def _parse_value(self, value: str) -> Any:
        """Parse a Ruby value to Python equivalent"""
        value = value.strip()

        # String
        if value.startswith('"') or value.startswith("'"):
            return value.strip('"\'')

        # Number
        if value.replace('.', '').replace('-', '').isdigit():
            return float(value) if '.' in value else int(value)

        # Boolean
        if value == 'true':
            return True
        if value == 'false':
            return False

        # Nil
        if value == 'nil':
            return None

        return value

    def _parse_array(self, array_str: str) -> List[Any]:
        """Parse a Ruby array"""
        # Handle both ["a", "b"] and %w[a b] syntax
        array_str = array_str.strip()

        # Remove brackets
        array_str = array_str.strip('[]')

        # Handle empty array
        if not array_str.strip():
            return []

        # Split by comma and parse each value
        values = []
        for item in array_str.split(','):
            item = item.strip()
            if item:
                # Remove quotes from string literals
                if item.startswith('"') and item.endswith('"'):
                    values.append(item[1:-1])
                elif item.startswith("'") and item.endswith("'"):
                    values.append(item[1:-1])
                else:
                    values.append(self._parse_value(item))

        return values

    def _extract_result_type(self) -> Optional[str]:
        """Extract result type declaration"""
        match = re.search(r'result\s+:(\w+)', self.ruby_code)
        if match:
            return match.group(1)

        # Try to infer from type declaration
        match = re.search(r'result\s+type:\s*:(\w+)', self.ruby_code)
        if match:
            return match.group(1)

        return None

    def _extract_methods(self) -> List[str]:
        """Extract method definitions"""
        methods = []

        # Find all def...end blocks
        pattern = r'def\s+(\w+).*?end'
        for match in re.finditer(pattern, self.ruby_code, re.DOTALL):
            methods.append(match.group(0))

        return methods


# =============================================================================
# Generator
# =============================================================================

class PydanticGenerator:
    """Generates Python/Pydantic code from command definition"""

    def __init__(self, command_def: CommandDefinition):
        self.command_def = command_def
        self.required_imports = set()

    def generate(self) -> str:
        """Generate complete Python command file"""
        sections = [
            self._generate_header(),
            self._generate_imports(),
            "",
            self._generate_inputs_model(),
            "",
            self._generate_result_model(),
            "",
            self._generate_command_class(),
            "",
            self._generate_example_usage(),
        ]

        return "\n".join(section for section in sections if section)

    def _generate_header(self) -> str:
        """Generate file header with docstring"""
        lines = ['"""']

        if self.command_def.description:
            lines.append(self.command_def.description)
        else:
            lines.append(f"{self.command_def.class_name} Command")

        lines.append("")
        lines.append("Auto-generated from Ruby using ruby_to_python_converter.py")
        lines.append('"""')

        return "\n".join(lines)

    def _generate_imports(self) -> str:
        """Generate import statements"""
        # Always needed
        self.required_imports.add("BaseModel")
        self.required_imports.add("Field")

        # Check what types are used
        for field in self.command_def.inputs:
            python_type = field.to_python_type()

            if "Optional" in python_type:
                self.required_imports.add("Optional")
            if "List" in python_type:
                self.required_imports.add("List")
            if "Dict" in python_type:
                self.required_imports.add("Dict")
            if "Annotated" in python_type:
                self.required_imports.add("Annotated")
            if "EmailStr" in python_type:
                self.required_imports.add("EmailStr")
            if "HttpUrl" in python_type:
                self.required_imports.add("HttpUrl")
            if "Literal" in python_type:
                self.required_imports.add("Literal")

            # Handle datetime types
            if "datetime" in python_type.lower():
                if "datetime" in python_type:
                    self.required_imports.add("datetime")
                if "date" in python_type:
                    self.required_imports.add("date")
                if "time" in python_type:
                    self.required_imports.add("time")

        # Check result type
        if self.command_def.result_type:
            result_type = TYPE_MAPPING.get(self.command_def.result_type, self.command_def.result_type)
            if "datetime" in result_type.lower():
                self.required_imports.add("datetime")

        # Build import lines
        import_lines = []

        # Group imports
        pydantic_imports = [imp for imp in self.required_imports
                           if imp in ["BaseModel", "Field", "EmailStr", "HttpUrl", "field_validator"]]
        typing_imports = [imp for imp in self.required_imports
                         if imp in ["Optional", "List", "Dict", "Any", "Annotated", "Literal"]]
        datetime_imports = [imp for imp in self.required_imports
                           if imp in ["datetime", "date", "time"]]

        if pydantic_imports:
            import_lines.append(f"from pydantic import {', '.join(sorted(pydantic_imports))}")

        if typing_imports:
            import_lines.append(f"from typing import {', '.join(sorted(typing_imports))}")

        if datetime_imports:
            import_lines.append(f"from datetime import {', '.join(sorted(datetime_imports))}")

        if "UUID" in self.required_imports:
            import_lines.append("from uuid import UUID")

        # Foobara import
        import_lines.append("from foobara_py import Command, Domain")

        return "\n".join(import_lines)

    def _generate_inputs_model(self) -> str:
        """Generate Pydantic input model"""
        if not self.command_def.inputs:
            return "# No inputs defined"

        lines = [f"class {self.command_def.class_name}Inputs(BaseModel):"]

        # Add docstring
        lines.append('    """Input model for command"""')

        # Add fields
        for field in self.command_def.inputs:
            field_type = field.to_python_type()
            default = field.get_default_value()

            if field.description and not field.has_field_constraints():
                # Description without other constraints
                lines.append(
                    f"    {field.name}: {field_type} = Field({default}, description={field.description!r})"
                )
            elif not field.has_field_constraints() or "Annotated" in field_type:
                # No Field needed or already in Annotated
                lines.append(f"    {field.name}: {field_type} = {default}")
            else:
                # Has constraints but not in Annotated (shouldn't happen, but handle it)
                lines.append(f"    {field.name}: {field_type} = {default}")

        return "\n".join(lines)

    def _generate_result_model(self) -> str:
        """Generate result model if needed"""
        if not self.command_def.result_type:
            return "# Result type not specified - using Any"

        result_type = TYPE_MAPPING.get(
            self.command_def.result_type,
            self.command_def.result_type
        )

        # For simple types, we don't need a separate model
        if result_type in ["str", "int", "float", "bool", "dict", "list"]:
            return f"# Result type: {result_type}"

        # For complex types, create a model stub
        return f"""class {self.command_def.class_name}Result(BaseModel):
    \"\"\"Result model for command\"\"\"
    # TODO: Define result structure
    pass"""

    def _generate_command_class(self) -> str:
        """Generate the command class"""
        # Determine result type
        if self.command_def.result_type:
            result_type = TYPE_MAPPING.get(
                self.command_def.result_type,
                self.command_def.result_type
            )
        else:
            result_type = "Any"
            self.required_imports.add("Any")

        inputs_type = f"{self.command_def.class_name}Inputs" if self.command_def.inputs else "BaseModel"

        lines = [
            f"class {self.command_def.class_name}(Command[{inputs_type}, {result_type}]):",
        ]

        # Add docstring
        if self.command_def.description:
            lines.append(f'    """{self.command_def.description}"""')
        else:
            lines.append('    """Command implementation"""')

        # Add execute method
        lines.append("")
        lines.append(f"    def execute(self) -> {result_type}:")
        lines.append("        # TODO: Port implementation from Ruby")

        if self.command_def.inputs:
            lines.append("        # Access inputs via self.inputs.<field_name>")
            lines.append("        # Example: name = self.inputs.name")

        lines.append("        raise NotImplementedError('TODO: Implement execute method')")

        return "\n".join(lines)

    def _generate_example_usage(self) -> str:
        """Generate example usage code"""
        lines = [
            'if __name__ == "__main__":',
            "    # Example usage",
            f"    outcome = {self.command_def.class_name}.run(",
        ]

        # Add example inputs
        if self.command_def.inputs:
            for i, field in enumerate(self.command_def.inputs):
                example_value = self._get_example_value(field)
                comma = "," if i < len(self.command_def.inputs) - 1 else ""
                lines.append(f"        {field.name}={example_value}{comma}")

        lines.append("    )")
        lines.append("")
        lines.append("    if outcome.is_success():")
        lines.append("        result = outcome.unwrap()")
        lines.append('        print(f"Success: {result}")')
        lines.append("    else:")
        lines.append('        print("Errors:")')
        lines.append("        for error in outcome.errors:")
        lines.append('            print(f"  - {error.symbol}: {error.message}")')

        return "\n".join(lines)

    def _get_example_value(self, field: FieldDefinition) -> str:
        """Get an example value for a field"""
        if field.default is not None:
            if isinstance(field.default, str):
                return repr(field.default)
            return str(field.default)

        type_examples = {
            "string": '"example"',
            "integer": "42",
            "float": "3.14",
            "boolean": "True",
            "email": '"user@example.com"',
            "url": '"https://example.com"',
            "array": "[]",
            "hash": "{}",
            "datetime": "datetime.now()",
        }

        return type_examples.get(field.type, "None")


# =============================================================================
# CLI Interface
# =============================================================================

class ConverterStats:
    """Track conversion statistics"""

    def __init__(self):
        self.total_files = 0
        self.successful = 0
        self.failed = 0
        self.total_inputs = 0
        self.total_validations = 0

    def report(self) -> str:
        """Generate stats report"""
        success_rate = (self.successful / self.total_files * 100) if self.total_files > 0 else 0

        lines = [
            "",
            "=" * 60,
            "Conversion Statistics",
            "=" * 60,
            f"Total files processed: {self.total_files}",
            f"Successful conversions: {self.successful}",
            f"Failed conversions: {self.failed}",
            f"Success rate: {success_rate:.1f}%",
            f"Total inputs converted: {self.total_inputs}",
            f"Total validations preserved: {self.total_validations}",
            "=" * 60,
        ]

        return "\n".join(lines)


def convert_file(input_path: Path, output_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Convert a single Ruby file to Python

    Args:
        input_path: Path to Ruby file
        output_path: Path for Python output (None for stdout)

    Returns:
        Tuple of (success, generated_code)
    """
    try:
        # Read Ruby file
        ruby_code = input_path.read_text()

        # Parse
        parser = RubyDSLParser(ruby_code)
        command_def = parser.parse()

        # Generate
        generator = PydanticGenerator(command_def)
        python_code = generator.generate()

        # Write output
        if output_path:
            output_path.write_text(python_code)
            print(f"✓ Converted: {input_path} → {output_path}")
        else:
            print(python_code)

        return True, python_code

    except Exception as e:
        error_msg = f"✗ Failed to convert {input_path}: {e}"
        print(error_msg, file=sys.stderr)
        return False, ""


def convert_batch(input_dir: Path, output_dir: Optional[Path] = None) -> ConverterStats:
    """
    Convert all Ruby files in a directory

    Args:
        input_dir: Directory containing Ruby files
        output_dir: Output directory for Python files

    Returns:
        ConverterStats with conversion statistics
    """
    stats = ConverterStats()

    # Find all .rb files
    ruby_files = list(input_dir.rglob("*.rb"))

    if not ruby_files:
        print(f"No Ruby files found in {input_dir}")
        return stats

    print(f"Found {len(ruby_files)} Ruby files to convert...")

    for ruby_file in ruby_files:
        stats.total_files += 1

        # Determine output path
        if output_dir:
            relative_path = ruby_file.relative_to(input_dir)
            python_file = output_dir / relative_path.with_suffix('.py')
            python_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            python_file = ruby_file.with_suffix('.py')

        # Convert
        success, code = convert_file(ruby_file, python_file)

        if success:
            stats.successful += 1
            # Count inputs and validations
            stats.total_inputs += code.count(': ')  # Rough estimate
            stats.total_validations += code.count('Field(')
        else:
            stats.failed += 1

    return stats


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Convert Foobara Ruby commands to Python/Pydantic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert single file to stdout
  python -m tools.ruby_to_python_converter --input command.rb

  # Convert single file to specific output
  python -m tools.ruby_to_python_converter --input command.rb --output command.py

  # Convert all files in directory
  python -m tools.ruby_to_python_converter --batch ./ruby_commands/ --output ./python_commands/

  # Generate conversion report
  python -m tools.ruby_to_python_converter --batch ./commands/ --stats
        """
    )

    parser.add_argument(
        '--input', '-i',
        type=Path,
        help='Input Ruby file'
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output Python file (default: stdout)'
    )

    parser.add_argument(
        '--batch', '-b',
        type=Path,
        help='Batch convert all .rb files in directory'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show detailed conversion statistics'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.input and not args.batch:
        parser.error("Either --input or --batch is required")

    if args.input and args.batch:
        parser.error("Cannot use both --input and --batch")

    # Execute conversion
    if args.batch:
        stats = convert_batch(args.batch, args.output)
        if args.stats:
            print(stats.report())
    else:
        success, _ = convert_file(args.input, args.output)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
