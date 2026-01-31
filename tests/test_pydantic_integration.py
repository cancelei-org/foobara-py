"""
Tests for Pydantic integration with FoobaraType.

Tests:
- Pydantic Field generation
- Model creation from FoobaraTypes
- Validator integration
- Runtime type checking
- Serialization with complex types
"""

import pytest
from datetime import date, datetime
from pydantic import BaseModel, ValidationError
from typing import Optional

from foobara_py.types import (
    FoobaraType,
    StringType,
    IntegerType,
    EmailType,
    PositiveIntegerType,
    DateType,
    StringCaster,
    IntegerCaster,
    MinLengthValidator,
    MaxLengthValidator,
    MinValueValidator,
    MaxValueValidator,
    EmailValidator,
    StripWhitespaceTransformer,
    LowercaseTransformer,
    RangeValidator,
    NotEmptyValidator,
)


class TestPydanticFieldGeneration:
    """Test FoobaraType to Pydantic Field conversion"""

    def test_simple_field_generation(self):
        """Test basic field generation"""
        string_type = StringType
        field_type, field_obj = string_type.to_pydantic_field()

        assert field_type == str
        assert field_obj.description is None

    def test_field_with_description(self):
        """Test field with description"""
        custom_type = FoobaraType(
            name="username",
            python_type=str,
            description="User's login name"
        )

        field_type, field_obj = custom_type.to_pydantic_field()
        assert field_obj.description == "User's login name"

    def test_field_with_default(self):
        """Test field with default value"""
        status_type = FoobaraType(
            name="status",
            python_type=str,
            default="active",
            has_default=True
        )

        field_type, field_obj = status_type.to_pydantic_field()
        assert field_obj.default == "active"
        assert field_type == Optional[str]

    def test_field_with_numeric_constraints(self):
        """Test field with numeric constraints"""
        age_type = FoobaraType(
            name="age",
            python_type=int,
            ge=0,
            le=150,
            description="Person's age"
        )

        field_type, field_obj = age_type.to_pydantic_field()
        assert field_obj.json_schema_extra or field_obj.metadata
        # Pydantic will use these constraints for validation

    def test_field_with_string_constraints(self):
        """Test field with string constraints"""
        username_type = FoobaraType(
            name="username",
            python_type=str,
            min_length=3,
            max_length=20,
            pattern=r"^[a-zA-Z0-9_]+$"
        )

        field_type, field_obj = username_type.to_pydantic_field()
        # Constraints will be in the field object

    def test_nullable_field(self):
        """Test nullable field generation"""
        optional_type = StringType.optional()
        field_type, field_obj = optional_type.to_pydantic_field()

        assert field_type == Optional[str]
        assert field_obj.default is None


class TestPydanticModelCreation:
    """Test creating Pydantic models from FoobaraTypes"""

    def test_create_simple_model(self):
        """Test creating a simple Pydantic model"""
        fields = {
            'name': StringType,
            'age': PositiveIntegerType,
            'email': EmailType,
        }

        UserModel = StringType.create_pydantic_model('User', fields)

        # Create instance
        user = UserModel(
            name='John Doe',
            age=30,
            email='john@example.com'
        )

        assert user.name == 'John Doe'
        assert user.age == 30
        assert user.email == 'john@example.com'

    def test_model_with_validation(self):
        """Test model validates using FoobaraType processors"""
        fields = {
            'email': EmailType,
            'age': PositiveIntegerType,
        }

        UserModel = StringType.create_pydantic_model('User', fields)

        # Valid input
        user = UserModel(email='user@example.com', age=25)
        assert user.email == 'user@example.com'

        # Email transformation (lowercasing)
        user2 = UserModel(email='  USER@EXAMPLE.COM  ', age=25)
        assert user2.email == 'user@example.com'

        # Invalid email should fail
        with pytest.raises(ValidationError):
            UserModel(email='not-an-email', age=25)

        # Negative age should fail
        with pytest.raises(ValidationError):
            UserModel(email='user@example.com', age=-1)

    def test_model_with_optional_fields(self):
        """Test model with optional fields"""
        fields = {
            'name': StringType,
            'nickname': StringType.optional(default='Anonymous'),
        }

        PersonModel = StringType.create_pydantic_model('Person', fields)

        # With nickname
        person1 = PersonModel(name='John', nickname='Johnny')
        assert person1.nickname == 'Johnny'

        # Without nickname (should use default)
        person2 = PersonModel(name='Jane')
        assert person2.nickname == 'Anonymous'

    def test_model_serialization(self):
        """Test model serialization to dict/JSON"""
        fields = {
            'email': EmailType,
            'age': PositiveIntegerType,
        }

        UserModel = StringType.create_pydantic_model('User', fields)
        user = UserModel(email='john@example.com', age=30)

        # Serialize to dict
        data = user.model_dump()
        assert data == {'email': 'john@example.com', 'age': 30}

        # Serialize to JSON
        json_str = user.model_dump_json()
        assert 'john@example.com' in json_str
        assert '30' in json_str

    def test_model_with_complex_types(self):
        """Test model with date and other complex types"""
        fields = {
            'name': StringType,
            'birth_date': DateType,
            'registered': DateType,
        }

        PersonModel = StringType.create_pydantic_model('Person', fields)

        # Create with string dates (will be cast)
        person = PersonModel(
            name='John',
            birth_date='1990-01-15',
            registered='2024-01-01'
        )

        assert isinstance(person.birth_date, date)
        assert person.birth_date == date(1990, 1, 15)


class TestPydanticValidatorIntegration:
    """Test FoobaraType validator integration with Pydantic"""

    def test_custom_validator_function(self):
        """Test creating custom validator from FoobaraType"""
        email_type = EmailType
        validator_func = email_type.to_pydantic_validator()

        assert validator_func is not None

        # Validator should process the value
        result = validator_func('  USER@EXAMPLE.COM  ')
        assert result == 'user@example.com'

        # Invalid email should raise
        with pytest.raises(ValueError):
            validator_func('not-an-email')

    def test_validator_with_transformers(self):
        """Test validator applies transformers before validation"""
        username_type = FoobaraType(
            name='username',
            python_type=str,
            casters=[StringCaster()],
            transformers=[StripWhitespaceTransformer(), LowercaseTransformer()],
            validators=[MinLengthValidator(3), MaxLengthValidator(20)]
        )

        validator_func = username_type.to_pydantic_validator()

        # Should strip and lowercase
        result = validator_func('  JohnDoe  ')
        assert result == 'johndoe'

        # Should fail validation if too short after transformation
        with pytest.raises(ValueError, match='at least 3'):
            validator_func('  AB  ')

    def test_multiple_validators_chain(self):
        """Test multiple validators execute in sequence"""
        bounded_int = FoobaraType(
            name='score',
            python_type=int,
            casters=[IntegerCaster()],
            validators=[
                MinValueValidator(0),
                MaxValueValidator(100)
            ]
        )

        validator_func = bounded_int.to_pydantic_validator()

        assert validator_func('50') == 50

        with pytest.raises(ValueError, match='at least 0'):
            validator_func('-1')

        with pytest.raises(ValueError, match='at most 100'):
            validator_func('101')


class TestRuntimeTypeChecking:
    """Test runtime type checking with Pydantic"""

    def test_type_coercion_in_model(self):
        """Test that Pydantic model uses type coercion"""
        fields = {
            'age': IntegerType,
            'name': StringType,
        }

        PersonModel = StringType.create_pydantic_model('Person', fields)

        # String age should be coerced to int
        person = PersonModel(age='25', name='John')
        assert person.age == 25
        assert isinstance(person.age, int)

    def test_validation_errors_are_helpful(self):
        """Test that validation errors provide helpful messages"""
        fields = {
            'email': EmailType,
        }

        UserModel = StringType.create_pydantic_model('User', fields)

        with pytest.raises(ValidationError) as exc_info:
            UserModel(email='invalid')

        error = exc_info.value
        assert 'email' in str(error).lower()

    def test_nested_model_validation(self):
        """Test validation with nested models"""
        # Create address type
        address_fields = {
            'street': StringType,
            'city': StringType,
        }

        AddressModel = StringType.create_pydantic_model('Address', address_fields)

        # Note: This is more for documentation - nested models would need
        # additional FoobaraType support for full integration
        address = AddressModel(street='123 Main St', city='Springfield')
        assert address.city == 'Springfield'


class TestNewValidators:
    """Test new validator implementations"""

    def test_range_validator(self):
        """Test RangeValidator"""
        percentage_type = FoobaraType(
            name='percentage',
            python_type=float,
            validators=[RangeValidator(0.0, 100.0)]
        )

        assert percentage_type.process(50.0) == 50.0
        assert percentage_type.process(0.0) == 0.0
        assert percentage_type.process(100.0) == 100.0

        with pytest.raises(ValueError, match='between 0.0 and 100.0'):
            percentage_type.process(-1.0)

        with pytest.raises(ValueError, match='between 0.0 and 100.0'):
            percentage_type.process(101.0)

    def test_not_empty_validator(self):
        """Test NotEmptyValidator"""
        required_string = FoobaraType(
            name='required',
            python_type=str,
            validators=[NotEmptyValidator()]
        )

        assert required_string.process('hello') == 'hello'

        with pytest.raises(ValueError, match='cannot be empty'):
            required_string.process('')

    def test_not_empty_with_list(self):
        """Test NotEmptyValidator with lists"""
        from foobara_py.types import ListCaster

        required_list = FoobaraType(
            name='items',
            python_type=list,
            casters=[ListCaster()],
            validators=[NotEmptyValidator()]
        )

        assert required_list.process([1, 2, 3]) == [1, 2, 3]

        with pytest.raises(ValueError, match='cannot be empty'):
            required_list.process([])


class TestSerializationEdgeCases:
    """Test serialization edge cases"""

    def test_date_serialization(self):
        """Test date serialization in models"""
        fields = {
            'event_date': DateType,
        }

        EventModel = StringType.create_pydantic_model('Event', fields)

        event = EventModel(event_date='2024-01-15')

        # Serialize to dict
        data = event.model_dump()
        assert isinstance(data['event_date'], date)

        # JSON serialization should work
        json_str = event.model_dump_json()
        assert '2024-01-15' in json_str

    def test_optional_field_serialization(self):
        """Test optional field serialization"""
        fields = {
            'name': StringType,
            'nickname': StringType.optional(),
        }

        PersonModel = StringType.create_pydantic_model('Person', fields)

        # With nickname
        person1 = PersonModel(name='John', nickname='Johnny')
        data1 = person1.model_dump()
        assert data1['nickname'] == 'Johnny'

        # Without nickname
        person2 = PersonModel(name='Jane', nickname=None)
        data2 = person2.model_dump()
        assert data2['nickname'] is None


class TestDocumentationExamples:
    """Test examples for documentation"""

    def test_basic_usage_example(self):
        """Example: Basic Pydantic model creation"""
        # Define types
        fields = {
            'email': EmailType,
            'age': PositiveIntegerType,
            'name': StringType,
        }

        # Create model
        UserModel = StringType.create_pydantic_model('User', fields)

        # Use model
        user = UserModel(
            email='john@example.com',
            age=30,
            name='John Doe'
        )

        assert user.email == 'john@example.com'
        assert user.age == 30

    def test_custom_type_example(self):
        """Example: Custom type with validation"""
        # Create custom type with constraints
        username_type = FoobaraType(
            name='username',
            python_type=str,
            min_length=3,
            max_length=20,
            pattern=r'^[a-zA-Z0-9_]+$',
            description='Alphanumeric username'
        )

        fields = {
            'username': username_type,
            'email': EmailType,
        }

        UserModel = StringType.create_pydantic_model('User', fields)

        # Valid username
        user = UserModel(username='john_doe', email='john@example.com')
        assert user.username == 'john_doe'

    def test_transformation_example(self):
        """Example: Automatic transformations"""
        fields = {
            'email': EmailType,  # Auto-lowercases and strips
        }

        UserModel = StringType.create_pydantic_model('User', fields)

        # Input with whitespace and uppercase
        user = UserModel(email='  JOHN@EXAMPLE.COM  ')

        # Output is normalized
        assert user.email == 'john@example.com'
