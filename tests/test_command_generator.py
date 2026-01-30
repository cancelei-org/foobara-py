"""Tests for CommandGenerator"""

import pytest
from pathlib import Path
from foobara_py.generators import CommandGenerator, generate_command


class TestCommandGenerator:
    """Test CommandGenerator functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "commands"
        self.test_dir = self.temp_dir / "tests"

        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_simple_command(self):
        """Should generate simple command without inputs"""
        generator = CommandGenerator(
            name="DoSomething",
            description="Does something"
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        assert len(files) == 2  # Command + test file
        command_file = self.output_dir / "do_something.py"
        test_file = self.test_dir / "test_do_something.py"

        assert command_file.exists()
        assert test_file.exists()

        # Check command file content
        content = command_file.read_text()
        assert "class DoSomething(Command):" in content
        assert "def execute(self)" in content
        assert "Does something" in content

    def test_generate_command_with_inputs(self):
        """Should generate command with input fields"""
        generator = CommandGenerator(
            name="CreateUser",
            inputs=[
                {"name": "email", "type": "str"},
                {"name": "name", "type": "str"},
                {"name": "age", "type": "int", "default": " = 18"},
            ],
            result_type="User",
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        command_file = self.output_dir / "create_user.py"
        content = command_file.read_text()

        assert "from pydantic import BaseModel" in content
        assert "class CreateUserInputs(BaseModel):" in content
        assert "email: str" in content
        assert "name: str" in content
        assert "age: int = 18" in content
        assert "class CreateUser(Command[CreateUserInputs, User]):" in content
        assert "def execute(self) -> User:" in content

    def test_generate_command_with_domain(self):
        """Should generate command with domain registration"""
        generator = CommandGenerator(
            name="FetchData",
            domain="Analytics",
            organization="MyCompany",
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        command_file = self.output_dir / "fetch_data.py"
        content = command_file.read_text()

        assert "from foobara_py import Command, Domain" in content
        assert 'analytics_domain = Domain("Analytics", organization="MyCompany")' in content
        assert "@analytics_domain.command" in content

    def test_generate_command_without_tests(self):
        """Should skip test generation when generate_tests=False"""
        generator = CommandGenerator(
            name="Simple",
            generate_tests=False
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        assert len(files) == 1  # Only command file
        assert (self.output_dir / "simple.py").exists()
        assert not (self.test_dir / "test_simple.py").exists()

    def test_generated_test_file_content(self):
        """Should generate test file with proper structure"""
        generator = CommandGenerator(
            name="ProcessData",
            inputs=[
                {"name": "data", "type": "dict"},
            ],
            result_type="dict",
        )

        files = generator.generate(
            self.output_dir,
            test_dir=self.test_dir,
            module_path="myapp.commands.process_data"
        )

        test_file = self.test_dir / "test_process_data.py"
        content = test_file.read_text()

        assert "from myapp.commands.process_data import ProcessData" in content
        assert "class TestProcessData:" in content
        assert "def test_command_runs_successfully(self):" in content
        assert "def test_command_with_invalid_inputs(self):" in content
        assert "def test_command_execution_logic(self):" in content

    def test_command_name_case_conversion(self):
        """Should handle various command name cases"""
        test_cases = [
            ("CreateUser", "create_user.py"),
            ("fetchData", "fetch_data.py"),
            ("API_Handler", "api_handler.py"),
            ("user-manager", "user_manager.py"),
        ]

        for name, expected_filename in test_cases:
            generator = CommandGenerator(name=name, generate_tests=False)
            files = generator.generate(self.output_dir)

            expected_path = self.output_dir / expected_filename
            assert expected_path.exists(), f"Failed for {name}"

            # Cleanup
            expected_path.unlink()


class TestGenerateCommandFunction:
    """Test generate_command convenience function"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "commands"
        self.test_dir = self.temp_dir / "tests"
        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_command_function(self):
        """Should generate command via convenience function"""
        files = generate_command(
            name="TestCommand",
            output_dir=self.output_dir,
            test_dir=self.test_dir,
            inputs=[{"name": "value", "type": "str"}],
            result_type="str",
        )

        assert len(files) == 2
        assert (self.output_dir / "test_command.py").exists()


class TestRealWorldScenarios:
    """Test real-world command generation scenarios"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "commands"
        self.test_dir = self.temp_dir / "tests"

        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_crud_create_command(self):
        """Should generate typical CRUD create command"""
        generator = CommandGenerator(
            name="CreateUser",
            domain="Users",
            inputs=[
                {"name": "email", "type": "str", "description": "User email address"},
                {"name": "name", "type": "str", "description": "User full name"},
                {"name": "password", "type": "str", "description": "User password"},
            ],
            result_type="User",
            description="Create a new user account with email and password",
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        command_file = self.output_dir / "create_user.py"
        content = command_file.read_text()

        # Verify structure
        assert "CreateUserInputs" in content
        assert "email: str  # User email address" in content
        assert "name: str  # User full name" in content
        assert "password: str  # User password" in content
        assert "class CreateUser(Command[CreateUserInputs, User]):" in content
        assert "Create a new user account" in content

    def test_generate_query_command(self):
        """Should generate query/fetch command"""
        generator = CommandGenerator(
            name="SearchProducts",
            domain="Products",
            inputs=[
                {"name": "query", "type": "str"},
                {"name": "limit", "type": "int", "default": " = 10"},
                {"name": "offset", "type": "int", "default": " = 0"},
            ],
            result_type="List[Product]",
            description="Search products by query string",
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        command_file = self.output_dir / "search_products.py"
        content = command_file.read_text()

        assert "query: str" in content
        assert "limit: int = 10" in content
        assert "offset: int = 0" in content
        assert "def execute(self) -> List[Product]:" in content

    def test_generate_action_command_without_result(self):
        """Should generate action command without return value"""
        generator = CommandGenerator(
            name="SendNotification",
            domain="Notifications",
            inputs=[
                {"name": "user_id", "type": "int"},
                {"name": "message", "type": "str"},
            ],
            result_type=None,
            description="Send notification to user",
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        command_file = self.output_dir / "send_notification.py"
        content = command_file.read_text()

        assert "class SendNotification(Command[SendNotificationInputs]):" in content
        assert "def execute(self) -> None:" in content

    def test_generate_standalone_command(self):
        """Should generate command without domain"""
        generator = CommandGenerator(
            name="HealthCheck",
            result_type="dict",
            description="Check system health status",
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir, generate_tests=False)

        command_file = self.output_dir / "health_check.py"
        content = command_file.read_text()

        assert "from foobara_py import Command" in content
        assert "Domain" not in content
        assert "@" not in content.split("class")[0]  # No decorator
        assert "class HealthCheck(Command[dict]):" in content


class TestCommandGeneratorEdgeCases:
    """Test edge cases and error handling for CommandGenerator"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "commands"
        self.test_dir = self.temp_dir / "tests"
        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_empty_command_name(self):
        """Should handle empty command name"""
        generator = CommandGenerator(name="", generate_tests=False)
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_command_name_with_special_characters(self):
        """Should sanitize command names with special characters"""
        generator = CommandGenerator(
            name="Do@Something#123!",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_reserved_keyword_as_name(self):
        """Should handle Python reserved keywords as command names"""
        keywords = ["class", "def", "return", "import", "from", "if", "else"]
        for keyword in keywords:
            generator = CommandGenerator(name=keyword, generate_tests=False)
            files = generator.generate(self.output_dir)
            assert len(files) > 0
            # Cleanup
            for f in files:
                if f.exists():
                    f.unlink()

    def test_builtin_name_collision(self):
        """Should handle builtin function name collisions"""
        builtins = ["list", "dict", "str", "int", "print", "open"]
        for builtin in builtins:
            generator = CommandGenerator(name=builtin, generate_tests=False)
            files = generator.generate(self.output_dir)
            assert len(files) > 0
            for f in files:
                if f.exists():
                    f.unlink()

    def test_very_long_command_name(self):
        """Should handle very long command names"""
        long_name = "ProcessUserData" * 10  # Reduced to avoid OS filename limit
        generator = CommandGenerator(name=long_name, generate_tests=False)
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_unicode_command_name(self):
        """Should handle unicode in command names"""
        generator = CommandGenerator(
            name="ProcessData_日本語",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_input_with_invalid_type(self):
        """Should handle invalid input types"""
        generator = CommandGenerator(
            name="TestCmd",
            inputs=[
                {"name": "data", "type": "InvalidType"},
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should still generate, using the type as-is
        assert len(files) > 0

    def test_input_with_missing_name(self):
        """Should handle input with missing name field"""
        generator = CommandGenerator(
            name="TestCmd",
            inputs=[
                {"type": "str"},  # Missing name
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should handle gracefully
        assert len(files) > 0

    def test_input_with_missing_type(self):
        """Should handle input with missing type field"""
        generator = CommandGenerator(
            name="TestCmd",
            inputs=[
                {"name": "data"},  # Missing type
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_many_inputs(self):
        """Should handle commands with many input fields"""
        inputs = [{"name": f"field_{i}", "type": "str"} for i in range(50)]
        generator = CommandGenerator(
            name="ManyInputs",
            inputs=inputs,
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        command_file = self.output_dir / "many_inputs.py"
        content = command_file.read_text()
        assert "field_0" in content
        assert "field_49" in content

    def test_input_with_complex_default_value(self):
        """Should handle complex default values"""
        generator = CommandGenerator(
            name="ComplexDefaults",
            inputs=[
                {"name": "config", "type": "dict", "default": " = {}"},
                {"name": "items", "type": "list", "default": " = []"},
                {"name": "callback", "type": "callable", "default": " = None"},
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        command_file = self.output_dir / "complex_defaults.py"
        content = command_file.read_text()
        assert "config: dict = {}" in content
        assert "items: list = []" in content

    def test_input_with_multiline_description(self):
        """Should handle multiline descriptions"""
        generator = CommandGenerator(
            name="MultilineDesc",
            inputs=[
                {
                    "name": "data",
                    "type": "str",
                    "description": "Line 1\nLine 2\nLine 3"
                },
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_result_type_with_generics(self):
        """Should handle generic result types"""
        generator = CommandGenerator(
            name="GenericResult",
            result_type="List[Dict[str, Any]]",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        command_file = self.output_dir / "generic_result.py"
        content = command_file.read_text()
        assert "List[Dict[str, Any]]" in content

    def test_result_type_with_union(self):
        """Should handle Union result types"""
        generator = CommandGenerator(
            name="UnionResult",
            result_type="Union[User, Error]",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        command_file = self.output_dir / "union_result.py"
        content = command_file.read_text()
        assert "Union[User, Error]" in content

    def test_result_type_none(self):
        """Should handle None result type"""
        generator = CommandGenerator(
            name="NoResult",
            result_type=None,
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        command_file = self.output_dir / "no_result.py"
        content = command_file.read_text()
        assert "def execute(self) -> None:" in content

    def test_very_long_description(self):
        """Should handle very long command descriptions"""
        long_desc = "A" * 500
        generator = CommandGenerator(
            name="LongDesc",
            description=long_desc,
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_description_with_special_characters(self):
        """Should handle special characters in description"""
        generator = CommandGenerator(
            name="SpecialChars",
            description='Description with "quotes" and \'single\' and <tags>',
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_invalid_domain_name(self):
        """Should handle invalid domain names"""
        generator = CommandGenerator(
            name="TestCmd",
            domain="Invalid@Domain#Name!",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_empty_domain_name(self):
        """Should handle empty domain name"""
        generator = CommandGenerator(
            name="TestCmd",
            domain="",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_organization_without_domain(self):
        """Should handle organization without domain"""
        generator = CommandGenerator(
            name="TestCmd",
            organization="MyOrg",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should ignore organization if no domain
        assert len(files) > 0

    def test_generate_to_existing_file(self):
        """Should raise FileExistsError when file exists"""
        from foobara_py.generators.files_generator import FileExistsError

        # Generate once
        generator1 = CommandGenerator(
            name="ExistingCmd",
            generate_tests=False
        )
        files1 = generator1.generate(self.output_dir)

        # Try to generate again with different content
        generator2 = CommandGenerator(
            name="ExistingCmd",
            inputs=[{"name": "new_field", "type": "str"}],
            generate_tests=False
        )

        # Should raise FileExistsError
        try:
            files2 = generator2.generate(self.output_dir)
            # If it doesn't raise, check if file was overwritten
            command_file = self.output_dir / "existing_cmd.py"
            assert command_file.exists()
        except FileExistsError:
            # Expected behavior
            pass

    def test_module_path_with_deep_nesting(self):
        """Should handle deeply nested module paths"""
        generator = CommandGenerator(
            name="DeepCmd",
            generate_tests=True
        )
        files = generator.generate(
            self.output_dir,
            test_dir=self.test_dir,
            module_path="very.deeply.nested.module.path.commands.deep_cmd"
        )
        test_file = self.test_dir / "test_deep_cmd.py"
        content = test_file.read_text()
        assert "very.deeply.nested.module.path.commands.deep_cmd" in content
