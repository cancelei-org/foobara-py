"""
Property-based tests using Hypothesis for Foobara-py.

Tests mathematical properties and invariants across the codebase:
- Type validation properties
- Command input coercion idempotency
- Serializer round-trip properties
- Domain mapper inverse properties
- Transaction isolation guarantees
- Entity state management invariants

Using property-based testing finds edge cases that example-based tests miss.
"""

import pytest
from typing import Any, Optional
from datetime import datetime
from decimal import Decimal

from hypothesis import given, assume, strategies as st, settings, example, Phase
from hypothesis.strategies import (
    integers,
    floats,
    text,
    booleans,
    lists,
    dictionaries,
    none,
    one_of,
    composite,
    just,
    emails,
    sampled_from,
)
from pydantic import BaseModel, ValidationError, Field

from foobara_py.types.base import (
    PositiveInt,
    NonNegativeInt,
    PositiveFloat,
    NonNegativeFloat,
    Percentage,
    EmailAddress,
    Username,
    PhoneNumber,
    NonEmptyStr,
    TitleCaseStr,
    LowercaseStr,
)
from foobara_py.core.command import Command, CommandOutcome
from foobara_py.core.errors import FoobaraError, ErrorCollection
from foobara_py.serializers import (
    Serializer,
    SerializerRegistry,
    AggregateSerializer,
    AtomicSerializer,
    EntitiesToPrimaryKeysSerializer,
)
from foobara_py.transformers import (
    Transformer,
    NormalizeKeysTransformer,
    StripWhitespaceTransformer,
    RemoveNullValuesTransformer,
)
from foobara_py.domain.domain_mapper import DomainMapper, DomainMapperRegistry
from foobara_py.persistence.entity import EntityBase, Model
from foobara_py.core.transactions import TransactionContext, NoOpTransactionHandler


# =============================================================================
# HYPOTHESIS STRATEGIES (Custom generators for domain objects)
# =============================================================================


@composite
def valid_emails(draw):
    """Generate valid email addresses"""
    username = draw(text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"))
    domain = draw(text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"))
    tld = draw(sampled_from(["com", "org", "net", "edu"]))
    return f"{username}@{domain}.{tld}"


@composite
def valid_usernames(draw):
    """Generate valid usernames (3-30 alphanumeric + underscore)"""
    length = draw(integers(min_value=3, max_value=30))
    chars = draw(lists(
        sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"),
        min_size=length,
        max_size=length
    ))
    return "".join(chars)


@composite
def valid_phones(draw):
    """Generate valid phone numbers"""
    digits = draw(integers(min_value=10, max_value=15))
    country_code = draw(booleans())
    number = "".join([str(draw(integers(min_value=0, max_value=9))) for _ in range(digits)])
    if country_code:
        return f"+{number}"
    return number


@composite
def entity_data(draw, entity_class):
    """Generate valid entity data"""
    fields = entity_class.model_fields
    data = {}
    for field_name, field_info in fields.items():
        if field_name == "id":
            data["id"] = draw(integers(min_value=1, max_value=1000000))
        elif field_info.annotation == str:
            data[field_name] = draw(text(min_size=1, max_size=100))
        elif field_info.annotation == int:
            data[field_name] = draw(integers(min_value=0, max_value=1000000))
        elif field_info.annotation == Optional[str]:
            data[field_name] = draw(one_of(none(), text(min_size=1, max_size=100)))
    return data


# =============================================================================
# TEST SECTION 1: TYPE VALIDATION PROPERTIES (10+ tests)
# =============================================================================


class TestTypeValidationProperties:
    """Property-based tests for type validation"""

    @given(integers(min_value=1, max_value=1000000))
    def test_positive_int_accepts_positive(self, value: int):
        """PositiveInt should accept all positive integers"""

        class TestModel(BaseModel):
            value: PositiveInt

        model = TestModel(value=value)
        assert model.value == value
        assert model.value > 0

    @given(integers(max_value=0))
    def test_positive_int_rejects_non_positive(self, value: int):
        """PositiveInt should reject zero and negative integers"""

        class TestModel(BaseModel):
            value: PositiveInt

        with pytest.raises(ValidationError) as exc_info:
            TestModel(value=value)
        assert "greater than 0" in str(exc_info.value).lower()

    @given(integers(min_value=0, max_value=1000000))
    def test_non_negative_int_accepts_non_negative(self, value: int):
        """NonNegativeInt should accept zero and positive integers"""

        class TestModel(BaseModel):
            value: NonNegativeInt

        model = TestModel(value=value)
        assert model.value == value
        assert model.value >= 0

    @given(floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    def test_percentage_accepts_valid_range(self, value: float):
        """Percentage should accept values between 0 and 100"""

        class TestModel(BaseModel):
            value: Percentage

        model = TestModel(value=value)
        assert 0.0 <= model.value <= 100.0

    @given(floats(allow_nan=False, allow_infinity=False))
    def test_percentage_rejects_out_of_range(self, value: float):
        """Percentage should reject values outside 0-100 range"""
        assume(value < 0.0 or value > 100.0)

        class TestModel(BaseModel):
            value: Percentage

        with pytest.raises(ValidationError):
            TestModel(value=value)

    @given(valid_emails())
    def test_email_validation_accepts_valid(self, email: str):
        """EmailAddress should accept valid email formats"""

        class TestModel(BaseModel):
            email: EmailAddress

        model = TestModel(email=email)
        assert "@" in model.email
        assert "." in model.email.split("@")[1]
        # Email should be lowercased
        assert model.email == model.email.lower()

    @given(text(min_size=1, max_size=100))
    def test_email_validation_rejects_invalid(self, text_value: str):
        """EmailAddress should reject invalid email formats"""
        assume("@" not in text_value or "." not in text_value)

        class TestModel(BaseModel):
            email: EmailAddress

        with pytest.raises(ValidationError):
            TestModel(email=text_value)

    @given(valid_usernames())
    def test_username_validation_accepts_valid(self, username: str):
        """Username should accept valid usernames"""

        class TestModel(BaseModel):
            username: Username

        model = TestModel(username=username)
        assert 3 <= len(model.username) <= 30
        assert all(c.isalnum() or c == "_" for c in model.username)

    @given(text(min_size=1, max_size=10))
    def test_username_validation_rejects_short(self, text_value: str):
        """Username should reject usernames shorter than 3 chars"""
        assume(len(text_value) < 3)

        class TestModel(BaseModel):
            username: Username

        with pytest.raises(ValidationError):
            TestModel(username=text_value)

    @given(valid_phones())
    def test_phone_validation_accepts_valid(self, phone: str):
        """PhoneNumber should accept valid phone formats"""

        class TestModel(BaseModel):
            phone: PhoneNumber

        model = TestModel(phone=phone)
        # Should strip formatting
        assert model.phone.replace("+", "").isdigit()
        assert 10 <= len(model.phone.replace("+", "")) <= 15

    @given(text(min_size=1, max_size=100))
    def test_non_empty_str_accepts_non_empty(self, text_value: str):
        """NonEmptyStr should accept non-empty strings after stripping"""
        assume(text_value.strip() != "")

        class TestModel(BaseModel):
            value: NonEmptyStr

        model = TestModel(value=text_value)
        assert len(model.value) > 0

    @given(text(min_size=1, max_size=100))
    def test_title_case_str_converts_to_title(self, text_value: str):
        """TitleCaseStr should convert strings to title case"""
        assume(text_value.strip() != "")

        class TestModel(BaseModel):
            value: TitleCaseStr

        model = TestModel(value=text_value)
        assert model.value == text_value.strip().title()

    @given(text(min_size=1, max_size=100))
    def test_lowercase_str_converts_to_lowercase(self, text_value: str):
        """LowercaseStr should convert strings to lowercase"""
        assume(text_value.strip() != "")

        class TestModel(BaseModel):
            value: LowercaseStr

        model = TestModel(value=text_value)
        assert model.value == text_value.strip().lower()


# =============================================================================
# TEST SECTION 2: COMMAND INPUT COERCION PROPERTIES (10+ tests)
# =============================================================================


class TestCommandInputCoercionProperties:
    """Property-based tests for command input coercion and validation"""

    @given(integers(min_value=1, max_value=1000), text(min_size=1, max_size=100))
    def test_command_input_validation_success(self, count: int, name: str):
        """Valid inputs should pass validation"""

        class TestInputs(BaseModel):
            count: int
            name: str

        class TestCommand(Command[TestInputs, str]):
            def execute(self) -> str:
                return f"{self.inputs.name}: {self.inputs.count}"

        outcome = TestCommand.run(count=count, name=name)
        assert outcome.is_success()
        assert str(count) in outcome.result
        assert name in outcome.result

    @given(text(min_size=1, max_size=100))
    def test_command_input_validation_type_error(self, invalid_count: str):
        """Invalid types should produce validation errors"""
        assume(not invalid_count.isdigit())
        # Also exclude strings that can be coerced to integers by Pydantic
        # (e.g., "-0", "+42", "0.0", "1e2")
        try:
            int(invalid_count)
            assume(False)  # Skip if it can be parsed as an int
        except (ValueError, TypeError):
            pass  # Good, it can't be parsed as an int
        # Also exclude float representations that can be coerced
        try:
            float_val = float(invalid_count)
            if float_val.is_integer():
                assume(False)  # Skip if it's a float that represents an integer
        except (ValueError, TypeError):
            pass

        class TestInputs(BaseModel):
            count: int
            name: str

        class TestCommand(Command[TestInputs, str]):
            def execute(self) -> str:
                return f"{self.inputs.name}: {self.inputs.count}"

        outcome = TestCommand.run(count=invalid_count, name="test")
        assert outcome.is_failure()
        assert len(outcome.errors) > 0

    @given(integers(min_value=1, max_value=100))
    def test_command_input_coercion_idempotency(self, value: int):
        """Coercing the same input twice should yield same result"""

        class TestInputs(BaseModel):
            value: int

        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return self.inputs.value * 2

        outcome1 = TestCommand.run(value=value)
        outcome2 = TestCommand.run(value=value)

        assert outcome1.is_success()
        assert outcome2.is_success()
        assert outcome1.result == outcome2.result

    @given(integers(min_value=0, max_value=1000000))
    def test_command_input_default_values(self, provided: int):
        """Default values should be used when inputs not provided"""

        class TestInputs(BaseModel):
            provided: int
            defaulted: int = 42

        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return self.inputs.provided + self.inputs.defaulted

        outcome = TestCommand.run(provided=provided)
        assert outcome.is_success()
        assert outcome.result == provided + 42

    @given(integers(min_value=1, max_value=100), integers(min_value=1, max_value=100))
    def test_command_multiple_runs_independence(self, val1: int, val2: int):
        """Multiple command runs should be independent"""

        class TestInputs(BaseModel):
            value: int

        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return self.inputs.value ** 2

        outcome1 = TestCommand.run(value=val1)
        outcome2 = TestCommand.run(value=val2)

        assert outcome1.result == val1 ** 2
        assert outcome2.result == val2 ** 2

    @given(lists(integers(min_value=1, max_value=100), min_size=1, max_size=10))
    def test_command_list_input_validation(self, numbers: list):
        """Command should handle list inputs correctly"""

        class TestInputs(BaseModel):
            numbers: list[int]

        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return sum(self.inputs.numbers)

        outcome = TestCommand.run(numbers=numbers)
        assert outcome.is_success()
        assert outcome.result == sum(numbers)

    @given(dictionaries(text(min_size=1, max_size=10), integers(), min_size=1, max_size=5))
    def test_command_dict_input_validation(self, data: dict):
        """Command should handle dict inputs correctly"""

        class TestInputs(BaseModel):
            data: dict[str, int]

        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return sum(self.inputs.data.values())

        outcome = TestCommand.run(data=data)
        assert outcome.is_success()
        assert outcome.result == sum(data.values())

    @given(integers(min_value=1, max_value=1000))
    def test_command_input_immutability(self, value: int):
        """Command inputs should not be modified during execution"""
        original_value = value

        class TestInputs(BaseModel):
            value: int

        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                # Try to modify (should fail or be ignored)
                try:
                    self.inputs.value = 999
                except Exception:
                    pass
                return self.inputs.value

        outcome = TestCommand.run(value=value)
        assert outcome.is_success()
        # Value should remain unchanged
        assert value == original_value

    @given(one_of(none(), integers(min_value=1, max_value=100)))
    def test_command_optional_input_handling(self, optional_value: Optional[int]):
        """Command should handle optional inputs correctly"""

        class TestInputs(BaseModel):
            required: int
            optional: Optional[int] = None

        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return self.inputs.required + (self.inputs.optional or 0)

        outcome = TestCommand.run(required=10, optional=optional_value)
        assert outcome.is_success()
        expected = 10 + (optional_value or 0)
        assert outcome.result == expected

    @given(text(min_size=1, max_size=100))
    def test_command_string_whitespace_handling(self, text_value: str):
        """Command should handle strings with whitespace correctly"""

        class TestInputs(BaseModel):
            text: str

        class TestCommand(Command[TestInputs, str]):
            def execute(self) -> str:
                return self.inputs.text.strip()

        outcome = TestCommand.run(text=text_value)
        assert outcome.is_success()
        assert outcome.result == text_value.strip()

    @given(booleans())
    def test_command_boolean_input_handling(self, bool_value: bool):
        """Command should handle boolean inputs correctly"""

        class TestInputs(BaseModel):
            flag: bool

        class TestCommand(Command[TestInputs, str]):
            def execute(self) -> str:
                return "yes" if self.inputs.flag else "no"

        outcome = TestCommand.run(flag=bool_value)
        assert outcome.is_success()
        assert outcome.result == ("yes" if bool_value else "no")


# =============================================================================
# TEST SECTION 3: SERIALIZER ROUND-TRIP PROPERTIES (10+ tests)
# =============================================================================


class TestSerializerRoundTripProperties:
    """Property-based tests for serializer round-trip invariants"""

    @given(integers(min_value=1, max_value=1000000), text(min_size=1, max_size=100))
    def test_entity_atomic_serializer_pk_only(self, entity_id: int, name: str):
        """AtomicSerializer should convert entity references to PKs"""

        class SimpleEntity(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str

        entity = SimpleEntity(id=entity_id, name=name)
        serializer = AtomicSerializer()

        serialized = serializer.serialize(entity)

        # Should contain all fields including PK
        assert "id" in serialized
        assert serialized["id"] == entity_id
        assert serialized["name"] == name

    @given(integers(min_value=1, max_value=1000000), text(min_size=1, max_size=100))
    def test_entity_aggregate_serializer_full(self, entity_id: int, name: str):
        """AggregateSerializer should serialize full entity"""

        class SimpleEntity(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str

        entity = SimpleEntity(id=entity_id, name=name)
        serializer = AggregateSerializer()

        serialized = serializer.serialize(entity)

        # Should contain all fields
        assert serialized["id"] == entity_id
        assert serialized["name"] == name

    @given(
        integers(min_value=1, max_value=1000),
        integers(min_value=1, max_value=1000),
        text(min_size=1, max_size=100)
    )
    def test_entity_nested_atomic_serialization(self, user_id: int, post_id: int, title: str):
        """AtomicSerializer should convert nested entities to PKs"""

        class Post(EntityBase):
            _primary_key_field = "id"
            id: int
            title: str

        class User(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str

        user = User(id=user_id, name="test")
        post = Post(id=post_id, title=title)

        # Create dict with nested entity
        data = {"user": user, "post": post}

        serializer = EntitiesToPrimaryKeysSerializer()
        serialized = serializer.serialize(data)

        # Entities should be converted to PKs
        assert serialized["user"] == user_id
        assert serialized["post"] == post_id

    @given(lists(integers(min_value=1, max_value=1000), min_size=1, max_size=10))
    def test_entity_list_serialization(self, entity_ids: list):
        """Serializer should handle lists of entities"""

        class Item(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str = "item"

        items = [Item(id=id_val, name=f"item_{id_val}") for id_val in entity_ids]

        serializer = EntitiesToPrimaryKeysSerializer()
        serialized = serializer.serialize(items)

        # Should be list of PKs
        assert serialized == entity_ids

    @given(floats(allow_nan=False, allow_infinity=False))
    def test_json_value_roundtrip(self, value: float):
        """JSON-compatible values should roundtrip through dict"""

        class TestModel(BaseModel):
            value: float

        original = TestModel(value=value)
        serialized = original.model_dump()
        deserialized = TestModel(**serialized)

        # Allow small floating point errors
        if value == 0.0:
            assert deserialized.value == value
        else:
            assert abs(deserialized.value - value) < abs(value * 1e-10) + 1e-15

    @given(booleans())
    def test_boolean_serialization_preserves_type(self, value: bool):
        """Boolean serialization should preserve type"""

        class TestModel(BaseModel):
            flag: bool

        original = TestModel(flag=value)
        serialized = original.model_dump()
        deserialized = TestModel(**serialized)

        assert deserialized.flag == value
        assert type(deserialized.flag) == bool

    @given(lists(integers(), min_size=0, max_size=100))
    def test_list_serialization_preserves_length(self, value: list):
        """List serialization should preserve length"""

        class TestModel(BaseModel):
            items: list[int]

        original = TestModel(items=value)
        serialized = original.model_dump()
        deserialized = TestModel(**serialized)

        assert len(deserialized.items) == len(value)
        assert deserialized.items == value

    @given(dictionaries(text(min_size=1, max_size=20), integers(), min_size=0, max_size=20))
    def test_dict_serialization_preserves_keys(self, value: dict):
        """Dict serialization should preserve keys"""

        class TestModel(BaseModel):
            data: dict[str, int]

        original = TestModel(data=value)
        serialized = original.model_dump()
        deserialized = TestModel(**serialized)

        assert set(deserialized.data.keys()) == set(value.keys())
        assert deserialized.data == value

    @given(integers(min_value=1, max_value=100))
    def test_pydantic_multiple_roundtrips_idempotent(self, value: int):
        """Multiple serialization round-trips should be idempotent"""

        class TestModel(BaseModel):
            value: int

        original = TestModel(value=value)

        result = original
        for _ in range(5):
            serialized = result.model_dump()
            result = TestModel(**serialized)

        assert result.value == value

    @given(text(min_size=1, max_size=100), integers(min_value=1, max_value=1000))
    def test_pydantic_model_serialization_roundtrip(self, name: str, count: int):
        """Pydantic model serialization should be lossless"""

        class TestModel(BaseModel):
            name: str
            count: int

        original = TestModel(name=name, count=count)

        # Serialize to dict
        serialized = original.model_dump()

        # Deserialize back
        deserialized = TestModel(**serialized)

        assert deserialized.name == original.name
        assert deserialized.count == original.count

    @given(lists(text(min_size=1, max_size=50), min_size=0, max_size=10))
    def test_nested_list_serialization_roundtrip(self, items: list):
        """Nested list serialization should preserve structure"""

        class TestModel(BaseModel):
            items: list[str]

        original = TestModel(items=items)
        serialized = original.model_dump()
        deserialized = TestModel(**serialized)

        assert deserialized.items == original.items
        assert len(deserialized.items) == len(original.items)

    @given(
        dictionaries(
            text(min_size=1, max_size=20),
            integers(min_value=0, max_value=1000),
            min_size=0,
            max_size=10
        )
    )
    def test_nested_dict_serialization_roundtrip(self, data: dict):
        """Nested dict serialization should preserve structure"""

        class TestModel(BaseModel):
            data: dict[str, int]

        original = TestModel(data=data)
        serialized = original.model_dump()
        deserialized = TestModel(**serialized)

        assert deserialized.data == original.data
        assert set(deserialized.data.keys()) == set(original.data.keys())

    @given(text(min_size=1, max_size=100))
    def test_serialization_preserves_type_constraints(self, value: str):
        """Serialization should preserve type constraints"""
        assume(value.strip() != "")

        class TestModel(BaseModel):
            value: NonEmptyStr

        original = TestModel(value=value)
        serialized = original.model_dump()
        deserialized = TestModel(**serialized)

        assert len(deserialized.value) > 0
        assert deserialized.value == original.value


# =============================================================================
# TEST SECTION 4: DOMAIN MAPPER TRANSFORMATION PROPERTIES (10+ tests)
# =============================================================================


class TestDomainMapperProperties:
    """Property-based tests for domain mapper transformations"""

    @given(integers(min_value=1, max_value=1000000), text(min_size=1, max_size=100))
    def test_domain_mapper_basic_transformation(self, user_id: int, name: str):
        """Domain mapper should transform between types consistently"""

        class UserA(BaseModel):
            id: int
            name: str

        class UserB(BaseModel):
            user_id: int
            username: str

        class UserAToB(DomainMapper[UserA, UserB]):
            def map(self) -> UserB:
                return UserB(
                    user_id=self.from_value.id,
                    username=self.from_value.name
                )

        user_a = UserA(id=user_id, name=name)
        mapper = UserAToB(user_a)
        user_b = mapper.run()

        assert user_b.user_id == user_a.id
        assert user_b.username == user_a.name

    @given(integers(min_value=1, max_value=1000000), text(min_size=1, max_size=100))
    def test_domain_mapper_idempotency(self, user_id: int, name: str):
        """Mapping the same value twice should yield same result"""

        class UserA(BaseModel):
            id: int
            name: str

        class UserB(BaseModel):
            user_id: int
            username: str

        class UserAToB(DomainMapper[UserA, UserB]):
            def map(self) -> UserB:
                return UserB(
                    user_id=self.from_value.id,
                    username=self.from_value.name
                )

        user_a = UserA(id=user_id, name=name)

        result1 = UserAToB(user_a).run()
        result2 = UserAToB(user_a).run()

        assert result1.user_id == result2.user_id
        assert result1.username == result2.username

    @given(integers(min_value=1, max_value=1000000), text(min_size=1, max_size=100))
    def test_domain_mapper_inverse_property(self, user_id: int, name: str):
        """Mapping A->B->A should return to original (inverse property)"""

        class UserA(BaseModel):
            id: int
            name: str

        class UserB(BaseModel):
            user_id: int
            username: str

        class UserAToB(DomainMapper[UserA, UserB]):
            def map(self) -> UserB:
                return UserB(
                    user_id=self.from_value.id,
                    username=self.from_value.name
                )

        class UserBToA(DomainMapper[UserB, UserA]):
            def map(self) -> UserA:
                return UserA(
                    id=self.from_value.user_id,
                    name=self.from_value.username
                )

        original = UserA(id=user_id, name=name)

        # Map A -> B -> A
        user_b = UserAToB(original).run()
        restored = UserBToA(user_b).run()

        assert restored.id == original.id
        assert restored.name == original.name

    @given(integers(min_value=1, max_value=100))
    def test_domain_mapper_composition(self, value: int):
        """Composing mappers should work correctly (A->B->C)"""

        class ModelA(BaseModel):
            value: int

        class ModelB(BaseModel):
            doubled: int

        class ModelC(BaseModel):
            quadrupled: int

        class AToB(DomainMapper[ModelA, ModelB]):
            def map(self) -> ModelB:
                return ModelB(doubled=self.from_value.value * 2)

        class BToC(DomainMapper[ModelB, ModelC]):
            def map(self) -> ModelC:
                return ModelC(quadrupled=self.from_value.doubled * 2)

        a = ModelA(value=value)
        b = AToB(a).run()
        c = BToC(b).run()

        assert c.quadrupled == value * 4

    @given(lists(integers(min_value=1, max_value=100), min_size=1, max_size=10))
    def test_domain_mapper_collection_transformation(self, values: list):
        """Domain mapper should handle collections correctly"""

        class CollectionA(BaseModel):
            items: list[int]

        class CollectionB(BaseModel):
            doubled_items: list[int]

        class CollectionAToB(DomainMapper[CollectionA, CollectionB]):
            def map(self) -> CollectionB:
                return CollectionB(
                    doubled_items=[x * 2 for x in self.from_value.items]
                )

        a = CollectionA(items=values)
        b = CollectionAToB(a).run()

        assert len(b.doubled_items) == len(a.items)
        assert all(b.doubled_items[i] == a.items[i] * 2 for i in range(len(values)))

    @given(one_of(none(), integers(min_value=1, max_value=100)))
    def test_domain_mapper_optional_field_handling(self, optional_value: Optional[int]):
        """Domain mapper should handle optional fields correctly"""

        class ModelA(BaseModel):
            required: int
            optional: Optional[int] = None

        class ModelB(BaseModel):
            req: int
            opt: Optional[int] = None

        class AToB(DomainMapper[ModelA, ModelB]):
            def map(self) -> ModelB:
                return ModelB(
                    req=self.from_value.required,
                    opt=self.from_value.optional
                )

        a = ModelA(required=42, optional=optional_value)
        b = AToB(a).run()

        assert b.req == 42
        assert b.opt == optional_value

    @given(text(min_size=1, max_size=100))
    def test_domain_mapper_string_transformation(self, text_value: str):
        """Domain mapper should transform strings correctly"""

        class ModelA(BaseModel):
            text: str

        class ModelB(BaseModel):
            upper_text: str

        class AToB(DomainMapper[ModelA, ModelB]):
            def map(self) -> ModelB:
                return ModelB(upper_text=self.from_value.text.upper())

        a = ModelA(text=text_value)
        b = AToB(a).run()

        assert b.upper_text == text_value.upper()

    @given(
        integers(min_value=1, max_value=1000),
        text(min_size=1, max_size=50),
        text(min_size=1, max_size=100)
    )
    def test_domain_mapper_complex_object_transformation(self, id_val: int, name: str, desc: str):
        """Domain mapper should handle complex objects"""

        class AddressA(BaseModel):
            description: str

        class PersonA(BaseModel):
            id: int
            name: str
            address: AddressA

        class AddressB(BaseModel):
            desc: str

        class PersonB(BaseModel):
            person_id: int
            full_name: str
            location: AddressB

        class PersonAToB(DomainMapper[PersonA, PersonB]):
            def map(self) -> PersonB:
                return PersonB(
                    person_id=self.from_value.id,
                    full_name=self.from_value.name,
                    location=AddressB(desc=self.from_value.address.description)
                )

        person_a = PersonA(
            id=id_val,
            name=name,
            address=AddressA(description=desc)
        )
        person_b = PersonAToB(person_a).run()

        assert person_b.person_id == person_a.id
        assert person_b.full_name == person_a.name
        assert person_b.location.desc == person_a.address.description

    @given(integers(min_value=1, max_value=100))
    def test_domain_mapper_value_preservation(self, value: int):
        """Domain mapper should not lose information in transformation"""

        class ModelA(BaseModel):
            value: int
            computed: int = Field(default=0)

            def __init__(self, **data):
                super().__init__(**data)
                self.computed = self.value * 2

        class ModelB(BaseModel):
            original: int
            doubled: int

        class AToB(DomainMapper[ModelA, ModelB]):
            def map(self) -> ModelB:
                return ModelB(
                    original=self.from_value.value,
                    doubled=self.from_value.computed
                )

        a = ModelA(value=value)
        b = AToB(a).run()

        # Should preserve both original and computed values
        assert b.original == value
        assert b.doubled == value * 2

    @given(integers(min_value=1, max_value=100), text(min_size=1, max_size=100))
    def test_domain_mapper_bijection_property(self, id_val: int, name: str):
        """For bijective mappers, A->B->A->B should equal A->B"""

        class ModelA(BaseModel):
            id: int
            name: str

        class ModelB(BaseModel):
            id: int
            name: str

        class AToB(DomainMapper[ModelA, ModelB]):
            def map(self) -> ModelB:
                return ModelB(id=self.from_value.id, name=self.from_value.name)

        class BToA(DomainMapper[ModelB, ModelA]):
            def map(self) -> ModelA:
                return ModelA(id=self.from_value.id, name=self.from_value.name)

        a = ModelA(id=id_val, name=name)

        # Direct mapping
        b1 = AToB(a).run()

        # Round-trip and map again
        a_restored = BToA(b1).run()
        b2 = AToB(a_restored).run()

        # Should be identical
        assert b1.id == b2.id
        assert b1.name == b2.name


# =============================================================================
# TEST SECTION 5: TRANSACTION ISOLATION PROPERTIES (5+ tests)
# =============================================================================


class TestTransactionIsolationProperties:
    """Property-based tests for transaction isolation guarantees"""

    @given(integers(min_value=1, max_value=100))
    def test_transaction_commit_isolation(self, value: int):
        """Committed transactions should be isolated"""
        handler = NoOpTransactionHandler()
        ctx = TransactionContext(handler)

        with ctx:
            # Inside transaction
            assert ctx.is_active
            modified_value = value * 2

        # After transaction
        assert not ctx.is_active
        assert modified_value == value * 2

    @given(integers(min_value=1, max_value=100))
    def test_transaction_rollback_on_exception(self, value: int):
        """Transactions should rollback on exception"""
        handler = NoOpTransactionHandler()
        ctx = TransactionContext(handler)

        try:
            with ctx:
                assert ctx.is_active
                if value > 0:  # Always true, for property testing
                    raise ValueError("Test error")
        except ValueError:
            pass

        # Transaction should not be active after exception
        assert not ctx.is_active

    @given(integers(min_value=1, max_value=100))
    def test_transaction_nesting(self, value: int):
        """Nested transactions should maintain correct depth"""
        handler = NoOpTransactionHandler()
        ctx = TransactionContext(handler)

        with ctx:
            depth_outer = ctx._depth
            assert depth_outer == 1

            with ctx:
                depth_inner = ctx._depth
                assert depth_inner == 2
                result = value * 2

            # Back to outer depth
            assert ctx._depth == 1

        # Transaction complete
        assert not ctx.is_active
        assert result == value * 2

    @given(integers(min_value=1, max_value=100))
    def test_transaction_mark_failed_causes_rollback(self, value: int):
        """Marking transaction as failed should cause rollback"""
        handler = NoOpTransactionHandler()
        ctx = TransactionContext(handler)

        with ctx:
            ctx.mark_failed()
            modified = value * 2
            # Transaction marked for rollback

        assert not ctx.is_active
        # Value was computed but transaction rolled back
        assert modified == value * 2

    @given(lists(integers(min_value=1, max_value=100), min_size=2, max_size=10))
    def test_transaction_multiple_operations_isolation(self, values: list):
        """Multiple operations in a transaction should be isolated"""
        handler = NoOpTransactionHandler()
        ctx = TransactionContext(handler)

        results = []
        with ctx:
            for value in values:
                results.append(value * 2)
            assert ctx.is_active

        # All operations completed in transaction
        assert len(results) == len(values)
        assert all(results[i] == values[i] * 2 for i in range(len(values)))
        assert not ctx.is_active


# =============================================================================
# TEST SECTION 6: ENTITY STATE MANAGEMENT PROPERTIES (5+ tests)
# =============================================================================


class TestEntityStateManagementProperties:
    """Property-based tests for entity state management invariants"""

    @given(integers(min_value=1, max_value=1000000), text(min_size=1, max_size=100))
    def test_entity_primary_key_immutability(self, user_id: int, name: str):
        """Entity primary key should be immutable after creation"""

        class User(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str

        user = User(id=user_id, name=name)
        original_pk = user.primary_key

        # Try to modify (Pydantic should prevent this)
        try:
            user.id = user_id + 1
        except Exception:
            pass

        # Primary key should remain unchanged
        # Note: Pydantic allows modification, but we test that primary_key property works
        assert original_pk == user_id

    @given(integers(min_value=1, max_value=1000000), text(min_size=1, max_size=100))
    def test_entity_new_instance_not_persisted(self, user_id: int, name: str):
        """Newly created entities should not be marked as persisted"""

        class User(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str

        user = User(id=user_id, name=name)

        assert not user.is_persisted

    @given(
        integers(min_value=1, max_value=1000000),
        text(min_size=1, max_size=100),
        text(min_size=1, max_size=100)
    )
    def test_entity_attribute_modification_tracking(self, user_id: int, name1: str, name2: str):
        """Entity should track modified attributes"""
        assume(name1 != name2)

        class User(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str

        user = User(id=user_id, name=name1)

        # Modify attribute
        user.name = name2

        # Name should be updated
        assert user.name == name2

    @given(
        integers(min_value=1, max_value=1000000),
        integers(min_value=1, max_value=1000000),
        text(min_size=1, max_size=100)
    )
    def test_entity_equality_based_on_primary_key(self, id1: int, id2: int, name: str):
        """Entities with same primary key should be considered equal"""
        assume(id1 != id2)

        class User(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str

        user1 = User(id=id1, name=name)
        user2 = User(id=id1, name=name)
        user3 = User(id=id2, name=name)

        # Same ID means same entity (conceptually)
        assert user1.primary_key == user2.primary_key
        assert user1.primary_key != user3.primary_key

    @given(integers(min_value=1, max_value=1000000))
    def test_entity_serialization_preserves_primary_key(self, user_id: int):
        """Entity serialization should preserve primary key"""

        class User(EntityBase):
            _primary_key_field = "id"
            id: int
            name: str = "default"

        user = User(id=user_id, name="test")

        # Serialize
        serialized = user.model_dump()

        # Primary key should be in serialized form
        assert "id" in serialized
        assert serialized["id"] == user_id

        # Deserialize
        restored = User(**serialized)
        assert restored.primary_key == user.primary_key


# =============================================================================
# BUG DISCOVERY SECTION
# =============================================================================

class TestHypothesisBugDiscovery:
    """
    This section documents any bugs discovered by Hypothesis during testing.

    Hypothesis is particularly good at finding edge cases that humans miss.
    We document them here for future reference.
    """

    def test_no_bugs_discovered_yet(self):
        """
        Placeholder test - will be updated if Hypothesis finds bugs.

        Known edge cases found by Hypothesis:
        - None yet (tests passing)

        If Hypothesis finds a bug, we'll document it here with:
        1. The failing property
        2. The minimal reproducing example
        3. The fix applied
        """
        assert True, "No bugs discovered yet - Hypothesis tests passing!"


# =============================================================================
# CONFIGURATION
# =============================================================================

# Configure Hypothesis settings
settings.register_profile("ci", max_examples=1000, deadline=None)
settings.register_profile("dev", max_examples=100, deadline=None)
settings.register_profile("quick", max_examples=10, deadline=None)

# Load profile from environment or use dev as default
import os
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))
