"""Tests for FilesGenerator base class"""

import pytest
from pathlib import Path
from foobara_py.generators import (
    FilesGenerator,
    GeneratorError,
    TemplateNotFoundError,
    FileExistsError,
)


# Test implementation of FilesGenerator
class SimpleGenerator(FilesGenerator):
    """Simple generator for testing"""

    def __init__(self, template_dir: Path):
        super().__init__(template_dir=template_dir)

    def generate(self, output_dir: Path, **kwargs) -> list[Path]:
        """Generate simple files"""
        context = kwargs.get("context", {})
        files = []

        # Create a file from template
        files.append(
            self.create_from_template(
                template_name="simple.txt.j2",
                output_path=output_dir / "output.txt",
                context=context,
            )
        )

        return files


class TestFilesGeneratorBasic:
    """Test basic FilesGenerator functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_dir = self.temp_dir / "templates"
        self.output_dir = self.temp_dir / "output"

        self.template_dir.mkdir()
        self.output_dir.mkdir()

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_create_generator(self):
        """Should create generator instance"""
        generator = SimpleGenerator(template_dir=self.template_dir)
        assert generator is not None

    def test_render_template_basic(self):
        """Should render simple template"""
        # Create template
        template_path = self.template_dir / "simple.txt.j2"
        template_path.write_text("Hello {{ name }}!")

        generator = SimpleGenerator(template_dir=self.template_dir)
        result = generator.render_template("simple.txt.j2", {"name": "World"})

        assert result == "Hello World!"

    def test_render_template_not_found(self):
        """Should raise error for missing template"""
        generator = SimpleGenerator(template_dir=self.template_dir)

        with pytest.raises(TemplateNotFoundError):
            generator.render_template("nonexistent.j2", {})

    def test_create_from_template(self):
        """Should create file from template"""
        # Create template
        template_path = self.template_dir / "file.txt.j2"
        template_path.write_text("Content: {{ value }}")

        generator = SimpleGenerator(template_dir=self.template_dir)
        output_path = self.output_dir / "result.txt"

        created_path = generator.create_from_template(
            template_name="file.txt.j2",
            output_path=output_path,
            context={"value": "test"},
        )

        assert created_path == output_path
        assert output_path.exists()
        assert output_path.read_text() == "Content: test"

    def test_create_from_template_creates_directories(self):
        """Should create parent directories"""
        template_path = self.template_dir / "file.txt.j2"
        template_path.write_text("Test")

        generator = SimpleGenerator(template_dir=self.template_dir)
        output_path = self.output_dir / "nested" / "deep" / "file.txt"

        generator.create_from_template(
            template_name="file.txt.j2",
            output_path=output_path,
            context={},
        )

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_create_from_template_file_exists_error(self):
        """Should raise error if file exists"""
        template_path = self.template_dir / "file.txt.j2"
        template_path.write_text("Test")

        output_path = self.output_dir / "existing.txt"
        output_path.write_text("Existing content")

        generator = SimpleGenerator(template_dir=self.template_dir)

        with pytest.raises(FileExistsError):
            generator.create_from_template(
                template_name="file.txt.j2",
                output_path=output_path,
                context={},
                overwrite=False,
            )

    def test_create_from_template_overwrite(self):
        """Should overwrite file if overwrite=True"""
        template_path = self.template_dir / "file.txt.j2"
        template_path.write_text("New content")

        output_path = self.output_dir / "existing.txt"
        output_path.write_text("Old content")

        generator = SimpleGenerator(template_dir=self.template_dir)

        generator.create_from_template(
            template_name="file.txt.j2",
            output_path=output_path,
            context={},
            overwrite=True,
        )

        assert output_path.read_text() == "New content"

    def test_create_file(self):
        """Should create file with content"""
        generator = SimpleGenerator(template_dir=self.template_dir)
        output_path = self.output_dir / "direct.txt"

        generator.create_file(output_path, "Direct content")

        assert output_path.exists()
        assert output_path.read_text() == "Direct content"

    def test_create_file_exists_error(self):
        """Should raise error if file exists"""
        output_path = self.output_dir / "existing.txt"
        output_path.write_text("Existing")

        generator = SimpleGenerator(template_dir=self.template_dir)

        with pytest.raises(FileExistsError):
            generator.create_file(output_path, "New", overwrite=False)

    def test_create_directory(self):
        """Should create directory"""
        generator = SimpleGenerator(template_dir=self.template_dir)
        dir_path = self.output_dir / "new_dir"

        created = generator.create_directory(dir_path)

        assert created == dir_path
        assert dir_path.exists()
        assert dir_path.is_dir()

    def test_create_directory_nested(self):
        """Should create nested directories"""
        generator = SimpleGenerator(template_dir=self.template_dir)
        dir_path = self.output_dir / "a" / "b" / "c"

        generator.create_directory(dir_path)

        assert dir_path.exists()

    def test_generate_method(self):
        """Should call generate method"""
        template_path = self.template_dir / "simple.txt.j2"
        template_path.write_text("Generated: {{ value }}")

        generator = SimpleGenerator(template_dir=self.template_dir)
        files = generator.generate(
            self.output_dir, context={"value": "test"}
        )

        assert len(files) == 1
        assert files[0].exists()
        assert files[0].read_text() == "Generated: test"


class TestJinja2Features:
    """Test Jinja2 template features"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_dir = self.temp_dir / "templates"
        self.output_dir = self.temp_dir / "output"

        self.template_dir.mkdir()
        self.output_dir.mkdir()

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_template_with_loops(self):
        """Should handle loops in templates"""
        template_path = self.template_dir / "loop.txt.j2"
        template_path.write_text(
            "{% for item in items %}\n{{ item }}\n{% endfor %}"
        )

        generator = SimpleGenerator(template_dir=self.template_dir)
        result = generator.render_template(
            "loop.txt.j2", {"items": ["a", "b", "c"]}
        )

        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_template_with_conditionals(self):
        """Should handle conditionals in templates"""
        template_path = self.template_dir / "cond.txt.j2"
        template_path.write_text(
            "{% if show %}Visible{% else %}Hidden{% endif %}"
        )

        generator = SimpleGenerator(template_dir=self.template_dir)

        result_true = generator.render_template("cond.txt.j2", {"show": True})
        result_false = generator.render_template("cond.txt.j2", {"show": False})

        assert result_true == "Visible"
        assert result_false == "Hidden"

    def test_template_with_filters(self):
        """Should handle built-in filters"""
        template_path = self.template_dir / "filter.txt.j2"
        template_path.write_text("{{ text | upper }}")

        generator = SimpleGenerator(template_dir=self.template_dir)
        result = generator.render_template("filter.txt.j2", {"text": "hello"})

        assert result == "HELLO"


class TestCaseConversionFilters:
    """Test custom case conversion filters"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_dir = self.temp_dir / "templates"

        self.template_dir.mkdir()
        self.generator = SimpleGenerator(template_dir=self.template_dir)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_snake_case_filter(self):
        """Should convert to snake_case"""
        template_path = self.template_dir / "snake.txt.j2"
        template_path.write_text("{{ name | snake_case }}")

        tests = [
            ("MyClass", "my_class"),
            ("getUserData", "get_user_data"),
            ("API_KEY", "api_key"),
            ("user-name", "user_name"),
            ("some text", "some_text"),
        ]

        for input_val, expected in tests:
            result = self.generator.render_template("snake.txt.j2", {"name": input_val})
            assert result == expected, f"Failed for {input_val}"

    def test_pascal_case_filter(self):
        """Should convert to PascalCase"""
        template_path = self.template_dir / "pascal.txt.j2"
        template_path.write_text("{{ name | pascal_case }}")

        tests = [
            ("my_class", "MyClass"),
            ("get_user_data", "GetUserData"),
            ("user-name", "UserName"),
            ("some text", "SomeText"),
        ]

        for input_val, expected in tests:
            result = self.generator.render_template("pascal.txt.j2", {"name": input_val})
            assert result == expected, f"Failed for {input_val}"

    def test_camel_case_filter(self):
        """Should convert to camelCase"""
        template_path = self.template_dir / "camel.txt.j2"
        template_path.write_text("{{ name | camel_case }}")

        tests = [
            ("my_class", "myClass"),
            ("get_user_data", "getUserData"),
            ("UserName", "userName"),
        ]

        for input_val, expected in tests:
            result = self.generator.render_template("camel.txt.j2", {"name": input_val})
            assert result == expected, f"Failed for {input_val}"

    def test_kebab_case_filter(self):
        """Should convert to kebab-case"""
        template_path = self.template_dir / "kebab.txt.j2"
        template_path.write_text("{{ name | kebab_case }}")

        tests = [
            ("my_class", "my-class"),
            ("getUserData", "get-user-data"),
            ("some text", "some-text"),
        ]

        for input_val, expected in tests:
            result = self.generator.render_template("kebab.txt.j2", {"name": input_val})
            assert result == expected, f"Failed for {input_val}"


class TestRealWorldScenarios:
    """Test real-world generator scenarios"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.template_dir = self.temp_dir / "templates"
        self.output_dir = self.temp_dir / "output"

        self.template_dir.mkdir()
        self.output_dir.mkdir()

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_python_class(self):
        """Should generate Python class file"""
        template = '''"""{{ description }}"""

from pydantic import BaseModel


class {{ class_name | pascal_case }}(BaseModel):
    """{{ class_name | pascal_case }} model"""
{% for field in fields %}
    {{ field.name }}: {{ field.type }}
{% endfor %}
'''
        template_path = self.template_dir / "class.py.j2"
        template_path.write_text(template)

        generator = SimpleGenerator(template_dir=self.template_dir)
        context = {
            "description": "User model",
            "class_name": "user",
            "fields": [
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
                {"name": "email", "type": "str"},
            ],
        }

        output_path = self.output_dir / "user.py"
        generator.create_from_template(
            template_name="class.py.j2",
            output_path=output_path,
            context=context,
        )

        content = output_path.read_text()
        assert "class User(BaseModel):" in content
        assert "id: int" in content
        assert "name: str" in content
        assert "email: str" in content

    def test_generate_multiple_files(self):
        """Should generate multiple files"""
        # Create templates
        init_template = self.template_dir / "init.py.j2"
        init_template.write_text('"""{{ package_name }} package"""')

        model_template = self.template_dir / "model.py.j2"
        model_template.write_text("class {{ model_name }}:\n    pass")

        generator = SimpleGenerator(template_dir=self.template_dir)

        # Generate __init__.py
        init_path = generator.create_from_template(
            template_name="init.py.j2",
            output_path=self.output_dir / "__init__.py",
            context={"package_name": "mypackage"},
        )

        # Generate model.py
        model_path = generator.create_from_template(
            template_name="model.py.j2",
            output_path=self.output_dir / "model.py",
            context={"model_name": "User"},
        )

        assert init_path.exists()
        assert model_path.exists()
        assert '__init__.py' in str(init_path)
        assert 'model.py' in str(model_path)
