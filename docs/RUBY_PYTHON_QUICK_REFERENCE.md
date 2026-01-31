# Ruby Foobara ↔ Python foobara-py Quick Reference

**Purpose:** Cheat sheet for porting Ruby Foobara code to Python
**Last Updated:** 2026-01-31

---

## Command Definition

### Basic Command

**Ruby:**
```ruby
class Greet < Foobara::Command
  inputs do
    name :string, default: "World"
  end

  result :string

  def execute
    "Hello, #{name}!"
  end
end
```

**Python:**
```python
from pydantic import BaseModel
from foobara_py import Command

class GreetInputs(BaseModel):
    name: str = "World"

class Greet(Command[GreetInputs, str]):
    def execute(self) -> str:
        return f"Hello, {self.inputs.name}!"
```

---

## Input Types

| Ruby | Python | Example |
|------|--------|---------|
| `:string` | `str` | `name: str` |
| `:integer` | `int` | `age: int` |
| `:float` | `float` | `price: float` |
| `:boolean` | `bool` | `active: bool` |
| `:array` | `List[T]` | `tags: List[str]` |
| `:hash` | `Dict[K, V]` | `metadata: Dict[str, Any]` |
| `:duck` / `:object` | `Any` | `data: Any` |
| `:date` | `date` | `from datetime import date; birthday: date` |
| `:datetime` | `datetime` | `from datetime import datetime; created: datetime` |

---

## Input Modifiers

### Required Fields

**Ruby:**
```ruby
inputs do
  name :string, :required
  email :string, :required
end
```

**Python:**
```python
from pydantic import Field

class Inputs(BaseModel):
    name: str = Field(..., description="Name")  # ... = required
    email: str = Field(..., description="Email")
```

### Default Values

**Ruby:**
```ruby
inputs do
  age :integer, default: 18
  active :boolean, default: true
end
```

**Python:**
```python
class Inputs(BaseModel):
    age: int = 18
    active: bool = True
```

### Validations

**Ruby:**
```ruby
inputs do
  age :integer, min: 0, max: 150
  email :string, pattern: /\A[\w+\-.]+@[a-z\d\-]+\.[a-z]+\z/i
end
```

**Python:**
```python
from pydantic import Field, field_validator
import re

class Inputs(BaseModel):
    age: int = Field(..., ge=0, le=150)  # ge = greater/equal, le = less/equal
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not re.match(r'[\w+\-.]+@[a-z\d\-]+\.[a-z]+', v, re.I):
            raise ValueError("Invalid email")
        return v
```

### Arrays with Element Type

**Ruby:**
```ruby
inputs do
  tags :array, element_type: :string
  scores :array, element_type: :integer
end
```

**Python:**
```python
from typing import List

class Inputs(BaseModel):
    tags: List[str] = []
    scores: List[int] = []
```

---

## Domain & Organization

### Ruby Module Structure

**Ruby:**
```ruby
module MyApp
  foobara_organization!

  module Users
    foobara_domain!

    class CreateUser < Foobara::Command
      # ...
    end
  end
end
```

**Python:**
```python
from foobara_py import Domain

users = Domain("Users", organization="MyApp")

@users.command
class CreateUser(Command[CreateUserInputs, User]):
    # ...
```

### Domain Dependencies

**Ruby:**
```ruby
module Billing
  foobara_domain!
  depends_on :Users, :Auth

  class CreateInvoice < Foobara::Command
    # Can call Users:: and Auth:: commands
  end
end
```

**Python:**
```python
billing = Domain("Billing", organization="MyApp")
billing.depends_on("Users", "Auth")

@billing.command
class CreateInvoice(Command[CreateInvoiceInputs, Invoice]):
    # Can call Users and Auth commands
    pass
```

---

## Error Handling

### Declaring Possible Errors

**Ruby:**
```ruby
class CreateUser < Foobara::Command
  possible_input_error :invalid_email, path: [:email]
  possible_runtime_error :user_exists
end
```

**Python:**
```python
class CreateUser(Command[CreateUserInputs, User]):
    _possible_errors = [
        ("invalid_email", "Invalid email format"),
        ("user_exists", "User already exists"),
    ]
```

### Adding Errors

**Ruby:**
```ruby
def execute
  if invalid?
    add_input_error(:email, :invalid_email, "Bad format")
    halt!
  end

  if exists?
    add_runtime_error(:user_exists, "Already registered")
    halt!
  end
end
```

**Python:**
```python
def execute(self) -> User:
    if invalid():
        self.add_input_error(
            path=["email"],
            symbol="invalid_email",
            message="Bad format"
        )
        return None  # Signals failure

    if exists():
        self.add_runtime_error(
            symbol="user_exists",
            message="Already registered",
            halt=True  # Raises Halt internally
        )
```

---

## Subcommands

### Non-Bang (Manual Error Handling)

**Ruby:**
```ruby
def execute
  outcome = run_subcommand(GetUser, user_id: inputs[:user_id])

  if outcome.success?
    user = outcome.result
  else
    # Handle errors
    return
  end
end
```

**Python:**
```python
def execute(self) -> Result:
    user = self.run_subcommand(GetUser, user_id=self.inputs.user_id)

    if user is None:  # Failed
        # Errors already in self.errors
        return None

    # Continue with user
```

### Bang (Automatic Error Propagation)

**Ruby:**
```ruby
def execute
  # Halts automatically on failure
  user = run_subcommand!(GetUser, user_id: inputs[:user_id])

  # Only reaches here if GetUser succeeded
  user
end
```

**Python:**
```python
def execute(self) -> Result:
    # Raises Halt on failure
    user = self.run_subcommand_bang(GetUser, user_id=self.inputs.user_id)

    # Only reaches here if GetUser succeeded
    return user

# Alternative: Ruby-like alias
user = self.run_subcommand_(GetUser, user_id=self.inputs.user_id)
```

---

## Callbacks

### Before/After Execute

**Ruby:**
```ruby
class MyCommand < Foobara::Command
  before_execute do
    puts "Starting..."
  end

  after_execute do |result|
    puts "Done: #{result}"
  end
end
```

**Python:**
```python
from foobara_py.core.callbacks import before, after, CallbackPhase

class MyCommand(Command[MyInputs, Result]):
    @before(CallbackPhase.EXECUTE)
    def log_start(self):
        print("Starting...")

    @after(CallbackPhase.EXECUTE)
    def log_finish(self, result):
        print(f"Done: {result}")
```

### Around Callbacks

**Ruby:**
```ruby
around_execute do |&block|
  start = Time.now
  result = block.call
  puts "Took #{Time.now - start}s"
  result
end
```

**Python:**
```python
import time

class MyCommand(Command[MyInputs, Result]):
    @around(CallbackPhase.EXECUTE)
    def time_execution(self, proceed):
        start = time.time()
        result = proceed()  # Call the original method
        print(f"Took {time.time() - start}s")
        return result
```

---

## Lifecycle Methods

### Ruby

**Ruby:**
```ruby
def execute
  # Main logic
end

def before_execute
  # Called before execute
end

def after_execute(result)
  # Called after execute
  result
end
```

**Python:**
```python
def execute(self) -> Result:
    # Main logic
    pass

def before_execute(self) -> None:
    # Called before execute
    pass

def after_execute(self, result: Result) -> Result:
    # Called after execute
    return result
```

---

## Running Commands

### Run and Get Outcome

**Ruby:**
```ruby
outcome = CreateUser.run(name: "John", email: "john@example.com")

if outcome.success?
  user = outcome.result
  puts "Created: #{user.name}"
else
  puts "Errors: #{outcome.errors_hash}"
end
```

**Python:**
```python
outcome = CreateUser.run(name="John", email="john@example.com")

if outcome.is_success():
    user = outcome.unwrap()  # Or outcome.result
    print(f"Created: {user.name}")
else:
    print(f"Errors: {outcome.errors}")
```

### Run Bang (Raise on Failure)

**Ruby:**
```ruby
user = CreateUser.run!(name: "John", email: "john@example.com")
# Raises if failed
```

**Python:**
```python
# Not supported in Python - use outcome pattern instead
outcome = CreateUser.run(name="John", email="john@example.com")
user = outcome.unwrap()  # Raises if failed
```

---

## Entities

### Basic Entity

**Ruby:**
```ruby
class User < Foobara::Model
  attributes do
    id :integer, :required
    name :string, :required
    email :string, :required
  end

  primary_key :id
end
```

**Python:**
```python
from foobara_py.persistence import EntityBase

class User(EntityBase):
    _primary_key_field = 'id'

    id: int = None
    name: str
    email: str
```

### CRUD Operations

**Ruby:**
```ruby
# Create
user = User.create(name: "John", email: "john@example.com")

# Find
user = User.find(1)
users = User.find_all
users = User.find_by(email: "john@example.com")

# Update
user.name = "Jane"
user.save

# Delete
user.delete
```

**Python:**
```python
# Create
user = User.create(name="John", email="john@example.com")

# Find
user = User.find(1)
users = User.find_all()
users = User.find_by(email="john@example.com")

# Update
user.name = "Jane"
user.save()

# Delete
user.delete()
```

---

## Domain Mappers

### Basic Mapper

**Ruby:**
```ruby
class InternalToExternalUserMapper < Foobara::DomainMapper
  inputs_type InternalUser
  result_type ExternalUser

  def execute
    ExternalUser.new(
      user_id: inputs.id.to_s,
      display_name: inputs.name
    )
  end
end
```

**Python:**
```python
from foobara_py.domain.domain_mapper import DomainMapper

class InternalToExternalUserMapper(DomainMapper[InternalUser, ExternalUser]):
    def map_value(self, value: InternalUser) -> ExternalUser:
        return ExternalUser(
            user_id=str(value.id),
            display_name=value.name
        )
```

### Using Mappers in Commands

**Ruby:**
```ruby
def execute
  external = run_mapped_subcommand!(
    ExternalServiceCommand,
    user,
    to: ExternalUser
  )
end
```

**Python:**
```python
def execute(self) -> ExternalUser:
    external = self.run_mapped_subcommand(
        ExternalServiceCommand,
        unmapped_inputs={"user": user},
        to=ExternalUser
    )
    return external
```

---

## Testing

### Basic Test

**Ruby (RSpec):**
```ruby
RSpec.describe CreateUser do
  describe "#execute" do
    context "with valid inputs" do
      it "creates a user" do
        outcome = CreateUser.run(name: "John", email: "john@example.com")

        expect(outcome).to be_success
        expect(outcome.result.name).to eq("John")
      end
    end

    context "with invalid email" do
      it "returns error" do
        outcome = CreateUser.run(name: "John", email: "invalid")

        expect(outcome).to be_failure
        expect(outcome.errors).to include_error(:invalid_email)
      end
    end
  end
end
```

**Python (pytest):**
```python
import pytest

class TestCreateUser:
    def test_valid_inputs(self):
        outcome = CreateUser.run(name="John", email="john@example.com")

        assert outcome.is_success()
        assert outcome.unwrap().name == "John"

    def test_invalid_email(self):
        outcome = CreateUser.run(name="John", email="invalid")

        assert outcome.is_failure()
        assert any(e.symbol == "invalid_email" for e in outcome.errors)

    @pytest.mark.parametrize("email", ["", "nodomain", "no@"])
    def test_email_validation(self, email):
        outcome = CreateUser.run(name="Test", email=email)
        assert outcome.is_failure()
```

---

## Common Patterns

### Accessing Input Fields

**Ruby:**
```ruby
def execute
  # Hash-like access
  name = inputs[:name]
  email = inputs[:email]

  # Or method_missing magic
  name = inputs.name
end
```

**Python:**
```python
def execute(self) -> Result:
    # Attribute access (with IDE autocomplete!)
    name = self.inputs.name
    email = self.inputs.email
```

### Checking if Errors Exist

**Ruby:**
```ruby
if errors.any?
  # Has errors
end
```

**Python:**
```python
if self.errors.has_errors():
    # Has errors
    pass
```

### Getting Full Command Name

**Ruby:**
```ruby
MyApp::Users::CreateUser.full_command_name
# => "MyApp::Users::CreateUser"
```

**Python:**
```python
CreateUser.full_name()
# => "MyApp::Users::CreateUser"
```

---

## Type Reference

### String Constraints

**Ruby:**
```ruby
inputs do
  name :string, min_length: 1, max_length: 100
  slug :string, pattern: /^[a-z0-9-]+$/
end
```

**Python:**
```python
from pydantic import Field

class Inputs(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., pattern=r'^[a-z0-9-]+$')
```

### Numeric Constraints

**Ruby:**
```ruby
inputs do
  age :integer, min: 0, max: 150
  price :float, min: 0.0
end
```

**Python:**
```python
class Inputs(BaseModel):
    age: int = Field(..., ge=0, le=150)  # ge=greater/equal, le=less/equal
    price: float = Field(..., ge=0.0)
```

### Optional Fields

**Ruby:**
```ruby
inputs do
  bio :string, :optional
  age :integer  # Optional by default unless :required
end
```

**Python:**
```python
from typing import Optional

class Inputs(BaseModel):
    bio: Optional[str] = None
    age: Optional[int] = None
```

---

## Transactions

### Ruby (Implicit)

**Ruby:**
```ruby
class CreateUserWithProfile < Foobara::Command
  def execute
    # Transaction automatic in ActiveRecord
    user = User.create!(name: inputs[:name])
    profile = Profile.create!(user_id: user.id)
    user
  end
end
```

### Python (Explicit)

**Python:**
```python
from foobara_py.core.transactions import TransactionConfig

class CreateUserWithProfile(Command[Inputs, User]):
    _transaction_config = TransactionConfig(
        enabled=True,
        auto_detect=True  # Detects SQLAlchemy/etc
    )

    def execute(self) -> User:
        # open_transaction() called automatically
        user = User.create(name=self.inputs.name)
        profile = Profile.create(user_id=user.id)
        # commit_transaction() called on success
        # rollback_transaction() called on failure
        return user
```

---

## Quick Tips

### 1. Always Type-Hint in Python
```python
# Good
def execute(self) -> User:
    user: User = create_user()
    return user

# Bad
def execute(self):
    user = create_user()
    return user
```

### 2. Use Field for Complex Constraints
```python
# Good
age: int = Field(..., ge=0, le=150, description="Age in years")

# OK but less informative
age: int
```

### 3. Separate Inputs Class
```python
# Good - separate class with predictable name
class CreateUserInputs(BaseModel):
    name: str

class CreateUser(Command[CreateUserInputs, User]):
    pass

# Avoid - nested class (harder for AI to parse)
class CreateUser(Command[...]):
    class Inputs(BaseModel):
        name: str
```

### 4. Document Port Source
```python
class CreateUser(Command[CreateUserInputs, User]):
    """Create a new user

    Ported from: ruby/app/commands/users/create_user.rb
    Ruby SHA: abc123...
    Port Date: 2026-01-31
    """
```

---

## Symbol Mapping

| Ruby | Python | Notes |
|------|--------|-------|
| `:symbol` | `"symbol"` | Symbols → strings |
| `{ key: value }` | `{"key": value}` | Hash → dict |
| `[1, 2, 3]` | `[1, 2, 3]` | Array → list |
| `nil` | `None` | Null values |
| `true/false` | `True/False` | Booleans |
| `ClassName` | `ClassName` | Classes |
| `@instance_var` | `self.instance_var` | Instance vars |
| `@@class_var` | `cls.class_var` | Class vars |

---

## Method Naming

| Ruby | Python | Notes |
|------|--------|-------|
| `method_name` | `method_name` | Same |
| `dangerous!` | `dangerous_bang` | No `!` in Python |
| `query?` | `is_query` or `has_query` | No `?` in Python |
| `setter=` | `set_value` | No `=` in Python |

---

## Import Differences

**Ruby:**
```ruby
require "foobara"

class MyCommand < Foobara::Command
  # ...
end
```

**Python:**
```python
from foobara_py import Command
from pydantic import BaseModel

class MyCommand(Command[MyInputs, Result]):
    # ...
```

---

**For Full Analysis:** See [FOOBARA_RUBY_PYTHON_PATTERN_ANALYSIS.md](./FOOBARA_RUBY_PYTHON_PATTERN_ANALYSIS.md)
