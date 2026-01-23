"""Tests for LoadDotenv utility."""

import os
import tempfile
from pathlib import Path
import pytest

from foobara_py.util import LoadDotenv, EnvFile


class TestEnvFile:
    """Test EnvFile dataclass."""

    def test_env_file_creation(self):
        """Should create EnvFile with correct attributes."""
        env_file = EnvFile(
            file_name=".env.production.local",
            envs=["production"],
            is_local=True,
        )

        assert env_file.file_name == ".env.production.local"
        assert env_file.envs == ["production"]
        assert env_file.is_local is True

    def test_env_file_without_envs(self):
        """Should create EnvFile with no envs."""
        env_file = EnvFile(
            file_name=".env",
            envs=None,
            is_local=False,
        )

        assert env_file.file_name == ".env"
        assert env_file.envs is None
        assert env_file.is_local is False


class TestLoadDotenv:
    """Test LoadDotenv class."""

    def test_initialization_with_defaults(self):
        """Should initialize with default values."""
        # Set environment variable for testing
        os.environ["FOOBARA_ENV"] = "test"

        loader = LoadDotenv()

        assert loader.env == "test"
        assert loader.dir == Path.cwd()
        assert loader.env_files == []
        assert loader.env_files_to_apply == []

        # Clean up
        del os.environ["FOOBARA_ENV"]

    def test_initialization_with_custom_env(self):
        """Should initialize with custom environment."""
        loader = LoadDotenv(env="production")

        assert loader.env == "production"

    def test_initialization_with_custom_dir(self):
        """Should initialize with custom directory."""
        custom_dir = "/tmp/custom"
        loader = LoadDotenv(dir=custom_dir)

        assert loader.dir == Path(custom_dir)

    def test_env_priority_dotenv_env(self):
        """Should prioritize DOTENV_ENV over FOOBARA_ENV."""
        os.environ["DOTENV_ENV"] = "staging"
        os.environ["FOOBARA_ENV"] = "test"

        loader = LoadDotenv()

        assert loader.env == "staging"

        # Clean up
        del os.environ["DOTENV_ENV"]
        del os.environ["FOOBARA_ENV"]

    def test_env_defaults_to_development(self):
        """Should default to development when no env vars set."""
        # Remove env vars if they exist
        os.environ.pop("DOTENV_ENV", None)
        os.environ.pop("FOOBARA_ENV", None)

        loader = LoadDotenv()

        assert loader.env == "development"

    def test_parse_env_file_names(self):
        """Should parse .env file names correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create various .env files
            (tmppath / ".env").touch()
            (tmppath / ".env.local").touch()
            (tmppath / ".env.production").touch()
            (tmppath / ".env.production.local").touch()
            (tmppath / ".env.test").touch()
            (tmppath / ".env.test.integration").touch()
            (tmppath / "not-an-env-file.txt").touch()
            (tmppath / ".envrc").touch()  # Should not match

            loader = LoadDotenv(dir=tmpdir)
            loader._parse_env_file_names()

            # Should find 6 valid .env files
            assert len(loader.env_files) == 6

            # Check specific files are parsed correctly
            env_file_names = [ef.file_name for ef in loader.env_files]
            assert ".env" in env_file_names
            assert ".env.local" in env_file_names
            assert ".env.production" in env_file_names
            assert ".env.production.local" in env_file_names
            assert ".env.test" in env_file_names
            assert ".env.test.integration" in env_file_names

            # Should not include invalid files
            assert "not-an-env-file.txt" not in env_file_names
            assert ".envrc" not in env_file_names

    def test_parse_env_file_attributes(self):
        """Should parse .env file attributes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / ".env").touch()
            (tmppath / ".env.local").touch()
            (tmppath / ".env.production").touch()
            (tmppath / ".env.production.local").touch()
            (tmppath / ".env.test.integration").touch()

            loader = LoadDotenv(dir=tmpdir)
            loader._parse_env_file_names()

            # Find specific files and check attributes
            env_files_by_name = {ef.file_name: ef for ef in loader.env_files}

            # .env - no envs, not local
            assert env_files_by_name[".env"].envs is None
            assert env_files_by_name[".env"].is_local is False

            # .env.local - no envs, is local
            assert env_files_by_name[".env.local"].envs is None
            assert env_files_by_name[".env.local"].is_local is True

            # .env.production - has production env, not local
            assert env_files_by_name[".env.production"].envs == ["production"]
            assert env_files_by_name[".env.production"].is_local is False

            # .env.production.local - has production env, is local
            assert env_files_by_name[".env.production.local"].envs == ["production"]
            assert env_files_by_name[".env.production.local"].is_local is True

            # .env.test.integration - has test and integration, not local
            assert env_files_by_name[".env.test.integration"].envs == ["test", "integration"]
            assert env_files_by_name[".env.test.integration"].is_local is False

    def test_determine_env_files_to_apply(self):
        """Should determine which files to apply based on environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / ".env").touch()
            (tmppath / ".env.local").touch()
            (tmppath / ".env.production").touch()
            (tmppath / ".env.production.local").touch()
            (tmppath / ".env.test").touch()

            # Test for production environment
            loader = LoadDotenv(env="production", dir=tmpdir)
            loader._parse_env_file_names()
            loader._determine_env_files_to_apply()

            file_names = [ef.file_name for ef in loader.env_files_to_apply]

            # Should include .env, .env.local, .env.production, .env.production.local
            assert ".env" in file_names
            assert ".env.local" in file_names
            assert ".env.production" in file_names
            assert ".env.production.local" in file_names

            # Should NOT include .env.test
            assert ".env.test" not in file_names

    def test_sort_env_files_priority(self):
        """Should sort env files by correct priority."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / ".env").touch()
            (tmppath / ".env.local").touch()
            (tmppath / ".env.production").touch()
            (tmppath / ".env.production.local").touch()

            loader = LoadDotenv(env="production", dir=tmpdir)
            loader._parse_env_file_names()
            loader._determine_env_files_to_apply()
            loader._sort_env_files()

            file_names = [ef.file_name for ef in loader.env_files_to_apply]

            # Priority order (highest to lowest):
            # 1. .env.production.local (local + specific)
            # 2. .env.local (local + general)
            # 3. .env.production (non-local + specific)
            # 4. .env (non-local + general)

            assert file_names[0] == ".env.production.local"
            assert file_names[1] == ".env.local"
            assert file_names[2] == ".env.production"
            assert file_names[3] == ".env"

    def test_sort_env_files_specificity(self):
        """Should sort by specificity (more dots = higher priority)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / ".env.test").touch()
            (tmppath / ".env.test.integration").touch()
            (tmppath / ".env.test.integration.local").touch()

            loader = LoadDotenv(env="test", dir=tmpdir)
            loader._parse_env_file_names()
            loader._determine_env_files_to_apply()
            loader._sort_env_files()

            file_names = [ef.file_name for ef in loader.env_files_to_apply]

            # .env.test.integration.local should come first (local + most specific)
            # .env.test.integration should come second (most specific non-local)
            # .env.test should come last (least specific)

            assert file_names[0] == ".env.test.integration.local"
            assert file_names[1] == ".env.test.integration"
            assert file_names[2] == ".env.test"

    def test_load_env_files_basic(self):
        """Should load environment variables from .env files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create .env file with variables
            env_file = tmppath / ".env"
            env_file.write_text("BASE_VAR=base_value\nSHARED_VAR=from_base\n")

            # Create .env.production file
            production_file = tmppath / ".env.production"
            production_file.write_text("PROD_VAR=prod_value\nSHARED_VAR=from_production\n")

            # Save current env state
            old_base_var = os.environ.get("BASE_VAR")
            old_prod_var = os.environ.get("PROD_VAR")
            old_shared_var = os.environ.get("SHARED_VAR")

            try:
                LoadDotenv.run(env="production", dir=tmpdir)

                # Should load both files
                assert os.environ.get("BASE_VAR") == "base_value"
                assert os.environ.get("PROD_VAR") == "prod_value"

                # More specific file should override
                assert os.environ.get("SHARED_VAR") == "from_production"

            finally:
                # Restore environment
                if old_base_var is None:
                    os.environ.pop("BASE_VAR", None)
                else:
                    os.environ["BASE_VAR"] = old_base_var

                if old_prod_var is None:
                    os.environ.pop("PROD_VAR", None)
                else:
                    os.environ["PROD_VAR"] = old_prod_var

                if old_shared_var is None:
                    os.environ.pop("SHARED_VAR", None)
                else:
                    os.environ["SHARED_VAR"] = old_shared_var

    def test_load_env_files_with_local_override(self):
        """Should allow local files to override other files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create .env file
            env_file = tmppath / ".env"
            env_file.write_text("VAR=from_base\n")

            # Create .env.local file
            local_file = tmppath / ".env.local"
            local_file.write_text("VAR=from_local\n")

            old_var = os.environ.get("VAR")

            try:
                LoadDotenv.run(dir=tmpdir)

                # Local should override base
                assert os.environ.get("VAR") == "from_local"

            finally:
                if old_var is None:
                    os.environ.pop("VAR", None)
                else:
                    os.environ["VAR"] = old_var

    def test_load_env_files_with_quotes(self):
        """Should handle quoted values correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            env_file = tmppath / ".env"
            env_file.write_text('QUOTED_VAR="quoted value"\nSINGLE_QUOTED=\'single quoted\'\n')

            old_quoted = os.environ.get("QUOTED_VAR")
            old_single = os.environ.get("SINGLE_QUOTED")

            try:
                LoadDotenv.run(dir=tmpdir)

                # Quotes should be stripped (basic implementation behavior)
                assert os.environ.get("QUOTED_VAR") == "quoted value"
                assert os.environ.get("SINGLE_QUOTED") == "single quoted"

            finally:
                if old_quoted is None:
                    os.environ.pop("QUOTED_VAR", None)
                else:
                    os.environ["QUOTED_VAR"] = old_quoted

                if old_single is None:
                    os.environ.pop("SINGLE_QUOTED", None)
                else:
                    os.environ["SINGLE_QUOTED"] = old_single

    def test_load_env_files_skip_comments(self):
        """Should skip comments and empty lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            env_file = tmppath / ".env"
            env_file.write_text("# This is a comment\nVAR=value\n\n# Another comment\n")

            old_var = os.environ.get("VAR")

            try:
                LoadDotenv.run(dir=tmpdir)

                assert os.environ.get("VAR") == "value"

            finally:
                if old_var is None:
                    os.environ.pop("VAR", None)
                else:
                    os.environ["VAR"] = old_var

    def test_missing_directory(self):
        """Should handle missing directory gracefully."""
        loader = LoadDotenv(dir="/nonexistent/directory/path")
        loader._parse_env_file_names()

        # Should not raise error, just have no files
        assert loader.env_files == []

    def test_empty_directory(self):
        """Should handle empty directory gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = LoadDotenv(dir=tmpdir)
            loader._parse_env_file_names()

            assert loader.env_files == []

    def test_run_class_method(self):
        """Should work via class method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            env_file = tmppath / ".env"
            env_file.write_text("CLASS_METHOD_VAR=works\n")

            old_var = os.environ.get("CLASS_METHOD_VAR")

            try:
                LoadDotenv.run(dir=tmpdir)

                assert os.environ.get("CLASS_METHOD_VAR") == "works"

            finally:
                if old_var is None:
                    os.environ.pop("CLASS_METHOD_VAR", None)
                else:
                    os.environ["CLASS_METHOD_VAR"] = old_var

    def test_execute_method(self):
        """Should work via execute method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            env_file = tmppath / ".env"
            env_file.write_text("EXECUTE_VAR=works\n")

            old_var = os.environ.get("EXECUTE_VAR")

            try:
                loader = LoadDotenv(dir=tmpdir)
                loader.execute()

                assert os.environ.get("EXECUTE_VAR") == "works"

            finally:
                if old_var is None:
                    os.environ.pop("EXECUTE_VAR", None)
                else:
                    os.environ["EXECUTE_VAR"] = old_var

    def test_full_integration(self):
        """Should work end-to-end with complex setup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create a full .env file structure
            (tmppath / ".env").write_text("BASE=base\nOVERRIDE_ME=base\n")
            (tmppath / ".env.local").write_text("LOCAL=local\nOVERRIDE_ME=local\n")
            (tmppath / ".env.production").write_text("PROD=production\nOVERRIDE_ME=production\n")
            (tmppath / ".env.production.local").write_text("PROD_LOCAL=prod_local\nOVERRIDE_ME=prod_local\n")
            (tmppath / ".env.test").write_text("TEST=test\n")

            # Save old values
            old_values = {
                "BASE": os.environ.get("BASE"),
                "LOCAL": os.environ.get("LOCAL"),
                "PROD": os.environ.get("PROD"),
                "PROD_LOCAL": os.environ.get("PROD_LOCAL"),
                "TEST": os.environ.get("TEST"),
                "OVERRIDE_ME": os.environ.get("OVERRIDE_ME"),
            }

            try:
                LoadDotenv.run(env="production", dir=tmpdir)

                # Should load base, local, production, and production.local
                assert os.environ.get("BASE") == "base"
                assert os.environ.get("LOCAL") == "local"
                assert os.environ.get("PROD") == "production"
                assert os.environ.get("PROD_LOCAL") == "prod_local"

                # Should NOT load test
                assert os.environ.get("TEST") is None or os.environ.get("TEST") == old_values["TEST"]

                # Most specific local should win
                assert os.environ.get("OVERRIDE_ME") == "prod_local"

            finally:
                # Restore environment
                for key, value in old_values.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
