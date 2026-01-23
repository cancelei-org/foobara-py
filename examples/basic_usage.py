#!/usr/bin/env python3
"""
Basic usage example for foobara-py

Demonstrates:
- Creating commands with Pydantic inputs
- Using the Outcome pattern
- Domain organization
- MCP integration
"""

from pydantic import BaseModel, Field
from typing import Optional, List

from foobara_py import Command, Domain, Outcome, command
from foobara_py.core import CommandOutcome, DataError
from foobara_py.connectors import MCPConnector


# =============================================================================
# 1. Define Types (Pydantic Models)
# =============================================================================

class UserInputs(BaseModel):
    """Inputs for creating a user"""
    name: str = Field(..., min_length=1, description="User's full name")
    email: str = Field(..., description="User's email address")
    age: Optional[int] = Field(None, ge=0, le=150, description="Age in years")


class User(BaseModel):
    """User entity"""
    id: int
    name: str
    email: str
    age: Optional[int] = None


class UpdateUserInputs(BaseModel):
    """Inputs for updating a user"""
    id: int = Field(..., description="User ID to update")
    name: Optional[str] = Field(None, min_length=1)
    email: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=150)


# =============================================================================
# 2. Create Domain
# =============================================================================

users_domain = Domain("Users", organization="Example")


# =============================================================================
# 3. Define Commands
# =============================================================================

# In-memory storage for demo
_users_db: dict[int, User] = {}
_next_id = 1


@users_domain.command
class CreateUser(Command[UserInputs, User]):
    """Create a new user account"""

    def execute(self) -> User:
        global _next_id

        # Validate email format (custom validation)
        if '@' not in self.inputs.email:
            self.add_input_error(
                path=["email"],
                symbol="invalid_format",
                message="Email must contain @ symbol"
            )
            return None

        # Check for duplicate email
        for user in _users_db.values():
            if user.email == self.inputs.email:
                self.add_input_error(
                    path=["email"],
                    symbol="already_exists",
                    message=f"Email {self.inputs.email} already registered"
                )
                return None

        # Create user
        user = User(
            id=_next_id,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )
        _users_db[_next_id] = user
        _next_id += 1

        return user


@users_domain.command
class GetUser(Command[BaseModel, User]):
    """Get user by ID"""

    class Inputs(BaseModel):
        id: int = Field(..., description="User ID")

    @classmethod
    def inputs_type(cls):
        return cls.Inputs

    def execute(self) -> User:
        user_id = self._raw_inputs.get("id")
        if user_id not in _users_db:
            self.add_runtime_error(
                symbol="not_found",
                message=f"User {user_id} not found"
            )
            return None
        return _users_db[user_id]


@users_domain.command
class ListUsers(Command[BaseModel, List[User]]):
    """List all users"""

    class Inputs(BaseModel):
        pass

    @classmethod
    def inputs_type(cls):
        return cls.Inputs

    def execute(self) -> List[User]:
        return list(_users_db.values())


@users_domain.command
class UpdateUser(Command[UpdateUserInputs, User]):
    """Update an existing user"""

    def execute(self) -> User:
        user_id = self.inputs.id

        if user_id not in _users_db:
            self.add_runtime_error(
                symbol="not_found",
                message=f"User {user_id} not found"
            )
            return None

        user = _users_db[user_id]

        # Update fields if provided
        if self.inputs.name:
            user = User(
                id=user.id,
                name=self.inputs.name,
                email=user.email,
                age=user.age
            )
        if self.inputs.email:
            user = User(
                id=user.id,
                name=user.name,
                email=self.inputs.email,
                age=user.age
            )
        if self.inputs.age is not None:
            user = User(
                id=user.id,
                name=user.name,
                email=user.email,
                age=self.inputs.age
            )

        _users_db[user_id] = user
        return user


@users_domain.command
class DeleteUser(Command[BaseModel, bool]):
    """Delete a user"""

    class Inputs(BaseModel):
        id: int

    @classmethod
    def inputs_type(cls):
        return cls.Inputs

    def execute(self) -> bool:
        user_id = self._raw_inputs.get("id")
        if user_id not in _users_db:
            self.add_runtime_error(
                symbol="not_found",
                message=f"User {user_id} not found"
            )
            return False
        del _users_db[user_id]
        return True


# =============================================================================
# 4. Usage Examples
# =============================================================================

def demo_basic_usage():
    """Demonstrate basic command usage"""
    print("\n=== Basic Command Usage ===\n")

    # Create a user
    outcome = CreateUser.run(
        name="John Doe",
        email="john@example.com",
        age=30
    )

    if outcome.is_success():
        user = outcome.unwrap()
        print(f"Created user: {user}")
    else:
        print(f"Failed: {outcome.errors}")

    # Try to create duplicate
    outcome = CreateUser.run(
        name="John Duplicate",
        email="john@example.com"
    )

    if outcome.is_failure():
        print(f"Expected error: {outcome.errors[0].message}")

    # List users
    outcome = ListUsers.run()
    print(f"All users: {outcome.unwrap()}")

    # Update user
    outcome = UpdateUser.run(id=1, name="John Updated")
    if outcome.is_success():
        print(f"Updated user: {outcome.unwrap()}")


def demo_mcp_integration():
    """Demonstrate MCP connector"""
    print("\n=== MCP Integration ===\n")

    # Create MCP connector
    connector = MCPConnector(
        name="UserService",
        version="1.0.0",
        instructions="User management service"
    )

    # Connect domain
    connector.connect(users_domain)

    # Simulate initialize request
    init_request = '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test"}, "capabilities": {}}}'
    response = connector.run(init_request)
    print(f"Initialize response: {response}")

    # List tools
    list_request = '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}'
    response = connector.run(list_request)
    print(f"Tools list: {response}")

    # Call a tool
    call_request = '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "Example::Users::ListUsers", "arguments": {}}}'
    response = connector.run(call_request)
    print(f"Tool call result: {response}")


def demo_domain_manifest():
    """Demonstrate manifest generation"""
    print("\n=== Domain Manifest ===\n")

    manifest = users_domain.manifest()
    import json
    print(json.dumps(manifest, indent=2, default=str))


if __name__ == "__main__":
    demo_basic_usage()
    demo_mcp_integration()
    demo_domain_manifest()
