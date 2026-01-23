"""Tests for AutoCRUDGenerator"""

import pytest
from pathlib import Path
from foobara_py.generators import AutoCRUDGenerator, generate_crud


class TestAutoCRUDGenerator:
    """Test AutoCRUDGenerator functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "commands"
        self.test_dir = self.temp_dir / "tests"

        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

        # Sample entity fields
        self.user_fields = [
            {"name": "id", "type": "int"},
            {"name": "email", "type": "str"},
            {"name": "name", "type": "str"},
            {"name": "age", "type": "int"},
        ]

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_all_crud_operations(self):
        """Should generate all CRUD operations by default"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            primary_key="id",
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        # Should create 5 files (create, read, update, delete, list)
        assert len(files) == 5

        assert (self.output_dir / "create_user.py").exists()
        assert (self.output_dir / "get_user.py").exists()
        assert (self.output_dir / "update_user.py").exists()
        assert (self.output_dir / "delete_user.py").exists()
        assert (self.output_dir / "list_users.py").exists()

    def test_generate_create_command(self):
        """Should generate proper Create command"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["create"],
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        create_file = self.output_dir / "create_user.py"
        content = create_file.read_text()

        assert "class CreateUserInputs(BaseModel):" in content
        assert "class CreateUser(Command[CreateUserInputs, User]):" in content
        assert "email: str" in content
        assert "name: str" in content
        assert "age: int" in content
        # Primary key should NOT be in inputs
        assert "id: int" not in content.split("CreateUserInputs")[1].split("class CreateUser")[0]
        assert "entity.save()" in content

    def test_generate_read_command(self):
        """Should generate proper Read (Get) command"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["read"],
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        read_file = self.output_dir / "get_user.py"
        content = read_file.read_text()

        assert "class GetUserInputs(BaseModel):" in content
        assert "class GetUser(Command[GetUserInputs, Optional[User]]):" in content
        assert "id: int" in content
        assert "User.find(self.inputs.id)" in content

    def test_generate_update_command(self):
        """Should generate proper Update command"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["update"],
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        update_file = self.output_dir / "update_user.py"
        content = update_file.read_text()

        assert "class UpdateUserInputs(BaseModel):" in content
        assert "class UpdateUser(Command[UpdateUserInputs, User]):" in content
        # Primary key is required
        assert "id: int" in content
        # Other fields are optional
        assert "email: Optional[str] = None" in content
        assert "name: Optional[str] = None" in content
        assert "NotFoundError" in content

    def test_generate_delete_command(self):
        """Should generate proper Delete command"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["delete"],
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        delete_file = self.output_dir / "delete_user.py"
        content = delete_file.read_text()

        assert "class DeleteUserInputs(BaseModel):" in content
        assert "class DeleteUser(Command[DeleteUserInputs, bool]):" in content
        assert "entity.delete()" in content
        assert "return True" in content
        assert "NotFoundError" in content

    def test_generate_list_command(self):
        """Should generate proper List command"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["list"],
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        list_file = self.output_dir / "list_users.py"
        content = list_file.read_text()

        assert "class ListUsersInputs(BaseModel):" in content
        assert "class ListUsers(Command[ListUsersInputs, List[User]]):" in content
        # Should have optional filters
        assert "email: Optional[str] = None" in content
        assert "name: Optional[str] = None" in content
        # Should have pagination
        assert "limit: Optional[int] = None" in content
        assert "offset: Optional[int] = None" in content
        assert "User.find_all()" in content
        assert "User.find_by(**filters)" in content

    def test_generate_with_domain(self):
        """Should include domain registration"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["create"],
            domain="Users",
            organization="MyApp",
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        create_file = self.output_dir / "create_user.py"
        content = create_file.read_text()

        assert 'users_domain = Domain("Users", organization="MyApp")' in content
        assert "@users_domain.command" in content

    def test_generate_subset_of_operations(self):
        """Should generate only specified operations"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["create", "read"],
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        assert len(files) == 2
        assert (self.output_dir / "create_user.py").exists()
        assert (self.output_dir / "get_user.py").exists()
        assert not (self.output_dir / "update_user.py").exists()
        assert not (self.output_dir / "delete_user.py").exists()
        assert not (self.output_dir / "list_users.py").exists()

    def test_generate_with_tests(self):
        """Should generate test files when generate_tests=True"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["create", "read"],
            generate_tests=True
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        # 2 commands + 2 tests = 4 files
        assert len(files) == 4
        assert (self.test_dir / "test_create_user.py").exists()
        assert (self.test_dir / "test_get_user.py").exists()

    def test_generate_test_content(self):
        """Should generate proper test file content"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="myapp.entities.user",
            fields=self.user_fields,
            operations=["create"],
            generate_tests=True
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        test_file = self.test_dir / "test_create_user.py"
        content = test_file.read_text()

        assert "class TestCreateUser:" in content
        assert "def test_creates_user(self):" in content
        assert "def test_validates_required_fields(self):" in content

    def test_custom_primary_key(self):
        """Should support custom primary key field"""
        fields = [
            {"name": "order_number", "type": "str"},
            {"name": "total", "type": "float"},
        ]

        generator = AutoCRUDGenerator(
            entity_name="Order",
            entity_module="myapp.entities.order",
            fields=fields,
            primary_key="order_number",
            operations=["read"],
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        read_file = self.output_dir / "get_order.py"
        content = read_file.read_text()

        assert "order_number: str" in content
        assert "Order.find(self.inputs.order_number)" in content


class TestGenerateCrudFunction:
    """Test generate_crud convenience function"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "commands"
        self.test_dir = self.temp_dir / "tests"

        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_crud_function(self):
        """Should generate CRUD commands via convenience function"""
        files = generate_crud(
            entity_name="Product",
            entity_module="myapp.entities.product",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
                {"name": "price", "type": "float"},
            ],
            output_dir=self.output_dir,
            primary_key="id",
            operations=["create", "read", "delete"],
            domain="Products",
            generate_tests=False
        )

        assert len(files) == 3
        assert (self.output_dir / "create_product.py").exists()
        assert (self.output_dir / "get_product.py").exists()
        assert (self.output_dir / "delete_product.py").exists()


class TestCRUDNaming:
    """Test CRUD command naming conventions"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "commands"
        self.output_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_naming_conventions(self):
        """Should follow naming conventions for CRUD commands"""
        generator = AutoCRUDGenerator(
            entity_name="UserProfile",
            entity_module="myapp.entities.user_profile",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "bio", "type": "str"},
            ],
            generate_tests=False
        )

        files = generator.generate(self.output_dir)

        # Check file naming
        assert (self.output_dir / "create_user_profile.py").exists()
        assert (self.output_dir / "get_user_profile.py").exists()
        assert (self.output_dir / "update_user_profile.py").exists()
        assert (self.output_dir / "delete_user_profile.py").exists()
        assert (self.output_dir / "list_user_profiles.py").exists()

        # Check class naming in files
        create_content = (self.output_dir / "create_user_profile.py").read_text()
        assert "class CreateUserProfile" in create_content

        list_content = (self.output_dir / "list_user_profiles.py").read_text()
        assert "class ListUserProfiles" in list_content
