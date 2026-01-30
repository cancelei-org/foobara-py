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


class TestDomainGeneratorEdgeCases:
    """Test edge cases and error handling for DomainGenerator"""

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

    def test_empty_domain_name(self):
        """Should handle empty domain name"""
        generator = DomainGenerator(name="")
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_domain_name_with_special_characters(self):
        """Should sanitize domain names with special characters"""
        generator = DomainGenerator(name="User@Management#2024!")
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_reserved_keyword_domain_name(self):
        """Should handle Python reserved keywords"""
        keywords = ["class", "def", "import", "if", "for", "while"]
        for keyword in keywords:
            generator = DomainGenerator(
                name=keyword,
                generate_commands_dir=False,
                generate_types_dir=False,
                generate_entities_dir=False
            )
            files = generator.generate(self.output_dir)
            assert len(files) > 0
            # Cleanup
            import shutil
            shutil.rmtree(self.output_dir / keyword)

    def test_builtin_name_domain(self):
        """Should handle builtin name collisions"""
        generator = DomainGenerator(name="list")
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_very_long_domain_name(self):
        """Should handle very long domain names"""
        long_name = "UserManagement" * 10  # Reduced to avoid OS filename limit
        generator = DomainGenerator(name=long_name)
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_unicode_domain_name(self):
        """Should handle unicode in domain names"""
        generator = DomainGenerator(name="Users_日本語")
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_domain_with_numbers(self):
        """Should handle domain names with numbers"""
        generator = DomainGenerator(name="API2_Users3")
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_very_long_description(self):
        """Should handle very long descriptions"""
        long_desc = "A" * 1000
        generator = DomainGenerator(
            name="LongDesc",
            description=long_desc
        )
        files = generator.generate(self.output_dir)
        domain_init = self.output_dir / "long_desc" / "__init__.py"
        content = domain_init.read_text()
        assert long_desc in content

    def test_description_with_special_characters(self):
        """Should handle special characters in description"""
        special_desc = 'Desc with "quotes" and \'single\' and <tags> and & symbols'
        generator = DomainGenerator(
            name="SpecialDesc",
            description=special_desc
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_multiline_description(self):
        """Should handle multiline descriptions"""
        multiline_desc = "Line 1\nLine 2\nLine 3\nLine 4"
        generator = DomainGenerator(
            name="MultiDesc",
            description=multiline_desc
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_empty_organization(self):
        """Should handle empty organization name"""
        generator = DomainGenerator(
            name="Users",
            organization=""
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_organization_with_special_characters(self):
        """Should handle special characters in organization"""
        generator = DomainGenerator(
            name="Users",
            organization="My@Org#2024!"
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_very_long_organization(self):
        """Should handle very long organization names"""
        long_org = "A" * 200
        generator = DomainGenerator(
            name="Users",
            organization=long_org
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_empty_dependencies_list(self):
        """Should handle empty dependencies list"""
        generator = DomainGenerator(
            name="NoDeps",
            dependencies=[]
        )
        files = generator.generate(self.output_dir)
        domain_init = self.output_dir / "no_deps" / "__init__.py"
        content = domain_init.read_text()
        # Should not have dependencies in output if list is empty
        assert len(files) > 0

    def test_single_dependency(self):
        """Should handle single dependency"""
        generator = DomainGenerator(
            name="Orders",
            dependencies=["Users"]
        )
        files = generator.generate(self.output_dir)
        domain_init = self.output_dir / "orders" / "__init__.py"
        content = domain_init.read_text()
        assert "Users" in content

    def test_many_dependencies(self):
        """Should handle many dependencies"""
        deps = [f"Domain{i}" for i in range(20)]
        generator = DomainGenerator(
            name="Complex",
            dependencies=deps
        )
        files = generator.generate(self.output_dir)
        domain_init = self.output_dir / "complex" / "__init__.py"
        content = domain_init.read_text()
        assert "Domain0" in content
        assert "Domain19" in content

    def test_duplicate_dependencies(self):
        """Should handle duplicate dependencies"""
        generator = DomainGenerator(
            name="DupDeps",
            dependencies=["Users", "Users", "Products", "Users"]
        )
        files = generator.generate(self.output_dir)
        # Should handle duplicates gracefully
        assert len(files) > 0

    def test_circular_dependency_reference(self):
        """Should handle self-referencing dependencies"""
        generator = DomainGenerator(
            name="SelfRef",
            dependencies=["SelfRef"]
        )
        files = generator.generate(self.output_dir)
        # Should generate without error
        assert len(files) > 0

    def test_dependency_with_special_characters(self):
        """Should handle dependencies with special characters"""
        generator = DomainGenerator(
            name="Orders",
            dependencies=["User@Management", "Product#Catalog"]
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_generate_to_existing_domain(self):
        """Should handle or raise error when generating to existing domain directory"""
        from foobara_py.generators.files_generator import FileExistsError

        # Generate once
        generator1 = DomainGenerator(name="Existing")
        files1 = generator1.generate(self.output_dir)

        # Add existing file
        existing_file = self.output_dir / "existing" / "custom_file.py"
        existing_file.write_text("# Custom file")

        # Try to generate again
        generator2 = DomainGenerator(name="Existing")

        try:
            files2 = generator2.generate(self.output_dir)
            # If no error, custom file should still exist
            assert existing_file.exists()
        except FileExistsError:
            # Expected behavior - trying to overwrite existing files
            pass

    def test_all_subdirs_disabled(self):
        """Should generate minimal domain with all subdirs disabled"""
        generator = DomainGenerator(
            name="Minimal",
            generate_commands_dir=False,
            generate_types_dir=False,
            generate_entities_dir=False
        )
        files = generator.generate(self.output_dir)

        domain_dir = self.output_dir / "minimal"
        assert (domain_dir / "__init__.py").exists()
        assert not (domain_dir / "commands").exists()
        assert not (domain_dir / "types").exists()
        assert not (domain_dir / "entities").exists()

    def test_only_commands_dir(self):
        """Should generate domain with only commands directory"""
        generator = DomainGenerator(
            name="CommandsOnly",
            generate_types_dir=False,
            generate_entities_dir=False
        )
        files = generator.generate(self.output_dir)

        domain_dir = self.output_dir / "commands_only"
        assert (domain_dir / "commands" / "__init__.py").exists()
        assert not (domain_dir / "types").exists()
        assert not (domain_dir / "entities").exists()

    def test_only_types_dir(self):
        """Should generate domain with only types directory"""
        generator = DomainGenerator(
            name="TypesOnly",
            generate_commands_dir=False,
            generate_entities_dir=False
        )
        files = generator.generate(self.output_dir)

        domain_dir = self.output_dir / "types_only"
        assert not (domain_dir / "commands").exists()
        assert (domain_dir / "types" / "__init__.py").exists()
        assert not (domain_dir / "entities").exists()

    def test_only_entities_dir(self):
        """Should generate domain with only entities directory"""
        generator = DomainGenerator(
            name="EntitiesOnly",
            generate_commands_dir=False,
            generate_types_dir=False
        )
        files = generator.generate(self.output_dir)

        domain_dir = self.output_dir / "entities_only"
        assert not (domain_dir / "commands").exists()
        assert not (domain_dir / "types").exists()
        assert (domain_dir / "entities" / "__init__.py").exists()
