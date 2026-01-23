"""
Tests for CLIConnectorGenerator
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from foobara_py.generators import CLIConnectorGenerator, generate_cli_connector


class TestCLIConnectorGenerator:
    """Test CLI connector code generation"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs"""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    def test_generate_basic_cli(self, temp_dir):
        """Test generating basic CLI connector"""
        generator = CLIConnectorGenerator(
            app_name="TestApp",
            cli_name="testapp"
        )

        files = generator.generate(temp_dir)

        assert len(files) == 1
        cli_file = files[0]
        assert cli_file.name == "cli.py"
        assert cli_file.exists()

        # Check file is executable
        assert cli_file.stat().st_mode & 0o111  # Has execute permission

        content = cli_file.read_text()
        assert "#!/usr/bin/env python" in content
        assert 'name="testapp"' in content
        assert "CLIConnector" in content

    def test_generate_with_commands(self, temp_dir):
        """Test generating CLI with command registration"""
        generator = CLIConnectorGenerator(
            app_name="MyApp",
            commands=["CreateUser", "ListUsers"],
            import_commands=["from myapp.commands import CreateUser, ListUsers"],
            cli_name="myapp"
        )

        files = generator.generate(temp_dir)
        content = files[0].read_text()

        assert "from myapp.commands import CreateUser, ListUsers" in content
        assert "cli.register(CreateUser)" in content
        assert "cli.register(ListUsers)" in content

    def test_generate_with_domains(self, temp_dir):
        """Test generating CLI with domain registration"""
        generator = CLIConnectorGenerator(
            app_name="OrgApp",
            domains=["users_domain", "products_domain"],
            import_domains=[
                "from myorg.users import users_domain",
                "from myorg.products import products_domain"
            ],
            cli_name="orgapp"
        )

        files = generator.generate(temp_dir)
        content = files[0].read_text()

        assert "from myorg.users import users_domain" in content
        assert "from myorg.products import products_domain" in content
        assert "cli.register_domain(users_domain)" in content
        assert "cli.register_domain(products_domain)" in content

    def test_generate_with_organizations(self, temp_dir):
        """Test generating CLI with organization registration"""
        generator = CLIConnectorGenerator(
            app_name="FullApp",
            organizations=["my_org"],
            import_organizations=["from myapp import my_org"],
            cli_name="fullapp"
        )

        files = generator.generate(temp_dir)
        content = files[0].read_text()

        assert "from myapp import my_org" in content
        assert "cli.register_organization(my_org)" in content

    def test_generate_with_custom_settings(self, temp_dir):
        """Test generating CLI with custom settings"""
        generator = CLIConnectorGenerator(
            app_name="CustomApp",
            cli_name="custom",
            description="Custom CLI application",
            help_text="Run custom commands",
            output_format="TABLE",
            filename="mycli.py"
        )

        files = generator.generate(temp_dir)

        assert files[0].name == "mycli.py"
        content = files[0].read_text()

        assert "Custom CLI application" in content
        assert 'help="Run custom commands"' in content
        assert "OutputFormat.TABLE" in content

    def test_convenience_function(self, temp_dir):
        """Test the generate_cli_connector convenience function"""
        files = generate_cli_connector(
            output_dir=temp_dir,
            app_name="ConvTest",
            commands=["TestCommand"],
            import_commands=["from test import TestCommand"],
            cli_name="convtest"
        )

        assert len(files) == 1
        assert files[0].exists()
        content = files[0].read_text()

        assert "from test import TestCommand" in content
        assert "cli.register(TestCommand)" in content

    def test_levels_up_path_adjustment(self, temp_dir):
        """Test path adjustment for nested CLI scripts"""
        generator = CLIConnectorGenerator(
            app_name="NestedApp",
            cli_name="nested",
            levels_up=2
        )

        files = generator.generate(temp_dir)
        content = files[0].read_text()

        assert ".parent.parent.parent" in content  # Goes up 2 levels (plus initial parent)
