"""
Tests for OrganizationGenerator
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from foobara_py.generators import OrganizationGenerator, generate_organization


class TestOrganizationGenerator:
    """Test organization code generation"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs"""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    def test_generate_organization_structure(self, temp_dir):
        """Test generating basic organization structure"""
        generator = OrganizationGenerator(
            name="MyApp",
            domains=["Users", "Products"],
            description="E-commerce application"
        )

        files = generator.generate(temp_dir)

        # Check organization __init__.py exists
        org_dir = temp_dir / "my_app"
        assert (org_dir / "__init__.py").exists()

        # Check domains created
        assert (org_dir / "users" / "__init__.py").exists()
        assert (org_dir / "products" / "__init__.py").exists()

        # Check subdirectories created for domains
        assert (org_dir / "users" / "commands" / "__init__.py").exists()
        assert (org_dir / "users" / "types" / "__init__.py").exists()
        assert (org_dir / "users" / "entities" / "__init__.py").exists()

    def test_organization_init_content(self, temp_dir):
        """Test organization __init__.py content"""
        generator = OrganizationGenerator(
            name="TestOrg",
            domains=["DomainA", "DomainB"],
            version="1.0.0"
        )

        files = generator.generate(temp_dir)

        org_init = temp_dir / "test_org" / "__init__.py"
        content = org_init.read_text()

        assert 'TestOrg' in content
        assert '__organization__ = "TestOrg"' in content
        assert '__version__ = "1.0.0"' in content
        assert "DomainA" in content
        assert "DomainB" in content

    def test_generate_without_domains(self, temp_dir):
        """Test generating organization without domains"""
        generator = OrganizationGenerator(
            name="EmptyOrg",
            domains=[],
            generate_domains=False
        )

        files = generator.generate(temp_dir)

        # Only organization __init__.py should exist
        org_dir = temp_dir / "empty_org"
        assert (org_dir / "__init__.py").exists()

        # No domain directories
        domain_dirs = [d for d in org_dir.iterdir() if d.is_dir()]
        assert len(domain_dirs) == 0

    def test_convenience_function(self, temp_dir):
        """Test the generate_organization convenience function"""
        files = generate_organization(
            name="ConvenienceTest",
            output_dir=temp_dir,
            domains=["Auth", "API"],
            description="Test organization"
        )

        org_dir = temp_dir / "convenience_test"
        assert (org_dir / "__init__.py").exists()
        assert (org_dir / "auth" / "__init__.py").exists()
        assert (org_dir / "api" / "__init__.py").exists()

    def test_domain_dependencies(self, temp_dir):
        """Test organization with domain dependencies"""
        generator = OrganizationGenerator(
            name="DependencyTest",
            domains=["Core", "Extended"]
        )

        files = generator.generate(
            temp_dir,
            domain_dependencies={
                "Extended": ["Core"]
            }
        )

        # Check that both domains were created
        org_dir = temp_dir / "dependency_test"
        assert (org_dir / "core" / "__init__.py").exists()
        assert (org_dir / "extended" / "__init__.py").exists()
