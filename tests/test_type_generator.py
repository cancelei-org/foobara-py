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
