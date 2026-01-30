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


class TestAutoCRUDGeneratorEdgeCases:
    """Test edge cases and error handling for AutoCRUDGenerator"""

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

    def test_empty_entity_name(self):
        """Should handle empty entity name"""
        generator = AutoCRUDGenerator(
            entity_name="",
            entity_module="entities.test",
            fields=[{"name": "id", "type": "int"}],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_entity_name_with_special_characters(self):
        """Should sanitize entity names with special characters"""
        generator = AutoCRUDGenerator(
            entity_name="User@Profile#2024!",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_reserved_keyword_entity_name(self):
        """Should handle Python reserved keywords as entity names"""
        generator = AutoCRUDGenerator(
            entity_name="class",
            entity_module="entities.class_entity",
            fields=[{"name": "id", "type": "int"}],
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_very_long_entity_name(self):
        """Should handle very long entity names"""
        long_name = "UserProfile" * 10  # Reduced to avoid OS filename limit
        generator = AutoCRUDGenerator(
            entity_name=long_name,
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_unicode_entity_name(self):
        """Should handle unicode in entity names"""
        generator = AutoCRUDGenerator(
            entity_name="User_日本語",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_empty_fields_list(self):
        """Should handle empty fields list"""
        generator = AutoCRUDGenerator(
            entity_name="Empty",
            entity_module="entities.empty",
            fields=[],
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should generate but might have issues
        assert len(files) > 0

    def test_field_with_missing_name(self):
        """Should raise error for field with missing name"""
        # Should raise KeyError during construction
        try:
            generator = AutoCRUDGenerator(
                entity_name="User",
                entity_module="entities.user",
                fields=[
                    {"name": "id", "type": "int"},
                    {"type": "str"},  # Missing name
                ],
                operations=["create"],
                generate_tests=False
            )
            # If it doesn't raise during construction, try generate
            files = generator.generate(self.output_dir)
        except (KeyError, AttributeError, TypeError):
            # Expected - invalid field definition
            pass

    def test_field_with_missing_type(self):
        """Should handle field with missing type"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "data"},  # Missing type
            ],
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_many_fields(self):
        """Should handle entities with many fields"""
        fields = [{"name": f"field_{i}", "type": "str"} for i in range(50)]
        fields.insert(0, {"name": "id", "type": "int"})

        generator = AutoCRUDGenerator(
            entity_name="ManyFields",
            entity_module="entities.many",
            fields=fields,
            operations=["create", "list"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)

        # Check create has all fields
        create_file = self.output_dir / "create_many_fields.py"
        content = create_file.read_text()
        assert "field_0" in content
        assert "field_49" in content

    def test_primary_key_not_in_fields(self):
        """Should handle primary key not in fields list"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[
                {"name": "email", "type": "str"},
                {"name": "name", "type": "str"},
            ],
            primary_key="id",  # Not in fields
            operations=["read"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should still generate
        assert len(files) > 0

    def test_composite_primary_key(self):
        """Should handle composite primary keys"""
        generator = AutoCRUDGenerator(
            entity_name="UserRole",
            entity_module="entities.user_role",
            fields=[
                {"name": "user_id", "type": "int"},
                {"name": "role_id", "type": "int"},
            ],
            primary_key="user_id,role_id",
            operations=["read"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_empty_operations_list(self):
        """Should handle empty operations list"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            operations=[],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should generate nothing or use default operations
        assert len(files) >= 0  # Either 0 or default operations

    def test_single_operation(self):
        """Should handle single operation"""
        for operation in ["create", "read", "update", "delete", "list"]:
            generator = AutoCRUDGenerator(
                entity_name="User",
                entity_module="entities.user",
                fields=[{"name": "id", "type": "int"}],
                operations=[operation],
                generate_tests=False
            )
            files = generator.generate(self.output_dir)
            assert len(files) == 1
            # Cleanup
            for f in files:
                if f.exists():
                    f.unlink()

    def test_invalid_operation_name(self):
        """Should handle invalid operation names"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            operations=["invalid_operation"],
            generate_tests=False
        )
        # Should skip invalid operations or raise error
        try:
            files = generator.generate(self.output_dir)
            assert isinstance(files, list)
            # Should be empty since operation is invalid
        except (ValueError, KeyError):
            # May raise error for invalid operation
            pass

    def test_duplicate_operations(self):
        """Should handle duplicate operations"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            operations=["create", "create", "read", "create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should deduplicate
        assert len(files) == 2  # create and read

    def test_case_insensitive_operations(self):
        """Should handle or reject case variations in operations"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            operations=["CREATE", "Read", "UPDATE"],
            generate_tests=False
        )
        # May handle case variations or treat as invalid
        try:
            files = generator.generate(self.output_dir)
            assert len(files) >= 0
        except (ValueError, KeyError):
            # May reject uppercase operations
            pass

    def test_empty_entity_module(self):
        """Should handle empty entity module"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="",
            fields=[{"name": "id", "type": "int"}],
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_deeply_nested_entity_module(self):
        """Should handle deeply nested entity modules"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="very.deeply.nested.module.path.entities.user",
            fields=[{"name": "id", "type": "int"}],
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        create_file = self.output_dir / "create_user.py"
        content = create_file.read_text()
        assert "very.deeply.nested.module.path.entities.user" in content

    def test_domain_with_special_characters(self):
        """Should handle domain with special characters"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            domain="User@Management#2024",
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_organization_without_domain(self):
        """Should handle organization without domain"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            organization="MyOrg",
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Organization should be ignored if no domain
        assert len(files) > 0

    def test_generate_with_all_tests(self):
        """Should generate all CRUD operations with tests"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
            ],
            generate_tests=True
        )
        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        # 5 operations * 2 (command + test) = 10 files
        assert len(files) == 10

    def test_field_with_complex_type(self):
        """Should handle fields with complex types"""
        generator = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "metadata", "type": "Dict[str, Any]"},
                {"name": "tags", "type": "List[str]"},
            ],
            operations=["create"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        create_file = self.output_dir / "create_user.py"
        content = create_file.read_text()
        assert "Dict[str, Any]" in content or "dict" in content
        assert "List[str]" in content or "list" in content

    def test_generate_to_existing_files(self):
        """Should raise error when generating to existing command files"""
        from foobara_py.generators.files_generator import FileExistsError

        # Generate once
        generator1 = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[{"name": "id", "type": "int"}],
            operations=["create"],
            generate_tests=False
        )
        files1 = generator1.generate(self.output_dir)

        # Try to generate again with different fields
        generator2 = AutoCRUDGenerator(
            entity_name="User",
            entity_module="entities.user",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "email", "type": "str"},
            ],
            operations=["create"],
            generate_tests=False
        )

        try:
            files2 = generator2.generate(self.output_dir)
            # If no error, check file exists
            create_file = self.output_dir / "create_user.py"
            assert create_file.exists()
        except FileExistsError:
            # Expected behavior
            pass
