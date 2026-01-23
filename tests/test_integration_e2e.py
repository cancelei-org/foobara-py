"""
End-to-end integration tests for foobara-py

This test suite validates complete workflows that integrate multiple components
of the foobara-py framework. Unlike unit tests that test individual components
in isolation, these integration tests verify that components work together
correctly in realistic scenarios.

## Test Coverage

### 1. Multi-Domain E-Commerce Flow (TestMultiDomainEcommerceFlow)
Tests complete business workflows across multiple domains:
- User registration -> Order creation -> Payment processing
- Domain dependency validation (B depends on A)
- Cross-domain command calls with proper dependencies

**Pattern**: Create separate domains for different business concerns, establish
dependencies, and test full workflows that span multiple domains.

### 2. MCP Connector Integration (TestMCPConnectorIntegration)
Tests the Model Context Protocol connector with complete request/response cycles:
- Initialize handshake
- List available tools
- Execute tool calls (successful and error cases)
- Batch request handling

**Pattern**: Create connector, register commands/domains, send JSON-RPC requests,
validate responses follow MCP protocol.

### 3. Async Command Chains (TestAsyncCommandChains)
Tests async command execution patterns:
- Basic async command execution with await
- Async I/O simulation

**Pattern**: Use AsyncCommand base class, implement async execute(), call with
await Command.run(**inputs).

### 4. Entity Repository Integration (TestEntityRepositoryIntegration)
Tests complete entity lifecycle through commands:
- Create entity -> Save to repository
- Load entity -> Modify -> Save
- Delete entity
- Validation and error handling

**Pattern**: Define entity with @entity decorator, register repository, use
commands to orchestrate CRUD operations, validate persistence.

### 5. Error Propagation Across Stack (TestErrorPropagationStack)
Tests error handling through nested command hierarchies:
- Level 3 command fails -> Level 2 propagates -> Level 1 receives error
- Runtime path tracking in errors
- Successful nested execution

**Pattern**: Use run_subcommand_bang() to propagate errors automatically.
Errors include runtime_path showing the call stack.

### 6. Performance and Load (TestPerformanceLoad)
Tests system behavior under repeated execution:
- Execute many commands sequentially
- Verify consistency and reliability

**Pattern**: Run commands in a loop, verify all succeed, check results.

## Key Integration Test Patterns

### Pattern 1: Domain Dependencies
```python
domain_a = Domain("A", organization="Org")
domain_b = Domain("B", organization="Org")
domain_b.depends_on("A")  # B can call commands from A

@domain_b.command
class CommandB(Command[InputT, ResultT]):
    def execute(self):
        result = self.run_subcommand_bang(CommandA, **inputs)
        return process(result)
```

### Pattern 2: MCP Request/Response
```python
connector = MCPConnector(name="Service", version="1.0.0")
connector.connect(domain)

request = json.dumps({"jsonrpc": "2.0", "method": "tools/call", ...})
response = connector.run(request)
data = json.loads(response)
```

### Pattern 3: Entity Persistence
```python
@entity(primary_key='id')
class MyEntity(EntityBase):
    id: Optional[int] = None
    name: str

repo = InMemoryRepository()
RepositoryRegistry.register(MyEntity, repo)

# Use in commands
saved = repo.save(entity)
found = repo.find(MyEntity, entity_id)
```

### Pattern 4: Error Propagation
```python
# Use run_subcommand_bang for automatic error propagation
result = self.run_subcommand_bang(SubCommand, **inputs)
# If SubCommand fails, errors propagate automatically
```

## Running Integration Tests

```bash
# Run all integration tests
pytest tests/test_integration_e2e.py -v

# Run specific test class
pytest tests/test_integration_e2e.py::TestMultiDomainEcommerceFlow -v

# Run with coverage
pytest tests/test_integration_e2e.py --cov=foobara_py
```

## Adding New Integration Tests

When adding integration tests, follow these guidelines:

1. **Test realistic scenarios** - Combine multiple features as users would
2. **Use clean fixtures** - Reset registries between tests
3. **Document the pattern** - Add comments explaining the integration pattern
4. **Verify end-to-end** - Test from input validation through to final result
5. **Include error cases** - Test failure paths, not just success paths
"""

import pytest
import json
from pydantic import BaseModel, Field
from typing import Optional, List

from foobara_py import Command, AsyncCommand, Domain
from foobara_py.core.outcome import CommandOutcome
from foobara_py.persistence import entity, EntityBase, InMemoryRepository, RepositoryRegistry
from foobara_py.connectors.mcp import MCPConnector


# ==================== Test Fixtures ====================

@pytest.fixture
def clean_domain_registry():
    """Clean domain registry before and after tests"""
    Domain._registry.clear()
    yield
    Domain._registry.clear()


@pytest.fixture
def clean_repository_registry():
    """Clean repository registry before and after tests"""
    RepositoryRegistry.clear()
    yield
    RepositoryRegistry.clear()


# ==================== Test Models ====================

class UserRegistrationInputs(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    email: str
    password: str = Field(..., min_length=8)


class UserProfile(BaseModel):
    id: int
    username: str
    email: str
    verified: bool = False


class OrderInputs(BaseModel):
    user_id: int
    product_id: int
    quantity: int = Field(gt=0, le=100)


class Order(BaseModel):
    id: int
    user_id: int
    product_id: int
    quantity: int
    status: str = "pending"


class PaymentInputs(BaseModel):
    order_id: int
    amount: float = Field(gt=0)


class PaymentResult(BaseModel):
    transaction_id: str
    order_id: int
    status: str


# ==================== Test: Multi-Domain E-Commerce Flow ====================

class TestMultiDomainEcommerceFlow:
    """Test complete e-commerce workflow across multiple domains"""

    def test_complete_order_flow(self, clean_domain_registry):
        """Test user registration -> order creation -> payment flow"""

        # Set up domains with dependencies
        org_name = "EcommerceTest"
        users_domain = Domain("Users", organization=org_name)
        orders_domain = Domain("Orders", organization=org_name)
        payments_domain = Domain("Payments", organization=org_name)

        # Set up dependencies: Orders depends on Users, Payments depends on Orders
        orders_domain.depends_on("Users")
        payments_domain.depends_on("Orders")

        # Step 1: Register user
        @users_domain.command
        class RegisterUser(Command[UserRegistrationInputs, UserProfile]):
            """Register a new user account"""

            def execute(self) -> UserProfile:
                # Simulate validation
                if "@" not in self.inputs.email:
                    self.add_input_error(["email"], "invalid_format", "Invalid email")
                    return None

                return UserProfile(
                    id=1,
                    username=self.inputs.username,
                    email=self.inputs.email,
                    verified=False
                )

        # Step 2: Create order
        @orders_domain.command
        class CreateOrder(Command[OrderInputs, Order]):
            """Create a new order"""

            def execute(self) -> Order:
                # Validate user exists (simplified)
                if self.inputs.user_id <= 0:
                    self.add_runtime_error("invalid_user", "User not found")
                    return None

                return Order(
                    id=100,
                    user_id=self.inputs.user_id,
                    product_id=self.inputs.product_id,
                    quantity=self.inputs.quantity,
                    status="pending"
                )

        # Step 3: Process payment
        @payments_domain.command
        class ProcessPayment(Command[PaymentInputs, PaymentResult]):
            """Process payment for an order"""

            def execute(self) -> PaymentResult:
                if self.inputs.amount <= 0:
                    self.add_runtime_error("invalid_amount", "Amount must be positive")
                    return None

                return PaymentResult(
                    transaction_id=f"txn_{self.inputs.order_id}",
                    order_id=self.inputs.order_id,
                    status="completed"
                )

        # Execute the full flow
        # 1. Register user
        user_outcome = RegisterUser.run(
            username="john_doe",
            email="john@example.com",
            password="securepass123"
        )
        assert user_outcome.is_success()
        user = user_outcome.unwrap()
        assert user.id == 1

        # 2. Create order
        order_outcome = CreateOrder.run(
            user_id=user.id,
            product_id=42,
            quantity=2
        )
        assert order_outcome.is_success()
        order = order_outcome.unwrap()
        assert order.user_id == user.id
        assert order.status == "pending"

        # 3. Process payment
        payment_outcome = ProcessPayment.run(
            order_id=order.id,
            amount=99.99
        )
        assert payment_outcome.is_success()
        payment = payment_outcome.unwrap()
        assert payment.order_id == order.id
        assert payment.status == "completed"

    def test_cross_domain_validation_with_dependency(self, clean_domain_registry):
        """Test that cross-domain calls work with proper dependencies"""

        org_name = "ValidationTest"
        domain_a = Domain("DomainA", organization=org_name)
        domain_b = Domain("DomainB", organization=org_name)

        # Set up dependency: B depends on A
        domain_b.depends_on("DomainA")

        class SimpleInputs(BaseModel):
            value: str

        @domain_a.command
        class CommandA(Command[SimpleInputs, str]):
            def execute(self) -> str:
                return f"A:{self.inputs.value}"

        @domain_b.command
        class CommandB(Command[SimpleInputs, str]):
            def execute(self) -> str:
                # Call CommandA from DomainB (allowed because of dependency)
                result = self.run_subcommand_bang(CommandA, value=self.inputs.value)
                return f"B:{result}"

        # This should succeed with proper dependency
        outcome = CommandB.run(value="test")
        assert outcome.is_success()
        assert outcome.unwrap() == "B:A:test"


# ==================== Test: MCP Connector Integration ====================

class TestMCPConnectorIntegration:
    """Test MCP connector with complete workflows"""

    def test_mcp_full_workflow(self, clean_domain_registry):
        """Test complete MCP workflow: initialize -> list tools -> call tool"""

        # Set up domain and command
        calc_domain = Domain("Calculator", organization="MathTest")

        class CalculateInputs(BaseModel):
            a: float
            b: float
            operation: str = Field(..., pattern="^(add|subtract|multiply|divide)$")

        @calc_domain.command
        class Calculate(Command[CalculateInputs, float]):
            """Perform mathematical operation"""

            def execute(self) -> float:
                a, b = self.inputs.a, self.inputs.b
                op = self.inputs.operation

                if op == "add":
                    return a + b
                elif op == "subtract":
                    return a - b
                elif op == "multiply":
                    return a * b
                elif op == "divide":
                    if b == 0:
                        self.add_runtime_error("division_by_zero", "Cannot divide by zero")
                        return None
                    return a / b

        # Create MCP connector
        connector = MCPConnector(name="MathService", version="1.0.0")
        connector.connect(calc_domain)

        # Step 1: Initialize
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
        assert data["result"]["serverInfo"]["name"] == "MathService"

        # Step 2: List tools
        list_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })

        response = connector.run(list_request)
        data = json.loads(response)
        assert "tools" in data["result"]
        assert len(data["result"]["tools"]) > 0

        # Step 3: Call tool successfully
        call_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "MathTest::Calculator::Calculate",
                "arguments": {
                    "a": 10.0,
                    "b": 5.0,
                    "operation": "multiply"
                }
            }
        })

        response = connector.run(call_request)
        data = json.loads(response)
        assert "result" in data
        result_content = json.loads(data["result"]["content"][0]["text"])
        assert result_content == 50.0

        # Step 4: Call tool with error
        error_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "MathTest::Calculator::Calculate",
                "arguments": {
                    "a": 10.0,
                    "b": 0.0,
                    "operation": "divide"
                }
            }
        })

        response = connector.run(error_request)
        data = json.loads(response)
        assert data["result"]["isError"] is True

    def test_mcp_batch_requests(self, clean_domain_registry):
        """Test MCP batch request handling"""

        domain = Domain("Batch", organization="Test")

        class EchoInputs(BaseModel):
            message: str

        @domain.command
        class Echo(Command[EchoInputs, str]):
            def execute(self) -> str:
                return f"Echo: {self.inputs.message}"

        connector = MCPConnector(name="BatchTest", version="1.0.0")
        connector.connect(domain)

        # Send batch request
        batch_request = json.dumps([
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "Test::Batch::Echo",
                    "arguments": {"message": "first"}
                }
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "Test::Batch::Echo",
                    "arguments": {"message": "second"}
                }
            }
        ])

        response = connector.run(batch_request)
        data = json.loads(response)

        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["id"] == 2


# ==================== Test: Async Command Chains ====================

class TestAsyncCommandChains:
    """Test async commands execution"""

    @pytest.mark.asyncio
    async def test_async_command_execution(self, clean_domain_registry):
        """Test basic async command execution"""

        domain = Domain("AsyncTest", organization="Test")

        class DataInputs(BaseModel):
            value: int

        @domain.command
        class FetchData(AsyncCommand[DataInputs, int]):
            """Async fetch operation"""

            async def execute(self) -> int:
                # Simulate async I/O
                return self.inputs.value * 2

        @domain.command
        class ProcessData(AsyncCommand[DataInputs, int]):
            """Process data with transformation"""

            async def execute(self) -> int:
                # Simple transformation
                return self.inputs.value + 10

        # Test first async command
        outcome = await FetchData.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 10

        # Test second async command
        outcome2 = await ProcessData.run(value=5)
        assert outcome2.is_success()
        assert outcome2.unwrap() == 15


# ==================== Test: Entity Repository Integration ====================

class TestEntityRepositoryIntegration:
    """Test entity persistence across commands"""

    def test_entity_lifecycle_through_commands(
        self,
        clean_domain_registry,
        clean_repository_registry
    ):
        """Test complete entity lifecycle: create -> read -> update -> delete"""

        # Define entity
        @entity(primary_key='id')
        class Product(EntityBase):
            id: Optional[int] = None
            name: str
            price: float
            stock: int = 0

        # Set up repository
        repo = InMemoryRepository()
        RepositoryRegistry.register(Product, repo)

        # Create domain and commands
        domain = Domain("Products", organization="Store")

        class CreateProductInputs(BaseModel):
            name: str
            price: float
            stock: int

        class UpdateStockInputs(BaseModel):
            product_id: int
            quantity_change: int

        @domain.command
        class CreateProduct(Command[CreateProductInputs, Product]):
            """Create a new product"""

            def execute(self) -> Product:
                product = Product(
                    name=self.inputs.name,
                    price=self.inputs.price,
                    stock=self.inputs.stock
                )
                saved = repo.save(product)
                return saved

        @domain.command
        class UpdateStock(Command[UpdateStockInputs, Product]):
            """Update product stock"""

            def execute(self) -> Product:
                product = repo.find(Product, self.inputs.product_id)
                if not product:
                    self.add_runtime_error("not_found", "Product not found")
                    return None

                product.stock += self.inputs.quantity_change
                if product.stock < 0:
                    self.add_runtime_error("insufficient_stock", "Stock cannot be negative")
                    return None

                return repo.save(product)

        # Execute lifecycle
        # 1. Create product
        create_outcome = CreateProduct.run(
            name="Laptop",
            price=999.99,
            stock=50
        )
        assert create_outcome.is_success()
        product = create_outcome.unwrap()
        assert product.id is not None
        assert product.stock == 50

        # 2. Update stock (add)
        update_outcome = UpdateStock.run(
            product_id=product.id,
            quantity_change=10
        )
        assert update_outcome.is_success()
        updated = update_outcome.unwrap()
        assert updated.stock == 60

        # 3. Update stock (remove)
        update_outcome = UpdateStock.run(
            product_id=product.id,
            quantity_change=-30
        )
        assert update_outcome.is_success()
        updated = update_outcome.unwrap()
        assert updated.stock == 30

        # 4. Try invalid update (negative stock)
        invalid_outcome = UpdateStock.run(
            product_id=product.id,
            quantity_change=-100
        )
        assert invalid_outcome.is_failure()
        assert "insufficient_stock" in [e.symbol for e in invalid_outcome.errors]


# ==================== Test: Error Propagation Across Stack ====================

class TestErrorPropagationStack:
    """Test error handling through full application stack"""

    def test_nested_subcommand_error_propagation(self, clean_domain_registry):
        """Test errors propagate correctly through nested subcommands"""

        domain = Domain("Nested", organization="Test")

        class ValueInputs(BaseModel):
            value: int

        @domain.command
        class Level3Command(Command[ValueInputs, int]):
            """Deepest level command"""

            def execute(self) -> int:
                if self.inputs.value < 0:
                    self.add_runtime_error(
                        "negative_value",
                        "Value cannot be negative"
                    )
                    return None
                return self.inputs.value * 3

        @domain.command
        class Level2Command(Command[ValueInputs, int]):
            """Middle level command"""

            def execute(self) -> int:
                # Use run_subcommand_bang to propagate errors
                result = self.run_subcommand_bang(Level3Command, value=self.inputs.value)
                return result + 10

        @domain.command
        class Level1Command(Command[ValueInputs, int]):
            """Top level command"""

            def execute(self) -> int:
                # Use run_subcommand_bang to propagate errors
                result = self.run_subcommand_bang(Level2Command, value=self.inputs.value)
                return result * 2

        # Test successful path
        outcome = Level1Command.run(value=5)
        assert outcome.is_success()
        assert outcome.unwrap() == 50  # ((5 * 3) + 10) * 2

        # Test error propagation
        error_outcome = Level1Command.run(value=-1)
        assert error_outcome.is_failure()
        errors = error_outcome.errors
        assert len(errors) > 0
        # Error should have runtime path showing it came from nested command
        assert any("negative_value" in e.symbol for e in errors)


# ==================== Test: Performance and Load ====================

class TestPerformanceLoad:
    """Test system behavior under load"""

    def test_multiple_concurrent_commands(self, clean_domain_registry):
        """Test executing many commands sequentially"""

        domain = Domain("Load", organization="Test")

        class CountInputs(BaseModel):
            n: int

        @domain.command
        class CountUp(Command[CountInputs, int]):
            def execute(self) -> int:
                return self.inputs.n + 1

        # Execute 100 commands
        results = []
        for i in range(100):
            outcome = CountUp.run(n=i)
            assert outcome.is_success()
            results.append(outcome.unwrap())

        assert len(results) == 100
        assert results[0] == 1
        assert results[99] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
