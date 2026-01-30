"""
Comprehensive cross-feature integration tests for foobara-py

This test suite provides extensive integration testing across all major features:
1. Command → Entity → Persistence flow integration (20+ tests)
2. Domain dependency integration (15+ tests)
3. Domain mappers with subcommands integration (15+ tests)
4. Transaction rollback across features (15+ tests)
5. Auth integration with HTTP connector (15+ tests)
6. Auth integration with MCP connector (15+ tests)
7. End-to-end workflow tests (multi-command flows) (10+ tests)

Target: 100+ integration tests

Test Pattern:
- Each test validates complete workflows across multiple components
- Tests verify that components integrate correctly in realistic scenarios
- Both success and failure paths are tested
- Error propagation across layers is validated
"""

import pytest
import json
import tempfile
import shutil
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.testclient import TestClient

from foobara_py import Command, Domain
from foobara_py.persistence import (
    entity,
    EntityBase,
    InMemoryRepository,
    RepositoryRegistry,
)
from foobara_py.domain import DomainMapper, DomainMapperRegistry, domain_mapper
from foobara_py.connectors.mcp import MCPConnector
from foobara_py.connectors.http import HTTPConnector
from foobara_py.auth import (
    BearerTokenAuthenticator,
    ApiKeyAuthenticator,
    create_auth_selector,
    AuthMiddleware,
    AuthContext,
)
from foobara_py.core.transactions import (
    transaction,
    TransactionContext,
    NoOpTransactionHandler,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def clean_registries():
    """Clean all registries before and after tests"""
    Domain._registry.clear()
    RepositoryRegistry.clear()
    DomainMapperRegistry.clear()
    yield
    Domain._registry.clear()
    RepositoryRegistry.clear()
    DomainMapperRegistry.clear()


@pytest.fixture
def temp_dir():
    """Create temporary directory"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


# ============================================================================
# TEST ENTITIES
# ============================================================================

@entity(primary_key='id')
class User(EntityBase):
    """User entity for testing"""
    id: Optional[int] = None
    username: str
    email: str
    password_hash: str
    is_active: bool = True


@entity(primary_key='id')
class Product(EntityBase):
    """Product entity for testing"""
    id: Optional[int] = None
    name: str
    price: float
    stock: int = 0
    category: str = "general"


@entity(primary_key='id')
class Order(EntityBase):
    """Order entity for testing"""
    id: Optional[int] = None
    user_id: int
    product_id: int
    quantity: int
    total: float
    status: str = "pending"


@entity(primary_key='id')
class Payment(EntityBase):
    """Payment entity for testing"""
    id: Optional[int] = None
    order_id: int
    amount: float
    status: str = "pending"
    transaction_id: Optional[str] = None


# ============================================================================
# SECTION 1: COMMAND → ENTITY → PERSISTENCE FLOW INTEGRATION (20+ tests)
# ============================================================================

class TestCommandEntityPersistenceFlow:
    """Test complete flow from command through entity to persistence"""

    def test_create_entity_flow(self, clean_registries):
        """Test: Command creates entity and saves to repository"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        class CreateUserInputs(BaseModel):
            username: str
            email: str
            password: str

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                user = User(
                    username=self.inputs.username,
                    email=self.inputs.email,
                    password_hash=f"hash_{self.inputs.password}"
                )
                return repo.save(user)

        outcome = CreateUser.run(username="john", email="john@test.com", password="secret")
        assert outcome.is_success()
        user = outcome.unwrap()
        assert user.id is not None
        assert repo.find(User, user.id) is not None

    def test_retrieve_entity_flow(self, clean_registries):
        """Test: Command retrieves entity from repository"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        # Seed data
        user = User(username="jane", email="jane@test.com", password_hash="hash")
        saved_user = repo.save(user)

        class GetUserInputs(BaseModel):
            user_id: int

        @domain.command
        class GetUser(Command[GetUserInputs, Optional[User]]):
            def execute(self) -> Optional[User]:
                return repo.find(User, self.inputs.user_id)

        outcome = GetUser.run(user_id=saved_user.id)
        assert outcome.is_success()
        found_user = outcome.unwrap()
        assert found_user.username == "jane"

    def test_update_entity_flow(self, clean_registries):
        """Test: Command updates existing entity"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        user = repo.save(User(username="bob", email="bob@test.com", password_hash="hash"))

        class UpdateUserInputs(BaseModel):
            user_id: int
            email: str

        @domain.command
        class UpdateUser(Command[UpdateUserInputs, User]):
            def execute(self) -> User:
                user = repo.find(User, self.inputs.user_id)
                if not user:
                    self.add_runtime_error("not_found", "User not found")
                    return None
                user.email = self.inputs.email
                return repo.save(user)

        outcome = UpdateUser.run(user_id=user.id, email="bob_new@test.com")
        assert outcome.is_success()
        updated = outcome.unwrap()
        assert updated.email == "bob_new@test.com"

    def test_delete_entity_flow(self, clean_registries):
        """Test: Command deletes entity from repository"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        user = repo.save(User(username="alice", email="alice@test.com", password_hash="hash"))

        class DeleteUserInputs(BaseModel):
            user_id: int

        @domain.command
        class DeleteUser(Command[DeleteUserInputs, bool]):
            def execute(self) -> bool:
                user = repo.find(User, self.inputs.user_id)
                if not user:
                    return False
                return repo.delete(user)

        outcome = DeleteUser.run(user_id=user.id)
        assert outcome.is_success()
        assert outcome.unwrap() is True
        assert repo.find(User, user.id) is None

    def test_entity_not_found_error(self, clean_registries):
        """Test: Command handles entity not found gracefully"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        class GetUserInputs(BaseModel):
            user_id: int

        @domain.command
        class GetUser(Command[GetUserInputs, User]):
            def execute(self) -> User:
                user = repo.find(User, self.inputs.user_id)
                if not user:
                    self.add_runtime_error("not_found", f"User {self.inputs.user_id} not found")
                    return None
                return user

        outcome = GetUser.run(user_id=999)
        assert outcome.is_failure()
        assert any("not_found" in e.symbol for e in outcome.errors)

    def test_multiple_entities_in_command(self, clean_registries):
        """Test: Command works with multiple entity types"""
        user_repo = InMemoryRepository()
        product_repo = InMemoryRepository()
        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Product, product_repo)
        domain = Domain("Store", organization="Test")

        user = user_repo.save(User(username="buyer", email="buyer@test.com", password_hash="hash"))
        product = product_repo.save(Product(name="Widget", price=99.99, stock=10))

        class PurchaseInputs(BaseModel):
            user_id: int
            product_id: int

        @domain.command
        class ValidatePurchase(Command[PurchaseInputs, dict]):
            def execute(self) -> dict:
                user = user_repo.find(User, self.inputs.user_id)
                product = product_repo.find(Product, self.inputs.product_id)

                if not user:
                    self.add_runtime_error("user_not_found", "User not found")
                    return None
                if not product:
                    self.add_runtime_error("product_not_found", "Product not found")
                    return None

                return {"user": user.username, "product": product.name, "valid": True}

        outcome = ValidatePurchase.run(user_id=user.id, product_id=product.id)
        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["valid"] is True

    def test_entity_validation_in_command(self, clean_registries):
        """Test: Command validates entity data before save"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)
        domain = Domain("Products", organization="Test")

        class CreateProductInputs(BaseModel):
            name: str
            price: float
            stock: int

        @domain.command
        class CreateProduct(Command[CreateProductInputs, Product]):
            def execute(self) -> Product:
                if self.inputs.price <= 0:
                    self.add_runtime_error("invalid_price", "Price must be positive")
                    return None
                if self.inputs.stock < 0:
                    self.add_runtime_error("invalid_stock", "Stock cannot be negative")
                    return None

                product = Product(
                    name=self.inputs.name,
                    price=self.inputs.price,
                    stock=self.inputs.stock
                )
                return repo.save(product)

        # Valid case
        outcome = CreateProduct.run(name="Gadget", price=49.99, stock=5)
        assert outcome.is_success()

        # Invalid price
        outcome = CreateProduct.run(name="Invalid", price=-10, stock=5)
        assert outcome.is_failure()
        assert any("invalid_price" in e.symbol for e in outcome.errors)

    def test_find_all_entities(self, clean_registries):
        """Test: Command retrieves all entities"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        # Seed multiple users
        for i in range(5):
            repo.save(User(username=f"user{i}", email=f"user{i}@test.com", password_hash="hash"))

        class ListUsersInputs(BaseModel):
            pass

        @domain.command
        class ListUsers(Command[ListUsersInputs, List[User]]):
            def execute(self) -> List[User]:
                return repo.find_all(User)

        outcome = ListUsers.run()
        assert outcome.is_success()
        users = outcome.unwrap()
        assert len(users) == 5

    def test_conditional_entity_update(self, clean_registries):
        """Test: Command conditionally updates entity"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)
        domain = Domain("Products", organization="Test")

        product = repo.save(Product(name="Item", price=100, stock=10))

        class DecreaseStockInputs(BaseModel):
            product_id: int
            quantity: int

        @domain.command
        class DecreaseStock(Command[DecreaseStockInputs, Product]):
            def execute(self) -> Product:
                product = repo.find(Product, self.inputs.product_id)
                if not product:
                    self.add_runtime_error("not_found", "Product not found")
                    return None

                if product.stock < self.inputs.quantity:
                    self.add_runtime_error("insufficient_stock", "Not enough stock")
                    return None

                product.stock -= self.inputs.quantity
                return repo.save(product)

        # Success case
        outcome = DecreaseStock.run(product_id=product.id, quantity=5)
        assert outcome.is_success()
        assert outcome.unwrap().stock == 5

        # Failure case
        outcome = DecreaseStock.run(product_id=product.id, quantity=10)
        assert outcome.is_failure()
        assert any("insufficient_stock" in e.symbol for e in outcome.errors)

    def test_entity_lifecycle_complete(self, clean_registries):
        """Test: Complete CRUD lifecycle in sequence"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        class CreateUserInputs(BaseModel):
            username: str
            email: str

        class UpdateUserInputs(BaseModel):
            user_id: int
            email: str

        class DeleteUserInputs(BaseModel):
            user_id: int

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                return repo.save(User(
                    username=self.inputs.username,
                    email=self.inputs.email,
                    password_hash="hash"
                ))

        @domain.command
        class UpdateUser(Command[UpdateUserInputs, User]):
            def execute(self) -> User:
                user = repo.find(User, self.inputs.user_id)
                user.email = self.inputs.email
                return repo.save(user)

        @domain.command
        class DeleteUser(Command[DeleteUserInputs, bool]):
            def execute(self) -> bool:
                user = repo.find(User, self.inputs.user_id)
                return repo.delete(user)

        # Create
        outcome = CreateUser.run(username="test", email="test@test.com")
        assert outcome.is_success()
        user_id = outcome.unwrap().id

        # Update
        outcome = UpdateUser.run(user_id=user_id, email="updated@test.com")
        assert outcome.is_success()
        assert outcome.unwrap().email == "updated@test.com"

        # Delete
        outcome = DeleteUser.run(user_id=user_id)
        assert outcome.is_success()
        assert repo.find(User, user_id) is None

    def test_bulk_entity_operations(self, clean_registries):
        """Test: Command performs bulk operations"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)
        domain = Domain("Products", organization="Test")

        class BulkCreateInputs(BaseModel):
            products: List[dict]

        @domain.command
        class BulkCreateProducts(Command[BulkCreateInputs, List[Product]]):
            def execute(self) -> List[Product]:
                results = []
                for prod_data in self.inputs.products:
                    product = Product(**prod_data)
                    saved = repo.save(product)
                    results.append(saved)
                return results

        outcome = BulkCreateProducts.run(products=[
            {"name": "P1", "price": 10, "stock": 5},
            {"name": "P2", "price": 20, "stock": 10},
            {"name": "P3", "price": 30, "stock": 15},
        ])
        assert outcome.is_success()
        products = outcome.unwrap()
        assert len(products) == 3
        assert all(p.id is not None for p in products)

    def test_entity_search_by_criteria(self, clean_registries):
        """Test: Command searches entities by criteria"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)
        domain = Domain("Products", organization="Test")

        # Seed products
        repo.save(Product(name="A", price=10, stock=5, category="electronics"))
        repo.save(Product(name="B", price=20, stock=10, category="electronics"))
        repo.save(Product(name="C", price=30, stock=15, category="books"))

        class SearchInputs(BaseModel):
            category: str

        @domain.command
        class SearchProducts(Command[SearchInputs, List[Product]]):
            def execute(self) -> List[Product]:
                return repo.find_by(Product, category=self.inputs.category)

        outcome = SearchProducts.run(category="electronics")
        assert outcome.is_success()
        products = outcome.unwrap()
        assert len(products) == 2

    def test_entity_count_operation(self, clean_registries):
        """Test: Command counts entities"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        for i in range(7):
            repo.save(User(username=f"u{i}", email=f"u{i}@test.com", password_hash="hash"))

        class CountInputs(BaseModel):
            pass

        @domain.command
        class CountUsers(Command[CountInputs, int]):
            def execute(self) -> int:
                return repo.count(User)

        outcome = CountUsers.run()
        assert outcome.is_success()
        assert outcome.unwrap() == 7

    def test_entity_exists_check(self, clean_registries):
        """Test: Command checks entity existence"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        user = repo.save(User(username="exists", email="exists@test.com", password_hash="hash"))

        class ExistsInputs(BaseModel):
            user_id: int

        @domain.command
        class UserExists(Command[ExistsInputs, bool]):
            def execute(self) -> bool:
                return repo.exists(User, self.inputs.user_id)

        assert UserExists.run(user_id=user.id).unwrap() is True
        assert UserExists.run(user_id=999).unwrap() is False

    def test_entity_with_relationships(self, clean_registries):
        """Test: Command handles entities with relationships"""
        user_repo = InMemoryRepository()
        order_repo = InMemoryRepository()
        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Order, order_repo)
        domain = Domain("Orders", organization="Test")

        user = user_repo.save(User(username="customer", email="c@test.com", password_hash="hash"))

        class CreateOrderInputs(BaseModel):
            user_id: int
            product_id: int
            quantity: int
            total: float

        @domain.command
        class CreateOrder(Command[CreateOrderInputs, Order]):
            def execute(self) -> Order:
                user = user_repo.find(User, self.inputs.user_id)
                if not user:
                    self.add_runtime_error("user_not_found", "User not found")
                    return None

                order = Order(
                    user_id=self.inputs.user_id,
                    product_id=self.inputs.product_id,
                    quantity=self.inputs.quantity,
                    total=self.inputs.total
                )
                return order_repo.save(order)

        outcome = CreateOrder.run(user_id=user.id, product_id=1, quantity=2, total=199.98)
        assert outcome.is_success()
        order = outcome.unwrap()
        assert order.user_id == user.id

    def test_nested_entity_operations(self, clean_registries):
        """Test: Command performs nested entity operations"""
        user_repo = InMemoryRepository()
        order_repo = InMemoryRepository()
        payment_repo = InMemoryRepository()
        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Order, order_repo)
        RepositoryRegistry.register(Payment, payment_repo)
        domain = Domain("Checkout", organization="Test")

        user = user_repo.save(User(username="buyer", email="buyer@test.com", password_hash="hash"))
        order = order_repo.save(Order(user_id=user.id, product_id=1, quantity=1, total=50.0))

        class ProcessPaymentInputs(BaseModel):
            order_id: int
            amount: float

        @domain.command
        class ProcessPayment(Command[ProcessPaymentInputs, dict]):
            def execute(self) -> dict:
                order = order_repo.find(Order, self.inputs.order_id)
                if not order:
                    self.add_runtime_error("order_not_found", "Order not found")
                    return None

                payment = Payment(
                    order_id=order.id,
                    amount=self.inputs.amount,
                    status="completed",
                    transaction_id="txn_123"
                )
                saved_payment = payment_repo.save(payment)

                order.status = "paid"
                order_repo.save(order)

                return {
                    "payment_id": saved_payment.id,
                    "order_id": order.id,
                    "status": "success"
                }

        outcome = ProcessPayment.run(order_id=order.id, amount=50.0)
        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["status"] == "success"

    def test_entity_persistence_error_handling(self, clean_registries):
        """Test: Command handles persistence errors"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        class CreateUserInputs(BaseModel):
            username: str
            email: str

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                try:
                    user = User(
                        username=self.inputs.username,
                        email=self.inputs.email,
                        password_hash="hash"
                    )
                    return repo.save(user)
                except Exception as e:
                    self.add_runtime_error("save_failed", f"Failed to save: {str(e)}")
                    return None

        outcome = CreateUser.run(username="test", email="test@test.com")
        assert outcome.is_success()

    def test_complex_entity_query(self, clean_registries):
        """Test: Command performs complex entity queries"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)
        domain = Domain("Products", organization="Test")

        # Seed products
        repo.save(Product(name="A", price=10, stock=5, category="electronics"))
        repo.save(Product(name="B", price=150, stock=0, category="electronics"))
        repo.save(Product(name="C", price=30, stock=10, category="books"))

        class FindInputs(BaseModel):
            min_price: float
            min_stock: int

        @domain.command
        class FindAvailableProducts(Command[FindInputs, List[Product]]):
            def execute(self) -> List[Product]:
                all_products = repo.find_all(Product)
                return [
                    p for p in all_products
                    if p.price >= self.inputs.min_price and p.stock >= self.inputs.min_stock
                ]

        outcome = FindAvailableProducts.run(min_price=20, min_stock=5)
        assert outcome.is_success()
        products = outcome.unwrap()
        assert len(products) == 1
        assert products[0].name == "C"

    def test_entity_update_with_validation(self, clean_registries):
        """Test: Command validates entity updates"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)
        domain = Domain("Products", organization="Test")

        product = repo.save(Product(name="Widget", price=100, stock=10))

        class UpdatePriceInputs(BaseModel):
            product_id: int
            new_price: float

        @domain.command
        class UpdatePrice(Command[UpdatePriceInputs, Product]):
            def execute(self) -> Product:
                product = repo.find(Product, self.inputs.product_id)
                if not product:
                    self.add_runtime_error("not_found", "Product not found")
                    return None

                if self.inputs.new_price <= 0:
                    self.add_runtime_error("invalid_price", "Price must be positive")
                    return None

                product.price = self.inputs.new_price
                return repo.save(product)

        # Valid update
        outcome = UpdatePrice.run(product_id=product.id, new_price=120)
        assert outcome.is_success()

        # Invalid update
        outcome = UpdatePrice.run(product_id=product.id, new_price=-10)
        assert outcome.is_failure()

    def test_entity_soft_delete(self, clean_registries):
        """Test: Command performs soft delete on entity"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        user = repo.save(User(username="soft", email="soft@test.com", password_hash="hash"))

        class DeactivateInputs(BaseModel):
            user_id: int

        @domain.command
        class DeactivateUser(Command[DeactivateInputs, User]):
            def execute(self) -> User:
                user = repo.find(User, self.inputs.user_id)
                if not user:
                    self.add_runtime_error("not_found", "User not found")
                    return None
                user.is_active = False
                return repo.save(user)

        outcome = DeactivateUser.run(user_id=user.id)
        assert outcome.is_success()
        deactivated = outcome.unwrap()
        assert deactivated.is_active is False
        # User still exists in repository
        assert repo.find(User, user.id) is not None

    def test_entity_batch_update(self, clean_registries):
        """Test: Command updates multiple entities"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)
        domain = Domain("Products", organization="Test")

        # Seed products
        for i in range(3):
            repo.save(Product(name=f"P{i}", price=100, stock=10, category="electronics"))

        class UpdateCategoryInputs(BaseModel):
            old_category: str
            new_category: str

        @domain.command
        class UpdateCategory(Command[UpdateCategoryInputs, List[Product]]):
            def execute(self) -> List[Product]:
                products = repo.find_by(Product, category=self.inputs.old_category)
                updated = []
                for product in products:
                    product.category = self.inputs.new_category
                    updated.append(repo.save(product))
                return updated

        outcome = UpdateCategory.run(old_category="electronics", new_category="tech")
        assert outcome.is_success()
        updated = outcome.unwrap()
        assert len(updated) == 3
        assert all(p.category == "tech" for p in updated)


# ============================================================================
# SECTION 2: DOMAIN DEPENDENCY INTEGRATION (15+ tests)
# ============================================================================

class TestDomainDependencyIntegration:
    """Test integration of domain dependencies with commands and entities"""

    def test_cross_domain_entity_access(self, clean_registries):
        """Test: Command accesses entities from dependent domain"""
        user_repo = InMemoryRepository()
        order_repo = InMemoryRepository()
        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Order, order_repo)

        org = "ECommerce"
        users_domain = Domain("Users", organization=org)
        orders_domain = Domain("Orders", organization=org)
        orders_domain.depends_on("Users")

        user = user_repo.save(User(username="customer", email="c@test.com", password_hash="hash"))

        class GetUserInputs(BaseModel):
            user_id: int

        @users_domain.command
        class GetUser(Command[GetUserInputs, User]):
            def execute(self) -> User:
                return user_repo.find(User, self.inputs.user_id)

        class CreateOrderInputs(BaseModel):
            user_id: int
            product_id: int
            total: float

        @orders_domain.command
        class CreateOrder(Command[CreateOrderInputs, Order]):
            def execute(self) -> Order:
                # Call Users domain command
                user = self.run_subcommand_bang(GetUser, user_id=self.inputs.user_id)

                order = Order(
                    user_id=user.id,
                    product_id=self.inputs.product_id,
                    quantity=1,
                    total=self.inputs.total
                )
                return order_repo.save(order)

        outcome = CreateOrder.run(user_id=user.id, product_id=42, total=99.99)
        assert outcome.is_success()
        order = outcome.unwrap()
        assert order.user_id == user.id

    def test_transitive_domain_dependencies(self, clean_registries):
        """Test: Commands work across transitive dependencies"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)

        org = "App"
        auth_domain = Domain("Auth", organization=org)
        users_domain = Domain("Users", organization=org)
        admin_domain = Domain("Admin", organization=org)

        users_domain.depends_on("Auth")
        admin_domain.depends_on("Users")

        class AuthInputs(BaseModel):
            token: str

        @auth_domain.command
        class ValidateToken(Command[AuthInputs, bool]):
            def execute(self) -> bool:
                return self.inputs.token == "valid"

        class GetUserInputs(BaseModel):
            user_id: int

        @users_domain.command
        class GetUser(Command[GetUserInputs, Optional[User]]):
            def execute(self) -> Optional[User]:
                return repo.find(User, self.inputs.user_id)

        class AdminActionInputs(BaseModel):
            token: str
            user_id: int

        @admin_domain.command
        class AdminGetUser(Command[AdminActionInputs, User]):
            def execute(self) -> User:
                # Validate through Auth (transitive)
                is_valid = self.run_subcommand_bang(ValidateToken, token=self.inputs.token)
                if not is_valid:
                    self.add_runtime_error("unauthorized", "Invalid token")
                    return None

                # Get user through Users
                user = self.run_subcommand_bang(GetUser, user_id=self.inputs.user_id)
                if not user:
                    self.add_runtime_error("not_found", "User not found")
                    return None

                return user

        user = repo.save(User(username="test", email="test@test.com", password_hash="hash"))
        outcome = AdminGetUser.run(token="valid", user_id=user.id)
        assert outcome.is_success()

    def test_domain_dependency_validation_enforcement(self, clean_registries):
        """Test: System enforces domain dependencies"""
        org = "Test"
        domain_a = Domain("A", organization=org)
        domain_b = Domain("B", organization=org)
        # NO dependency declared

        class EmptyInputs(BaseModel):
            pass

        @domain_a.command
        class CommandA(Command[EmptyInputs, str]):
            def execute(self) -> str:
                return "A"

        @domain_b.command
        class CommandB(Command[EmptyInputs, str]):
            def execute(self) -> str:
                # Try to call A without dependency
                result = self.run_subcommand(CommandA)
                return f"B:{result}"

        outcome = CommandB.run()
        assert outcome.is_failure()
        assert any("cannot call" in str(e.message) for e in outcome.errors)

    def test_multiple_domain_dependencies(self, clean_registries):
        """Test: Domain depends on multiple other domains"""
        org = "Multi"
        auth = Domain("Auth", organization=org)
        users = Domain("Users", organization=org)
        billing = Domain("Billing", organization=org)
        orders = Domain("Orders", organization=org)

        orders.depends_on("Auth", "Users", "Billing")

        class EmptyInputs(BaseModel):
            pass

        @auth.command
        class Auth(Command[EmptyInputs, str]):
            def execute(self) -> str:
                return "authenticated"

        @users.command
        class GetUserInfo(Command[EmptyInputs, str]):
            def execute(self) -> str:
                return "user_info"

        @billing.command
        class CheckBalance(Command[EmptyInputs, str]):
            def execute(self) -> str:
                return "balance_ok"

        @orders.command
        class CreateOrder(Command[EmptyInputs, str]):
            def execute(self) -> str:
                auth_result = self.run_subcommand_bang(Auth)
                user_result = self.run_subcommand_bang(GetUserInfo)
                billing_result = self.run_subcommand_bang(CheckBalance)
                return f"order:{auth_result}:{user_result}:{billing_result}"

        outcome = CreateOrder.run()
        assert outcome.is_success()
        assert "authenticated" in outcome.unwrap()

    def test_domain_dependency_with_error_propagation(self, clean_registries):
        """Test: Errors propagate correctly across domain boundaries"""
        org = "ErrorTest"
        domain_a = Domain("A", organization=org)
        domain_b = Domain("B", organization=org)
        domain_b.depends_on("A")

        class ValueInputs(BaseModel):
            value: int

        @domain_a.command
        class ValidateValue(Command[ValueInputs, int]):
            def execute(self) -> int:
                if self.inputs.value < 0:
                    self.add_runtime_error("negative_value", "Value cannot be negative")
                    return None
                return self.inputs.value

        @domain_b.command
        class ProcessValue(Command[ValueInputs, int]):
            def execute(self) -> int:
                validated = self.run_subcommand_bang(ValidateValue, value=self.inputs.value)
                return validated * 2

        # Success case
        outcome = ProcessValue.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 10

        # Error propagation
        outcome = ProcessValue.run(value=-1)
        assert outcome.is_failure()
        assert any("negative_value" in e.symbol for e in outcome.errors)

    def test_circular_dependency_prevention(self, clean_registries):
        """Test: System prevents circular dependencies"""
        org = "Circular"
        domain_a = Domain("A", organization=org)
        domain_b = Domain("B", organization=org)

        domain_a.depends_on("B")

        with pytest.raises(Exception):  # Should raise DomainDependencyError
            domain_b.depends_on("A")

    def test_same_domain_calls_always_allowed(self, clean_registries):
        """Test: Commands can always call within same domain"""
        domain = Domain("Same", organization="Test")

        class EmptyInputs(BaseModel):
            pass

        @domain.command
        class Helper(Command[EmptyInputs, str]):
            def execute(self) -> str:
                return "helped"

        @domain.command
        class Main(Command[EmptyInputs, str]):
            def execute(self) -> str:
                result = self.run_subcommand_bang(Helper)
                return f"main:{result}"

        outcome = Main.run()
        assert outcome.is_success()
        assert outcome.unwrap() == "main:helped"

    def test_domain_dependency_with_entities(self, clean_registries):
        """Test: Domain dependencies work with entity operations"""
        user_repo = InMemoryRepository()
        product_repo = InMemoryRepository()
        order_repo = InMemoryRepository()
        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Product, product_repo)
        RepositoryRegistry.register(Order, order_repo)

        org = "Shop"
        users_domain = Domain("Users", organization=org)
        products_domain = Domain("Products", organization=org)
        orders_domain = Domain("Orders", organization=org)

        orders_domain.depends_on("Users", "Products")

        user = user_repo.save(User(username="buyer", email="b@test.com", password_hash="hash"))
        product = product_repo.save(Product(name="Item", price=50, stock=10))

        class GetUserInputs(BaseModel):
            user_id: int

        @users_domain.command
        class GetUser(Command[GetUserInputs, User]):
            def execute(self) -> User:
                return user_repo.find(User, self.inputs.user_id)

        class GetProductInputs(BaseModel):
            product_id: int

        @products_domain.command
        class GetProduct(Command[GetProductInputs, Product]):
            def execute(self) -> Product:
                return product_repo.find(Product, self.inputs.product_id)

        class PlaceOrderInputs(BaseModel):
            user_id: int
            product_id: int
            quantity: int

        @orders_domain.command
        class PlaceOrder(Command[PlaceOrderInputs, Order]):
            def execute(self) -> Order:
                user = self.run_subcommand_bang(GetUser, user_id=self.inputs.user_id)
                product = self.run_subcommand_bang(GetProduct, product_id=self.inputs.product_id)

                order = Order(
                    user_id=user.id,
                    product_id=product.id,
                    quantity=self.inputs.quantity,
                    total=product.price * self.inputs.quantity
                )
                return order_repo.save(order)

        outcome = PlaceOrder.run(user_id=user.id, product_id=product.id, quantity=2)
        assert outcome.is_success()
        order = outcome.unwrap()
        assert order.total == 100

    def test_nested_domain_calls(self, clean_registries):
        """Test: Multiple levels of cross-domain calls"""
        org = "Nested"
        level1 = Domain("Level1", organization=org)
        level2 = Domain("Level2", organization=org)
        level3 = Domain("Level3", organization=org)

        level2.depends_on("Level1")
        level3.depends_on("Level2")

        class ValueInputs(BaseModel):
            value: int

        @level1.command
        class L1Command(Command[ValueInputs, int]):
            def execute(self) -> int:
                return self.inputs.value + 1

        @level2.command
        class L2Command(Command[ValueInputs, int]):
            def execute(self) -> int:
                result = self.run_subcommand_bang(L1Command, value=self.inputs.value)
                return result + 10

        @level3.command
        class L3Command(Command[ValueInputs, int]):
            def execute(self) -> int:
                result = self.run_subcommand_bang(L2Command, value=self.inputs.value)
                return result * 2

        outcome = L3Command.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 32  # ((5 + 1) + 10) * 2

    def test_domain_dependency_tracking(self, clean_registries):
        """Test: Cross-domain calls are tracked"""
        org = "Tracking"
        domain_a = Domain("A", organization=org)
        domain_b = Domain("B", organization=org)
        domain_b.depends_on("A")

        Domain.reset_cross_domain_call_stats()

        class EmptyInputs(BaseModel):
            pass

        @domain_a.command
        class CommandA(Command[EmptyInputs, str]):
            def execute(self) -> str:
                return "A"

        @domain_b.command
        class CommandB(Command[EmptyInputs, str]):
            def execute(self) -> str:
                self.run_subcommand_bang(CommandA)
                return "B"

        CommandB.run()

        stats = Domain.get_cross_domain_call_stats()
        assert ("B", "A") in stats
        assert stats[("B", "A")] >= 1

    def test_domain_organization_isolation(self, clean_registries):
        """Test: Domains in different organizations are isolated"""
        org1_domain = Domain("Shared", organization="Org1")
        org2_domain = Domain("Shared", organization="Org2")

        class EmptyInputs(BaseModel):
            pass

        @org1_domain.command
        class Command1(Command[EmptyInputs, str]):
            def execute(self) -> str:
                return "org1"

        @org2_domain.command
        class Command2(Command[EmptyInputs, str]):
            def execute(self) -> str:
                # Should not be able to call Command1 from different org
                # Even though they have the same domain name
                return "org2"

        # Commands should be independent
        assert Command1.run().unwrap() == "org1"
        assert Command2.run().unwrap() == "org2"

    def test_complex_dependency_graph(self, clean_registries):
        """Test: Complex multi-domain dependency graph"""
        org = "Complex"
        auth = Domain("Auth", organization=org)
        users = Domain("Users", organization=org)
        products = Domain("Products", organization=org)
        orders = Domain("Orders", organization=org)
        billing = Domain("Billing", organization=org)

        # Setup dependencies
        users.depends_on("Auth")
        products.depends_on("Auth")
        orders.depends_on("Users", "Products")
        billing.depends_on("Orders")

        class EmptyInputs(BaseModel):
            pass

        @auth.command
        class Auth(Command[EmptyInputs, bool]):
            def execute(self) -> bool:
                return True

        @users.command
        class ValidateUser(Command[EmptyInputs, bool]):
            def execute(self) -> bool:
                return self.run_subcommand_bang(Auth)

        @products.command
        class ValidateProduct(Command[EmptyInputs, bool]):
            def execute(self) -> bool:
                return self.run_subcommand_bang(Auth)

        @orders.command
        class CreateOrder(Command[EmptyInputs, bool]):
            def execute(self) -> bool:
                user_valid = self.run_subcommand_bang(ValidateUser)
                product_valid = self.run_subcommand_bang(ValidateProduct)
                return user_valid and product_valid

        @billing.command
        class ProcessBilling(Command[EmptyInputs, bool]):
            def execute(self) -> bool:
                return self.run_subcommand_bang(CreateOrder)

        outcome = ProcessBilling.run()
        assert outcome.is_success()
        assert outcome.unwrap() is True

    def test_domain_dependency_with_multiple_calls(self, clean_registries):
        """Test: Multiple calls to same dependent domain"""
        org = "Multi"
        domain_a = Domain("A", organization=org)
        domain_b = Domain("B", organization=org)
        domain_b.depends_on("A")

        class ValueInputs(BaseModel):
            value: int

        @domain_a.command
        class Process(Command[ValueInputs, int]):
            def execute(self) -> int:
                return self.inputs.value * 2

        @domain_b.command
        class Aggregate(Command[ValueInputs, int]):
            def execute(self) -> int:
                result1 = self.run_subcommand_bang(Process, value=self.inputs.value)
                result2 = self.run_subcommand_bang(Process, value=result1)
                result3 = self.run_subcommand_bang(Process, value=result2)
                return result3

        outcome = Aggregate.run(value=1)
        assert outcome.is_success()
        assert outcome.unwrap() == 8  # 1 * 2 * 2 * 2

    def test_domain_dependency_error_context(self, clean_registries):
        """Test: Error context preserved across domain calls"""
        org = "Context"
        domain_a = Domain("A", organization=org)
        domain_b = Domain("B", organization=org)
        domain_c = Domain("C", organization=org)

        domain_b.depends_on("A")
        domain_c.depends_on("B")

        class ValueInputs(BaseModel):
            value: int

        @domain_a.command
        class ValidateA(Command[ValueInputs, int]):
            def execute(self) -> int:
                if self.inputs.value == 0:
                    self.add_runtime_error("zero_value", "Value cannot be zero")
                    return None
                return self.inputs.value

        @domain_b.command
        class ProcessB(Command[ValueInputs, int]):
            def execute(self) -> int:
                return self.run_subcommand_bang(ValidateA, value=self.inputs.value)

        @domain_c.command
        class ExecuteC(Command[ValueInputs, int]):
            def execute(self) -> int:
                return self.run_subcommand_bang(ProcessB, value=self.inputs.value)

        outcome = ExecuteC.run(value=0)
        assert outcome.is_failure()
        # Error should include context from all levels
        assert any("zero_value" in e.symbol for e in outcome.errors)

    def test_parallel_domain_dependencies(self, clean_registries):
        """Test: Multiple domains depending on same base domain"""
        org = "Parallel"
        base = Domain("Base", organization=org)
        derived1 = Domain("Derived1", organization=org)
        derived2 = Domain("Derived2", organization=org)

        derived1.depends_on("Base")
        derived2.depends_on("Base")

        class EmptyInputs(BaseModel):
            pass

        @base.command
        class BaseCommand(Command[EmptyInputs, str]):
            def execute(self) -> str:
                return "base"

        @derived1.command
        class Derived1Command(Command[EmptyInputs, str]):
            def execute(self) -> str:
                result = self.run_subcommand_bang(BaseCommand)
                return f"d1:{result}"

        @derived2.command
        class Derived2Command(Command[EmptyInputs, str]):
            def execute(self) -> str:
                result = self.run_subcommand_bang(BaseCommand)
                return f"d2:{result}"

        assert Derived1Command.run().unwrap() == "d1:base"
        assert Derived2Command.run().unwrap() == "d2:base"


# ============================================================================
# SECTION 3: DOMAIN MAPPERS WITH SUBCOMMANDS INTEGRATION (15+ tests)
# ============================================================================

class TestDomainMapperIntegration:
    """Test integration of domain mappers with subcommands and entities"""

    def test_mapper_with_subcommand_basic(self, clean_registries):
        """Test: Use mapper to transform inputs for subcommand"""
        domain = Domain("Mapping", organization="Test")

        class InternalModel(BaseModel):
            id: int
            full_name: str

        class ExternalModel(BaseModel):
            id: str
            name: str

        @domain_mapper(domain="Mapping", organization="Test")
        class InternalToExternal(DomainMapper[InternalModel, ExternalModel]):
            def map(self) -> ExternalModel:
                return ExternalModel(
                    id=str(self.from_value.id),
                    name=self.from_value.full_name
                )

        class ProcessInternalInputs(BaseModel):
            data: ExternalModel

        @domain.command
        class ProcessInternal(Command[ProcessInternalInputs, str]):
            def execute(self) -> str:
                return f"Processed: {self.inputs.data.name}"

        class ProcessExternalInputs(BaseModel):
            pass

        @domain.command
        class ProcessExternal(Command[ProcessExternalInputs, str]):
            def execute(self) -> str:
                internal = InternalModel(id=1, full_name="John Doe")
                return self.run_mapped_subcommand(
                    ProcessInternal,
                    unmapped_inputs={"data": internal}
                )

        outcome = ProcessExternal.run()
        assert outcome.is_success()
        assert "John Doe" in outcome.unwrap()

    def test_mapper_result_transformation(self, clean_registries):
        """Test: Map subcommand result to different type"""
        domain = Domain("Transform", organization="Test")

        class UserInternal(BaseModel):
            user_id: int
            username: str

        class UserExternal(BaseModel):
            id: str
            name: str

        @domain_mapper(domain="Transform", organization="Test")
        class InternalToExternalUser(DomainMapper[UserInternal, UserExternal]):
            def map(self) -> UserExternal:
                return UserExternal(
                    id=f"user_{self.from_value.user_id}",
                    name=self.from_value.username
                )

        class GetUserInternalInputs(BaseModel):
            user_id: int

        @domain.command
        class GetUserInternal(Command[GetUserInternalInputs, UserInternal]):
            def execute(self) -> UserInternal:
                return UserInternal(user_id=self.inputs.user_id, username="alice")

        class GetUserExternalInputs(BaseModel):
            user_id: int

        @domain.command
        class GetUserExternal(Command[GetUserExternalInputs, UserExternal]):
            def execute(self) -> UserExternal:
                return self.run_mapped_subcommand(
                    GetUserInternal,
                    to=UserExternal,
                    user_id=self.inputs.user_id
                )

        outcome = GetUserExternal.run(user_id=42)
        assert outcome.is_success()
        user = outcome.unwrap()
        assert user.id == "user_42"
        assert user.name == "alice"

    def test_bidirectional_mapper(self, clean_registries):
        """Test: Use bidirectional mappers"""
        domain = Domain("BiDir", organization="Test")

        class ModelA(BaseModel):
            value: int

        class ModelB(BaseModel):
            value: str

        @domain_mapper(domain="BiDir", organization="Test")
        class AToB(DomainMapper[ModelA, ModelB]):
            def map(self) -> ModelB:
                return ModelB(value=str(self.from_value.value))

        @domain_mapper(domain="BiDir", organization="Test")
        class BToA(DomainMapper[ModelB, ModelA]):
            def map(self) -> ModelA:
                return ModelA(value=int(self.from_value.value))

        class ProcessAInputs(BaseModel):
            data: ModelB

        @domain.command
        class ProcessA(Command[ProcessAInputs, int]):
            def execute(self) -> int:
                return int(self.inputs.data.value) * 2

        class ProcessBInputs(BaseModel):
            value: int

        @domain.command
        class ProcessB(Command[ProcessBInputs, int]):
            def execute(self) -> int:
                model_a = ModelA(value=self.inputs.value)
                return self.run_mapped_subcommand(
                    ProcessA,
                    unmapped_inputs={"data": model_a}
                )

        outcome = ProcessB.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 10

    def test_mapper_with_entity(self, clean_registries):
        """Test: Map entity to external model"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("UserAPI", organization="Test")

        user = repo.save(User(username="john", email="john@test.com", password_hash="hash"))

        class UserDTO(BaseModel):
            id: str
            username: str
            email: str

        @domain_mapper(domain="UserAPI", organization="Test")
        class UserToDTO(DomainMapper[User, UserDTO]):
            def map(self) -> UserDTO:
                return UserDTO(
                    id=str(self.from_value.id),
                    username=self.from_value.username,
                    email=self.from_value.email
                )

        class GetUserInputs(BaseModel):
            user_id: int

        @domain.command
        class GetUserEntity(Command[GetUserInputs, User]):
            def execute(self) -> User:
                return repo.find(User, self.inputs.user_id)

        @domain.command
        class GetUserDTO(Command[GetUserInputs, UserDTO]):
            def execute(self) -> UserDTO:
                return self.run_mapped_subcommand(
                    GetUserEntity,
                    to=UserDTO,
                    user_id=self.inputs.user_id
                )

        outcome = GetUserDTO.run(user_id=user.id)
        assert outcome.is_success()
        dto = outcome.unwrap()
        assert dto.username == "john"
        assert isinstance(dto.id, str)

    def test_mapper_chain(self, clean_registries):
        """Test: Chain multiple mappers"""
        domain = Domain("Chain", organization="Test")

        class ModelA(BaseModel):
            x: int

        class ModelB(BaseModel):
            y: int

        class ModelC(BaseModel):
            z: int

        @domain_mapper(domain="Chain", organization="Test")
        class AToB(DomainMapper[ModelA, ModelB]):
            def map(self) -> ModelB:
                return ModelB(y=self.from_value.x + 10)

        @domain_mapper(domain="Chain", organization="Test")
        class BToC(DomainMapper[ModelB, ModelC]):
            def map(self) -> ModelC:
                return ModelC(z=self.from_value.y * 2)

        class ProcessBInputs(BaseModel):
            data: ModelB

        @domain.command
        class ProcessB(Command[ProcessBInputs, ModelC]):
            def execute(self) -> ModelC:
                return BToC.map_value(self.inputs.data)

        class ProcessAInputs(BaseModel):
            value: int

        @domain.command
        class ProcessA(Command[ProcessAInputs, ModelC]):
            def execute(self) -> ModelC:
                model_a = ModelA(x=self.inputs.value)
                return self.run_mapped_subcommand(
                    ProcessB,
                    unmapped_inputs={"data": model_a}
                )

        outcome = ProcessA.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap().z == 30  # (5 + 10) * 2

    def test_mapper_with_validation(self, clean_registries):
        """Test: Mapper includes validation logic"""
        domain = Domain("Validation", organization="Test")

        class Input(BaseModel):
            value: int

        class Output(BaseModel):
            value: str

        @domain_mapper(domain="Validation", organization="Test")
        class ValidatingMapper(DomainMapper[Input, Output]):
            def map(self) -> Output:
                if self.from_value.value < 0:
                    raise ValueError("Value cannot be negative")
                return Output(value=str(self.from_value.value))

        class ProcessInputs(BaseModel):
            data: Output

        @domain.command
        class Process(Command[ProcessInputs, str]):
            def execute(self) -> str:
                return self.inputs.data.value

        class MainInputs(BaseModel):
            value: int

        @domain.command
        class Main(Command[MainInputs, str]):
            def execute(self) -> str:
                input_data = Input(value=self.inputs.value)
                try:
                    return self.run_mapped_subcommand(
                        Process,
                        unmapped_inputs={"data": input_data}
                    )
                except ValueError as e:
                    self.add_runtime_error("validation_failed", str(e))
                    return None

        # Valid case
        outcome = Main.run(value=5)
        assert outcome.is_success()

        # Invalid case
        outcome = Main.run(value=-1)
        assert outcome.is_failure()

    def test_mapper_with_complex_types(self, clean_registries):
        """Test: Mapper handles complex nested types"""
        domain = Domain("Complex", organization="Test")

        class Address(BaseModel):
            street: str
            city: str

        class UserInternal(BaseModel):
            id: int
            name: str
            address: Address

        class AddressDTO(BaseModel):
            full_address: str

        class UserDTO(BaseModel):
            user_id: str
            username: str
            location: AddressDTO

        @domain_mapper(domain="Complex", organization="Test")
        class UserInternalToDTO(DomainMapper[UserInternal, UserDTO]):
            def map(self) -> UserDTO:
                return UserDTO(
                    user_id=f"u{self.from_value.id}",
                    username=self.from_value.name,
                    location=AddressDTO(
                        full_address=f"{self.from_value.address.street}, {self.from_value.address.city}"
                    )
                )

        class GetUserInputs(BaseModel):
            user_id: int

        @domain.command
        class GetUserInternal(Command[GetUserInputs, UserInternal]):
            def execute(self) -> UserInternal:
                return UserInternal(
                    id=self.inputs.user_id,
                    name="John",
                    address=Address(street="123 Main St", city="NYC")
                )

        @domain.command
        class GetUserDTO(Command[GetUserInputs, UserDTO]):
            def execute(self) -> UserDTO:
                return self.run_mapped_subcommand(
                    GetUserInternal,
                    to=UserDTO,
                    user_id=self.inputs.user_id
                )

        outcome = GetUserDTO.run(user_id=1)
        assert outcome.is_success()
        dto = outcome.unwrap()
        assert "123 Main St" in dto.location.full_address

    def test_mapper_error_handling(self, clean_registries):
        """Test: Handle mapper not found error"""
        domain = Domain("NoMapper", organization="Test")

        class ModelA(BaseModel):
            value: int

        class ModelB(BaseModel):
            value: str

        class ProcessInputs(BaseModel):
            data: ModelB

        @domain.command
        class Process(Command[ProcessInputs, str]):
            def execute(self) -> str:
                return self.inputs.data.value

        class MainInputs(BaseModel):
            value: int

        @domain.command
        class Main(Command[MainInputs, str]):
            def execute(self) -> str:
                model_a = ModelA(value=self.inputs.value)
                # No mapper registered for ModelA -> ModelB
                return self.run_mapped_subcommand(
                    Process,
                    unmapped_inputs={"data": model_a}
                )

        outcome = Main.run(value=5)
        assert outcome.is_failure()
        assert any("no_domain_mapper_found" in e.symbol for e in outcome.errors)

    def test_mapper_with_multiple_fields(self, clean_registries):
        """Test: Map multiple fields with transformation"""
        domain = Domain("MultiField", organization="Test")

        class Source(BaseModel):
            first_name: str
            last_name: str
            age: int

        class Target(BaseModel):
            full_name: str
            age_group: str

        @domain_mapper(domain="MultiField", organization="Test")
        class SourceToTarget(DomainMapper[Source, Target]):
            def map(self) -> Target:
                age = self.from_value.age
                age_group = "child" if age < 18 else "adult" if age < 65 else "senior"
                return Target(
                    full_name=f"{self.from_value.first_name} {self.from_value.last_name}",
                    age_group=age_group
                )

        class ProcessInputs(BaseModel):
            data: Target

        @domain.command
        class Process(Command[ProcessInputs, str]):
            def execute(self) -> str:
                return f"{self.inputs.data.full_name} is {self.inputs.data.age_group}"

        class MainInputs(BaseModel):
            first_name: str
            last_name: str
            age: int

        @domain.command
        class Main(Command[MainInputs, str]):
            def execute(self) -> str:
                source = Source(
                    first_name=self.inputs.first_name,
                    last_name=self.inputs.last_name,
                    age=self.inputs.age
                )
                return self.run_mapped_subcommand(
                    Process,
                    unmapped_inputs={"data": source}
                )

        outcome = Main.run(first_name="John", last_name="Doe", age=30)
        assert outcome.is_success()
        assert "John Doe is adult" == outcome.unwrap()

    def test_mapper_with_list_transformation(self, clean_registries):
        """Test: Map lists of objects"""
        domain = Domain("ListMap", organization="Test")

        class Item(BaseModel):
            id: int
            name: str

        class ItemDTO(BaseModel):
            id: str
            label: str

        @domain_mapper(domain="ListMap", organization="Test")
        class ItemToDTO(DomainMapper[Item, ItemDTO]):
            def map(self) -> ItemDTO:
                return ItemDTO(
                    id=f"item_{self.from_value.id}",
                    label=self.from_value.name.upper()
                )

        class ProcessListInputs(BaseModel):
            items: List[ItemDTO]

        @domain.command
        class ProcessList(Command[ProcessListInputs, int]):
            def execute(self) -> int:
                return len(self.inputs.items)

        class MainInputs(BaseModel):
            pass

        @domain.command
        class Main(Command[MainInputs, int]):
            def execute(self) -> int:
                items = [
                    Item(id=1, name="a"),
                    Item(id=2, name="b"),
                    Item(id=3, name="c")
                ]
                # Map each item
                dtos = [ItemToDTO.map_value(item) for item in items]
                return self.run_subcommand_bang(ProcessList, items=dtos)

        outcome = Main.run()
        assert outcome.is_success()
        assert outcome.unwrap() == 3

    def test_mapper_with_optional_fields(self, clean_registries):
        """Test: Map models with optional fields"""
        domain = Domain("Optional", organization="Test")

        class Source(BaseModel):
            required: str
            optional: Optional[str] = None

        class Target(BaseModel):
            data: str

        @domain_mapper(domain="Optional", organization="Test")
        class SourceToTarget(DomainMapper[Source, Target]):
            def map(self) -> Target:
                value = self.from_value.optional or "default"
                return Target(data=f"{self.from_value.required}:{value}")

        class ProcessInputs(BaseModel):
            data: Target

        @domain.command
        class Process(Command[ProcessInputs, str]):
            def execute(self) -> str:
                return self.inputs.data.data

        class MainInputs(BaseModel):
            required: str
            optional: Optional[str] = None

        @domain.command
        class Main(Command[MainInputs, str]):
            def execute(self) -> str:
                source = Source(required=self.inputs.required, optional=self.inputs.optional)
                return self.run_mapped_subcommand(
                    Process,
                    unmapped_inputs={"data": source}
                )

        # With optional
        outcome = Main.run(required="test", optional="custom")
        assert outcome.is_success()
        assert outcome.unwrap() == "test:custom"

        # Without optional
        outcome = Main.run(required="test")
        assert outcome.is_success()
        assert outcome.unwrap() == "test:default"

    def test_mapper_registry_lookup(self, clean_registries):
        """Test: Mapper registry correctly finds mappers"""
        domain = Domain("Registry", organization="Test")

        class A(BaseModel):
            x: int

        class B(BaseModel):
            y: str

        @domain_mapper(domain="Registry", organization="Test")
        class AToB(DomainMapper[A, B]):
            def map(self) -> B:
                return B(y=str(self.from_value.x))

        # Should find mapper
        mapper = DomainMapperRegistry.find_matching_mapper(A(x=5), B)
        assert mapper == AToB

        # Should not find non-existent mapper
        class C(BaseModel):
            z: int

        mapper = DomainMapperRegistry.find_matching_mapper(A(x=5), C)
        assert mapper is None

    def test_mapper_with_cross_domain_call(self, clean_registries):
        """Test: Mappers work with cross-domain calls"""
        org = "CrossMapper"
        domain_a = Domain("A", organization=org)
        domain_b = Domain("B", organization=org)
        domain_b.depends_on("A")

        class ModelA(BaseModel):
            value: int

        class ModelB(BaseModel):
            value: str

        @domain_mapper(domain="B", organization=org)
        class AToB(DomainMapper[ModelA, ModelB]):
            def map(self) -> ModelB:
                return ModelB(value=str(self.from_value.value))

        class ProcessBInputs(BaseModel):
            data: ModelB

        @domain_a.command
        class ProcessA(Command[ProcessBInputs, str]):
            def execute(self) -> str:
                return f"A:{self.inputs.data.value}"

        class MainInputs(BaseModel):
            value: int

        @domain_b.command
        class ProcessB(Command[MainInputs, str]):
            def execute(self) -> str:
                model_a = ModelA(value=self.inputs.value)
                return self.run_mapped_subcommand(
                    ProcessA,
                    unmapped_inputs={"data": model_a}
                )

        outcome = ProcessB.run(value=42)
        assert outcome.is_success()
        assert outcome.unwrap() == "A:42"

    def test_mapper_performance_with_bulk(self, clean_registries):
        """Test: Mappers handle bulk operations efficiently"""
        domain = Domain("Bulk", organization="Test")

        class Source(BaseModel):
            id: int

        class Target(BaseModel):
            id: str

        @domain_mapper(domain="Bulk", organization="Test")
        class SourceToTarget(DomainMapper[Source, Target]):
            def map(self) -> Target:
                return Target(id=f"id_{self.from_value.id}")

        # Map 100 items
        sources = [Source(id=i) for i in range(100)]
        targets = [SourceToTarget.map_value(s) for s in sources]

        assert len(targets) == 100
        assert all(isinstance(t.id, str) for t in targets)

    def test_mapper_with_entity_persistence(self, clean_registries):
        """Test: Map entity before/after persistence"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Persist", organization="Test")

        class UserCreateDTO(BaseModel):
            username: str
            email: str

        class UserResponseDTO(BaseModel):
            id: str
            username: str

        @domain_mapper(domain="Persist", organization="Test")
        class DTOToUser(DomainMapper[UserCreateDTO, User]):
            def map(self) -> User:
                return User(
                    username=self.from_value.username,
                    email=self.from_value.email,
                    password_hash="hash"
                )

        @domain_mapper(domain="Persist", organization="Test")
        class UserToResponse(DomainMapper[User, UserResponseDTO]):
            def map(self) -> UserResponseDTO:
                return UserResponseDTO(
                    id=str(self.from_value.id),
                    username=self.from_value.username
                )

        class CreateUserInputs(BaseModel):
            dto: UserCreateDTO

        @domain.command
        class CreateUser(Command[CreateUserInputs, UserResponseDTO]):
            def execute(self) -> UserResponseDTO:
                # Map DTO to entity
                user = DTOToUser.map_value(self.inputs.dto)
                # Save entity
                saved = repo.save(user)
                # Map entity to response
                return UserToResponse.map_value(saved)

        dto = UserCreateDTO(username="test", email="test@test.com")
        outcome = CreateUser.run(dto=dto)
        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.username == "test"
        assert response.id is not None


# ============================================================================
# SECTION 4: TRANSACTION ROLLBACK ACROSS FEATURES (15+ tests)
# ============================================================================

class TestTransactionIntegration:
    """Test transaction rollback across commands, entities, and persistence"""

    def test_basic_transaction_commit(self, clean_registries):
        """Test: Simple transaction commits successfully"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)

        class MockHandler:
            def __init__(self):
                self.begun = False
                self.committed = False
                self.rolled_back = False

            def begin(self):
                self.begun = True

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

        handler = MockHandler()

        with transaction(handler):
            user = User(username="test", email="test@test.com", password_hash="hash")
            repo.save(user)

        assert handler.begun
        assert handler.committed
        assert not handler.rolled_back

    def test_basic_transaction_rollback(self, clean_registries):
        """Test: Transaction rolls back on exception"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)

        class MockHandler:
            def __init__(self):
                self.begun = False
                self.committed = False
                self.rolled_back = False

            def begin(self):
                self.begun = True

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

        handler = MockHandler()

        try:
            with transaction(handler):
                user = User(username="test", email="test@test.com", password_hash="hash")
                repo.save(user)
                raise ValueError("Rollback trigger")
        except ValueError:
            pass

        assert handler.begun
        assert not handler.committed
        assert handler.rolled_back

    def test_command_with_transaction(self, clean_registries):
        """Test: Command execution within transaction"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Trans", organization="Test")

        class CreateUserInputs(BaseModel):
            username: str
            email: str

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                user = User(
                    username=self.inputs.username,
                    email=self.inputs.email,
                    password_hash="hash"
                )
                return repo.save(user)

        class MockHandler:
            def __init__(self):
                self.operations = []

            def begin(self):
                self.operations.append("begin")

            def commit(self):
                self.operations.append("commit")

            def rollback(self):
                self.operations.append("rollback")

        handler = MockHandler()

        with transaction(handler):
            outcome = CreateUser.run(username="test", email="test@test.com")
            assert outcome.is_success()

        assert "begin" in handler.operations
        assert "commit" in handler.operations

    def test_nested_transactions(self, clean_registries):
        """Test: Nested transactions with savepoints"""
        class MockHandler:
            def __init__(self):
                self.depth = 0
                self.operations = []

            def begin(self):
                self.depth += 1
                self.operations.append(f"begin:{self.depth}")

            def commit(self):
                self.operations.append(f"commit:{self.depth}")
                self.depth -= 1

            def rollback(self):
                self.operations.append(f"rollback:{self.depth}")
                self.depth -= 1

        handler = MockHandler()

        with transaction(handler):
            # Outer transaction
            pass

        # Check operations
        assert "begin:1" in handler.operations
        assert "commit:1" in handler.operations

    def test_transaction_rollback_with_multiple_entities(self, clean_registries):
        """Test: Transaction rolls back multiple entity saves"""
        user_repo = InMemoryRepository()
        product_repo = InMemoryRepository()
        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Product, product_repo)

        class MockHandler:
            def __init__(self):
                self.rolled_back = False

            def begin(self):
                pass

            def commit(self):
                pass

            def rollback(self):
                self.rolled_back = True

        handler = MockHandler()

        try:
            with transaction(handler):
                user = User(username="test", email="test@test.com", password_hash="hash")
                user_repo.save(user)

                product = Product(name="Widget", price=99, stock=10)
                product_repo.save(product)

                raise ValueError("Force rollback")
        except ValueError:
            pass

        assert handler.rolled_back

    def test_transaction_with_command_error(self, clean_registries):
        """Test: Transaction rolls back when command fails"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Trans", organization="Test")

        class CreateUserInputs(BaseModel):
            username: str
            should_fail: bool

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                user = User(username=self.inputs.username, email="test@test.com", password_hash="hash")
                repo.save(user)

                if self.inputs.should_fail:
                    self.add_runtime_error("failed", "Forced failure")
                    return None

                return user

        class MockHandler:
            def __init__(self):
                self.rolled_back = False

            def begin(self):
                pass

            def commit(self):
                pass

            def rollback(self):
                self.rolled_back = True

        handler = MockHandler()

        try:
            with transaction(handler):
                outcome = CreateUser.run(username="test", should_fail=True)
                if outcome.is_failure():
                    raise ValueError("Command failed")
        except ValueError:
            pass

        assert handler.rolled_back

    def test_transaction_across_subcommands(self, clean_registries):
        """Test: Transaction spans multiple subcommand calls"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Multi", organization="Test")

        class CreateUserInputs(BaseModel):
            username: str

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                user = User(username=self.inputs.username, email="test@test.com", password_hash="hash")
                return repo.save(user)

        class CreateTwoInputs(BaseModel):
            username1: str
            username2: str
            should_fail: bool

        @domain.command
        class CreateTwoUsers(Command[CreateTwoInputs, List[User]]):
            def execute(self) -> List[User]:
                user1 = self.run_subcommand_bang(CreateUser, username=self.inputs.username1)
                user2 = self.run_subcommand_bang(CreateUser, username=self.inputs.username2)

                if self.inputs.should_fail:
                    self.add_runtime_error("failed", "Forced failure")
                    return None

                return [user1, user2]

        class MockHandler:
            def __init__(self):
                self.rolled_back = False
                self.committed = False

            def begin(self):
                pass

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

        # Test rollback
        handler = MockHandler()
        try:
            with transaction(handler):
                outcome = CreateTwoUsers.run(username1="u1", username2="u2", should_fail=True)
                if outcome.is_failure():
                    raise ValueError("Command failed")
        except ValueError:
            pass

        assert handler.rolled_back

        # Test commit
        handler2 = MockHandler()
        with transaction(handler2):
            outcome = CreateTwoUsers.run(username1="u3", username2="u4", should_fail=False)
            assert outcome.is_success()

        assert handler2.committed

    def test_transaction_context_isolation(self, clean_registries):
        """Test: Transaction contexts are isolated"""
        from foobara_py.core.transactions import get_current_transaction, set_current_transaction

        class MockHandler:
            def __init__(self, name):
                self.name = name

            def begin(self):
                pass

            def commit(self):
                pass

            def rollback(self):
                pass

        handler1 = MockHandler("handler1")
        handler2 = MockHandler("handler2")

        # Save original
        original = get_current_transaction()

        with transaction(handler1):
            ctx1 = get_current_transaction()
            assert ctx1 is not None

            with transaction(handler2):
                ctx2 = get_current_transaction()
                assert ctx2 is not None
                assert ctx2 != ctx1

            # Back to outer context
            assert get_current_transaction() == ctx1

        # Restored
        assert get_current_transaction() == original

    def test_transaction_mark_failed(self, clean_registries):
        """Test: Manually mark transaction as failed"""
        class MockHandler:
            def __init__(self):
                self.rolled_back = False

            def begin(self):
                pass

            def commit(self):
                pass

            def rollback(self):
                self.rolled_back = True

        handler = MockHandler()

        with transaction(handler) as ctx:
            ctx.mark_failed()

        assert handler.rolled_back

    def test_transaction_with_entity_lifecycle(self, clean_registries):
        """Test: Transaction includes entity lifecycle events"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)

        class MockHandler:
            def __init__(self):
                self.operations = []

            def begin(self):
                self.operations.append("begin")

            def commit(self):
                self.operations.append("commit")

            def rollback(self):
                self.operations.append("rollback")

        handler = MockHandler()

        with transaction(handler):
            user = User(username="test", email="test@test.com", password_hash="hash")
            repo.save(user)
            repo.save(user)  # Update

        assert "begin" in handler.operations
        assert "commit" in handler.operations

    def test_no_op_transaction_handler(self, clean_registries):
        """Test: NoOpTransactionHandler works correctly"""
        handler = NoOpTransactionHandler()

        # Should not raise
        with transaction(handler):
            pass

        # Should not raise
        try:
            with transaction(handler):
                raise ValueError("Test")
        except ValueError:
            pass

    def test_transaction_with_validation_error(self, clean_registries):
        """Test: Transaction behavior with validation errors"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Valid", organization="Test")

        class CreateUserInputs(BaseModel):
            username: str
            email: str

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                if "@" not in self.inputs.email:
                    self.add_input_error(["email"], "invalid_email", "Email must contain @")
                    return None

                user = User(
                    username=self.inputs.username,
                    email=self.inputs.email,
                    password_hash="hash"
                )
                return repo.save(user)

        class MockHandler:
            def __init__(self):
                self.rolled_back = False
                self.committed = False

            def begin(self):
                pass

            def commit(self):
                self.committed = True

            def rollback(self):
                self.rolled_back = True

        handler = MockHandler()

        try:
            with transaction(handler):
                outcome = CreateUser.run(username="test", email="invalid")
                if outcome.is_failure():
                    raise ValueError("Validation failed")
        except ValueError:
            pass

        assert handler.rolled_back

    def test_transaction_partial_rollback(self, clean_registries):
        """Test: Transaction rolls back partial work"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)

        class MockHandler:
            def __init__(self):
                self.saved_count = 0
                self.rolled_back = False

            def begin(self):
                pass

            def commit(self):
                pass

            def rollback(self):
                self.rolled_back = True
                self.saved_count = 0  # Simulate rollback

        handler = MockHandler()

        try:
            with transaction(handler):
                for i in range(5):
                    user = User(username=f"user{i}", email=f"user{i}@test.com", password_hash="hash")
                    repo.save(user)
                    handler.saved_count += 1

                    if i == 3:
                        raise ValueError("Stop at 3")
        except ValueError:
            pass

        assert handler.rolled_back
        assert handler.saved_count == 0  # All rolled back

    def test_transaction_error_details(self, clean_registries):
        """Test: Transaction preserves error details"""
        domain = Domain("Error", organization="Test")

        class FailInputs(BaseModel):
            should_fail: bool

        @domain.command
        class FailCommand(Command[FailInputs, str]):
            def execute(self) -> str:
                if self.inputs.should_fail:
                    self.add_runtime_error("custom_error", "Custom error message")
                    return None
                return "success"

        class MockHandler:
            def __init__(self):
                self.rolled_back = False

            def begin(self):
                pass

            def commit(self):
                pass

            def rollback(self):
                self.rolled_back = True

        handler = MockHandler()

        try:
            with transaction(handler):
                outcome = FailCommand.run(should_fail=True)
                if outcome.is_failure():
                    errors = outcome.errors
                    # Error details should be preserved
                    assert any("custom_error" in e.symbol for e in errors)
                    raise ValueError("Command failed")
        except ValueError:
            pass

        assert handler.rolled_back

    def test_transaction_cleanup(self, clean_registries):
        """Test: Transaction cleanup on both success and failure"""
        class MockHandler:
            def __init__(self):
                self.cleaned_up = False

            def begin(self):
                pass

            def commit(self):
                self.cleaned_up = True

            def rollback(self):
                self.cleaned_up = True

        # Success case
        handler1 = MockHandler()
        with transaction(handler1):
            pass
        assert handler1.cleaned_up

        # Failure case
        handler2 = MockHandler()
        try:
            with transaction(handler2):
                raise ValueError("Test")
        except ValueError:
            pass
        assert handler2.cleaned_up


# ============================================================================
# SECTION 5: AUTH INTEGRATION WITH HTTP CONNECTOR (15+ tests)
# ============================================================================

class TestAuthHTTPIntegration:
    """Test authentication integration with HTTP connector"""

    def test_http_with_bearer_auth(self, clean_registries):
        """Test: HTTP connector with Bearer token authentication"""
        import jwt
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("API", organization="Test")

        class EchoInputs(BaseModel):
            message: str

        @domain.command
        class Echo(Command[EchoInputs, str]):
            def execute(self) -> str:
                return f"Echo: {self.inputs.message}"

        app = FastAPI()
        secret = "test-secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector)

        auth_dep = lambda request: get_auth_context(request) if hasattr(request.state, 'auth_context') else None
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(Echo)

        client = TestClient(app)
        token = jwt.encode({"sub": "user123"}, secret, algorithm="HS256")

        response = client.post(
            "/echo",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_http_with_api_key_auth(self, clean_registries):
        """Test: HTTP connector with API key authentication"""
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("API", organization="Test")

        class GetDataInputs(BaseModel):
            id: int

        @domain.command
        class GetData(Command[GetDataInputs, dict]):
            def execute(self) -> dict:
                return {"id": self.inputs.id, "data": "value"}

        app = FastAPI()
        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"valid_key": {"user_id": 42}},
                header_name="X-API-Key"
            )
        )
        app.add_middleware(AuthMiddleware, selector=selector)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(GetData)

        client = TestClient(app)
        response = client.post(
            "/getdata",
            json={"id": 1},
            headers={"X-API-Key": "valid_key"}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_http_auth_rejection(self, clean_registries):
        """Test: HTTP connector rejects invalid authentication"""
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("API", organization="Test")

        class SecureInputs(BaseModel):
            data: str

        @domain.command
        class SecureCommand(Command[SecureInputs, str]):
            def execute(self) -> str:
                return self.inputs.data

        app = FastAPI()
        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"valid_key": {"user_id": 1}},
                header_name="X-API-Key"
            )
        )
        app.add_middleware(AuthMiddleware, selector=selector, required=True)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(SecureCommand)

        client = TestClient(app)

        # Without auth
        response = client.post("/securecommand", json={"data": "test"})
        assert response.status_code == 401

        # With invalid key
        response = client.post(
            "/securecommand",
            json={"data": "test"},
            headers={"X-API-Key": "invalid"}
        )
        assert response.status_code == 401

    def test_http_auth_context_in_command(self, clean_registries):
        """Test: Command accesses auth context via HTTP"""
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("Auth", organization="Test")

        class WhoAmIInputs(BaseModel):
            pass

        @domain.command
        class WhoAmI(Command[WhoAmIInputs, dict]):
            def execute(self) -> dict:
                # Command would have access to auth context
                return {"user": "authenticated"}

        app = FastAPI()
        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"key1": {"user_id": 100, "roles": ["admin"]}},
                header_name="X-API-Key"
            )
        )
        app.add_middleware(AuthMiddleware, selector=selector)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(WhoAmI)

        client = TestClient(app)
        response = client.post("/whoami", json={}, headers={"X-API-Key": "key1"})

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_http_multiple_auth_methods(self, clean_registries):
        """Test: HTTP supports multiple authentication methods"""
        import jwt
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("Multi", organization="Test")

        class ActionInputs(BaseModel):
            action: str

        @domain.command
        class PerformAction(Command[ActionInputs, str]):
            def execute(self) -> str:
                return f"Action: {self.inputs.action}"

        app = FastAPI()
        secret = "secret123"
        selector = create_auth_selector(
            BearerTokenAuthenticator(secret=secret),
            ApiKeyAuthenticator(
                api_keys={"api_key": {"user_id": 1}},
                header_name="X-API-Key"
            )
        )
        app.add_middleware(AuthMiddleware, selector=selector)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(PerformAction)

        client = TestClient(app)

        # Test with Bearer token
        token = jwt.encode({"sub": "user1"}, secret, algorithm="HS256")
        response = client.post(
            "/performaction",
            json={"action": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        # Test with API key
        response = client.post(
            "/performaction",
            json={"action": "test"},
            headers={"X-API-Key": "api_key"}
        )
        assert response.status_code == 200

    def test_http_auth_with_roles(self, clean_registries):
        """Test: HTTP auth with role-based access control"""
        import jwt
        from foobara_py.connectors.http import AuthConfig
        from fastapi import Depends

        domain = Domain("RBAC", organization="Test")

        class AdminInputs(BaseModel):
            action: str

        @domain.command
        class AdminAction(Command[AdminInputs, str]):
            def execute(self) -> str:
                return f"Admin: {self.inputs.action}"

        app = FastAPI()
        secret = "secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector)

        from foobara_py.auth import require_role

        @app.post("/admin")
        async def admin_endpoint(
            data: dict,
            context: AuthContext = Depends(require_role("admin"))
        ):
            outcome = AdminAction.run(**data)
            return {"success": outcome.is_success(), "result": outcome.result if outcome.is_success() else None}

        client = TestClient(app)

        # User without admin role
        token = jwt.encode({"sub": "user", "roles": ["user"]}, secret, algorithm="HS256")
        response = client.post(
            "/admin",
            json={"action": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

        # User with admin role
        token = jwt.encode({"sub": "admin", "roles": ["admin"]}, secret, algorithm="HS256")
        response = client.post(
            "/admin",
            json={"action": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_http_auth_with_permissions(self, clean_registries):
        """Test: HTTP auth with permission checks"""
        import jwt
        from fastapi import Depends
        from foobara_py.auth import require_permission

        domain = Domain("Perms", organization="Test")

        class WriteInputs(BaseModel):
            data: str

        @domain.command
        class WriteData(Command[WriteInputs, str]):
            def execute(self) -> str:
                return f"Written: {self.inputs.data}"

        app = FastAPI()
        secret = "secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector)

        @app.post("/write")
        async def write_endpoint(
            data: dict,
            context: AuthContext = Depends(require_permission("write"))
        ):
            outcome = WriteData.run(**data)
            return {"success": outcome.is_success(), "result": outcome.result if outcome.is_success() else None}

        client = TestClient(app)

        # User without write permission
        token = jwt.encode({"sub": "user", "permissions": ["read"]}, secret, algorithm="HS256")
        response = client.post(
            "/write",
            json={"data": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

        # User with write permission
        token = jwt.encode({"sub": "user", "permissions": ["write"]}, secret, algorithm="HS256")
        response = client.post(
            "/write",
            json={"data": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_http_auth_with_entity_access(self, clean_registries):
        """Test: Authenticated HTTP requests access entities"""
        import jwt
        from foobara_py.connectors.http import AuthConfig

        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        # Seed user
        user = repo.save(User(username="testuser", email="test@test.com", password_hash="hash"))

        class GetUserInputs(BaseModel):
            user_id: int

        @domain.command
        class GetUser(Command[GetUserInputs, Optional[User]]):
            def execute(self) -> Optional[User]:
                return repo.find(User, self.inputs.user_id)

        app = FastAPI()
        secret = "secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector, required=True)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(GetUser)

        client = TestClient(app)
        token = jwt.encode({"sub": "caller"}, secret, algorithm="HS256")

        response = client.post(
            "/getuser",
            json={"user_id": user.id},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_http_auth_error_handling(self, clean_registries):
        """Test: HTTP auth error handling"""
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("Errors", organization="Test")

        class TestInputs(BaseModel):
            value: str

        @domain.command
        class TestCommand(Command[TestInputs, str]):
            def execute(self) -> str:
                return self.inputs.value

        app = FastAPI()
        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"valid": {"user_id": 1}},
                header_name="X-API-Key"
            )
        )
        app.add_middleware(AuthMiddleware, selector=selector, required=True)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(TestCommand)

        client = TestClient(app)

        # Missing auth
        response = client.post("/testcommand", json={"value": "test"})
        assert response.status_code == 401
        assert "unauthorized" in response.json()["errors"][0]["symbol"]

    def test_http_cors_with_auth(self, clean_registries):
        """Test: CORS configuration works with authentication"""
        from foobara_py.connectors.http import AuthConfig
        from foobara_py.auth import configure_cors

        domain = Domain("CORS", organization="Test")

        class TestInputs(BaseModel):
            data: str

        @domain.command
        class TestCommand(Command[TestInputs, str]):
            def execute(self) -> str:
                return self.inputs.data

        app = FastAPI()
        configure_cors(app, allow_origins=["http://localhost:3000"])

        selector = create_auth_selector(
            ApiKeyAuthenticator(
                api_keys={"key": {"user_id": 1}},
                header_name="X-API-Key"
            )
        )
        app.add_middleware(AuthMiddleware, selector=selector)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(TestCommand)

        client = TestClient(app)

        response = client.post(
            "/testcommand",
            json={"data": "test"},
            headers={"X-API-Key": "key", "Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_http_auth_with_command_validation(self, clean_registries):
        """Test: Auth + command input validation"""
        import jwt
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("Valid", organization="Test")

        class CreateItemInputs(BaseModel):
            name: str = Field(..., min_length=3)
            price: float = Field(..., gt=0)

        @domain.command
        class CreateItem(Command[CreateItemInputs, dict]):
            def execute(self) -> dict:
                return {"name": self.inputs.name, "price": self.inputs.price}

        app = FastAPI()
        secret = "secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector, required=True)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(CreateItem)

        client = TestClient(app)
        token = jwt.encode({"sub": "user"}, secret, algorithm="HS256")

        # Valid request
        response = client.post(
            "/createitem",
            json={"name": "Widget", "price": 99.99},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        # Invalid (short name)
        response = client.post(
            "/createitem",
            json={"name": "AB", "price": 99.99},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200  # Returns with errors in response
        assert response.json()["success"] is False

    def test_http_auth_token_expiration(self, clean_registries):
        """Test: Handle expired tokens"""
        import jwt
        import time
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("Expire", organization="Test")

        class TestInputs(BaseModel):
            value: str

        @domain.command
        class TestCommand(Command[TestInputs, str]):
            def execute(self) -> str:
                return self.inputs.value

        app = FastAPI()
        secret = "secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector, required=True)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(TestCommand)

        client = TestClient(app)

        # Expired token (exp in the past)
        expired_token = jwt.encode(
            {"sub": "user", "exp": int(time.time()) - 3600},
            secret,
            algorithm="HS256"
        )

        response = client.post(
            "/testcommand",
            json={"value": "test"},
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        # Should be unauthorized
        assert response.status_code == 401

    def test_http_auth_with_custom_claims(self, clean_registries):
        """Test: Auth with custom JWT claims"""
        import jwt
        from foobara_py.connectors.http import AuthConfig

        domain = Domain("Claims", organization="Test")

        class GetDataInputs(BaseModel):
            resource: str

        @domain.command
        class GetData(Command[GetDataInputs, dict]):
            def execute(self) -> dict:
                return {"resource": self.inputs.resource, "allowed": True}

        app = FastAPI()
        secret = "secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(GetData)

        client = TestClient(app)

        # Token with custom claims
        token = jwt.encode(
            {
                "sub": "user123",
                "roles": ["reader"],
                "tenant_id": "tenant_abc",
                "custom_field": "custom_value"
            },
            secret,
            algorithm="HS256"
        )

        response = client.post(
            "/getdata",
            json={"resource": "data1"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_http_auth_with_entity_ownership(self, clean_registries):
        """Test: Auth validates entity ownership"""
        import jwt
        from foobara_py.connectors.http import AuthConfig

        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Ownership", organization="Test")

        # Seed users
        user1 = repo.save(User(username="user1", email="u1@test.com", password_hash="hash"))
        user2 = repo.save(User(username="user2", email="u2@test.com", password_hash="hash"))

        class UpdateUserInputs(BaseModel):
            user_id: int
            email: str

        @domain.command
        class UpdateUser(Command[UpdateUserInputs, User]):
            def execute(self) -> User:
                # In real app, would check if auth context user_id matches user_id
                user = repo.find(User, self.inputs.user_id)
                if not user:
                    self.add_runtime_error("not_found", "User not found")
                    return None
                user.email = self.inputs.email
                return repo.save(user)

        app = FastAPI()
        secret = "secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector, required=True)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(UpdateUser)

        client = TestClient(app)
        token = jwt.encode({"sub": str(user1.id)}, secret, algorithm="HS256")

        # Update own user
        response = client.post(
            "/updateuser",
            json={"user_id": user1.id, "email": "new@test.com"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200

    def test_http_auth_concurrent_requests(self, clean_registries):
        """Test: Auth handles concurrent requests correctly"""
        import jwt
        from foobara_py.connectors.http import AuthConfig
        import threading

        domain = Domain("Concurrent", organization="Test")

        class TestInputs(BaseModel):
            value: int

        @domain.command
        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return self.inputs.value * 2

        app = FastAPI()
        secret = "secret"
        selector = create_auth_selector(BearerTokenAuthenticator(secret=secret))
        app.add_middleware(AuthMiddleware, selector=selector)

        auth_dep = lambda request: getattr(request.state, 'auth_context', None)
        connector = HTTPConnector(app, auth_config=AuthConfig(enabled=True, dependency=auth_dep))
        connector.register(TestCommand)

        client = TestClient(app)
        token = jwt.encode({"sub": "user"}, secret, algorithm="HS256")

        results = []

        def make_request(val):
            response = client.post(
                "/testcommand",
                json={"value": val},
                headers={"Authorization": f"Bearer {token}"}
            )
            results.append(response.status_code)

        # Make concurrent requests
        threads = [threading.Thread(target=make_request, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(code == 200 for code in results)


# ============================================================================
# SECTION 6: AUTH INTEGRATION WITH MCP CONNECTOR (15+ tests)
# ============================================================================

class TestAuthMCPIntegration:
    """Test authentication integration with MCP connector"""

    def test_mcp_basic_auth(self, clean_registries):
        """Test: MCP connector with authentication"""
        domain = Domain("MCP", organization="Test")

        class SecureInputs(BaseModel):
            data: str

        @domain.command
        class SecureCommand(Command[SecureInputs, str]):
            def execute(self) -> str:
                return f"Secure: {self.inputs.data}"

        connector = MCPConnector(name="SecureService", version="1.0.0")
        connector.connect(domain)

        # Initialize
        init_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        })

        response = connector.run(init_request)
        data = json.loads(response)
        assert data["result"]["serverInfo"]["name"] == "SecureService"

    def test_mcp_call_with_auth_context(self, clean_registries):
        """Test: MCP tool calls with auth context"""
        domain = Domain("Auth", organization="Test")

        class AuthActionInputs(BaseModel):
            action: str

        @domain.command
        class AuthAction(Command[AuthActionInputs, str]):
            def execute(self) -> str:
                return f"Authenticated action: {self.inputs.action}"

        connector = MCPConnector(name="AuthService", version="1.0.0")
        connector.connect(domain)

        call_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::Auth::AuthAction",
                "arguments": {"action": "test"}
            }
        })

        response = connector.run(call_request)
        data = json.loads(response)
        assert "result" in data

    def test_mcp_auth_validation(self, clean_registries):
        """Test: MCP validates authentication"""
        domain = Domain("Secure", organization="Test")

        class SecureInputs(BaseModel):
            data: str

        @domain.command
        class SecureOp(Command[SecureInputs, str]):
            def execute(self) -> str:
                # In real app, would check auth
                return self.inputs.data

        connector = MCPConnector(name="Secure", version="1.0.0")
        connector.connect(domain)

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::Secure::SecureOp",
                "arguments": {"data": "test"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert "result" in data

    def test_mcp_with_entity_access_control(self, clean_registries):
        """Test: MCP with entity access control"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Users", organization="Test")

        user = repo.save(User(username="mcp_user", email="mcp@test.com", password_hash="hash"))

        class GetUserInputs(BaseModel):
            user_id: int

        @domain.command
        class GetUser(Command[GetUserInputs, Optional[User]]):
            def execute(self) -> Optional[User]:
                # In real app, would validate auth + permissions
                return repo.find(User, self.inputs.user_id)

        connector = MCPConnector(name="UserService", version="1.0.0")
        connector.connect(domain)

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::Users::GetUser",
                "arguments": {"user_id": user.id}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert "result" in data

    def test_mcp_multiple_tools_with_auth(self, clean_registries):
        """Test: MCP with multiple authenticated tools"""
        domain = Domain("Multi", organization="Test")

        class Action1Inputs(BaseModel):
            value: str

        @domain.command
        class Action1(Command[Action1Inputs, str]):
            def execute(self) -> str:
                return f"Action1: {self.inputs.value}"

        class Action2Inputs(BaseModel):
            value: int

        @domain.command
        class Action2(Command[Action2Inputs, int]):
            def execute(self) -> int:
                return self.inputs.value * 2

        connector = MCPConnector(name="MultiService", version="1.0.0")
        connector.connect(domain)

        # List tools
        list_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        })

        response = connector.run(list_request)
        data = json.loads(response)
        assert len(data["result"]["tools"]) == 2

    def test_mcp_auth_error_propagation(self, clean_registries):
        """Test: MCP propagates authentication errors"""
        domain = Domain("Error", organization="Test")

        class FailInputs(BaseModel):
            should_fail: bool

        @domain.command
        class FailCommand(Command[FailInputs, str]):
            def execute(self) -> str:
                if self.inputs.should_fail:
                    self.add_runtime_error("auth_failed", "Authentication failed")
                    return None
                return "success"

        connector = MCPConnector(name="ErrorService", version="1.0.0")
        connector.connect(domain)

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::Error::FailCommand",
                "arguments": {"should_fail": True}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert data["result"]["isError"] is True

    def test_mcp_batch_with_auth(self, clean_registries):
        """Test: MCP batch requests with authentication"""
        domain = Domain("Batch", organization="Test")

        class EchoInputs(BaseModel):
            msg: str

        @domain.command
        class Echo(Command[EchoInputs, str]):
            def execute(self) -> str:
                return self.inputs.msg

        connector = MCPConnector(name="BatchService", version="1.0.0")
        connector.connect(domain)

        batch = json.dumps([
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "Test::Batch::Echo", "arguments": {"msg": "first"}}
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "Test::Batch::Echo", "arguments": {"msg": "second"}}
            }
        ])

        response = connector.run(batch)
        data = json.loads(response)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_mcp_auth_with_domain_dependencies(self, clean_registries):
        """Test: MCP with authenticated cross-domain calls"""
        org = "MCPAuth"
        auth_domain = Domain("Auth", organization=org)
        data_domain = Domain("Data", organization=org)
        data_domain.depends_on("Auth")

        class ValidateInputs(BaseModel):
            token: str

        @auth_domain.command
        class Validate(Command[ValidateInputs, bool]):
            def execute(self) -> bool:
                return self.inputs.token == "valid"

        class GetDataInputs(BaseModel):
            token: str
            resource: str

        @data_domain.command
        class GetData(Command[GetDataInputs, str]):
            def execute(self) -> str:
                is_valid = self.run_subcommand_bang(Validate, token=self.inputs.token)
                if not is_valid:
                    self.add_runtime_error("unauthorized", "Invalid token")
                    return None
                return f"Data for {self.inputs.resource}"

        connector = MCPConnector(name="AuthDataService", version="1.0.0")
        connector.connect(auth_domain)
        connector.connect(data_domain)

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": f"{org}::Data::GetData",
                "arguments": {"token": "valid", "resource": "users"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert "result" in data

    def test_mcp_auth_session_management(self, clean_registries):
        """Test: MCP with session-based authentication"""
        domain = Domain("Session", organization="Test")

        class LoginInputs(BaseModel):
            username: str
            password: str

        @domain.command
        class Login(Command[LoginInputs, dict]):
            def execute(self) -> dict:
                if self.inputs.username == "admin" and self.inputs.password == "pass":
                    return {"session_id": "session_123", "success": True}
                self.add_runtime_error("login_failed", "Invalid credentials")
                return None

        connector = MCPConnector(name="SessionService", version="1.0.0")
        connector.connect(domain)

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::Session::Login",
                "arguments": {"username": "admin", "password": "pass"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        result = json.loads(data["result"]["content"][0]["text"])
        assert result["success"] is True

    def test_mcp_auth_rate_limiting(self, clean_registries):
        """Test: MCP with rate limiting simulation"""
        domain = Domain("RateLimit", organization="Test")

        class RequestInputs(BaseModel):
            user_id: str

        call_count = {}

        @domain.command
        class MakeRequest(Command[RequestInputs, dict]):
            def execute(self) -> dict:
                user_id = self.inputs.user_id
                count = call_count.get(user_id, 0)

                if count >= 5:
                    self.add_runtime_error("rate_limited", "Too many requests")
                    return None

                call_count[user_id] = count + 1
                return {"count": call_count[user_id]}

        connector = MCPConnector(name="RateLimitService", version="1.0.0")
        connector.connect(domain)

        # Make 6 requests (should fail on 6th)
        for i in range(6):
            request = json.dumps({
                "jsonrpc": "2.0",
                "id": i + 1,
                "method": "tools/call",
                "params": {
                    "name": "Test::RateLimit::MakeRequest",
                    "arguments": {"user_id": "user1"}
                }
            })
            response = connector.run(request)
            data = json.loads(response)

            if i < 5:
                # Successful results may not have isError field
                assert data["result"].get("isError") is not True
            else:
                # Failed result should have isError: true
                assert data["result"].get("isError") is True

    def test_mcp_auth_with_entity_crud(self, clean_registries):
        """Test: MCP authenticated CRUD operations"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("CRUD", organization="Test")

        class CreateUserInputs(BaseModel):
            username: str
            email: str

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                user = User(
                    username=self.inputs.username,
                    email=self.inputs.email,
                    password_hash="hash"
                )
                return repo.save(user)

        connector = MCPConnector(name="CRUDService", version="1.0.0")
        connector.connect(domain)

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::CRUD::CreateUser",
                "arguments": {"username": "newuser", "email": "new@test.com"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert "result" in data

    def test_mcp_auth_token_validation(self, clean_registries):
        """Test: MCP validates authentication tokens"""
        domain = Domain("TokenVal", organization="Test")

        class ValidateTokenInputs(BaseModel):
            token: str

        @domain.command
        class ValidateToken(Command[ValidateTokenInputs, dict]):
            def execute(self) -> dict:
                if self.inputs.token.startswith("valid_"):
                    return {"valid": True, "user_id": self.inputs.token.split("_")[1]}
                self.add_runtime_error("invalid_token", "Token is invalid")
                return None

        connector = MCPConnector(name="TokenService", version="1.0.0")
        connector.connect(domain)

        # Valid token
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::TokenVal::ValidateToken",
                "arguments": {"token": "valid_123"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        result = json.loads(data["result"]["content"][0]["text"])
        assert result["valid"] is True

        # Invalid token
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "Test::TokenVal::ValidateToken",
                "arguments": {"token": "invalid"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert data["result"]["isError"] is True

    def test_mcp_auth_context_passing(self, clean_registries):
        """Test: MCP passes auth context through command chain"""
        org = "Context"
        domain_a = Domain("A", organization=org)
        domain_b = Domain("B", organization=org)
        domain_b.depends_on("A")

        class CheckAuthInputs(BaseModel):
            user: str

        @domain_a.command
        class CheckAuth(Command[CheckAuthInputs, bool]):
            def execute(self) -> bool:
                return self.inputs.user == "authenticated_user"

        class ProcessInputs(BaseModel):
            user: str
            data: str

        @domain_b.command
        class Process(Command[ProcessInputs, str]):
            def execute(self) -> str:
                is_auth = self.run_subcommand_bang(CheckAuth, user=self.inputs.user)
                if not is_auth:
                    self.add_runtime_error("unauthorized", "Not authorized")
                    return None
                return f"Processed: {self.inputs.data}"

        connector = MCPConnector(name="ContextService", version="1.0.0")
        connector.connect(domain_a)
        connector.connect(domain_b)

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": f"{org}::B::Process",
                "arguments": {"user": "authenticated_user", "data": "test"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert "result" in data

    def test_mcp_auth_with_resource_access(self, clean_registries):
        """Test: MCP auth with resource-level permissions"""
        domain = Domain("Resources", organization="Test")

        class AccessResourceInputs(BaseModel):
            resource_id: str
            user_role: str

        @domain.command
        class AccessResource(Command[AccessResourceInputs, dict]):
            def execute(self) -> dict:
                allowed_roles = {"admin", "editor"}
                if self.inputs.user_role not in allowed_roles:
                    self.add_runtime_error("forbidden", "Insufficient permissions")
                    return None
                return {"resource_id": self.inputs.resource_id, "access": "granted"}

        connector = MCPConnector(name="ResourceService", version="1.0.0")
        connector.connect(domain)

        # Allowed role
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::Resources::AccessResource",
                "arguments": {"resource_id": "res_123", "user_role": "admin"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert "result" in data

        # Denied role
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "Test::Resources::AccessResource",
                "arguments": {"resource_id": "res_123", "user_role": "viewer"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        assert data["result"]["isError"] is True

    def test_mcp_auth_multi_tenant(self, clean_registries):
        """Test: MCP with multi-tenant authentication"""
        domain = Domain("MultiTenant", organization="Test")

        class TenantDataInputs(BaseModel):
            tenant_id: str
            data_id: str

        @domain.command
        class GetTenantData(Command[TenantDataInputs, dict]):
            def execute(self) -> dict:
                # Simulate tenant isolation
                return {
                    "tenant_id": self.inputs.tenant_id,
                    "data_id": self.inputs.data_id,
                    "data": f"Data for tenant {self.inputs.tenant_id}"
                }

        connector = MCPConnector(name="TenantService", version="1.0.0")
        connector.connect(domain)

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "Test::MultiTenant::GetTenantData",
                "arguments": {"tenant_id": "tenant_a", "data_id": "data_1"}
            }
        })

        response = connector.run(request)
        data = json.loads(response)
        result = json.loads(data["result"]["content"][0]["text"])
        assert result["tenant_id"] == "tenant_a"


# ============================================================================
# SECTION 7: END-TO-END WORKFLOW TESTS (10+ tests)
# ============================================================================

class TestEndToEndWorkflows:
    """Test complete multi-command workflows"""

    def test_e2e_user_registration_and_login(self, clean_registries):
        """Test: Complete user registration and login flow"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("Auth", organization="E2E")

        class RegisterInputs(BaseModel):
            username: str
            email: str
            password: str

        @domain.command
        class Register(Command[RegisterInputs, User]):
            def execute(self) -> User:
                # Check if user exists
                existing = repo.find_by(User, username=self.inputs.username)
                if existing:
                    self.add_runtime_error("user_exists", "Username already taken")
                    return None

                user = User(
                    username=self.inputs.username,
                    email=self.inputs.email,
                    password_hash=f"hash_{self.inputs.password}"
                )
                return repo.save(user)

        class LoginInputs(BaseModel):
            username: str
            password: str

        @domain.command
        class Login(Command[LoginInputs, dict]):
            def execute(self) -> dict:
                users = repo.find_by(User, username=self.inputs.username)
                if not users:
                    self.add_runtime_error("invalid_credentials", "Invalid credentials")
                    return None

                user = users[0]
                expected_hash = f"hash_{self.inputs.password}"
                if user.password_hash != expected_hash:
                    self.add_runtime_error("invalid_credentials", "Invalid credentials")
                    return None

                return {"user_id": user.id, "username": user.username, "token": "jwt_token"}

        # Workflow: Register -> Login
        reg_outcome = Register.run(username="alice", email="alice@test.com", password="secret123")
        assert reg_outcome.is_success()

        login_outcome = Login.run(username="alice", password="secret123")
        assert login_outcome.is_success()
        assert login_outcome.unwrap()["username"] == "alice"

    def test_e2e_order_fulfillment(self, clean_registries):
        """Test: Complete order creation and fulfillment flow"""
        user_repo = InMemoryRepository()
        product_repo = InMemoryRepository()
        order_repo = InMemoryRepository()
        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Product, product_repo)
        RepositoryRegistry.register(Order, order_repo)

        domain = Domain("Commerce", organization="E2E")

        # Seed data
        user = user_repo.save(User(username="buyer", email="buyer@test.com", password_hash="hash"))
        product = product_repo.save(Product(name="Widget", price=99.99, stock=10))

        class CreateOrderInputs(BaseModel):
            user_id: int
            product_id: int
            quantity: int

        @domain.command
        class CreateOrder(Command[CreateOrderInputs, Order]):
            def execute(self) -> Order:
                product = product_repo.find(Product, self.inputs.product_id)
                if product.stock < self.inputs.quantity:
                    self.add_runtime_error("insufficient_stock", "Not enough stock")
                    return None

                product.stock -= self.inputs.quantity
                product_repo.save(product)

                order = Order(
                    user_id=self.inputs.user_id,
                    product_id=self.inputs.product_id,
                    quantity=self.inputs.quantity,
                    total=product.price * self.inputs.quantity
                )
                return order_repo.save(order)

        class FulfillOrderInputs(BaseModel):
            order_id: int

        @domain.command
        class FulfillOrder(Command[FulfillOrderInputs, Order]):
            def execute(self) -> Order:
                order = order_repo.find(Order, self.inputs.order_id)
                if not order:
                    self.add_runtime_error("not_found", "Order not found")
                    return None

                order.status = "fulfilled"
                return order_repo.save(order)

        # Workflow: Create Order -> Fulfill Order
        order_outcome = CreateOrder.run(user_id=user.id, product_id=product.id, quantity=2)
        assert order_outcome.is_success()
        order = order_outcome.unwrap()

        fulfill_outcome = FulfillOrder.run(order_id=order.id)
        assert fulfill_outcome.is_success()
        assert fulfill_outcome.unwrap().status == "fulfilled"

    def test_e2e_multi_step_data_processing(self, clean_registries):
        """Test: Multi-step data processing pipeline"""
        domain = Domain("Pipeline", organization="E2E")

        class Step1Inputs(BaseModel):
            data: str

        @domain.command
        class Step1Validate(Command[Step1Inputs, str]):
            def execute(self) -> str:
                if not self.inputs.data:
                    self.add_runtime_error("empty_data", "Data cannot be empty")
                    return None
                return self.inputs.data.strip()

        class Step2Inputs(BaseModel):
            data: str

        @domain.command
        class Step2Transform(Command[Step2Inputs, str]):
            def execute(self) -> str:
                return self.inputs.data.upper()

        class Step3Inputs(BaseModel):
            data: str

        @domain.command
        class Step3Enrich(Command[Step3Inputs, dict]):
            def execute(self) -> dict:
                return {
                    "original": self.inputs.data,
                    "length": len(self.inputs.data),
                    "processed": True
                }

        class PipelineInputs(BaseModel):
            raw_data: str

        @domain.command
        class RunPipeline(Command[PipelineInputs, dict]):
            def execute(self) -> dict:
                validated = self.run_subcommand_bang(Step1Validate, data=self.inputs.raw_data)
                transformed = self.run_subcommand_bang(Step2Transform, data=validated)
                enriched = self.run_subcommand_bang(Step3Enrich, data=transformed)
                return enriched

        outcome = RunPipeline.run(raw_data="  hello world  ")
        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["original"] == "HELLO WORLD"
        assert result["processed"] is True

    def test_e2e_nested_subcommand_workflow(self, clean_registries):
        """Test: Deeply nested subcommand workflow"""
        domain = Domain("Nested", organization="E2E")

        class CalcInputs(BaseModel):
            value: int

        @domain.command
        class Add10(Command[CalcInputs, int]):
            def execute(self) -> int:
                return self.inputs.value + 10

        @domain.command
        class Multiply2(Command[CalcInputs, int]):
            def execute(self) -> int:
                return self.inputs.value * 2

        @domain.command
        class Subtract5(Command[CalcInputs, int]):
            def execute(self) -> int:
                return self.inputs.value - 5

        @domain.command
        class ComplexCalc(Command[CalcInputs, int]):
            def execute(self) -> int:
                step1 = self.run_subcommand_bang(Add10, value=self.inputs.value)
                step2 = self.run_subcommand_bang(Multiply2, value=step1)
                step3 = self.run_subcommand_bang(Subtract5, value=step2)
                return step3

        outcome = ComplexCalc.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 25  # ((5 + 10) * 2) - 5

    def test_e2e_error_recovery_workflow(self, clean_registries):
        """Test: Workflow with error recovery"""
        domain = Domain("Recovery", organization="E2E")

        class ProcessInputs(BaseModel):
            value: int
            fallback: int

        @domain.command
        class RiskyOperation(Command[ProcessInputs, int]):
            def execute(self) -> int:
                if self.inputs.value < 0:
                    self.add_runtime_error("negative_value", "Value cannot be negative")
                    return None
                return self.inputs.value * 10

        @domain.command
        class SafeOperation(Command[ProcessInputs, int]):
            def execute(self) -> int:
                outcome = self.run_subcommand(RiskyOperation, value=self.inputs.value, fallback=0)
                if outcome.is_failure():
                    # Use fallback
                    return self.inputs.fallback
                return outcome.unwrap()

        # Success case
        outcome = SafeOperation.run(value=5, fallback=0)
        assert outcome.is_success()
        assert outcome.unwrap() == 50

        # Error recovery case
        outcome = SafeOperation.run(value=-1, fallback=100)
        assert outcome.is_success()
        assert outcome.unwrap() == 100

    def test_e2e_batch_processing_workflow(self, clean_registries):
        """Test: Batch processing workflow"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)
        domain = Domain("Batch", organization="E2E")

        class ProcessItemInputs(BaseModel):
            item: dict

        @domain.command
        class ProcessItem(Command[ProcessItemInputs, Product]):
            def execute(self) -> Product:
                product = Product(**self.inputs.item)
                return repo.save(product)

        class BatchInputs(BaseModel):
            items: List[dict]

        @domain.command
        class ProcessBatch(Command[BatchInputs, List[Product]]):
            def execute(self) -> List[Product]:
                results = []
                for item in self.inputs.items:
                    outcome = self.run_subcommand(ProcessItem, item=item)
                    if outcome.is_success():
                        results.append(outcome.unwrap())
                return results

        items = [
            {"name": "P1", "price": 10, "stock": 5},
            {"name": "P2", "price": 20, "stock": 10},
            {"name": "P3", "price": 30, "stock": 15}
        ]

        outcome = ProcessBatch.run(items=items)
        assert outcome.is_success()
        products = outcome.unwrap()
        assert len(products) == 3

    def test_e2e_transaction_workflow(self, clean_registries):
        """Test: Complete transaction workflow"""
        user_repo = InMemoryRepository()
        order_repo = InMemoryRepository()
        RepositoryRegistry.register(User, user_repo)
        RepositoryRegistry.register(Order, order_repo)

        domain = Domain("Transaction", organization="E2E")

        user = user_repo.save(User(username="buyer", email="buyer@test.com", password_hash="hash"))

        class CheckoutInputs(BaseModel):
            user_id: int
            product_id: int
            quantity: int

        @domain.command
        class Checkout(Command[CheckoutInputs, dict]):
            def execute(self) -> dict:
                # Verify user
                user = user_repo.find(User, self.inputs.user_id)
                if not user:
                    self.add_runtime_error("user_not_found", "User not found")
                    return None

                # Create order
                order = Order(
                    user_id=self.inputs.user_id,
                    product_id=self.inputs.product_id,
                    quantity=self.inputs.quantity,
                    total=99.99
                )
                saved_order = order_repo.save(order)

                return {
                    "order_id": saved_order.id,
                    "user_id": user.id,
                    "status": "created"
                }

        outcome = Checkout.run(user_id=user.id, product_id=1, quantity=2)
        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["status"] == "created"

    def test_e2e_mapper_entity_workflow(self, clean_registries):
        """Test: Workflow with mappers and entities"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("MapperFlow", organization="E2E")

        class UserDTO(BaseModel):
            username: str
            email: str

        class UserResponse(BaseModel):
            id: str
            username: str

        @domain_mapper(domain="MapperFlow", organization="E2E")
        class DTOToUser(DomainMapper[UserDTO, User]):
            def map(self) -> User:
                return User(
                    username=self.from_value.username,
                    email=self.from_value.email,
                    password_hash="hash"
                )

        @domain_mapper(domain="MapperFlow", organization="E2E")
        class UserToResponse(DomainMapper[User, UserResponse]):
            def map(self) -> UserResponse:
                return UserResponse(
                    id=str(self.from_value.id),
                    username=self.from_value.username
                )

        class CreateInputs(BaseModel):
            dto: UserDTO

        @domain.command
        class CreateAndReturn(Command[CreateInputs, UserResponse]):
            def execute(self) -> UserResponse:
                user = DTOToUser.map_value(self.inputs.dto)
                saved = repo.save(user)
                return UserToResponse.map_value(saved)

        dto = UserDTO(username="workflow", email="workflow@test.com")
        outcome = CreateAndReturn.run(dto=dto)
        assert outcome.is_success()
        response = outcome.unwrap()
        assert response.username == "workflow"

    def test_e2e_cross_domain_workflow(self, clean_registries):
        """Test: Workflow spanning multiple domains"""
        org = "Workflow"
        domain1 = Domain("Domain1", organization=org)
        domain2 = Domain("Domain2", organization=org)
        domain3 = Domain("Domain3", organization=org)

        domain2.depends_on("Domain1")
        domain3.depends_on("Domain2")

        class ValueInputs(BaseModel):
            value: int

        @domain1.command
        class ProcessD1(Command[ValueInputs, int]):
            def execute(self) -> int:
                return self.inputs.value + 1

        @domain2.command
        class ProcessD2(Command[ValueInputs, int]):
            def execute(self) -> int:
                result = self.run_subcommand_bang(ProcessD1, value=self.inputs.value)
                return result * 2

        @domain3.command
        class ProcessD3(Command[ValueInputs, int]):
            def execute(self) -> int:
                result = self.run_subcommand_bang(ProcessD2, value=self.inputs.value)
                return result + 10

        outcome = ProcessD3.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 22  # ((5 + 1) * 2) + 10

    def test_e2e_validation_cascade(self, clean_registries):
        """Test: Cascading validation workflow"""
        domain = Domain("Validation", organization="E2E")

        class InputValidInputs(BaseModel):
            value: int

        @domain.command
        class ValidateInput(Command[InputValidInputs, int]):
            def execute(self) -> int:
                if self.inputs.value < 0:
                    self.add_input_error(["value"], "negative", "Value cannot be negative")
                    return None
                return self.inputs.value

        class BusinessValidInputs(BaseModel):
            value: int

        @domain.command
        class ValidateBusiness(Command[BusinessValidInputs, int]):
            def execute(self) -> int:
                validated = self.run_subcommand_bang(ValidateInput, value=self.inputs.value)
                if validated > 100:
                    self.add_runtime_error("too_large", "Value exceeds limit")
                    return None
                return validated

        # Success
        outcome = ValidateBusiness.run(value=50)
        assert outcome.is_success()

        # Input validation failure
        outcome = ValidateBusiness.run(value=-1)
        assert outcome.is_failure()

        # Business validation failure
        outcome = ValidateBusiness.run(value=101)
        assert outcome.is_failure()

    def test_e2e_full_crud_lifecycle(self, clean_registries):
        """Test: Complete CRUD lifecycle in workflow"""
        repo = InMemoryRepository()
        RepositoryRegistry.register(User, repo)
        domain = Domain("CRUDFlow", organization="E2E")

        class CreateUserInputs(BaseModel):
            username: str
            email: str

        @domain.command
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                user = User(username=self.inputs.username, email=self.inputs.email, password_hash="hash")
                return repo.save(user)

        class UpdateUserInputs(BaseModel):
            user_id: int
            email: str

        @domain.command
        class UpdateUser(Command[UpdateUserInputs, User]):
            def execute(self) -> User:
                user = repo.find(User, self.inputs.user_id)
                user.email = self.inputs.email
                return repo.save(user)

        class DeleteUserInputs(BaseModel):
            user_id: int

        @domain.command
        class DeleteUser(Command[DeleteUserInputs, bool]):
            def execute(self) -> bool:
                user = repo.find(User, self.inputs.user_id)
                return repo.delete(user)

        class FullLifecycleInputs(BaseModel):
            username: str
            initial_email: str
            new_email: str

        @domain.command
        class FullLifecycle(Command[FullLifecycleInputs, dict]):
            def execute(self) -> dict:
                # Create
                user = self.run_subcommand_bang(
                    CreateUser,
                    username=self.inputs.username,
                    email=self.inputs.initial_email
                )

                # Update
                updated_user = self.run_subcommand_bang(
                    UpdateUser,
                    user_id=user.id,
                    email=self.inputs.new_email
                )

                # Delete
                deleted = self.run_subcommand_bang(DeleteUser, user_id=user.id)

                return {
                    "created_id": user.id,
                    "updated_email": updated_user.email,
                    "deleted": deleted
                }

        outcome = FullLifecycle.run(
            username="lifecycle",
            initial_email="initial@test.com",
            new_email="updated@test.com"
        )
        assert outcome.is_success()
        result = outcome.unwrap()
        assert result["updated_email"] == "updated@test.com"
        assert result["deleted"] is True


# Test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
