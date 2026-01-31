"""
Greet Command

Auto-generated from Ruby using ruby_to_python_converter.py
"""
from pydantic import BaseModel, Field
from typing import Optional
from foobara_py import Command, Domain
class GreetInputs(BaseModel):
    """Input model for command"""
    who: Optional[str] = 'World'
# Result type: str
class Greet(Command[GreetInputs, str]):
    """Command implementation"""

    def execute(self) -> str:
        # TODO: Port implementation from Ruby
        # Access inputs via self.inputs.<field_name>
        # Example: name = self.inputs.name
        raise NotImplementedError('TODO: Implement execute method')
if __name__ == "__main__":
    # Example usage
    outcome = Greet.run(
        who='World'
    )

    if outcome.is_success():
        result = outcome.unwrap()
        print(f"Success: {result}")
    else:
        print("Errors:")
        for error in outcome.errors:
            print(f"  - {error.symbol}: {error.message}")