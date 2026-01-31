"""
Creates a new user account with validation

Auto-generated from Ruby using ruby_to_python_converter.py
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Annotated, List, Literal, Optional
from foobara_py import Command, Domain
class CreateUserInputs(BaseModel):
    """Input model for command"""
    name: Annotated[str, Field(min_length=1, max_length=100)] = ...
    email: EmailStr = ...
    age: Optional[Annotated[int, Field(ge=0.0, le=150.0)]] = None
    tags: Optional[List[str]] = None
    role: Optional[Literal['admin', 'user', 'guest']] = 'user'
    bio: Optional[Annotated[str, Field(max_length=500)]] = None
class CreateUserResult(BaseModel):
    """Result model for command"""
    # TODO: Define result structure
    pass
class CreateUser(Command[CreateUserInputs, Any]):
    """Creates a new user account with validation"""

    def execute(self) -> Any:
        # TODO: Port implementation from Ruby
        # Access inputs via self.inputs.<field_name>
        # Example: name = self.inputs.name
        raise NotImplementedError('TODO: Implement execute method')
if __name__ == "__main__":
    # Example usage
    outcome = CreateUser.run(
        name="example",
        email="user@example.com",
        age=42,
        tags=[],
        role='user',
        bio="example"
    )

    if outcome.is_success():
        result = outcome.unwrap()
        print(f"Success: {result}")
    else:
        print("Errors:")
        for error in outcome.errors:
            print(f"  - {error.symbol}: {error.message}")