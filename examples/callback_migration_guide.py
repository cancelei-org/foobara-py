#!/usr/bin/env python3
"""
Callback Migration Guide: Old System vs Enhanced DSL

This file demonstrates how to migrate from the old instance method callbacks
to the new enhanced callback DSL system.

The enhanced DSL provides:
- Better separation of concerns
- More flexible callback conditions
- Better performance through callback chain compilation
- Ruby-like expressiveness
"""

from pydantic import BaseModel, Field
from foobara_py import Command


# ============================================================================
# Example Models
# ============================================================================

class CreateUserInputs(BaseModel):
    name: str = Field(..., min_length=1)
    email: str
    age: int = Field(..., ge=0, le=150)


class User(BaseModel):
    id: int
    name: str
    email: str
    age: int


# ============================================================================
# BEFORE: Old Instance Method Approach (DEPRECATED - DON'T USE)
# ============================================================================

class CreateUserOld(Command[CreateUserInputs, User]):
    """
    OLD WAY - Using instance methods (DEPRECATED)

    This approach is no longer recommended:
    - Callbacks are tightly coupled to the class
    - Harder to reuse callbacks across commands
    - Less flexible - can't conditionally register
    - No priority control
    """

    def before_execute(self) -> None:
        """Check permissions before execution"""
        # This method is called automatically
        print(f"[OLD] Checking permissions for {self.inputs.email}")
        if self.inputs.email.endswith("@blocked.com"):
            self.add_runtime_error(
                "blocked_domain",
                "This email domain is blocked",
                halt=True
            )

    def after_execute(self, result: User) -> User:
        """Log after execution"""
        # This method is called automatically with the result
        print(f"[OLD] User created: {result.name}")
        return result

    def execute(self) -> User:
        """Create the user"""
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )


# ============================================================================
# AFTER: Enhanced Callback DSL (RECOMMENDED)
# ============================================================================

class CreateUserNew(Command[CreateUserInputs, User]):
    """
    NEW WAY - Using enhanced callback DSL

    Benefits:
    - Callbacks are decoupled from the class
    - Easy to reuse across commands
    - Flexible registration with conditions
    - Priority control for callback ordering
    - Better testability
    """

    def execute(self) -> User:
        """Create the user"""
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )


# Register callbacks using DSL - outside the class definition
def check_permissions(cmd):
    """Check permissions before execution"""
    print(f"[NEW] Checking permissions for {cmd.inputs.email}")
    if cmd.inputs.email.endswith("@blocked.com"):
        cmd.add_runtime_error(
            "blocked_domain",
            "This email domain is blocked",
            halt=True
        )


def log_user_created(cmd):
    """Log after execution"""
    if hasattr(cmd, '_result') and cmd._result:
        print(f"[NEW] User created: {cmd._result.name}")


# Register callbacks with the command class
CreateUserNew.before_execute_transition(check_permissions)
CreateUserNew.after_execute_transition(log_user_created)


# ============================================================================
# Advanced: Reusable Callbacks
# ============================================================================

def email_domain_validator(cmd):
    """Reusable callback to validate email domains"""
    blocked_domains = ["@spam.com", "@blocked.com", "@test.invalid"]
    email = cmd.inputs.email

    for domain in blocked_domains:
        if email.endswith(domain):
            cmd.add_runtime_error(
                "blocked_domain",
                f"Email domain {domain} is not allowed",
                halt=True
            )
            return


def audit_logger(cmd):
    """Reusable callback to log command execution"""
    import datetime
    timestamp = datetime.datetime.now().isoformat()
    print(f"[AUDIT {timestamp}] Command executed: {cmd.__class__.__name__}")


class CreateUserAdvanced(Command[CreateUserInputs, User]):
    """Command using reusable callbacks"""

    def execute(self) -> User:
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )


# Register multiple reusable callbacks
CreateUserAdvanced.before_validate_transition(email_domain_validator)
CreateUserAdvanced.before_execute_transition(audit_logger, priority=0)
CreateUserAdvanced.after_execute_transition(audit_logger, priority=100)


# ============================================================================
# Advanced: Conditional Callbacks
# ============================================================================

class UpdateUser(Command[CreateUserInputs, User]):
    """Command with conditional callbacks"""

    def execute(self) -> User:
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )


def age_validator(cmd):
    """Only validate age for specific transitions"""
    if cmd.inputs.age < 18:
        print("[CONDITIONAL] Warning: User is under 18")


def senior_discount_check(cmd):
    """Check for senior discount eligibility"""
    if cmd.inputs.age >= 65:
        print("[CONDITIONAL] User eligible for senior discount")


# Register with priorities to control execution order
UpdateUser.before_execute_transition(age_validator, priority=10)
UpdateUser.before_execute_transition(senior_discount_check, priority=20)


# ============================================================================
# Migration Pattern: Async Commands
# ============================================================================

# IMPORTANT NOTE: AsyncCommand currently still uses the old callback methods.
# The enhanced callback DSL is not yet available for async commands.
# Use instance methods for async commands:

from foobara_py import AsyncCommand


class AsyncCommandExample(AsyncCommand[CreateUserInputs, User]):
    """
    For async commands, continue using instance methods for now.

    The enhanced callback DSL will be added to AsyncCommand in a future update.
    """

    async def before_execute(self) -> None:
        """Async hook before execution"""
        print(f"[ASYNC] Checking permissions for {self.inputs.email}")
        # Could do: await some_async_permission_service.check(self.inputs.email)

    async def after_execute(self, result: User) -> User:
        """Async hook after execution"""
        print(f"[ASYNC] User created: {result.name}")
        # Could do: await some_async_logging_service.log(result)
        return result

    async def execute(self) -> User:
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            age=self.inputs.age
        )


# ============================================================================
# Quick Reference: All Available Callback Methods
# ============================================================================

"""
Available DSL methods on Command class:

Transition-specific:
- Command.before_execute_transition(callback, priority=50)
- Command.after_execute_transition(callback, priority=50)
- Command.before_validate_transition(callback, priority=50)
- Command.after_validate_transition(callback, priority=50)
- Command.around_execute_transition(callback, priority=50)

State-based (from/to):
- Command.before_transition_from_initialized(callback, priority=50)
- Command.before_transition_to_succeeded(callback, priority=50)
- Command.before_transition_to_failed(callback, priority=50)
# ... (other states available)

Generic:
- Command.before_any_transition(callback, priority=50)
- Command.after_any_transition(callback, priority=50)
- Command.before_transition(callback, from_state=..., to_state=..., transition=..., priority=50)

Notes:
- Lower priority = runs earlier (priority 0 runs before priority 100)
- Callbacks receive the command instance as first parameter
- Around callbacks receive (cmd, proceed) and must call proceed()
- Async commands support async callbacks
"""


# ============================================================================
# Demo Usage
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Callback Migration Guide")
    print("=" * 70)

    # Test OLD system (deprecated)
    print("\n--- Testing OLD System (Deprecated) ---")
    outcome_old = CreateUserOld.run(
        name="John Doe",
        email="john@example.com",
        age=30
    )
    if outcome_old.is_success():
        print(f"✓ OLD: User created: {outcome_old.result}")

    # Test NEW system (recommended)
    print("\n--- Testing NEW System (Recommended) ---")
    outcome_new = CreateUserNew.run(
        name="Jane Smith",
        email="jane@example.com",
        age=25
    )
    if outcome_new.is_success():
        print(f"✓ NEW: User created: {outcome_new.result}")

    # Test reusable callbacks
    print("\n--- Testing Reusable Callbacks ---")
    outcome_advanced = CreateUserAdvanced.run(
        name="Bob Johnson",
        email="bob@example.com",
        age=35
    )
    if outcome_advanced.is_success():
        print(f"✓ ADVANCED: User created: {outcome_advanced.result}")

    # Test blocked domain
    print("\n--- Testing Blocked Domain ---")
    outcome_blocked = CreateUserNew.run(
        name="Spammer",
        email="spam@blocked.com",
        age=20
    )
    if outcome_blocked.is_failure():
        print(f"✗ BLOCKED: {outcome_blocked.errors[0].message}")

    print("\n" + "=" * 70)
    print("Migration complete! Use the NEW system for all new code.")
    print("=" * 70)
