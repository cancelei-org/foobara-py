#!/usr/bin/env python3
"""
Basic Command Example

Demonstrates the fundamental command pattern with input validation
and structured outcomes.
"""

from pydantic import BaseModel, Field, field_validator
from foobara_py import Command, Domain


# Define a domain for organizing commands
users = Domain("Users", organization="MyApp")


# Define input model with validation
class CreateUserInputs(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="User's full name")
    email: str = Field(..., description="Email address")
    age: int = Field(..., ge=0, le=150, description="User's age")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v or '.' not in v:
            raise ValueError('Invalid email format')
        return v.lower()


# Define result model
class User(BaseModel):
    id: int
    name: str
    email: str
    age: int


# Define the command
@users.command
class CreateUser(Command[CreateUserInputs, User]):
    """Create a new user account"""

    def execute(self) -> User:
        # Access validated inputs via self.inputs
        return User(
            id=1,  # In real app, this would come from database
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )


if __name__ == "__main__":
    # Run command with valid inputs
    print("=== Valid Input ===")
    outcome = CreateUser.run(name="John Doe", email="John@Example.com", age=30)

    if outcome.is_success():
        user = outcome.unwrap()
        print(f"Created user: {user.name} ({user.email})")
    else:
        print("Errors:")
        for error in outcome.errors:
            print(f"  - {error.symbol}: {error.message}")

    # Run command with invalid inputs
    print("\n=== Invalid Input ===")
    outcome = CreateUser.run(name="", email="invalid", age=200)

    if outcome.is_failure():
        print("Validation errors:")
        for error in outcome.errors:
            print(f"  - [{'.'.join(map(str, error.path))}] {error.symbol}: {error.message}")

    # Get command manifest (JSON Schema)
    print("\n=== Command Manifest ===")
    import json
    manifest = CreateUser.manifest()
    print(json.dumps(manifest, indent=2))
