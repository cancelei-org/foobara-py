"""
Test Factories - Inspired by Ruby's factory_bot

This module provides factory functions for creating test data with sensible defaults
and easy customization. Factories help create consistent, reusable test fixtures.

Usage:
    # Basic usage with defaults
    user = UserFactory.create()

    # Override specific attributes
    user = UserFactory.create(username="custom_user", email="custom@test.com")

    # Build without saving to repository
    user = UserFactory.build(username="temp_user")

    # Create multiple instances
    users = UserFactory.create_batch(5)

    # Create with associations
    order = OrderFactory.create(user=user)
"""

from typing import Optional, Any, Dict, List, Type, TypeVar
from datetime import datetime, timedelta
from decimal import Decimal
import random
import string
from pydantic import BaseModel

from foobara_py.core.command import Command
from foobara_py.persistence import EntityBase, Repository, RepositoryRegistry
from foobara_py import Domain


T = TypeVar('T')


# ============================================================================
# BASE FACTORY CLASS
# ============================================================================


class Factory:
    """Base factory class for creating test objects"""

    _sequence_counters: Dict[str, int] = {}

    @classmethod
    def _get_sequence(cls, name: str) -> int:
        """Get next value in a sequence"""
        if name not in cls._sequence_counters:
            cls._sequence_counters[name] = 0
        cls._sequence_counters[name] += 1
        return cls._sequence_counters[name]

    @classmethod
    def _reset_sequences(cls):
        """Reset all sequences - useful between tests"""
        cls._sequence_counters.clear()

    @classmethod
    def random_string(cls, length: int = 10, prefix: str = "") -> str:
        """Generate random string"""
        chars = string.ascii_lowercase + string.digits
        random_part = ''.join(random.choice(chars) for _ in range(length))
        return f"{prefix}{random_part}" if prefix else random_part

    @classmethod
    def random_email(cls, domain: str = "test.com") -> str:
        """Generate random email"""
        username = cls.random_string(8)
        return f"{username}@{domain}"

    @classmethod
    def random_phone(cls) -> str:
        """Generate random phone number"""
        return f"+1{random.randint(2000000000, 9999999999)}"


# ============================================================================
# ENTITY FACTORIES
# ============================================================================


class EntityFactory(Factory):
    """Base factory for entity creation"""

    entity_class: Type[EntityBase] = None

    @classmethod
    def build(cls, **kwargs) -> EntityBase:
        """Build entity instance without saving to repository"""
        if cls.entity_class is None:
            raise ValueError(f"{cls.__name__} must define entity_class")

        # Get defaults and merge with provided kwargs
        defaults = cls.get_defaults()
        data = {**defaults, **kwargs}

        return cls.entity_class(**data)

    @classmethod
    def create(cls, repository: Optional[Repository] = None, **kwargs) -> EntityBase:
        """Create and save entity to repository"""
        entity = cls.build(**kwargs)

        if repository is None:
            # Try to get from registry
            repository = RepositoryRegistry.get(cls.entity_class)

        if repository is not None:
            return repository.save(entity)

        return entity

    @classmethod
    def build_batch(cls, count: int, **kwargs) -> List[EntityBase]:
        """Build multiple entities"""
        return [cls.build(**kwargs) for _ in range(count)]

    @classmethod
    def create_batch(
        cls,
        count: int,
        repository: Optional[Repository] = None,
        **kwargs
    ) -> List[EntityBase]:
        """Create and save multiple entities"""
        return [cls.create(repository=repository, **kwargs) for _ in range(count)]

    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        """Override in subclass to provide default values"""
        return {}


class UserFactory(EntityFactory):
    """Factory for creating User entities"""

    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        seq = cls._get_sequence('user')
        return {
            'id': None,
            'username': f"user{seq}",
            'email': f"user{seq}@test.com",
            'password_hash': f"hash_password{seq}",
            'is_active': True,
        }


class ProductFactory(EntityFactory):
    """Factory for creating Product entities"""

    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        seq = cls._get_sequence('product')
        return {
            'id': None,
            'name': f"Product {seq}",
            'description': f"Description for product {seq}",
            'price': Decimal('19.99') * seq,
            'stock': 100,
            'category': 'general',
        }


class OrderFactory(EntityFactory):
    """Factory for creating Order entities"""

    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        seq = cls._get_sequence('order')
        return {
            'id': None,
            'user_id': 1,
            'product_id': 1,
            'quantity': 1,
            'total': Decimal('19.99'),
            'status': 'pending',
        }


# ============================================================================
# COMMAND FACTORIES
# ============================================================================


class CommandFactory(Factory):
    """Factory for creating test commands"""

    @staticmethod
    def create_simple_command(
        name: str = "TestCommand",
        domain: Optional[Domain] = None,
        organization: Optional[str] = None,
        **kwargs
    ) -> Type[Command]:
        """
        Create a basic command for testing

        Args:
            name: Command class name
            domain: Domain to register command with
            organization: Organization name
            **kwargs: Additional command configuration

        Returns:
            Command class
        """
        class Inputs(BaseModel):
            value: int

        class SimpleCommand(Command[Inputs, int]):
            def execute(self) -> int:
                return self.inputs.value * 2

        SimpleCommand.__name__ = name

        if domain:
            domain.command(SimpleCommand)
        elif organization:
            SimpleCommand._organization = organization

        return SimpleCommand

    @staticmethod
    def create_command_with_validation(
        name: str = "ValidatedCommand",
        domain: Optional[Domain] = None,
        **kwargs
    ) -> Type[Command]:
        """
        Create command with input validation

        Args:
            name: Command class name
            domain: Domain to register command with
            **kwargs: Additional command configuration

        Returns:
            Command class with validation
        """
        class Inputs(BaseModel):
            email: str
            age: int

        class ValidatedCommand(Command[Inputs, str]):
            def execute(self) -> str:
                if "@" not in self.inputs.email:
                    self.add_input_error(
                        path=["email"],
                        symbol="invalid_email",
                        message="Email must contain @"
                    )
                    return ""

                if self.inputs.age < 0:
                    self.add_input_error(
                        path=["age"],
                        symbol="invalid_age",
                        message="Age must be positive"
                    )
                    return ""

                return f"Valid: {self.inputs.email}"

        ValidatedCommand.__name__ = name

        if domain:
            domain.command(ValidatedCommand)

        return ValidatedCommand

    @staticmethod
    def create_command_with_entity(
        name: str = "EntityCommand",
        entity_class: Type[EntityBase] = None,
        repository: Optional[Repository] = None,
        domain: Optional[Domain] = None,
        **kwargs
    ) -> Type[Command]:
        """
        Create command that works with entities

        Args:
            name: Command class name
            entity_class: Entity class to work with
            repository: Repository for persistence
            domain: Domain to register command with
            **kwargs: Additional command configuration

        Returns:
            Command class that works with entities
        """
        class Inputs(BaseModel):
            name: str

        class EntityCommand(Command[Inputs, EntityBase]):
            def execute(self) -> EntityBase:
                entity_data = {'name': self.inputs.name}
                if entity_class:
                    entity = entity_class(**entity_data)
                    if repository:
                        return repository.save(entity)
                    return entity
                return None

        EntityCommand.__name__ = name

        if domain:
            domain.command(EntityCommand)

        return EntityCommand

    @staticmethod
    def create_async_command(
        name: str = "AsyncCommand",
        domain: Optional[Domain] = None,
        **kwargs
    ) -> Type[Command]:
        """
        Create async command for testing

        Args:
            name: Command class name
            domain: Domain to register command with
            **kwargs: Additional command configuration

        Returns:
            Async command class
        """
        class Inputs(BaseModel):
            value: int

        class AsyncCommand(Command[Inputs, int]):
            async def execute(self) -> int:
                # Simulate async work
                return self.inputs.value * 2

        AsyncCommand.__name__ = name

        if domain:
            domain.command(AsyncCommand)

        return AsyncCommand


# ============================================================================
# DOMAIN FACTORIES
# ============================================================================


class DomainFactory(Factory):
    """Factory for creating test domains"""

    @classmethod
    def create(
        cls,
        name: Optional[str] = None,
        organization: Optional[str] = None,
        **kwargs
    ) -> Domain:
        """
        Create a test domain

        Args:
            name: Domain name (auto-generated if not provided)
            organization: Organization name
            **kwargs: Additional domain configuration

        Returns:
            Domain instance
        """
        if name is None:
            seq = cls._get_sequence('domain')
            name = f"TestDomain{seq}"

        if organization is None:
            organization = "TestOrg"

        return Domain(name=name, organization=organization, **kwargs)

    @classmethod
    def create_with_commands(
        cls,
        command_count: int = 3,
        name: Optional[str] = None,
        **kwargs
    ) -> Domain:
        """
        Create domain with multiple commands

        Args:
            command_count: Number of commands to create
            name: Domain name
            **kwargs: Additional domain configuration

        Returns:
            Domain with registered commands
        """
        domain = cls.create(name=name, **kwargs)

        for i in range(command_count):
            CommandFactory.create_simple_command(
                name=f"Command{i+1}",
                domain=domain
            )

        return domain


# ============================================================================
# MOCK DATA GENERATORS
# ============================================================================


class MockDataGenerator:
    """Generate realistic mock data for testing"""

    @staticmethod
    def generate_user_data(count: int = 10) -> List[Dict[str, Any]]:
        """Generate mock user data"""
        users = []
        for i in range(count):
            users.append({
                'id': i + 1,
                'username': f"user{i+1}",
                'email': f"user{i+1}@example.com",
                'password_hash': f"hash_{i+1}",
                'is_active': random.choice([True, True, True, False]),  # 75% active
                'created_at': datetime.now() - timedelta(days=random.randint(1, 365))
            })
        return users

    @staticmethod
    def generate_product_data(count: int = 20) -> List[Dict[str, Any]]:
        """Generate mock product data"""
        categories = ['electronics', 'books', 'clothing', 'food', 'toys']
        products = []

        for i in range(count):
            products.append({
                'id': i + 1,
                'name': f"Product {i+1}",
                'description': f"High quality product {i+1}",
                'price': round(random.uniform(9.99, 999.99), 2),
                'stock': random.randint(0, 1000),
                'category': random.choice(categories),
            })

        return products

    @staticmethod
    def generate_order_data(
        user_count: int = 10,
        product_count: int = 20,
        order_count: int = 50
    ) -> List[Dict[str, Any]]:
        """Generate mock order data"""
        orders = []
        statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']

        for i in range(order_count):
            quantity = random.randint(1, 5)
            price = round(random.uniform(9.99, 199.99), 2)

            orders.append({
                'id': i + 1,
                'user_id': random.randint(1, user_count),
                'product_id': random.randint(1, product_count),
                'quantity': quantity,
                'total': round(price * quantity, 2),
                'status': random.choice(statuses),
                'created_at': datetime.now() - timedelta(days=random.randint(1, 90))
            })

        return orders


# ============================================================================
# HYPOTHESIS STRATEGIES (for property-based testing)
# ============================================================================


try:
    from hypothesis import strategies as st
    from hypothesis.strategies import composite

    @composite
    def user_strategy(draw):
        """Hypothesis strategy for generating User entities"""
        seq = draw(st.integers(min_value=1, max_value=10000))
        return {
            'id': seq,
            'username': f"user{seq}",
            'email': f"user{seq}@test.com",
            'password_hash': f"hash_{seq}",
            'is_active': draw(st.booleans()),
        }

    @composite
    def product_strategy(draw):
        """Hypothesis strategy for generating Product entities"""
        seq = draw(st.integers(min_value=1, max_value=10000))
        return {
            'id': seq,
            'name': draw(st.text(min_size=3, max_size=50)),
            'price': draw(st.decimals(min_value=0, max_value=10000, places=2)),
            'stock': draw(st.integers(min_value=0, max_value=10000)),
            'category': draw(st.sampled_from(['electronics', 'books', 'clothing', 'food'])),
        }

    @composite
    def command_inputs_strategy(draw):
        """Hypothesis strategy for generating command inputs"""
        return {
            'value': draw(st.integers(min_value=-1000, max_value=1000)),
        }

except ImportError:
    # Hypothesis not installed
    pass


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def reset_all_factories():
    """Reset all factory sequences - call this in test setup"""
    Factory._reset_sequences()


def create_test_suite_data(
    user_count: int = 5,
    product_count: int = 10,
    order_count: int = 20
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Create a complete test suite data set

    Returns:
        Dictionary with users, products, and orders
    """
    return {
        'users': MockDataGenerator.generate_user_data(user_count),
        'products': MockDataGenerator.generate_product_data(product_count),
        'orders': MockDataGenerator.generate_order_data(
            user_count=user_count,
            product_count=product_count,
            order_count=order_count
        ),
    }
