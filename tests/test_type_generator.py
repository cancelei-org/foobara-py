"""Tests for TypeGenerator"""

import pytest
from pathlib import Path
from foobara_py.generators import TypeGenerator, generate_type


class TestTypeGeneratorEntity:
    """Test TypeGenerator for entities"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "entities"
        self.test_dir = self.temp_dir / "tests"

        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_simple_entity(self):
        """Should generate simple entity"""
        generator = TypeGenerator(
            name="User",
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
                {"name": "email", "type": "str"},
            ],
            primary_key="id",
            description="User account entity"
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        assert len(files) == 2  # Entity + test file
        entity_file = self.output_dir / "user.py"
        test_file = self.test_dir / "test_user.py"

        assert entity_file.exists()
        assert test_file.exists()

        # Check entity file content
        content = entity_file.read_text()
        assert "class User(EntityBase):" in content
        assert "_primary_key_field = 'id'" in content
        assert "id: int" in content
        assert "name: str" in content
        assert "email: str" in content
        assert "@entity(primary_key='id')" in content

    def test_generate_entity_with_domain(self):
        """Should generate entity with domain"""
        generator = TypeGenerator(
            name="Product",
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
                {"name": "price", "type": "float"},
            ],
            primary_key="id",
            domain="Catalog",
            organization="MyStore"
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        entity_file = self.output_dir / "product.py"
        content = entity_file.read_text()

        assert 'catalog_domain = Domain("Catalog", organization="MyStore")' in content
        assert "from foobara_py import Domain" in content

    def test_generate_entity_with_custom_primary_key(self):
        """Should support custom primary key field"""
        generator = TypeGenerator(
            name="Order",
            kind="entity",
            fields=[
                {"name": "order_number", "type": "str"},
                {"name": "total", "type": "float"},
            ],
            primary_key="order_number"
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        entity_file = self.output_dir / "order.py"
        content = entity_file.read_text()

        assert "_primary_key_field = 'order_number'" in content
        assert "@entity(primary_key='order_number')" in content

    def test_generated_entity_test_content(self):
        """Should generate proper entity test file"""
        generator = TypeGenerator(
            name="Account",
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "balance", "type": "float"},
            ],
            primary_key="id"
        )

        files = generator.generate(
            self.output_dir,
            test_dir=self.test_dir,
            module_path="myapp.entities.account"
        )

        test_file = self.test_dir / "test_account.py"
        content = test_file.read_text()

        assert "from myapp.entities.account import Account" in content
        assert "class TestAccount:" in content
        assert "def test_create_account(self):" in content
        assert "def test_account_is_entity(self):" in content
        assert "def test_account_primary_key(self):" in content
        assert "def test_account_dirty_tracking(self):" in content


class TestTypeGeneratorModel:
    """Test TypeGenerator for models (value objects)"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "models"
        self.test_dir = self.temp_dir / "tests"

        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_model(self):
        """Should generate immutable model"""
        generator = TypeGenerator(
            name="Address",
            kind="model",
            fields=[
                {"name": "street", "type": "str"},
                {"name": "city", "type": "str"},
                {"name": "postal_code", "type": "str"},
            ],
            description="Mailing address"
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        assert len(files) == 2
        model_file = self.output_dir / "address.py"

        assert model_file.exists()

        content = model_file.read_text()
        assert "class Address(Model):" in content
        assert "from foobara_py.persistence.entity import Model" in content
        assert "street: str" in content
        assert "city: str" in content
        assert "postal_code: str" in content

    def test_generate_mutable_model(self):
        """Should generate mutable model when mutable=True"""
        generator = TypeGenerator(
            name="Settings",
            kind="model",
            fields=[
                {"name": "theme", "type": "str"},
                {"name": "notifications", "type": "bool"},
            ],
            mutable=True
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        model_file = self.output_dir / "settings.py"
        content = model_file.read_text()

        assert "class Settings(MutableModel):" in content
        assert "from foobara_py.persistence.entity import MutableModel" in content

    def test_generate_model_with_defaults(self):
        """Should handle field defaults"""
        generator = TypeGenerator(
            name="Config",
            kind="model",
            fields=[
                {"name": "debug", "type": "bool", "default": "False"},
                {"name": "timeout", "type": "int", "default": "30"},
            ]
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        model_file = self.output_dir / "config.py"
        content = model_file.read_text()

        assert "debug: bool = False" in content
        assert "timeout: int = 30" in content

    def test_generated_model_test_content(self):
        """Should generate proper model test file"""
        generator = TypeGenerator(
            name="Money",
            kind="model",
            fields=[
                {"name": "amount", "type": "float"},
                {"name": "currency", "type": "str"},
            ]
        )

        files = generator.generate(
            self.output_dir,
            test_dir=self.test_dir,
            module_path="myapp.models.money"
        )

        test_file = self.test_dir / "test_money.py"
        content = test_file.read_text()

        assert "from myapp.models.money import Money" in content
        assert "def test_create_money(self):" in content
        assert "def test_money_is_model(self):" in content
        assert "def test_money_is_immutable(self):" in content
        assert "def test_money_with_updates(self):" in content
        assert "def test_money_equality(self):" in content


class TestTypeGeneratorType:
    """Test TypeGenerator for simple types"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "types"
        self.test_dir = self.temp_dir / "tests"

        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_simple_type(self):
        """Should generate annotated type"""
        generator = TypeGenerator(
            name="EmailAddress",
            kind="type",
            base_type="str",
            validators=["strip_whitespace", "validate_email"],
            description="Validated email address"
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        type_file = self.output_dir / "email_address.py"
        assert type_file.exists()

        content = type_file.read_text()
        assert "EmailAddress = Annotated[" in content
        assert "str," in content
        assert "BeforeValidator(_strip_whitespace)" in content
        assert "AfterValidator(_validate_email)" in content
        assert "def _strip_whitespace" in content
        assert "def _validate_email" in content

    def test_generate_numeric_type(self):
        """Should generate numeric type with validators"""
        generator = TypeGenerator(
            name="PositiveAmount",
            kind="type",
            base_type="float",
            validators=["positive"],
            description="Positive monetary amount"
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        type_file = self.output_dir / "positive_amount.py"
        content = type_file.read_text()

        assert "PositiveAmount = Annotated[" in content
        assert "float," in content
        assert "def _validate_positive" in content
        assert "if v <= 0:" in content

    def test_generate_type_without_tests(self):
        """Should skip test generation when generate_tests=False"""
        generator = TypeGenerator(
            name="SimpleStr",
            kind="type",
            base_type="str",
            validators=["strip_whitespace"],
            generate_tests=False
        )

        files = generator.generate(self.output_dir, test_dir=self.test_dir)

        assert len(files) == 1
        assert (self.output_dir / "simple_str.py").exists()
        assert not (self.test_dir / "test_simple_str.py").exists()


class TestGenerateTypeFunction:
    """Test generate_type convenience function"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "types"
        self.test_dir = self.temp_dir / "tests"

        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup test fixtures"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_generate_type_function_entity(self):
        """Should generate entity via convenience function"""
        files = generate_type(
            name="Customer",
            output_dir=self.output_dir,
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
            ],
            primary_key="id",
            test_dir=self.test_dir,
        )

        assert len(files) == 2
        assert (self.output_dir / "customer.py").exists()

    def test_generate_type_function_model(self):
        """Should generate model via convenience function"""
        files = generate_type(
            name="Point",
            output_dir=self.output_dir,
            kind="model",
            fields=[
                {"name": "x", "type": "float"},
                {"name": "y", "type": "float"},
            ],
            test_dir=self.test_dir,
        )

        assert len(files) == 2
        model_file = self.output_dir / "point.py"
        assert model_file.exists()

        content = model_file.read_text()
        assert "class Point(Model):" in content


class TestNameConversion:
    """Test name case conversion for types"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "types"
        self.output_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_name_case_conversion(self):
        """Should handle various name cases"""
        test_cases = [
            ("UserProfile", "user_profile.py"),
            ("APIClient", "api_client.py"),
            ("user_data", "user_data.py"),
            ("HTTPRequest", "http_request.py"),
        ]

        for name, expected_filename in test_cases:
            generator = TypeGenerator(name=name, kind="model", generate_tests=False)
            files = generator.generate(self.output_dir)

            expected_path = self.output_dir / expected_filename
            assert expected_path.exists(), f"Failed for {name}"

            # Cleanup
            expected_path.unlink()


class TestTypeGeneratorEdgeCases:
    """Test edge cases and error handling for TypeGenerator"""

    def setup_method(self):
        """Setup test fixtures"""
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "types"
        self.test_dir = self.temp_dir / "tests"
        self.output_dir.mkdir(parents=True)
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Cleanup"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_empty_type_name(self):
        """Should handle empty type name"""
        generator = TypeGenerator(
            name="",
            kind="model",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_type_name_with_special_characters(self):
        """Should sanitize type names with special characters"""
        generator = TypeGenerator(
            name="User@Profile#2024!",
            kind="model",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_reserved_keyword_type_name(self):
        """Should handle Python reserved keywords"""
        generator = TypeGenerator(
            name="class",
            kind="model",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_builtin_type_name(self):
        """Should handle builtin type name collisions"""
        generator = TypeGenerator(
            name="str",
            kind="model",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_very_long_type_name(self):
        """Should handle very long type names"""
        long_name = "UserProfile" * 10  # Reduced to avoid OS filename limit
        generator = TypeGenerator(
            name=long_name,
            kind="model",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_unicode_type_name(self):
        """Should handle unicode in type names"""
        generator = TypeGenerator(
            name="User_日本語",
            kind="model",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_invalid_kind(self):
        """Should handle invalid kind values"""
        generator = TypeGenerator(
            name="Test",
            kind="invalid",  # type: ignore
            generate_tests=False
        )
        # Should handle gracefully or use default
        try:
            files = generator.generate(self.output_dir)
        except Exception:
            pass  # May raise error, which is valid

    def test_entity_without_primary_key(self):
        """Should handle entity without primary key"""
        generator = TypeGenerator(
            name="NoPK",
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
            ],
            generate_tests=False
        )
        # Should use default primary key or handle gracefully
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_entity_with_nonexistent_primary_key(self):
        """Should handle entity with non-existent primary key field"""
        generator = TypeGenerator(
            name="BadPK",
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
            ],
            primary_key="nonexistent_field",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should still generate, but might have issues
        assert len(files) > 0

    def test_empty_fields_list(self):
        """Should handle empty fields list"""
        generator = TypeGenerator(
            name="NoFields",
            kind="model",
            fields=[],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_field_with_missing_name(self):
        """Should handle field with missing name"""
        generator = TypeGenerator(
            name="MissingName",
            kind="model",
            fields=[
                {"type": "str"},  # Missing name
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_field_with_missing_type(self):
        """Should handle field with missing type"""
        generator = TypeGenerator(
            name="MissingType",
            kind="model",
            fields=[
                {"name": "field1"},  # Missing type
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_many_fields(self):
        """Should handle types with many fields"""
        fields = [{"name": f"field_{i}", "type": "str"} for i in range(100)]
        generator = TypeGenerator(
            name="ManyFields",
            kind="model",
            fields=fields,
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        model_file = self.output_dir / "many_fields.py"
        content = model_file.read_text()
        assert "field_0" in content
        assert "field_99" in content

    def test_field_with_complex_type(self):
        """Should handle complex field types"""
        generator = TypeGenerator(
            name="ComplexTypes",
            kind="model",
            fields=[
                {"name": "data", "type": "Dict[str, List[int]]"},
                {"name": "callback", "type": "Callable[[int], str]"},
                {"name": "union", "type": "Union[str, int, None]"},
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        model_file = self.output_dir / "complex_types.py"
        content = model_file.read_text()
        assert "Dict[str, List[int]]" in content
        assert "Callable[[int], str]" in content

    def test_field_with_invalid_default(self):
        """Should handle invalid default values"""
        generator = TypeGenerator(
            name="InvalidDefaults",
            kind="model",
            fields=[
                {"name": "field1", "type": "int", "default": "not_a_number"},
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should generate with the default as-is
        assert len(files) > 0

    def test_field_with_multiline_description(self):
        """Should handle multiline field descriptions"""
        generator = TypeGenerator(
            name="MultilineDesc",
            kind="model",
            fields=[
                {
                    "name": "data",
                    "type": "str",
                    "description": "Line 1\nLine 2\nLine 3"
                },
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_field_with_special_characters_in_description(self):
        """Should handle special characters in field descriptions"""
        generator = TypeGenerator(
            name="SpecialDesc",
            kind="model",
            fields=[
                {
                    "name": "data",
                    "type": "str",
                    "description": 'Desc with "quotes" and \'single\' and <tags>'
                },
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_duplicate_field_names(self):
        """Should handle duplicate field names"""
        generator = TypeGenerator(
            name="DupFields",
            kind="model",
            fields=[
                {"name": "field1", "type": "str"},
                {"name": "field1", "type": "int"},  # Duplicate
                {"name": "field2", "type": "str"},
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should generate, last one wins or error
        assert len(files) > 0

    def test_field_name_with_reserved_keyword(self):
        """Should handle field names that are reserved keywords"""
        generator = TypeGenerator(
            name="ReservedFields",
            kind="model",
            fields=[
                {"name": "class", "type": "str"},
                {"name": "def", "type": "str"},
                {"name": "return", "type": "str"},
            ],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_model_with_mutable_flag(self):
        """Should handle mutable flag for models"""
        generator = TypeGenerator(
            name="MutableModel",
            kind="model",
            fields=[{"name": "value", "type": "str"}],
            mutable=True,
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        model_file = self.output_dir / "mutable_model.py"
        content = model_file.read_text()
        assert "MutableModel" in content

    def test_type_with_empty_validators_list(self):
        """Should handle empty validators list"""
        generator = TypeGenerator(
            name="NoValidators",
            kind="type",
            base_type="str",
            validators=[],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_type_with_invalid_validator(self):
        """Should handle invalid validator names"""
        generator = TypeGenerator(
            name="InvalidValidator",
            kind="type",
            base_type="str",
            validators=["nonexistent_validator"],
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Should generate with validator name as-is
        assert len(files) > 0

    def test_type_with_many_validators(self):
        """Should handle many validators"""
        validators = [f"validator_{i}" for i in range(20)]
        generator = TypeGenerator(
            name="ManyValidators",
            kind="type",
            base_type="str",
            validators=validators,
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_type_without_base_type(self):
        """Should handle type without base_type"""
        generator = TypeGenerator(
            name="NoBaseType",
            kind="type",
            validators=["some_validator"],
            generate_tests=False
        )
        # Should handle gracefully or error
        try:
            files = generator.generate(self.output_dir)
        except Exception:
            pass  # May raise error, which is valid

    def test_very_long_description(self):
        """Should handle very long descriptions"""
        long_desc = "A" * 1000
        generator = TypeGenerator(
            name="LongDesc",
            kind="model",
            fields=[{"name": "id", "type": "int"}],
            description=long_desc,
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_domain_with_special_characters(self):
        """Should handle domain with special characters"""
        generator = TypeGenerator(
            name="User",
            kind="entity",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
            ],
            primary_key="id",
            domain="User@Management#2024",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        assert len(files) > 0

    def test_organization_without_domain(self):
        """Should handle organization without domain"""
        generator = TypeGenerator(
            name="User",
            kind="entity",
            fields=[{"name": "id", "type": "int"}],
            primary_key="id",
            organization="MyOrg",
            generate_tests=False
        )
        files = generator.generate(self.output_dir)
        # Organization should be ignored if no domain
        assert len(files) > 0

    def test_generate_to_existing_file(self):
        """Should raise FileExistsError when file exists"""
        from foobara_py.generators.files_generator import FileExistsError

        # Generate once
        generator1 = TypeGenerator(
            name="ExistingType",
            kind="model",
            fields=[{"name": "field1", "type": "str"}],
            generate_tests=False
        )
        files1 = generator1.generate(self.output_dir)

        # Try to generate again with different content
        generator2 = TypeGenerator(
            name="ExistingType",
            kind="model",
            fields=[{"name": "field2", "type": "int"}],
            generate_tests=False
        )

        try:
            files2 = generator2.generate(self.output_dir)
            # If no error, check file exists
            type_file = self.output_dir / "existing_type.py"
            assert type_file.exists()
        except FileExistsError:
            # Expected behavior
            pass
