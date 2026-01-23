"""Tests for DomainMapper and DomainMapperRegistry"""

import pytest
from pydantic import BaseModel

from foobara_py.domain import DomainMapper, DomainMapperRegistry, domain_mapper, Domain
from foobara_py.core.command import Command


# Test models
class UserInternal(BaseModel):
    id: int
    full_name: str
    email: str
    is_active: bool = True


class UserExternal(BaseModel):
    id: str
    name: str
    email: str


class OrderInternal(BaseModel):
    order_id: int
    total: float


class OrderExternal(BaseModel):
    id: str
    amount: str


# Domain mappers
class UserInternalToExternal(DomainMapper[UserInternal, UserExternal]):
    """Maps internal user model to external API model"""

    def map(self) -> UserExternal:
        return UserExternal(
            id=str(self.from_value.id),
            name=self.from_value.full_name,
            email=self.from_value.email
        )


class UserExternalToInternal(DomainMapper[UserExternal, UserInternal]):
    """Maps external user model to internal model"""

    def map(self) -> UserInternal:
        return UserInternal(
            id=int(self.from_value.id),
            full_name=self.from_value.name,
            email=self.from_value.email
        )


class OrderInternalToExternal(DomainMapper[OrderInternal, OrderExternal]):
    """Maps internal order to external"""

    def map(self) -> OrderExternal:
        return OrderExternal(
            id=str(self.from_value.order_id),
            amount=f"${self.from_value.total:.2f}"
        )


class TestDomainMapper:
    """Test DomainMapper base class"""

    def test_from_type_extraction(self):
        """Should extract FromT from generic parameters"""
        assert UserInternalToExternal.from_type() == UserInternal

    def test_to_type_extraction(self):
        """Should extract ToT from generic parameters"""
        assert UserInternalToExternal.to_type() == UserExternal

    def test_map_basic(self):
        """Should map from one type to another"""
        user_internal = UserInternal(
            id=1,
            full_name="John Doe",
            email="john@example.com"
        )

        mapper = UserInternalToExternal(user_internal)
        result = mapper.run()

        assert isinstance(result, UserExternal)
        assert result.id == "1"
        assert result.name == "John Doe"
        assert result.email == "john@example.com"

    def test_map_value_class_method(self):
        """Should map using class method"""
        user_internal = UserInternal(
            id=2,
            full_name="Jane Smith",
            email="jane@example.com"
        )

        result = UserInternalToExternal.map_value(user_internal)

        assert isinstance(result, UserExternal)
        assert result.id == "2"
        assert result.name == "Jane Smith"

    def test_bidirectional_mapping(self):
        """Should support bidirectional mapping"""
        # Internal -> External
        user_internal = UserInternal(
            id=3,
            full_name="Bob Jones",
            email="bob@example.com"
        )
        user_external = UserInternalToExternal.map_value(user_internal)

        assert user_external.name == "Bob Jones"

        # External -> Internal
        user_internal_2 = UserExternalToInternal.map_value(user_external)

        assert user_internal_2.id == 3
        assert user_internal_2.full_name == "Bob Jones"

    def test_match_score(self):
        """Should calculate match scores"""
        user = UserInternal(id=1, full_name="Test", email="test@example.com")

        # Should have high score for exact type match
        score = UserInternalToExternal.match_score(user, UserExternal)
        assert score > 0

        # Should have zero score for non-matching types
        score = OrderInternalToExternal.match_score(user, OrderExternal)
        assert score == 0

    def test_applicable(self):
        """Should check if mapper is applicable"""
        user = UserInternal(id=1, full_name="Test", email="test@example.com")

        assert UserInternalToExternal.applicable(user, UserExternal)
        assert not OrderInternalToExternal.applicable(user, OrderExternal)


class TestDomainMapperRegistry:
    """Test DomainMapperRegistry"""

    def setup_method(self):
        """Clear registry before each test"""
        DomainMapperRegistry.clear()

    def test_register_mapper(self):
        """Should register mapper"""
        DomainMapperRegistry.register(UserInternalToExternal)

        mapper = DomainMapperRegistry.get(UserInternalToExternal.full_name())
        assert mapper == UserInternalToExternal

    def test_find_matching_mapper(self):
        """Should find matching mapper"""
        DomainMapperRegistry.register(UserInternalToExternal)
        DomainMapperRegistry.register(OrderInternalToExternal)

        user = UserInternal(id=1, full_name="Test", email="test@example.com")

        mapper = DomainMapperRegistry.find_matching_mapper(user, UserExternal)
        assert mapper == UserInternalToExternal

    def test_find_best_mapper_by_score(self):
        """Should find mapper with highest score"""
        # Register both user mappers
        DomainMapperRegistry.register(UserInternalToExternal)
        DomainMapperRegistry.register(UserExternalToInternal)

        user_internal = UserInternal(id=1, full_name="Test", email="test@example.com")

        # Should find the correct mapper
        mapper = DomainMapperRegistry.find_matching_mapper(user_internal, UserExternal)
        assert mapper == UserInternalToExternal

    def test_domain_mapper_decorator(self):
        """Should auto-register with decorator"""
        @domain_mapper(domain="Users", organization="TestApp")
        class TestMapper(DomainMapper[UserInternal, UserExternal]):
            def map(self) -> UserExternal:
                return UserExternal(
                    id=str(self.from_value.id),
                    name=self.from_value.full_name,
                    email=self.from_value.email
                )

        # Should be auto-registered
        mapper = DomainMapperRegistry.get("TestApp::Users::TestMapper")
        assert mapper == TestMapper
        assert mapper._domain == "Users"
        assert mapper._organization == "TestApp"


class TestCommandMappedSubcommand:
    """Test Command.run_mapped_subcommand"""

    def setup_method(self):
        """Clear registries before each test"""
        DomainMapperRegistry.clear()
        Domain.clear_registry()

    def test_run_mapped_subcommand_with_input_mapper(self):
        """Should map inputs before running subcommand"""
        DomainMapperRegistry.register(UserInternalToExternal)

        class CreateUserInputs(BaseModel):
            user: UserExternal

        class CreateUserResult(BaseModel):
            success: bool
            user_id: str

        class CreateUserCommand(Command[CreateUserInputs, CreateUserResult]):
            def execute(self) -> CreateUserResult:
                return CreateUserResult(
                    success=True,
                    user_id=self.inputs.user.id
                )

        class ParentCommandInputs(BaseModel):
            pass

        class ParentCommand(Command[ParentCommandInputs, CreateUserResult]):
            def execute(self) -> CreateUserResult:
                user_internal = UserInternal(
                    id=123,
                    full_name="Test User",
                    email="test@example.com"
                )

                # Map and run subcommand
                return self.run_mapped_subcommand(
                    CreateUserCommand,
                    unmapped_inputs={"user": user_internal}
                )

        outcome = ParentCommand.run()
        assert outcome.is_success()
        assert outcome.result.success
        assert outcome.result.user_id == "123"

    def test_run_mapped_subcommand_with_result_mapper(self):
        """Should map result after running subcommand"""
        DomainMapperRegistry.register(UserExternalToInternal)

        class GetUserInputs(BaseModel):
            user_id: str

        class GetUserCommand(Command[GetUserInputs, UserExternal]):
            def execute(self) -> UserExternal:
                return UserExternal(
                    id=self.inputs.user_id,
                    name="Test User",
                    email="test@example.com"
                )

        class ParentCommandInputs(BaseModel):
            pass

        class ParentCommand(Command[ParentCommandInputs, UserInternal]):
            def execute(self) -> UserInternal:
                # Run subcommand and map result
                return self.run_mapped_subcommand(
                    GetUserCommand,
                    to=UserInternal,
                    user_id="456"
                )

        outcome = ParentCommand.run()
        assert outcome.is_success()
        assert isinstance(outcome.result, UserInternal)
        assert outcome.result.id == 456
        assert outcome.result.full_name == "Test User"

    def test_run_mapped_subcommand_no_mapper_error(self):
        """Should raise error if no mapper found"""
        class SomeCommandInputs(BaseModel):
            data: str

        class SomeCommand(Command[SomeCommandInputs, str]):
            def execute(self) -> str:
                return self.inputs.data

        class ParentCommandInputs(BaseModel):
            pass

        class ParentCommand(Command[ParentCommandInputs, str]):
            def execute(self) -> str:
                # Try to use mapped subcommand without any mapper
                return self.run_mapped_subcommand(
                    SomeCommand,
                    unmapped_inputs={"data": "test"}
                )

        outcome = ParentCommand.run()
        # Should fail because no mapper found
        assert outcome.is_failure()
        assert any("no_domain_mapper_found" in error.symbol for error in outcome.errors)
