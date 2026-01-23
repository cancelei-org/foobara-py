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
