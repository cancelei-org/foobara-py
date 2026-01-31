"""
Example demonstrating the Ruby-like callback DSL for Commands.

This example shows various ways to register callbacks using the enhanced
callback system with conditional execution based on state transitions.
"""

from pydantic import BaseModel
from foobara_py.core.command import Command
from foobara_py.core.state_machine import CommandState


class CreateUserInputs(BaseModel):
    """Input model for CreateUser command."""
    name: str
    email: str
    role: str = "user"


class User(BaseModel):
    """User model."""
    id: int
    name: str
    email: str
    role: str


class CreateUser(Command[CreateUserInputs, User]):
    """
    Command demonstrating callback DSL usage.

    Shows various callback registration patterns:
    - Transition-specific callbacks (before_execute, after_validate)
    - State-based callbacks (before_transition_from_initialized)
    - Generic callbacks (before_any_transition)
    - Combined conditions (before_transition)
    """

    def execute(self) -> User:
        """Create a new user."""
        # Simulate user creation
        return User(
            id=1,
            name=self.inputs.name,
            email=self.inputs.email,
            role=self.inputs.role,
        )


# ============================================================================
# Callback Registration Examples
# ============================================================================

# Example 1: Transition-specific callbacks
# These run for specific transitions (execute, validate, etc.)

@staticmethod
def check_permissions(cmd):
    """Check user has permission to create users."""
    print(f"[before_execute] Checking permissions for {cmd.inputs.email}")
    # Could check permissions and add errors:
    # if not has_permission(cmd.inputs.user):
    #     cmd.add_error("permission_denied", "Not allowed to create users")


@staticmethod
def log_user_created(cmd):
    """Log after user is created."""
    if hasattr(cmd, '_result') and cmd._result:
        print(f"[after_execute] Created user: {cmd._result.name}")
    else:
        print(f"[after_execute] User created")


CreateUser.before_execute_transition(check_permissions)
CreateUser.after_execute_transition(log_user_created)


# Example 2: Validation callbacks

@staticmethod
def validate_email_domain(cmd):
    """Validate email domain is allowed."""
    print(f"[before_validate] Validating email domain for {cmd.inputs.email}")
    if not cmd.inputs.email.endswith("@example.com"):
        cmd.add_input_error(
            ("email",),
            "invalid_domain",
            "Only @example.com emails allowed"
        )


CreateUser.before_validate_transition(validate_email_domain)


# Example 3: Any transition callbacks
# These run for ALL state transitions

@staticmethod
def log_all_transitions(cmd):
    """Log every state transition."""
    print(f"[any_transition] State: {cmd.state_name}")


CreateUser.before_any_transition(log_all_transitions, priority=10)


# Example 4: From-state callbacks
# Run when transitioning FROM a specific state

@staticmethod
def setup_context(cmd):
    """Setup context when leaving initialized state."""
    print(f"[from_initialized] Setting up execution context")


CreateUser.before_transition_from_initialized(setup_context)


# Example 5: To-state callbacks
# Run when transitioning TO a specific state

@staticmethod
def on_success(cmd):
    """Handle successful completion."""
    if hasattr(cmd, '_result'):
        print(f"[to_succeeded] Command succeeded with result: {cmd._result}")
    else:
        print(f"[to_succeeded] Command succeeded")


CreateUser.before_transition_to_succeeded(on_success)


@staticmethod
def on_failure(cmd):
    """Handle failure."""
    if hasattr(cmd, '_errors'):
        print(f"[to_failed] Command failed with errors: {cmd._errors.all()}")
    else:
        print(f"[to_failed] Command failed")


CreateUser.before_transition_to_failed(on_failure)


# Example 6: Generic callbacks with multiple conditions
# Most flexible - specify any combination of conditions

@staticmethod
def specific_callback(cmd):
    """Run only for execute transition from validating state."""
    print("[specific] Execute transition from validating state")


CreateUser.before_transition(
    specific_callback,
    from_state=CommandState.VALIDATING,
    to_state=CommandState.EXECUTING,
    transition="execute"
)


# Example 7: Around callbacks
# Wrap the transition with before/after logic

@staticmethod
def time_execution(cmd, proceed):
    """Time the execute transition."""
    import time
    print("[around_execute] Starting execution...")
    start = time.time()

    # Call the actual execute method
    result = proceed()

    elapsed = time.time() - start
    print(f"[around_execute] Execution took {elapsed*1000:.2f}ms")
    return result


CreateUser.around_execute_transition(time_execution)


# Example 8: Priority control
# Lower priority = runs earlier

@staticmethod
def first_callback(cmd):
    """Runs first (priority 0)."""
    print("[execute priority=0] First!")


@staticmethod
def second_callback(cmd):
    """Runs second (priority 100)."""
    print("[execute priority=100] Second!")


CreateUser.before_execute_transition(first_callback, priority=0)
CreateUser.before_execute_transition(second_callback, priority=100)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Running CreateUser with callbacks")
    print("=" * 70)

    # Run the command
    outcome = CreateUser.run(
        name="John Doe",
        email="john@example.com",
        role="admin"
    )

    print("\n" + "=" * 70)
    print("Outcome:")
    print("=" * 70)

    if outcome.is_success():
        print(f"✓ Success! Created user: {outcome.result}")
    else:
        print(f"✗ Failed with errors: {outcome.errors}")

    print("\n" + "=" * 70)
    print("Callback Statistics:")
    print("=" * 70)

    # Show callback statistics
    reg = CreateUser._enhanced_callback_registry
    if reg:
        stats = reg.get_cache_stats()
        print(f"Registry has {len(reg._callbacks)} total callbacks")
        print(f"Cache hits: {stats['hits']}")
        print(f"Cache misses: {stats['misses']}")
        print(f"Hit rate: {stats['hit_rate']:.1f}%")
        print(f"Compiled chains: {stats['compiled_chains']}")
