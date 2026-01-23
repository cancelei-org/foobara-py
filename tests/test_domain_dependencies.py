"""
Integration tests for domain dependency system

Tests complete domain dependency functionality:
- depends_on() validation
- can_call_from() enforcement
- Circular dependency detection
- Cross-domain call tracking
- Domain dependency violations
"""

import pytest
from pydantic import BaseModel

from foobara_py import Command
from foobara_py.domain.domain import Domain, DomainDependencyError


# Empty inputs model for commands that don't need inputs
class EmptyInputs(BaseModel):
    pass


# Reset domain registry before each test
@pytest.fixture(autouse=True)
def reset_domains():
    """Reset domain registry and call stats before each test"""
    Domain._registry.clear()
    Domain.reset_cross_domain_call_stats()
    yield
    Domain._registry.clear()
    Domain.reset_cross_domain_call_stats()


class TestDomainDependencies:
    """Test depends_on() and dependency validation"""

    def test_simple_dependency(self):
        """Test declaring simple domain dependency"""
        auth = Domain("Auth")
        users = Domain("Users")

        users.depends_on("Auth")

        assert "Auth" in users._dependencies
        assert users.can_call_from("Auth")

    def test_multiple_dependencies(self):
        """Test declaring multiple dependencies at once"""
        auth = Domain("Auth")
        billing = Domain("Billing")
        users = Domain("Users")

        users.depends_on("Auth", "Billing")

        assert "Auth" in users._dependencies
        assert "Billing" in users._dependencies
        assert users.can_call_from("Auth")
        assert users.can_call_from("Billing")

    def test_circular_dependency_direct(self):
        """Test that direct circular dependencies are detected"""
        auth = Domain("Auth")
        users = Domain("Users")

        users.depends_on("Auth")

        # This should raise because Auth -> Users -> Auth is a cycle
        with pytest.raises(DomainDependencyError, match="circular dependency"):
            auth.depends_on("Users")

    def test_circular_dependency_transitive(self):
        """Test that transitive circular dependencies are detected"""
        auth = Domain("Auth")
        users = Domain("Users")
        billing = Domain("Billing")

        # Create chain: Users -> Auth -> Billing
        users.depends_on("Auth")
        auth.depends_on("Billing")

        # This should raise because Billing -> Users -> Auth -> Billing is a cycle
        with pytest.raises(DomainDependencyError, match="circular dependency"):
            billing.depends_on("Users")

    def test_self_dependency_rejected(self):
        """Test that domain cannot depend on itself"""
        users = Domain("Users")

        with pytest.raises(DomainDependencyError, match="circular dependency"):
            users.depends_on("Users")

    def test_complex_dependency_graph(self):
        """Test complex valid dependency graph"""
        # Create domains
        auth = Domain("Auth")
        users = Domain("Users")
        billing = Domain("Billing")
        reports = Domain("Reports")

        # Create valid DAG:
        # Reports -> Users -> Auth
        # Reports -> Billing
        users.depends_on("Auth")
        billing.depends_on("Auth")
        reports.depends_on("Users", "Billing")

        assert reports.can_call_from("Users")
        assert reports.can_call_from("Billing")
        assert users.can_call_from("Auth")
        assert billing.can_call_from("Auth")


class TestCanCallFrom:
    """Test can_call_from() validation logic"""

    def test_same_domain_always_allowed(self):
        """Test commands can always call within same domain"""
        users = Domain("Users")
        assert users.can_call_from("Users")

    def test_global_domain_always_allowed(self):
        """Test commands can always call Global domain"""
        users = Domain("Users")
        assert users.can_call_from("Global")

    def test_dependency_allows_call(self):
        """Test dependency allows cross-domain calls"""
        auth = Domain("Auth")
        users = Domain("Users")

        users.depends_on("Auth")

        assert users.can_call_from("Auth")

    def test_no_dependency_blocks_call(self):
        """Test calls are blocked without dependency"""
        auth = Domain("Auth")
        users = Domain("Users")

        # No dependency declared
        assert not users.can_call_from("Auth")


class TestCrossDomainCallEnforcement:
    """Test that cross-domain calls are enforced at runtime"""

    def test_allowed_cross_domain_call(self):
        """Test that allowed cross-domain calls succeed"""
        auth = Domain("Auth")
        users = Domain("Users")

        # Declare dependency
        users.depends_on("Auth")

        # Define commands
        class AuthInputs(BaseModel):
            pass

        class AuthResult(BaseModel):
            token: str

        class Authenticate(Command[AuthInputs, AuthResult]):
            """Auth command"""
            _domain = "Auth"

            def execute(self) -> AuthResult:
                return AuthResult(token="abc123")

        class CreateUserInputs(BaseModel):
            email: str

        class CreateUser(Command[CreateUserInputs, dict]):
            """Users command that calls Auth"""
            _domain = "Users"

            def execute(self) -> dict:
                # This should succeed because Users depends on Auth
                auth_result = self.run_subcommand(Authenticate)
                return {"email": self.inputs.email, "token": auth_result.token}

        # Should succeed
        outcome = CreateUser.run(email="test@example.com")
        assert outcome.is_success()
        assert outcome.result["token"] == "abc123"

    def test_blocked_cross_domain_call(self):
        """Test that non-allowed cross-domain calls are blocked"""
        auth = Domain("Auth")
        users = Domain("Users")

        # NO dependency declared

        # Define commands
        class Authenticate(Command[EmptyInputs, str]):
            """Auth command"""
            _domain = "Auth"

            def execute(self) -> str:
                return "token"

        class CreateUserInputs(BaseModel):
            email: str

        class CreateUser(Command[CreateUserInputs, dict]):
            """Users command that tries to call Auth"""
            _domain = "Users"

            def execute(self) -> dict:
                # This should FAIL because Users does NOT depend on Auth
                self.run_subcommand(Authenticate)
                return {}

        # Should fail with domain dependency error
        outcome = CreateUser.run(email="test@example.com")
        assert outcome.is_failure()
        assert len(outcome.errors) > 0
        assert "cannot call commands from" in str(outcome.errors[0].message)

    def test_same_domain_call_always_allowed(self):
        """Test that calls within same domain always work"""
        users = Domain("Users")

        class Helper(Command[EmptyInputs, str]):
            """Helper command in Users domain"""
            _domain = "Users"

            def execute(self) -> str:
                return "helped"

        class CreateUserInputs(BaseModel):
            email: str

        class CreateUser(Command[CreateUserInputs, dict]):
            """Users command that calls another Users command"""
            _domain = "Users"

            def execute(self) -> dict:
                result = self.run_subcommand(Helper)
                return {"email": self.inputs.email, "status": result}

        # Should succeed - same domain
        outcome = CreateUser.run(email="test@example.com")
        assert outcome.is_success()
        assert outcome.result["status"] == "helped"


class TestCrossDomainCallTracking:
    """Test cross-domain call tracking for observability"""

    def test_cross_domain_calls_tracked(self):
        """Test that cross-domain calls are tracked"""
        auth = Domain("Auth")
        users = Domain("Users")

        users.depends_on("Auth")

        class Authenticate(Command[EmptyInputs, str]):
            _domain = "Auth"

            def execute(self) -> str:
                return "token"

        class CreateUser(Command[EmptyInputs, str]):
            _domain = "Users"

            def execute(self) -> str:
                self.run_subcommand(Authenticate)
                return "created"

        # Reset stats
        Domain.reset_cross_domain_call_stats()

        # Make cross-domain call
        CreateUser.run()

        # Check tracking
        stats = Domain.get_cross_domain_call_stats()
        assert ("Users", "Auth") in stats
        assert stats[("Users", "Auth")] == 1

    def test_same_domain_calls_not_tracked(self):
        """Test that same-domain calls are not tracked"""
        users = Domain("Users")

        class Helper(Command[EmptyInputs, str]):
            _domain = "Users"

            def execute(self) -> str:
                return "helped"

        class CreateUser(Command[EmptyInputs, str]):
            _domain = "Users"

            def execute(self) -> str:
                self.run_subcommand(Helper)
                return "created"

        Domain.reset_cross_domain_call_stats()

        CreateUser.run()

        stats = Domain.get_cross_domain_call_stats()
        # Should be empty - same domain call
        assert len(stats) == 0

    def test_multiple_calls_increment_count(self):
        """Test that multiple calls increment the counter"""
        auth = Domain("Auth")
        users = Domain("Users")

        users.depends_on("Auth")

        class Authenticate(Command[EmptyInputs, str]):
            _domain = "Auth"

            def execute(self) -> str:
                return "token"

        class CreateUser(Command[EmptyInputs, str]):
            _domain = "Users"

            def execute(self) -> str:
                # Call Auth twice
                self.run_subcommand(Authenticate)
                self.run_subcommand(Authenticate)
                return "created"

        Domain.reset_cross_domain_call_stats()

        CreateUser.run()

        stats = Domain.get_cross_domain_call_stats()
        assert stats[("Users", "Auth")] == 2

    def test_reset_call_stats(self):
        """Test resetting call statistics"""
        auth = Domain("Auth")
        users = Domain("Users")

        users.depends_on("Auth")

        class Authenticate(Command[EmptyInputs, str]):
            _domain = "Auth"

            def execute(self) -> str:
                return "token"

        class CreateUser(Command[EmptyInputs, str]):
            _domain = "Users"

            def execute(self) -> str:
                self.run_subcommand(Authenticate)
                return "created"

        CreateUser.run()

        # Reset
        Domain.reset_cross_domain_call_stats()

        stats = Domain.get_cross_domain_call_stats()
        assert len(stats) == 0


class TestDomainDependencyEdgeCases:
    """Test edge cases and error conditions"""

    def test_nonexistent_dependency(self):
        """Test depending on a domain that doesn't exist yet"""
        users = Domain("Users")

        # Should not raise - dependency on non-existent domain is allowed
        users.depends_on("NonExistent")

        assert "NonExistent" in users._dependencies

    def test_command_without_domain(self):
        """Test commands without explicit domain are treated as global"""
        users = Domain("Users")

        class GlobalCommand(Command[EmptyInputs, str]):
            # No _domain attribute

            def execute(self) -> str:
                return "global"

        class UserCommand(Command[EmptyInputs, str]):
            _domain = "Users"

            def execute(self) -> str:
                # Should succeed - global commands can always be called
                result = self.run_subcommand(GlobalCommand)
                return result

        outcome = UserCommand.run()
        assert outcome.is_success()
        assert outcome.result == "global"
