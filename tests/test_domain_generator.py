"""Tests for DomainGenerator"""

import pytest
from pathlib import Path
from foobara_py.generators import DomainGenerator, generate_domain


class TestDomainGenerator:
    """Test DomainGenerator functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "domains"
        self.output_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_simple_domain(self):
        """Should generate domain with standard structure"""
        generator = DomainGenerator(
            name="Users",
            description="User management domain"
        )

        files = generator.generate(self.output_dir)

        # Should create 4 files: domain __init__ + 3 subdirs
        assert len(files) == 4

        domain_dir = self.output_dir / "users"
        assert domain_dir.exists()
        assert (domain_dir / "__init__.py").exists()
        assert (domain_dir / "commands" / "__init__.py").exists()
        assert (domain_dir / "types" / "__init__.py").exists()
        assert (domain_dir / "entities" / "__init__.py").exists()

    def test_generate_domain_init_content(self):
        """Should generate proper domain __init__.py"""
        generator = DomainGenerator(
            name="Analytics",
            organization="MyApp",
            description="Analytics and reporting domain"
        )

        files = generator.generate(self.output_dir)

        init_file = self.output_dir / "analytics" / "__init__.py"
        content = init_file.read_text()

        assert "from foobara_py import Domain" in content
        assert 'analytics_domain = Domain(' in content
        assert '"Analytics"' in content
        assert 'organization="MyApp"' in content
        assert "Analytics and reporting domain" in content
        assert '__all__ = ["analytics_domain"]' in content

    def test_generate_domain_with_dependencies(self):
        """Should include dependencies in domain definition"""
        generator = DomainGenerator(
            name="Orders",
            dependencies=["Users", "Products", "Inventory"]
        )

        files = generator.generate(self.output_dir)

        init_file = self.output_dir / "orders" / "__init__.py"
        content = init_file.read_text()

        assert "dependencies=[" in content
        assert '"Users"' in content
        assert '"Products"' in content
        assert '"Inventory"' in content

    def test_generate_commands_subdir_content(self):
        """Should generate proper commands __init__.py"""
        generator = DomainGenerator(name="Users")
        generator.generate(self.output_dir)

        cmd_init = self.output_dir / "users" / "commands" / "__init__.py"
        content = cmd_init.read_text()

        assert "Users domain commands" in content
        assert "Commands define the operations" in content
        assert "__all__ = []" in content

    def test_generate_types_subdir_content(self):
        """Should generate proper types __init__.py"""
        generator = DomainGenerator(name="Users")
        generator.generate(self.output_dir)

        types_init = self.output_dir / "users" / "types" / "__init__.py"
        content = types_init.read_text()

        assert "Users domain types" in content
        assert "Types define the data structures" in content

    def test_generate_entities_subdir_content(self):
        """Should generate proper entities __init__.py"""
        generator = DomainGenerator(name="Users")
        generator.generate(self.output_dir)

        entities_init = self.output_dir / "users" / "entities" / "__init__.py"
        content = entities_init.read_text()

        assert "Users domain entities" in content
        assert "Entities are domain objects with identity" in content

    def test_generate_domain_without_commands_dir(self):
        """Should skip commands dir when generate_commands_dir=False"""
        generator = DomainGenerator(
            name="Config",
            generate_commands_dir=False
        )

        files = generator.generate(self.output_dir)

        assert len(files) == 3  # init + types + entities
        assert not (self.output_dir / "config" / "commands").exists()
        assert (self.output_dir / "config" / "types" / "__init__.py").exists()
        assert (self.output_dir / "config" / "entities" / "__init__.py").exists()

    def test_generate_domain_without_types_dir(self):
        """Should skip types dir when generate_types_dir=False"""
        generator = DomainGenerator(
            name="Config",
            generate_types_dir=False
        )

        files = generator.generate(self.output_dir)

        assert len(files) == 3  # init + commands + entities
        assert (self.output_dir / "config" / "commands" / "__init__.py").exists()
        assert not (self.output_dir / "config" / "types").exists()

    def test_generate_domain_without_entities_dir(self):
        """Should skip entities dir when generate_entities_dir=False"""
        generator = DomainGenerator(
            name="Utils",
            generate_entities_dir=False
        )

        files = generator.generate(self.output_dir)

        assert len(files) == 3  # init + commands + types
        assert (self.output_dir / "utils" / "commands" / "__init__.py").exists()
        assert (self.output_dir / "utils" / "types" / "__init__.py").exists()
        assert not (self.output_dir / "utils" / "entities").exists()

    def test_generate_minimal_domain(self):
        """Should generate domain with no subdirectories"""
        generator = DomainGenerator(
            name="Minimal",
            generate_commands_dir=False,
            generate_types_dir=False,
            generate_entities_dir=False
        )

        files = generator.generate(self.output_dir)

        assert len(files) == 1  # Just the init
        assert (self.output_dir / "minimal" / "__init__.py").exists()

    def test_domain_name_case_conversion(self):
        """Should handle various domain name cases"""
        test_cases = [
            ("UserManagement", "user_management"),
            ("API_Client", "api_client"),
            ("http-service", "http_service"),
            ("analytics", "analytics"),
        ]

        for name, expected_dir in test_cases:
            generator = DomainGenerator(
                name=name,
                generate_commands_dir=False,
                generate_types_dir=False,
                generate_entities_dir=False
            )
            files = generator.generate(self.output_dir)

            expected_path = self.output_dir / expected_dir / "__init__.py"
            assert expected_path.exists(), f"Failed for {name}"

            # Cleanup
            import shutil
            shutil.rmtree(self.output_dir / expected_dir)


class TestGenerateDomainFunction:
    """Test generate_domain convenience function"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "domains"
        self.output_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_domain_function(self):
        """Should generate domain via convenience function"""
        files = generate_domain(
            name="Products",
            output_dir=self.output_dir,
            organization="MyStore",
            dependencies=["Inventory"],
            description="Product catalog domain"
        )

        assert len(files) == 4
        assert (self.output_dir / "products" / "__init__.py").exists()

        content = (self.output_dir / "products" / "__init__.py").read_text()
        assert 'products_domain = Domain(' in content
        assert '"Products"' in content
        assert 'organization="MyStore"' in content

    def test_generate_domain_function_minimal(self):
        """Should generate minimal domain via convenience function"""
        files = generate_domain(
            name="Simple",
            output_dir=self.output_dir,
            generate_commands_dir=False,
            generate_types_dir=False,
            generate_entities_dir=False
        )

        assert len(files) == 1
        assert (self.output_dir / "simple" / "__init__.py").exists()


class TestDomainStructure:
    """Test domain directory structure"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "domains"
        self.output_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_domain_is_valid_python_package(self):
        """Generated domain should be a valid Python package"""
        generator = DomainGenerator(name="Users")
        generator.generate(self.output_dir)

        # All directories should have __init__.py
        domain_dir = self.output_dir / "users"
        assert (domain_dir / "__init__.py").exists()
        assert (domain_dir / "commands" / "__init__.py").exists()
        assert (domain_dir / "types" / "__init__.py").exists()
        assert (domain_dir / "entities" / "__init__.py").exists()

    def test_subdirectories_are_independent(self):
        """Subdirectory __init__.py should not import from each other"""
        generator = DomainGenerator(name="Users")
        generator.generate(self.output_dir)

        domain_dir = self.output_dir / "users"

        # Check that subdirectory inits don't have cross-imports
        for subdir in ["commands", "types", "entities"]:
            content = (domain_dir / subdir / "__init__.py").read_text()
            # Should not import from sibling directories
            assert "from ..commands" not in content
            assert "from ..types" not in content
            assert "from ..entities" not in content
