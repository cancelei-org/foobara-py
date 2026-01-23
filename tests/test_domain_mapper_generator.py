"""
Tests for DomainMapperGenerator
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from foobara_py.generators import DomainMapperGenerator, generate_domain_mapper


class TestDomainMapperGenerator:
    """Test domain mapper code generation"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs"""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    def test_generate_simple_mapper(self, temp_dir):
        """Test generating a simple domain mapper"""
        generator = DomainMapperGenerator(
            name="IntegerToString",
            from_type="int",
            to_type="str",
            is_simple_conversion=True,
            mapping_expression="str(self.from_value)"
        )

        files = generator.generate(temp_dir)

        assert len(files) == 1
        assert files[0].name == "integer_to_string.py"
        assert files[0].exists()

        content = files[0].read_text()
        assert "class IntegerToString(DomainMapper[int, str]):" in content
        assert "def map(self) -> str:" in content
        assert "return str(self.from_value)" in content

    def test_generate_domain_mapper_with_domain(self, temp_dir):
        """Test generating a domain mapper with domain registration"""
        generator = DomainMapperGenerator(
            name="UserInternalToExternal",
            from_type="UserInternal",
            to_type="UserExternal",
            domain="Users",
            organization="MyApp",
            description="Maps internal user model to external API model"
        )

        files = generator.generate(temp_dir)

        assert len(files) == 1
        content = files[0].read_text()
        assert '@domain_mapper(domain="Users", organization="MyApp")' in content
        assert "class UserInternalToExternal(DomainMapper[UserInternal, UserExternal]):" in content
        assert "Maps internal user model to external API model" in content

    def test_generate_with_imports(self, temp_dir):
        """Test generating mapper with custom type imports"""
        generator = DomainMapperGenerator(
            name="UserAToUserB",
            from_type="UserA",
            to_type="UserB",
            from_type_import="from myapp.domain_a.models import UserA",
            to_type_import="from myapp.domain_b.models import UserB"
        )

        files = generator.generate(temp_dir)
        content = files[0].read_text()

        assert "from myapp.domain_a.models import UserA" in content
        assert "from myapp.domain_b.models import UserB" in content

    def test_convenience_function(self, temp_dir):
        """Test the generate_domain_mapper convenience function"""
        files = generate_domain_mapper(
            name="StringToInteger",
            from_type="str",
            to_type="int",
            output_dir=temp_dir,
            is_simple_conversion=True,
            mapping_expression="int(self.from_value)"
        )

        assert len(files) == 1
        assert files[0].exists()
        content = files[0].read_text()
        assert "return int(self.from_value)" in content
