"""Tests for foob CLI"""

import pytest
from pathlib import Path
from typer.testing import CliRunner
from foobara_py.cli.foob import app


runner = CliRunner()


class TestCLIBasic:
    """Test basic CLI functionality"""

    def test_help(self):
        """Should show help message"""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Foobara Python CLI" in result.stdout

    def test_version(self):
        """Should show version"""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "foob" in result.stdout


class TestNewCommand:
    """Test 'foob new' command"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_new_basic_project(self):
        """Should create basic project"""
        result = runner.invoke(app, [
            "new", "TestApp",
            "--path", str(self.temp_dir),
            "--template", "basic"
        ])

        assert result.exit_code == 0
        assert "Creating project" in result.stdout
        assert "Created" in result.stdout

        project_dir = self.temp_dir / "test_app"
        assert project_dir.exists()
        assert (project_dir / "pyproject.toml").exists()

    def test_new_api_project(self):
        """Should create API project"""
        result = runner.invoke(app, [
            "new", "ApiApp",
            "--path", str(self.temp_dir),
            "--template", "api"
        ])

        assert result.exit_code == 0

        project_dir = self.temp_dir / "api_app"
        assert (project_dir / "api_app" / "server.py").exists()

    def test_new_project_with_options(self):
        """Should create project with Docker and CI"""
        result = runner.invoke(app, [
            "new", "FullApp",
            "--path", str(self.temp_dir),
            "--docker",
            "--ci"
        ])

        assert result.exit_code == 0

        project_dir = self.temp_dir / "full_app"
        assert (project_dir / "Dockerfile").exists()
        assert (project_dir / ".github" / "workflows" / "ci.yml").exists()


class TestGenerateCommands:
    """Test 'foob generate' commands"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_command(self):
        """Should generate command"""
        result = runner.invoke(app, [
            "generate", "command", "CreateUser",
            "--output", str(self.temp_dir),
            "--no-tests"
        ])

        assert result.exit_code == 0
        assert "Generating command" in result.stdout
        assert (self.temp_dir / "create_user.py").exists()

    def test_generate_command_with_inputs(self):
        """Should generate command with input fields"""
        result = runner.invoke(app, [
            "generate", "command", "ProcessOrder",
            "--output", str(self.temp_dir),
            "-i", "order_id:int",
            "-i", "amount:float",
            "--no-tests"
        ])

        assert result.exit_code == 0

        content = (self.temp_dir / "process_order.py").read_text()
        assert "order_id: int" in content
        assert "amount: float" in content

    def test_generate_command_with_domain(self):
        """Should generate command with domain"""
        result = runner.invoke(app, [
            "generate", "command", "SendEmail",
            "--output", str(self.temp_dir),
            "--domain", "Notifications",
            "--no-tests"
        ])

        assert result.exit_code == 0

        content = (self.temp_dir / "send_email.py").read_text()
        assert "notifications_domain" in content

    def test_generate_domain(self):
        """Should generate domain"""
        result = runner.invoke(app, [
            "generate", "domain", "Users",
            "--output", str(self.temp_dir)
        ])

        assert result.exit_code == 0
        assert "Generating domain" in result.stdout

        domain_dir = self.temp_dir / "users"
        assert domain_dir.exists()
        assert (domain_dir / "__init__.py").exists()
        assert (domain_dir / "commands" / "__init__.py").exists()

    def test_generate_domain_with_dependencies(self):
        """Should generate domain with dependencies"""
        result = runner.invoke(app, [
            "generate", "domain", "Orders",
            "--output", str(self.temp_dir),
            "--dep", "Users",
            "--dep", "Products"
        ])

        assert result.exit_code == 0

        content = (self.temp_dir / "orders" / "__init__.py").read_text()
        assert '"Users"' in content
        assert '"Products"' in content

    def test_generate_entity(self):
        """Should generate entity"""
        result = runner.invoke(app, [
            "generate", "entity", "User",
            "--output", str(self.temp_dir),
            "-f", "id:int",
            "-f", "email:str",
            "-f", "name:str",
            "--no-tests"
        ])

        assert result.exit_code == 0
        assert "Generating entity" in result.stdout

        content = (self.temp_dir / "user.py").read_text()
        assert "class User(EntityBase):" in content
        assert "id: int" in content
        assert "email: str" in content

    def test_generate_model(self):
        """Should generate model"""
        result = runner.invoke(app, [
            "generate", "model", "Address",
            "--output", str(self.temp_dir),
            "-f", "street:str",
            "-f", "city:str",
            "--no-tests"
        ])

        assert result.exit_code == 0
        assert "Generating model" in result.stdout

        content = (self.temp_dir / "address.py").read_text()
        assert "class Address(Model):" in content

    def test_generate_mutable_model(self):
        """Should generate mutable model"""
        result = runner.invoke(app, [
            "generate", "model", "Settings",
            "--output", str(self.temp_dir),
            "--mutable",
            "-f", "theme:str",
            "--no-tests"
        ])

        assert result.exit_code == 0

        content = (self.temp_dir / "settings.py").read_text()
        assert "MutableModel" in content

    def test_generate_crud(self):
        """Should generate CRUD commands"""
        result = runner.invoke(app, [
            "generate", "crud", "User",
            "--output", str(self.temp_dir),
            "-f", "id:int",
            "-f", "email:str",
            "--no-tests"
        ])

        assert result.exit_code == 0
        assert "Generating CRUD" in result.stdout

        assert (self.temp_dir / "create_user.py").exists()
        assert (self.temp_dir / "get_user.py").exists()
        assert (self.temp_dir / "update_user.py").exists()
        assert (self.temp_dir / "delete_user.py").exists()
        assert (self.temp_dir / "list_users.py").exists()

    def test_generate_crud_specific_operations(self):
        """Should generate only specified CRUD operations"""
        result = runner.invoke(app, [
            "generate", "crud", "Product",
            "--output", str(self.temp_dir),
            "--op", "create",
            "--op", "read",
            "-f", "id:int",
            "--no-tests"
        ])

        assert result.exit_code == 0

        assert (self.temp_dir / "create_product.py").exists()
        assert (self.temp_dir / "get_product.py").exists()
        assert not (self.temp_dir / "update_product.py").exists()
        assert not (self.temp_dir / "delete_product.py").exists()


class TestGenerateAlias:
    """Test 'foob g' alias for generate"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_g_alias_for_generate(self):
        """Should use 'g' as alias for 'generate'"""
        result = runner.invoke(app, [
            "g", "command", "QuickCommand",
            "--output", str(self.temp_dir),
            "--no-tests"
        ])

        assert result.exit_code == 0
        assert (self.temp_dir / "quick_command.py").exists()


class TestConsoleCommand:
    """Test 'foob console' command"""

    def test_console_help(self):
        """Should show console help"""
        result = runner.invoke(app, ["console", "--help"])
        assert result.exit_code == 0
        assert "interactive" in result.stdout.lower()
