"""Tests for Ruby-compatible type declaration system"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from foobara_py.types import (
    # Core classes
    FoobaraType,
    TypeRegistry,
    Caster,
    Validator,
    Transformer,
    # Built-in casters
    StringCaster,
    IntegerCaster,
    FloatCaster,
    BooleanCaster,
    DateCaster,
    DateTimeCaster,
    UUIDCaster,
    ListCaster,
    # Built-in validators
    MinLengthValidator,
    MaxLengthValidator,
    MinValueValidator,
    MaxValueValidator,
    PatternValidator,
    OneOfValidator,
    EmailValidator,
    URLValidator,
    # Built-in transformers
    StripWhitespaceTransformer,
    LowercaseTransformer,
    UppercaseTransformer,
    RoundTransformer,
    # Built-in types
    StringType,
    IntegerType,
    FloatType,
    BooleanType,
    DateType,
    DateTimeType,
    UUIDType,
    EmailType,
    URLType,
    PositiveIntegerType,
    NonNegativeIntegerType,
    PercentageType,
    ArrayType,
    # DSL
    type_declaration,
    define_type,
)


class TestCasters:
    """Test built-in casters"""

    def test_string_caster(self):
        caster = StringCaster()
        assert caster.process(123) == "123"
        assert caster.process(45.67) == "45.67"
        assert caster.process(True) == "True"

    def test_string_caster_none_raises(self):
        caster = StringCaster()
        with pytest.raises(TypeError):
            caster.process(None)

    def test_integer_caster(self):
        caster = IntegerCaster()
        assert caster.process("42") == 42
        assert caster.process(42.9) == 42
        assert caster.process("  123  ") == 123
        assert caster.process(True) == 1
        assert caster.process(False) == 0

    def test_integer_caster_invalid(self):
        caster = IntegerCaster()
        with pytest.raises(ValueError):
            caster.process("")
        with pytest.raises(ValueError):
            caster.process("not a number")

    def test_float_caster(self):
        caster = FloatCaster()
        assert caster.process("3.14") == 3.14
        assert caster.process(42) == 42.0
        assert caster.process(Decimal("1.5")) == 1.5

    def test_boolean_caster(self):
        caster = BooleanCaster()
        assert caster.process("true") is True
        assert caster.process("yes") is True
        assert caster.process("1") is True
        assert caster.process("false") is False
        assert caster.process("no") is False
        assert caster.process("0") is False
        assert caster.process(1) is True
        assert caster.process(0) is False

    def test_boolean_caster_invalid(self):
        caster = BooleanCaster()
        with pytest.raises(ValueError):
            caster.process("maybe")

    def test_date_caster(self):
        caster = DateCaster()
        assert caster.process("2024-01-15") == date(2024, 1, 15)
        assert caster.process(datetime(2024, 1, 15, 10, 30)) == date(2024, 1, 15)

    def test_datetime_caster(self):
        caster = DateTimeCaster()
        assert caster.process("2024-01-15T10:30:00") == datetime(2024, 1, 15, 10, 30, 0)
        assert caster.process(date(2024, 1, 15)) == datetime(2024, 1, 15, 0, 0, 0)

    def test_uuid_caster(self):
        caster = UUIDCaster()
        uuid_str = "12345678-1234-5678-1234-567812345678"
        result = caster.process(uuid_str)
        assert isinstance(result, UUID)
        assert str(result) == uuid_str

    def test_list_caster(self):
        caster = ListCaster()
        assert caster.process([1, 2, 3]) == [1, 2, 3]
        assert caster.process((1, 2, 3)) == [1, 2, 3]
        assert caster.process("a,b,c") == ["a", "b", "c"]

    def test_list_caster_with_element_caster(self):
        caster = ListCaster(element_caster=IntegerCaster())
        assert caster.process(["1", "2", "3"]) == [1, 2, 3]


class TestValidators:
    """Test built-in validators"""

    def test_min_length_validator(self):
        validator = MinLengthValidator(3)
        assert validator.process("hello") == "hello"
        with pytest.raises(ValueError):
            validator.process("ab")

    def test_max_length_validator(self):
        validator = MaxLengthValidator(5)
        assert validator.process("hi") == "hi"
        with pytest.raises(ValueError):
            validator.process("hello world")

    def test_min_value_validator(self):
        validator = MinValueValidator(10)
        assert validator.process(15) == 15
        assert validator.process(10) == 10
        with pytest.raises(ValueError):
            validator.process(5)

    def test_min_value_validator_exclusive(self):
        validator = MinValueValidator(10, exclusive=True)
        assert validator.process(15) == 15
        with pytest.raises(ValueError):
            validator.process(10)

    def test_max_value_validator(self):
        validator = MaxValueValidator(100)
        assert validator.process(50) == 50
        assert validator.process(100) == 100
        with pytest.raises(ValueError):
            validator.process(150)

    def test_pattern_validator(self):
        validator = PatternValidator(r"^[A-Z]{2}\d{4}$", "Must be format XX1234")
        assert validator.process("AB1234") == "AB1234"
        with pytest.raises(ValueError, match="Must be format XX1234"):
            validator.process("abc123")

    def test_one_of_validator(self):
        validator = OneOfValidator(["red", "green", "blue"])
        assert validator.process("red") == "red"
        with pytest.raises(ValueError):
            validator.process("yellow")

    def test_email_validator(self):
        validator = EmailValidator()
        assert validator.process("john@example.com") == "john@example.com"
        with pytest.raises(ValueError):
            validator.process("not-an-email")

    def test_url_validator(self):
        validator = URLValidator()
        assert validator.process("https://example.com") == "https://example.com"
        with pytest.raises(ValueError):
            validator.process("not-a-url")


class TestTransformers:
    """Test built-in transformers"""

    def test_strip_whitespace(self):
        transformer = StripWhitespaceTransformer()
        assert transformer.process("  hello  ") == "hello"

    def test_lowercase(self):
        transformer = LowercaseTransformer()
        assert transformer.process("HELLO") == "hello"

    def test_uppercase(self):
        transformer = UppercaseTransformer()
        assert transformer.process("hello") == "HELLO"

    def test_round(self):
        transformer = RoundTransformer(2)
        assert transformer.process(3.14159) == 3.14


class TestFoobaraType:
    """Test FoobaraType class"""

    def test_simple_type_processing(self):
        string_type = FoobaraType(
            name="trimmed_string",
            python_type=str,
            casters=[StringCaster()],
            transformers=[StripWhitespaceTransformer()]
        )
        assert string_type.process("  hello  ") == "hello"

    def test_type_with_validation(self):
        positive_int = FoobaraType(
            name="positive_int",
            python_type=int,
            casters=[IntegerCaster()],
            validators=[MinValueValidator(1)]
        )
        assert positive_int.process("42") == 42
        with pytest.raises(ValueError):
            positive_int.process("0")

    def test_email_type_full_pipeline(self):
        email_type = FoobaraType(
            name="email",
            python_type=str,
            casters=[StringCaster()],
            validators=[EmailValidator()],
            transformers=[StripWhitespaceTransformer(), LowercaseTransformer()]
        )
        assert email_type.process("  John@Example.COM  ") == "john@example.com"

    def test_nullable_type(self):
        nullable_string = FoobaraType(
            name="nullable_string",
            python_type=str,
            nullable=True
        )
        assert nullable_string.process(None) is None

    def test_default_value(self):
        string_with_default = FoobaraType(
            name="string_with_default",
            python_type=str,
            default="default_value",
            has_default=True
        )
        assert string_with_default.process(None) == "default_value"

    def test_validate_method(self):
        positive_int = FoobaraType(
            name="positive_int",
            python_type=int,
            casters=[IntegerCaster()],
            validators=[MinValueValidator(1)]
        )
        valid, error = positive_int.validate(42)
        assert valid is True
        assert error is None

        valid, error = positive_int.validate(0)
        assert valid is False
        assert error is not None

    def test_is_valid_method(self):
        positive_int = FoobaraType(
            name="positive_int",
            python_type=int,
            casters=[IntegerCaster()],
            validators=[MinValueValidator(1)]
        )
        assert positive_int.is_valid(42) is True
        assert positive_int.is_valid(0) is False

    def test_with_validators(self):
        base_int = FoobaraType(
            name="int",
            python_type=int,
            casters=[IntegerCaster()]
        )
        bounded_int = base_int.with_validators(MinValueValidator(0), MaxValueValidator(100))

        assert bounded_int.process(50) == 50
        with pytest.raises(ValueError):
            bounded_int.process(-1)
        with pytest.raises(ValueError):
            bounded_int.process(101)

    def test_with_transformers(self):
        base_string = FoobaraType(
            name="string",
            python_type=str,
            casters=[StringCaster()]
        )
        normalized = base_string.with_transformers(
            StripWhitespaceTransformer(),
            LowercaseTransformer()
        )
        assert normalized.process("  HELLO  ") == "hello"

    def test_optional(self):
        string_type = FoobaraType(
            name="string",
            python_type=str,
            casters=[StringCaster()]
        )
        optional_string = string_type.optional("default")

        assert optional_string.process(None) == "default"
        assert optional_string.process("hello") == "hello"

    def test_array_type(self):
        int_type = FoobaraType(
            name="int",
            python_type=int,
            casters=[IntegerCaster()]
        )
        int_array = int_type.array()

        assert int_array.process(["1", "2", "3"]) == [1, 2, 3]

    def test_callable(self):
        string_type = FoobaraType(
            name="string",
            python_type=str,
            casters=[StringCaster()],
            transformers=[StripWhitespaceTransformer()]
        )
        # Can call type like a function
        assert string_type("  hello  ") == "hello"

    def test_to_manifest(self):
        email_type = FoobaraType(
            name="email",
            python_type=str,
            description="Email address",
            nullable=False
        )
        manifest = email_type.to_manifest()

        assert manifest["name"] == "email"
        assert manifest["type"] == "str"
        assert manifest["description"] == "Email address"
        assert manifest["nullable"] is False


class TestTypeRegistry:
    """Test TypeRegistry"""

    def setup_method(self):
        """Store original types before test"""
        self._original_types = TypeRegistry._types.copy()
        self._original_categories = {k: v.copy() for k, v in TypeRegistry._categories.items()}

    def teardown_method(self):
        """Restore original types after test"""
        TypeRegistry._types = self._original_types
        TypeRegistry._categories = self._original_categories

    def test_register_and_get(self):
        test_type = FoobaraType(name="test_type", python_type=str)
        TypeRegistry.register(test_type)

        retrieved = TypeRegistry.get("test_type")
        assert retrieved is test_type

    def test_get_nonexistent(self):
        assert TypeRegistry.get("nonexistent_type") is None

    def test_get_or_raise(self):
        test_type = FoobaraType(name="test_type2", python_type=str)
        TypeRegistry.register(test_type)

        retrieved = TypeRegistry.get_or_raise("test_type2")
        assert retrieved is test_type

        with pytest.raises(KeyError):
            TypeRegistry.get_or_raise("nonexistent")

    def test_register_with_category(self):
        test_type = FoobaraType(name="test_type3", python_type=str)
        TypeRegistry.register(test_type, category="custom")

        types_in_category = TypeRegistry.by_category("custom")
        assert test_type in types_in_category

    def test_list_all(self):
        all_types = TypeRegistry.list_all()
        assert "string" in all_types
        assert "integer" in all_types

    def test_builtin_types_registered(self):
        """Verify built-in types are registered"""
        assert TypeRegistry.get("string") is not None
        assert TypeRegistry.get("integer") is not None
        assert TypeRegistry.get("float") is not None
        assert TypeRegistry.get("boolean") is not None
        assert TypeRegistry.get("date") is not None
        assert TypeRegistry.get("datetime") is not None
        assert TypeRegistry.get("email") is not None
        assert TypeRegistry.get("url") is not None


class TestBuiltinTypes:
    """Test built-in types from TypeRegistry"""

    def test_string_type(self):
        assert StringType.process("  hello  ") == "hello"

    def test_integer_type(self):
        assert IntegerType.process("42") == 42

    def test_float_type(self):
        assert FloatType.process("3.14") == 3.14

    def test_boolean_type(self):
        assert BooleanType.process("yes") is True
        assert BooleanType.process("no") is False

    def test_date_type(self):
        assert DateType.process("2024-01-15") == date(2024, 1, 15)

    def test_datetime_type(self):
        result = DateTimeType.process("2024-01-15T10:30:00")
        assert result == datetime(2024, 1, 15, 10, 30, 0)

    def test_uuid_type(self):
        uuid_str = "12345678-1234-5678-1234-567812345678"
        result = UUIDType.process(uuid_str)
        assert str(result) == uuid_str

    def test_email_type(self):
        assert EmailType.process("  John@Example.COM  ") == "john@example.com"

    def test_url_type(self):
        assert URLType.process("  https://example.com  ") == "https://example.com"

    def test_positive_integer_type(self):
        assert PositiveIntegerType.process("42") == 42
        with pytest.raises(ValueError):
            PositiveIntegerType.process("0")

    def test_non_negative_integer_type(self):
        assert NonNegativeIntegerType.process("0") == 0
        with pytest.raises(ValueError):
            NonNegativeIntegerType.process("-1")

    def test_percentage_type(self):
        assert PercentageType.process("50") == 50.0
        with pytest.raises(ValueError):
            PercentageType.process("-1")
        with pytest.raises(ValueError):
            PercentageType.process("101")

    def test_array_type(self):
        assert ArrayType.process([1, 2, 3]) == [1, 2, 3]
        assert ArrayType.process("a,b,c") == ["a", "b", "c"]


class TestTypeDeclarationDSL:
    """Test type_declaration DSL function"""

    def test_simple_declaration(self):
        phone_type = type_declaration(
            "phone_number_test",
            validate=[PatternValidator(r"^\+?[0-9]{10,15}$")],
            transform=[StripWhitespaceTransformer()],
            register=False  # Don't pollute registry
        )
        assert phone_type.process("  +12345678901  ") == "+12345678901"

    def test_declaration_with_casting(self):
        amount_type = type_declaration(
            "amount_test",
            python_type=float,
            cast=[FloatCaster()],
            validate=[MinValueValidator(0.0)],
            transform=[RoundTransformer(2)],
            register=False
        )
        assert amount_type.process("99.999") == 100.0

    def test_declaration_with_default(self):
        status_type = type_declaration(
            "status_test",
            default="active",
            nullable=True,
            register=False
        )
        assert status_type.process(None) == "active"

    def test_define_type_alias(self):
        """Test define_type is alias for type_declaration"""
        my_type = define_type(
            "my_test_type",
            validate=[MinLengthValidator(1)],
            register=False
        )
        assert my_type.process("hello") == "hello"


class TestCustomTypeCreation:
    """Test creating custom types"""

    def test_custom_caster(self):
        """Test creating custom caster"""
        class CurrencyCaster(Caster[float]):
            def process(self, value):
                if isinstance(value, str):
                    # Remove currency symbols
                    value = value.replace("$", "").replace(",", "").strip()
                return float(value)

        money_type = FoobaraType(
            name="money",
            python_type=float,
            casters=[CurrencyCaster()],
            transformers=[RoundTransformer(2)]
        )

        assert money_type.process("$1,234.567") == 1234.57

    def test_custom_validator(self):
        """Test creating custom validator"""
        class EvenValidator(Validator[int]):
            def process(self, value):
                if value % 2 != 0:
                    raise ValueError("Value must be even")
                return value

        even_int = FoobaraType(
            name="even_int",
            python_type=int,
            casters=[IntegerCaster()],
            validators=[EvenValidator()]
        )

        assert even_int.process("42") == 42
        with pytest.raises(ValueError, match="must be even"):
            even_int.process("41")

    def test_custom_transformer(self):
        """Test creating custom transformer"""
        class SlugTransformer(Transformer[str]):
            def process(self, value):
                import re
                value = value.lower().strip()
                value = re.sub(r"[^\w\s-]", "", value)
                value = re.sub(r"[-\s]+", "-", value)
                return value

        slug_type = FoobaraType(
            name="slug",
            python_type=str,
            transformers=[SlugTransformer()]
        )

        assert slug_type.process("Hello World!") == "hello-world"
