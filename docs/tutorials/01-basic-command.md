# Tutorial 1: Basic Command

**Time:** 15 minutes
**Difficulty:** Beginner

## Learning Objectives

By the end of this tutorial, you will:
- Create a simple foobara-py command
- Define typed inputs using Pydantic
- Run commands and handle outcomes
- Understand the command lifecycle

## Prerequisites

- Python 3.9+
- foobara-py installed (`pip install foobara-py`)
- Basic Python knowledge

## What We'll Build

A temperature converter that converts between Celsius and Fahrenheit.

---

## Step 1: Create the Project Structure

```bash
mkdir temperature_converter
cd temperature_converter
touch converter.py test_converter.py
```

---

## Step 2: Define Input Types

First, we need to define what inputs our command accepts. We use Pydantic models for this:

```python
# converter.py
from pydantic import BaseModel, Field
from typing import Literal

class ConvertTemperatureInputs(BaseModel):
    """Inputs for temperature conversion"""
    temperature: float = Field(..., description="Temperature value to convert")
    from_unit: Literal["C", "F"] = Field(..., description="Source unit (C or F)")
    to_unit: Literal["C", "F"] = Field(..., description="Target unit (C or F)")
```

**What's happening here:**
- `BaseModel` is from Pydantic - it provides validation
- `Field(...)` means the field is required
- `Literal["C", "F"]` means only "C" or "F" are valid
- Docstrings help document your API

---

## Step 3: Create the Command

Now let's create the command that performs the conversion:

```python
# converter.py (continued)
from foobara_py import Command

class ConvertTemperature(Command[ConvertTemperatureInputs, float]):
    """Convert temperature between Celsius and Fahrenheit"""

    def execute(self) -> float:
        """Perform the conversion"""
        temp = self.inputs.temperature
        from_unit = self.inputs.from_unit
        to_unit = self.inputs.to_unit

        # If units are the same, no conversion needed
        if from_unit == to_unit:
            return temp

        # Convert to Celsius first (if not already)
        if from_unit == "F":
            celsius = (temp - 32) * 5/9
        else:
            celsius = temp

        # Convert from Celsius to target unit
        if to_unit == "F":
            return celsius * 9/5 + 32
        else:
            return celsius
```

**Key points:**
- `Command[InputsType, ResultType]` - Generic types for safety
- `execute()` method contains your business logic
- Access inputs via `self.inputs.field_name`
- Return the result directly

---

## Step 4: Run the Command

Now let's use our command:

```python
# converter.py (continued)
if __name__ == "__main__":
    # Convert 0°C to Fahrenheit
    outcome = ConvertTemperature.run(
        temperature=0,
        from_unit="C",
        to_unit="F"
    )

    if outcome.is_success():
        result = outcome.result
        print(f"0°C = {result}°F")  # Output: 0°C = 32.0°F
    else:
        for error in outcome.errors:
            print(f"Error: {error.message}")
```

**Understanding outcomes:**
- Commands return `CommandOutcome` objects
- Check success with `outcome.is_success()`
- Get result with `outcome.result`
- Get errors with `outcome.errors`

---

## Step 5: Test Your Command

Let's write some tests:

```python
# test_converter.py
import pytest
from converter import ConvertTemperature

def test_celsius_to_fahrenheit():
    """Test C to F conversion"""
    outcome = ConvertTemperature.run(
        temperature=0,
        from_unit="C",
        to_unit="F"
    )

    assert outcome.is_success()
    assert outcome.result == 32.0

def test_fahrenheit_to_celsius():
    """Test F to C conversion"""
    outcome = ConvertTemperature.run(
        temperature=32,
        from_unit="F",
        to_unit="C"
    )

    assert outcome.is_success()
    assert outcome.result == 0.0

def test_same_unit_returns_same_value():
    """Test that same unit returns same value"""
    outcome = ConvertTemperature.run(
        temperature=100,
        from_unit="C",
        to_unit="C"
    )

    assert outcome.is_success()
    assert outcome.result == 100.0

def test_invalid_unit_fails_validation():
    """Test that invalid units fail validation"""
    with pytest.raises(Exception):  # Pydantic validation error
        ConvertTemperature.run(
            temperature=100,
            from_unit="K",  # Invalid!
            to_unit="C"
        )
```

Run the tests:

```bash
pytest test_converter.py -v
```

---

## Step 6: Add a Domain

Let's organize our command in a domain:

```python
# converter.py (add at top)
from foobara_py import Domain

# Create domain
conversion = Domain("Conversion", organization="Tutorial")

# Register command
@conversion.command
class ConvertTemperature(Command[ConvertTemperatureInputs, float]):
    # ... same as before
```

**Why use domains:**
- Organize related commands
- Create namespaces
- Enable command discovery
- Support domain dependencies

---

## Complete Code

Here's the full working example:

```python
# converter.py
from pydantic import BaseModel, Field
from typing import Literal
from foobara_py import Command, Domain

# Create domain
conversion = Domain("Conversion", organization="Tutorial")

# Define inputs
class ConvertTemperatureInputs(BaseModel):
    """Inputs for temperature conversion"""
    temperature: float = Field(..., description="Temperature value to convert")
    from_unit: Literal["C", "F"] = Field(..., description="Source unit")
    to_unit: Literal["C", "F"] = Field(..., description="Target unit")

# Create command
@conversion.command
class ConvertTemperature(Command[ConvertTemperatureInputs, float]):
    """Convert temperature between Celsius and Fahrenheit"""

    def execute(self) -> float:
        """Perform the conversion"""
        temp = self.inputs.temperature
        from_unit = self.inputs.from_unit
        to_unit = self.inputs.to_unit

        # If units are the same, no conversion needed
        if from_unit == to_unit:
            return temp

        # Convert to Celsius first (if not already)
        if from_unit == "F":
            celsius = (temp - 32) * 5/9
        else:
            celsius = temp

        # Convert from Celsius to target unit
        if to_unit == "F":
            return celsius * 9/5 + 32
        else:
            return celsius

# Example usage
if __name__ == "__main__":
    # Test conversions
    conversions = [
        (0, "C", "F"),
        (32, "F", "C"),
        (100, "C", "F"),
        (212, "F", "C"),
    ]

    for temp, from_unit, to_unit in conversions:
        outcome = ConvertTemperature.run(
            temperature=temp,
            from_unit=from_unit,
            to_unit=to_unit
        )

        if outcome.is_success():
            print(f"{temp}°{from_unit} = {outcome.result:.1f}°{to_unit}")
```

---

## Exercises

Try these on your own:

### Exercise 1: Add Kelvin Support

Extend the command to support Kelvin:

```python
from_unit: Literal["C", "F", "K"]
to_unit: Literal["C", "F", "K"]
```

Conversion formulas:
- C to K: K = C + 273.15
- K to C: C = K - 273.15

### Exercise 2: Add Validation

Add a validator to ensure Kelvin is never negative:

```python
def execute(self) -> float:
    # Add validation
    if self.inputs.from_unit == "K" and self.inputs.temperature < 0:
        self.add_runtime_error(
            "invalid_kelvin",
            "Kelvin cannot be negative",
            suggestion="Use a temperature >= 0"
        )
        return None

    # ... rest of conversion logic
```

### Exercise 3: Add More Conversions

Create new commands for:
- Length conversion (meters, feet, miles)
- Weight conversion (kg, lbs, oz)
- Currency conversion (use a fixed exchange rate)

---

## Key Takeaways

You've learned:

1. **Commands encapsulate business logic** with typed inputs and outputs
2. **Pydantic provides validation** automatically
3. **Outcomes handle results and errors** without exceptions
4. **Domains organize commands** into logical groups
5. **Testing is straightforward** with simple assertions

---

## Next Steps

Ready for more? Continue to:

- [Tutorial 2: Input Validation](./02-validation.md) - Learn advanced validation
- [Testing Guide](../TESTING_GUIDE.md) - Learn more testing patterns
- [Quick Reference](../QUICK_REFERENCE.md) - See more command patterns

---

## Common Issues

**Q: "Command doesn't accept my inputs"**

A: Make sure all required fields have values. Use `Field(default=...)` for optional fields.

**Q: "How do I make a field optional?"**

A: Use `Optional` type or provide a default:

```python
field: str | None = None
field: str = "default value"
```

**Q: "Can I return multiple values?"**

A: Yes! Use a Pydantic model or dict:

```python
class Result(BaseModel):
    value: float
    unit: str

class MyCommand(Command[Inputs, Result]):
    def execute(self) -> Result:
        return Result(value=42.0, unit="C")
```

---

**Congratulations!** You've completed Tutorial 1. You now know how to create basic commands. Ready for [Tutorial 2](./02-validation.md)?
