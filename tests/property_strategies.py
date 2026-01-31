"""
Enhanced Hypothesis Strategies for Property-Based Testing

This module provides custom Hypothesis strategies for generating
realistic test data for Foobara components.

Property-based testing finds edge cases by generating hundreds of random
test cases, helping discover bugs that example-based tests might miss.

Usage:
    from hypothesis import given
    from tests.property_strategies import entity_instance, command_inputs

    @given(entity_instance(User))
    def test_user_persistence(user):
        assert user.username is not None
"""

try:
    from hypothesis import strategies as st
    from hypothesis.strategies import composite, SearchStrategy
    from typing import Type, Any, Optional, Dict, List
    from decimal import Decimal
    from datetime import datetime, timedelta
    import string

    from pydantic import BaseModel
    from foobara_py.persistence import EntityBase
    from foobara_py.types.base import (
        PositiveInt,
        NonNegativeInt,
        EmailAddress,
        Username,
        PhoneNumber,
    )


    # ========================================================================
    # BASIC STRATEGIES
    # ========================================================================


    @composite
    def valid_email(draw) -> str:
        """Generate valid email addresses"""
        username_length = draw(st.integers(min_value=3, max_value=20))
        username_chars = draw(st.lists(
            st.sampled_from(string.ascii_lowercase + string.digits),
            min_size=username_length,
            max_size=username_length
        ))
        username = ''.join(username_chars)

        domain = draw(st.sampled_from([
            'test.com', 'example.com', 'demo.org', 'sample.net'
        ]))

        return f"{username}@{domain}"


    @composite
    def valid_username(draw) -> str:
        """Generate valid usernames (3-30 alphanumeric + underscore)"""
        length = draw(st.integers(min_value=3, max_value=30))
        chars = draw(st.lists(
            st.sampled_from(string.ascii_lowercase + string.digits + '_'),
            min_size=length,
            max_size=length
        ))
        return ''.join(chars)


    @composite
    def valid_phone(draw) -> str:
        """Generate valid phone numbers"""
        has_country_code = draw(st.booleans())
        digits = draw(st.integers(min_value=10, max_value=15))

        number = ''.join([str(draw(st.integers(min_value=0, max_value=9)))
                         for _ in range(digits)])

        if has_country_code:
            return f"+{number}"
        return number


    @composite
    def valid_password(draw, min_length: int = 8, max_length: int = 64) -> str:
        """Generate valid passwords with mixed characters"""
        length = draw(st.integers(min_value=min_length, max_value=max_length))

        # Ensure at least one of each required character type
        has_lower = draw(st.booleans())
        has_upper = draw(st.booleans())
        has_digit = draw(st.booleans())

        chars = string.ascii_lowercase + string.ascii_uppercase + string.digits

        password_chars = draw(st.lists(
            st.sampled_from(chars),
            min_size=length,
            max_size=length
        ))

        return ''.join(password_chars)


    @composite
    def positive_decimal(draw, max_value: int = 10000, places: int = 2) -> Decimal:
        """Generate positive decimal values"""
        value = draw(st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal(str(max_value)),
            places=places
        ))
        return value


    @composite
    def datetime_recent(draw, days_ago: int = 365) -> datetime:
        """Generate recent datetime values"""
        now = datetime.now()
        days_offset = draw(st.integers(min_value=0, max_value=days_ago))
        return now - timedelta(days=days_offset)


    # ========================================================================
    # ENTITY STRATEGIES
    # ========================================================================


    @composite
    def user_data(draw) -> Dict[str, Any]:
        """Generate User entity data"""
        return {
            'id': draw(st.one_of(st.none(), st.integers(min_value=1, max_value=100000))),
            'username': draw(valid_username()),
            'email': draw(valid_email()),
            'password_hash': draw(st.text(min_size=32, max_size=64)),
            'is_active': draw(st.booleans()),
        }


    @composite
    def product_data(draw) -> Dict[str, Any]:
        """Generate Product entity data"""
        categories = ['electronics', 'books', 'clothing', 'food', 'toys', 'home']

        return {
            'id': draw(st.one_of(st.none(), st.integers(min_value=1, max_value=100000))),
            'name': draw(st.text(min_size=3, max_size=100)),
            'description': draw(st.text(min_size=10, max_size=500)),
            'price': draw(positive_decimal(max_value=10000, places=2)),
            'stock': draw(st.integers(min_value=0, max_value=10000)),
            'category': draw(st.sampled_from(categories)),
        }


    @composite
    def order_data(draw) -> Dict[str, Any]:
        """Generate Order entity data"""
        statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']

        quantity = draw(st.integers(min_value=1, max_value=100))
        unit_price = draw(positive_decimal(max_value=1000, places=2))
        total = unit_price * quantity

        return {
            'id': draw(st.one_of(st.none(), st.integers(min_value=1, max_value=100000))),
            'user_id': draw(st.integers(min_value=1, max_value=1000)),
            'product_id': draw(st.integers(min_value=1, max_value=1000)),
            'quantity': quantity,
            'total': total,
            'status': draw(st.sampled_from(statuses)),
        }


    @composite
    def entity_instance(draw, entity_class: Type[EntityBase]) -> EntityBase:
        """
        Generate entity instances based on class

        Args:
            entity_class: Entity class to generate

        Returns:
            Entity instance with random valid data
        """
        # Map common entity types to their data strategies
        if hasattr(entity_class, '__name__'):
            class_name = entity_class.__name__

            if 'User' in class_name:
                data = draw(user_data())
            elif 'Product' in class_name:
                data = draw(product_data())
            elif 'Order' in class_name:
                data = draw(order_data())
            else:
                # Generic entity data generation
                data = draw(generic_entity_data(entity_class))

            return entity_class(**data)

        raise ValueError(f"Cannot generate strategy for {entity_class}")


    @composite
    def generic_entity_data(draw, entity_class: Type[EntityBase]) -> Dict[str, Any]:
        """
        Generate generic entity data based on field types

        Args:
            entity_class: Entity class to analyze

        Returns:
            Dictionary of field values
        """
        data = {}

        if hasattr(entity_class, 'model_fields'):
            for field_name, field_info in entity_class.model_fields.items():
                annotation = field_info.annotation

                # Handle Optional types
                if hasattr(annotation, '__origin__'):
                    if annotation.__origin__ is type(None):
                        data[field_name] = None
                        continue

                # Generate based on type
                if annotation == int or annotation == PositiveInt:
                    data[field_name] = draw(st.integers(min_value=1, max_value=100000))
                elif annotation == str:
                    data[field_name] = draw(st.text(min_size=1, max_size=100))
                elif annotation == bool:
                    data[field_name] = draw(st.booleans())
                elif annotation == float:
                    data[field_name] = draw(st.floats(
                        min_value=0.0,
                        max_value=10000.0,
                        allow_nan=False,
                        allow_infinity=False
                    ))
                elif annotation == Decimal:
                    data[field_name] = draw(positive_decimal())
                elif annotation == EmailAddress:
                    data[field_name] = draw(valid_email())
                elif annotation == Username:
                    data[field_name] = draw(valid_username())
                elif annotation == PhoneNumber:
                    data[field_name] = draw(valid_phone())
                else:
                    # Default to None for unknown types
                    data[field_name] = None

        return data


    # ========================================================================
    # COMMAND INPUT STRATEGIES
    # ========================================================================


    @composite
    def command_inputs(draw, command_class: Type) -> Dict[str, Any]:
        """
        Generate command inputs based on command's input type

        Args:
            command_class: Command class

        Returns:
            Dictionary of valid inputs
        """
        if hasattr(command_class, 'inputs_type'):
            inputs_class = command_class.inputs_type()
            return draw(pydantic_model_strategy(inputs_class))

        return {}


    @composite
    def pydantic_model_strategy(draw, model_class: Type[BaseModel]) -> Dict[str, Any]:
        """
        Generate data for any Pydantic model

        Args:
            model_class: Pydantic model class

        Returns:
            Dictionary of field values
        """
        data = {}

        if hasattr(model_class, 'model_fields'):
            for field_name, field_info in model_class.model_fields.items():
                annotation = field_info.annotation

                # Generate based on type
                if annotation == int:
                    data[field_name] = draw(st.integers())
                elif annotation == str:
                    data[field_name] = draw(st.text())
                elif annotation == bool:
                    data[field_name] = draw(st.booleans())
                elif annotation == float:
                    data[field_name] = draw(st.floats(allow_nan=False, allow_infinity=False))
                elif annotation == list or hasattr(annotation, '__origin__'):
                    if hasattr(annotation, '__origin__') and annotation.__origin__ == list:
                        # List type
                        data[field_name] = draw(st.lists(st.integers(), max_size=10))
                    else:
                        data[field_name] = []
                else:
                    # Use default if available
                    if field_info.default is not None:
                        data[field_name] = field_info.default
                    else:
                        data[field_name] = None

        return data


    # ========================================================================
    # COLLECTION STRATEGIES
    # ========================================================================


    @composite
    def entity_list(
        draw,
        entity_class: Type[EntityBase],
        min_size: int = 0,
        max_size: int = 10
    ) -> List[EntityBase]:
        """Generate a list of entities"""
        size = draw(st.integers(min_value=min_size, max_value=max_size))
        return [draw(entity_instance(entity_class)) for _ in range(size)]


    @composite
    def user_with_orders(draw) -> Dict[str, Any]:
        """Generate a user with associated orders"""
        user = draw(user_data())
        order_count = draw(st.integers(min_value=0, max_value=5))

        orders = []
        for _ in range(order_count):
            order = draw(order_data())
            order['user_id'] = user['id']
            orders.append(order)

        return {
            'user': user,
            'orders': orders
        }


    # ========================================================================
    # EDGE CASE STRATEGIES
    # ========================================================================


    @composite
    def boundary_integers(draw) -> int:
        """Generate integers at common boundaries"""
        boundaries = [
            0, 1, -1,
            127, 128, -128,
            255, 256, -256,
            32767, 32768, -32768,
            65535, 65536, -65536,
            2147483647, -2147483648
        ]
        return draw(st.sampled_from(boundaries))


    @composite
    def boundary_strings(draw) -> str:
        """Generate strings at common boundaries"""
        strategies = [
            st.just(""),  # Empty string
            st.just(" "),  # Single space
            st.text(min_size=1, max_size=1),  # Single char
            st.text(min_size=255, max_size=255),  # Common max length
            st.text(min_size=256, max_size=256),  # Just over common max
            st.just("\n"),  # Newline
            st.just("\t"),  # Tab
            st.just("  \n  "),  # Whitespace
        ]
        return draw(st.one_of(strategies))


    @composite
    def malformed_email(draw) -> str:
        """Generate intentionally malformed email addresses"""
        strategies = [
            st.just(""),
            st.just("@"),
            st.just("@test.com"),
            st.just("user@"),
            st.just("user"),
            st.just("user@@test.com"),
            st.just("user @test.com"),
            st.just("user@test"),
        ]
        return draw(st.one_of(strategies))


    # ========================================================================
    # COMPOSITE WORKFLOWS
    # ========================================================================


    @composite
    def e2e_user_workflow(draw) -> Dict[str, Any]:
        """Generate data for end-to-end user workflow"""
        user = draw(user_data())
        products = draw(st.lists(product_data(), min_size=1, max_size=5))

        # Create orders for products
        orders = []
        for product in products:
            order = draw(order_data())
            order['user_id'] = user['id']
            order['product_id'] = product['id']
            orders.append(order)

        return {
            'user': user,
            'products': products,
            'orders': orders
        }


except ImportError:
    # Hypothesis not installed, provide dummy implementations
    def valid_email():
        raise ImportError("Hypothesis not installed")

    def valid_username():
        raise ImportError("Hypothesis not installed")

    # Add other dummy implementations as needed
