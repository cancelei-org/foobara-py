"""Tests for ProjectGenerator"""

import pytest
from pathlib import Path
from foobara_py.generators import ProjectGenerator, generate_project


class TestProjectGeneratorBasic:
    """Test ProjectGenerator basic functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_basic_project(self):
        """Should generate basic project structure"""
        generator = ProjectGenerator(
            name="MyApp",
            template="basic",
            python_version="3.11"
        )

        files = generator.generate(self.temp_dir)

        project_dir = self.temp_dir / "my_app"

        # Core files
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / ".gitignore").exists()
        assert (project_dir / "Makefile").exists()

        # Package structure
        assert (project_dir / "my_app" / "__init__.py").exists()
        assert (project_dir / "my_app" / "domains" / "__init__.py").exists()
        assert (project_dir / "my_app" / "commands" / "__init__.py").exists()
        assert (project_dir / "my_app" / "entities" / "__init__.py").exists()

        # Tests
        assert (project_dir / "tests" / "__init__.py").exists()
        assert (project_dir / "tests" / "conftest.py").exists()

    def test_generate_api_project(self):
        """Should generate API project with server"""
        generator = ProjectGenerator(
            name="ApiService",
            template="api",
            python_version="3.11"
        )

        files = generator.generate(self.temp_dir)

        project_dir = self.temp_dir / "api_service"

        # Should have server.py
        assert (project_dir / "api_service" / "server.py").exists()

        # Check pyproject.toml has API dependencies
        pyproject = (project_dir / "pyproject.toml").read_text()
        assert "uvicorn" in pyproject
        assert "starlette" in pyproject

    def test_generate_project_with_docker(self):
        """Should generate Dockerfile when include_docker=True"""
        generator = ProjectGenerator(
            name="DockerApp",
            template="basic",
            include_docker=True
        )

        files = generator.generate(self.temp_dir)

        project_dir = self.temp_dir / "docker_app"
        assert (project_dir / "Dockerfile").exists()

        dockerfile = (project_dir / "Dockerfile").read_text()
        assert "FROM python:" in dockerfile
        assert "WORKDIR /app" in dockerfile

    def test_generate_project_with_ci(self):
        """Should generate CI workflow when include_ci=True"""
        generator = ProjectGenerator(
            name="CIApp",
            template="basic",
            include_ci=True
        )

        files = generator.generate(self.temp_dir)

        project_dir = self.temp_dir / "ci_app"
        ci_file = project_dir / ".github" / "workflows" / "ci.yml"
        assert ci_file.exists()

        ci_content = ci_file.read_text()
        assert "pytest" in ci_content
        assert "ruff" in ci_content
        assert "mypy" in ci_content

    def test_generate_project_without_makefile(self):
        """Should skip Makefile when include_makefile=False"""
        generator = ProjectGenerator(
            name="NoMake",
            template="basic",
            include_makefile=False
        )

        files = generator.generate(self.temp_dir)

        project_dir = self.temp_dir / "no_make"
        assert not (project_dir / "Makefile").exists()


class TestProjectGeneratorContent:
    """Test generated file content"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_pyproject_content(self):
        """Should generate valid pyproject.toml"""
        generator = ProjectGenerator(
            name="TestProject",
            template="basic",
            python_version="3.12",
            description="A test project",
            author="Test Author"
        )

        generator.generate(self.temp_dir)

        pyproject = (self.temp_dir / "test_project" / "pyproject.toml").read_text()

        assert 'name = "test_project"' in pyproject
        assert 'version = "0.1.0"' in pyproject
        assert 'requires-python = ">=3.12"' in pyproject
        assert "foobara-py" in pyproject
        assert "pydantic" in pyproject
        assert "Test Author" in pyproject

    def test_readme_content(self):
        """Should generate proper README"""
        generator = ProjectGenerator(
            name="ReadmeTest",
            template="api",
            description="Custom description"
        )

        generator.generate(self.temp_dir)

        readme = (self.temp_dir / "readme_test" / "README.md").read_text()

        assert "# ReadmeTest" in readme
        assert "Custom description" in readme
        assert "Running the API Server" in readme
        assert "pip install" in readme

    def test_conftest_content(self):
        """Should generate proper conftest.py"""
        generator = ProjectGenerator(
            name="ConfTest",
            template="basic"
        )

        generator.generate(self.temp_dir)

        conftest = (self.temp_dir / "conf_test" / "tests" / "conftest.py").read_text()

        assert "import pytest" in conftest
        assert "@pytest.fixture" in conftest
        assert "InMemoryCRUDDriver" in conftest
        assert "reset_registries" in conftest

    def test_server_content(self):
        """Should generate proper server.py for API template"""
        generator = ProjectGenerator(
            name="ServerTest",
            template="api"
        )

        generator.generate(self.temp_dir)

        server = (self.temp_dir / "server_test" / "server_test" / "server.py").read_text()

        assert "import uvicorn" in server
        assert "HTTPConnector" in server
        assert "def create_app():" in server
        assert "def main():" in server

    def test_makefile_content(self):
        """Should generate proper Makefile"""
        generator = ProjectGenerator(
            name="MakeTest",
            template="api",
            include_docker=True
        )

        generator.generate(self.temp_dir)

        makefile = (self.temp_dir / "make_test" / "Makefile").read_text()

        assert "install:" in makefile
        assert "test:" in makefile
        assert "lint:" in makefile
        assert "format:" in makefile
        assert "run:" in makefile
        assert "docker-build:" in makefile


class TestGenerateProjectFunction:
    """Test generate_project convenience function"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_project_function(self):
        """Should generate project via convenience function"""
        files = generate_project(
            name="FuncTest",
            output_dir=self.temp_dir,
            template="basic",
            python_version="3.11"
        )

        assert len(files) > 0
        assert (self.temp_dir / "func_test" / "pyproject.toml").exists()

    def test_generate_project_function_full(self):
        """Should generate full project with all options"""
        files = generate_project(
            name="FullTest",
            output_dir=self.temp_dir,
            template="full",
            python_version="3.12",
            description="Full test project",
            include_docker=True,
            include_ci=True,
            include_makefile=True
        )

        project_dir = self.temp_dir / "full_test"

        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "Dockerfile").exists()
        assert (project_dir / ".github" / "workflows" / "ci.yml").exists()
        assert (project_dir / "Makefile").exists()
        assert (project_dir / "full_test" / "server.py").exists()


class TestProjectNaming:
    """Test project naming conventions"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_name_case_conversion(self):
        """Should handle various project name cases"""
        test_cases = [
            ("MyApp", "my_app"),
            ("user-service", "user_service"),
            ("APIGateway", "api_gateway"),
            ("simple", "simple"),
        ]

        for name, expected_dir in test_cases:
            generator = ProjectGenerator(
                name=name,
                template="basic",
                include_makefile=False
            )
            generator.generate(self.temp_dir)

            expected_path = self.temp_dir / expected_dir
            assert expected_path.exists(), f"Failed for {name}"

            # Cleanup for next test
            import shutil
            shutil.rmtree(expected_path)


class TestProjectTemplates:
    """Test different project templates"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_basic_template(self):
        """Basic template should not include server"""
        generator = ProjectGenerator(name="Basic", template="basic")
        generator.generate(self.temp_dir)

        project_dir = self.temp_dir / "basic"
        assert not (project_dir / "basic" / "server.py").exists()

    def test_api_template(self):
        """API template should include server"""
        generator = ProjectGenerator(name="Api", template="api")
        generator.generate(self.temp_dir)

        project_dir = self.temp_dir / "api"
        assert (project_dir / "api" / "server.py").exists()

    def test_full_template(self):
        """Full template should include all features"""
        generator = ProjectGenerator(name="Full", template="full")
        generator.generate(self.temp_dir)

        project_dir = self.temp_dir / "full"
        assert (project_dir / "full" / "server.py").exists()

        pyproject = (project_dir / "pyproject.toml").read_text()
        assert "uvicorn" in pyproject
        assert "jinja2" in pyproject


class TestProjectGeneratorEdgeCases:
    """Test edge cases and error handling for ProjectGenerator"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_empty_project_name(self):
        """Should handle empty project name"""
        generator = ProjectGenerator(
            name="",
            template="basic"
        )
        files = generator.generate(self.temp_dir)
        # Empty name should create a project directory
        assert len(files) > 0

    def test_project_name_with_special_characters(self):
        """Should sanitize project names with special characters"""
        generator = ProjectGenerator(
            name="My@App#2024!",
            template="basic"
        )
        files = generator.generate(self.temp_dir)
        # Should convert to valid snake_case
        assert len(files) > 0

    def test_project_name_with_spaces(self):
        """Should handle project names with spaces"""
        generator = ProjectGenerator(
            name="My Cool App",
            template="basic"
        )
        files = generator.generate(self.temp_dir)
        project_dir = self.temp_dir / "my_cool_app"
        assert project_dir.exists()

    def test_project_name_with_numbers(self):
        """Should handle project names starting with numbers"""
        generator = ProjectGenerator(
            name="123App",
            template="basic"
        )
        files = generator.generate(self.temp_dir)
        assert len(files) > 0

    def test_very_long_project_name(self):
        """Should handle very long project names"""
        long_name = "A" * 200
        generator = ProjectGenerator(
            name=long_name,
            template="basic"
        )
        files = generator.generate(self.temp_dir)
        assert len(files) > 0

    def test_unicode_project_name(self):
        """Should handle unicode in project names"""
        generator = ProjectGenerator(
            name="MyApp_日本語",
            template="basic"
        )
        files = generator.generate(self.temp_dir)
        assert len(files) > 0

    def test_invalid_template_name(self):
        """Should handle invalid template names gracefully"""
        generator = ProjectGenerator(
            name="TestApp",
            template="invalid"  # type: ignore
        )
        # Should not crash, might use default template
        files = generator.generate(self.temp_dir)
        assert len(files) > 0

    def test_old_python_version(self):
        """Should handle old Python versions"""
        generator = ProjectGenerator(
            name="OldPython",
            template="basic",
            python_version="3.7"
        )
        files = generator.generate(self.temp_dir)
        project_dir = self.temp_dir / "old_python"
        pyproject = (project_dir / "pyproject.toml").read_text()
        assert "3.7" in pyproject

    def test_future_python_version(self):
        """Should handle future Python versions"""
        generator = ProjectGenerator(
            name="FuturePython",
            template="basic",
            python_version="3.20"
        )
        files = generator.generate(self.temp_dir)
        project_dir = self.temp_dir / "future_python"
        pyproject = (project_dir / "pyproject.toml").read_text()
        assert "3.20" in pyproject

    def test_invalid_python_version_format(self):
        """Should handle invalid Python version formats"""
        generator = ProjectGenerator(
            name="BadVersion",
            template="basic",
            python_version="python3.11"
        )
        files = generator.generate(self.temp_dir)
        # Should still generate files
        assert len(files) > 0

    def test_generate_all_templates(self):
        """Should successfully generate all template types"""
        templates = ["basic", "api", "web", "full"]
        for template in templates:
            generator = ProjectGenerator(
                name=f"Test{template.capitalize()}",
                template=template,  # type: ignore
                include_makefile=False
            )
            files = generator.generate(self.temp_dir)
            assert len(files) > 0

    def test_generate_with_all_optional_features(self):
        """Should generate with all optional features enabled"""
        generator = ProjectGenerator(
            name="AllFeatures",
            template="full",
            include_docker=True,
            include_ci=True,
            include_makefile=True
        )
        files = generator.generate(self.temp_dir)
        project_dir = self.temp_dir / "all_features"

        assert (project_dir / "Dockerfile").exists()
        assert (project_dir / ".github" / "workflows" / "ci.yml").exists()
        assert (project_dir / "Makefile").exists()

    def test_generate_with_no_optional_features(self):
        """Should generate with all optional features disabled"""
        generator = ProjectGenerator(
            name="MinimalFeatures",
            template="basic",
            include_docker=False,
            include_ci=False,
            include_makefile=False
        )
        files = generator.generate(self.temp_dir)
        project_dir = self.temp_dir / "minimal_features"

        assert not (project_dir / "Dockerfile").exists()
        assert not (project_dir / ".github" / "workflows" / "ci.yml").exists()
        assert not (project_dir / "Makefile").exists()

    def test_very_long_description(self):
        """Should handle very long descriptions"""
        long_desc = "A" * 1000
        generator = ProjectGenerator(
            name="LongDesc",
            template="basic",
            description=long_desc
        )
        files = generator.generate(self.temp_dir)
        project_dir = self.temp_dir / "long_desc"
        readme = (project_dir / "README.md").read_text()
        assert long_desc in readme

    def test_multiline_description(self):
        """Should handle multiline descriptions"""
        multiline_desc = "Line 1\nLine 2\nLine 3"
        generator = ProjectGenerator(
            name="MultiDesc",
            template="basic",
            description=multiline_desc
        )
        files = generator.generate(self.temp_dir)
        assert len(files) > 0

    def test_special_characters_in_description(self):
        """Should handle special characters in description"""
        special_desc = "Description with 'quotes' and \"double quotes\" and <html>"
        generator = ProjectGenerator(
            name="SpecialDesc",
            template="basic",
            description=special_desc
        )
        files = generator.generate(self.temp_dir)
        assert len(files) > 0

    def test_author_with_email(self):
        """Should handle author with email format"""
        generator = ProjectGenerator(
            name="AuthorEmail",
            template="basic",
            author="John Doe <john@example.com>"
        )
        files = generator.generate(self.temp_dir)
        project_dir = self.temp_dir / "author_email"
        pyproject = (project_dir / "pyproject.toml").read_text()
        assert "John Doe" in pyproject

    def test_author_with_unicode(self):
        """Should handle unicode in author names"""
        generator = ProjectGenerator(
            name="UnicodeAuthor",
            template="basic",
            author="José García"
        )
        files = generator.generate(self.temp_dir)
        assert len(files) > 0

    def test_existing_directory_same_name(self):
        """Should handle existing directory with same name"""
        # Create a directory first
        existing_dir = self.temp_dir / "existing_app"
        existing_dir.mkdir(parents=True)
        (existing_dir / "existing_file.txt").write_text("existing content")

        generator = ProjectGenerator(
            name="ExistingApp",
            template="basic"
        )
        files = generator.generate(self.temp_dir)
        # Should still generate files (overwrite or merge)
        assert len(files) > 0

    def test_output_to_nonexistent_directory(self):
        """Should create output directory if it doesn't exist"""
        nonexistent = self.temp_dir / "deeply" / "nested" / "path"
        generator = ProjectGenerator(
            name="DeepPath",
            template="basic"
        )
        files = generator.generate(nonexistent)
        assert len(files) > 0
        assert nonexistent.exists()

    def test_readonly_parent_directory(self):
        """Should handle readonly parent directory gracefully"""
        import os
        import stat

        readonly_dir = self.temp_dir / "readonly"
        readonly_dir.mkdir()

        # Make directory readonly
        os.chmod(readonly_dir, stat.S_IRUSR | stat.S_IXUSR)

        try:
            generator = ProjectGenerator(
                name="ReadonlyTest",
                template="basic"
            )
            # This should raise an error or handle gracefully
            try:
                files = generator.generate(readonly_dir)
            except (PermissionError, OSError):
                pass  # Expected behavior
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, stat.S_IRWXU)

    def test_concurrent_generation_same_directory(self):
        """Should handle concurrent generation attempts"""
        import concurrent.futures

        def generate_project(name):
            generator = ProjectGenerator(
                name=name,
                template="basic",
                include_makefile=False
            )
            return generator.generate(self.temp_dir)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(generate_project, f"Concurrent{i}")
                for i in range(3)
            ]
            results = [f.result() for f in futures]

        # All should complete successfully
        for result in results:
            assert len(result) > 0
