"""
Tests for RemoteImportsGenerator
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from foobara_py.generators import RemoteImportsGenerator, generate_remote_imports


class TestRemoteImportsGenerator:
    """Test remote imports code generation"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test outputs"""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def mock_manifest(self):
        """Mock manifest data"""
        return {
            "commands": [
                {
                    "name": "CreateUser",
                    "full_name": "Users::CreateUser",
                    "description": "Create a new user",
                    "domain": "Users",
                    "organization": "MyApp",
                    "inputs_type": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "email": {
                                    "type": "string",
                                    "description": "User email address"
                                },
                                "name": {
                                    "type": "string",
                                    "description": "User full name"
                                },
                                "age": {
                                    "type": "integer",
                                    "default": 18
                                }
                            },
                            "required": ["email", "name"]
                        }
                    },
                    "result_type": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "email": {"type": "string"},
                                "name": {"type": "string"}
                            },
                            "required": ["id", "email", "name"]
                        }
                    }
                },
                {
                    "name": "ListUsers",
                    "full_name": "Users::ListUsers",
                    "description": "List all users",
                    "domain": "Users",
                    "inputs_type": {"schema": {"type": "object", "properties": {}}},
                    "result_type": {"schema": {}}
                }
            ]
        }

    def test_generate_remote_commands(self, temp_dir, mock_manifest):
        """Test generating remote command files from manifest"""
        with patch('httpx.Client') as mock_client:
            # Mock HTTP response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_manifest

            mock_context = MagicMock()
            mock_context.__enter__.return_value.get.return_value = mock_response
            mock_client.return_value = mock_context

            generator = RemoteImportsGenerator(
                manifest_url="https://api.example.com/manifest",
                remote_url="https://api.example.com"
            )

            files = generator.generate(temp_dir)

            # Should generate 2 command files + 1 __init__.py
            assert len(files) == 3

            # Check command files exist
            create_user_file = temp_dir / "create_user.py"
            list_users_file = temp_dir / "list_users.py"
            init_file = temp_dir / "__init__.py"

            assert create_user_file.exists()
            assert list_users_file.exists()
            assert init_file.exists()

    def test_command_file_content(self, temp_dir, mock_manifest):
        """Test content of generated command files"""
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_manifest

            mock_context = MagicMock()
            mock_context.__enter__.return_value.get.return_value = mock_response
            mock_client.return_value = mock_context

            generator = RemoteImportsGenerator(
                manifest_url="https://api.example.com/manifest"
            )

            files = generator.generate(temp_dir)

            create_user_file = temp_dir / "create_user.py"
            content = create_user_file.read_text()

            # Check class definition
            assert "class CreateUser(RemoteCommand[CreateUserInputs, CreateUserResult]):" in content

            # Check inputs model
            assert "class CreateUserInputs(BaseModel):" in content
            assert "email: str" in content
            assert "name: str" in content
            assert "age: Optional[int] = 18" in content

            # Check result model
            assert "class CreateUserResult(BaseModel):" in content
            assert "id: int" in content

            # Check metadata
            assert '_command_name = "Users::CreateUser"' in content
            assert '_domain = "Users"' in content

    def test_filter_specific_commands(self, temp_dir, mock_manifest):
        """Test generating only specific commands"""
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_manifest

            mock_context = MagicMock()
            mock_context.__enter__.return_value.get.return_value = mock_response
            mock_client.return_value = mock_context

            generator = RemoteImportsGenerator(
                manifest_url="https://api.example.com/manifest",
                commands=["Users::CreateUser"]  # Only import this one
            )

            files = generator.generate(temp_dir)

            # Should generate 1 command file + 1 __init__.py
            assert len(files) == 2

            assert (temp_dir / "create_user.py").exists()
            assert not (temp_dir / "list_users.py").exists()

    def test_convenience_function(self, temp_dir, mock_manifest):
        """Test the generate_remote_imports convenience function"""
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_manifest

            mock_context = MagicMock()
            mock_context.__enter__.return_value.get.return_value = mock_response
            mock_client.return_value = mock_context

            files = generate_remote_imports(
                manifest_url="https://api.example.com/manifest",
                output_dir=temp_dir,
                commands=["Users::CreateUser"]
            )

            assert len(files) == 2
            assert (temp_dir / "create_user.py").exists()

    def test_init_file_exports(self, temp_dir, mock_manifest):
        """Test __init__.py exports all commands"""
        with patch('httpx.Client') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_manifest

            mock_context = MagicMock()
            mock_context.__enter__.return_value.get.return_value = mock_response
            mock_client.return_value = mock_context

            generator = RemoteImportsGenerator(
                manifest_url="https://api.example.com/manifest"
            )

            files = generator.generate(temp_dir)

            init_file = temp_dir / "__init__.py"
            content = init_file.read_text()

            assert "from .create_user import CreateUser, create_user" in content
            assert "from .list_users import ListUsers, list_users" in content
            assert '"CreateUser"' in content
            assert '"create_user"' in content
