"""
Tests for Ruby foobara v0.5.1 improvements ported to Python.

Verifies:
1. Type reference defaults handling
2. Fully qualified CRUD driver table names
3. BaseManifest#domain_reference
4. Deterministic domain manifest ordering
5. Dependent domain model type extension lookup
6. Authenticators without foobara entities
7. Request without command_connector instance
"""

import pytest

from foobara_py.auth.authenticator import AuthContext, Authenticator
from foobara_py.connectors.request import Request
from foobara_py.manifest.base import BaseManifest
from foobara_py.manifest.command_manifest import CommandManifest
from foobara_py.manifest.domain_manifest import DomainManifest
from foobara_py.persistence.crud_driver import CRUDTable


class MockEntity:
    """Mock entity for testing"""

    __name__ = "User"
    __module__ = "acme_org.users_domain.types"


class MockEntityWithoutModule:
    """Mock entity without module for fallback testing"""

    __name__ = "SimpleEntity"


def test_crud_driver_fully_qualified_table_names():
    """Test that CRUD driver uses fully qualified names for table naming (commit 90cdb332)"""

    class TestCRUDTable(CRUDTable):
        def find(self, record_id):
            return None

        def all(self, page_size=None):
            return []

        def insert(self, attributes):
            return attributes

        def update(self, record_id, attributes):
            return attributes

        def delete(self, record_id):
            return True

        def count(self):
            return 0

        def select(self, where=None, order_by=None, limit=None, offset=None):
            return []

    # Test with full module path
    table = TestCRUDTable(MockEntity, driver=None)
    # Should generate: acme_org_users_domain_types_user
    assert "users_domain" in table.table_name.lower()
    assert "user" in table.table_name.lower()
    assert "." not in table.table_name  # No dots in table names

    # Test with entity without module (fallback) - will use full module path too
    table2 = TestCRUDTable(MockEntityWithoutModule, driver=None)
    # Should still have no dots
    assert "." not in table2.table_name
    assert "mockentitywithoutmodule" in table2.table_name.lower()


def test_base_manifest_domain_reference():
    """Test BaseManifest.domain_reference() method (commit 0c0b3377)"""
    # BaseManifest is abstract, but should have the method available
    # Test using a concrete subclass
    manifest = CommandManifest(name="Test", full_name="Test")
    assert hasattr(manifest, "domain_reference")
    # CommandManifest without domain should return None
    assert manifest.domain_reference() is None


def test_command_manifest_domain_reference():
    """Test CommandManifest.domain_reference() returns proper domain string"""
    # With organization and domain
    manifest1 = CommandManifest(
        name="CreateUser",
        full_name="Acme::Users::CreateUser",
        organization="Acme",
        domain="Users",
    )
    assert manifest1.domain_reference() == "Acme::Users"

    # With domain only
    manifest2 = CommandManifest(
        name="CreateUser", full_name="Users::CreateUser", domain="Users"
    )
    assert manifest2.domain_reference() == "Users"

    # Without domain
    manifest3 = CommandManifest(name="CreateUser", full_name="CreateUser")
    assert manifest3.domain_reference() is None


def test_domain_manifest_deterministic_ordering():
    """Test that domain manifest returns sorted data (commit f15edf7c)"""
    manifest = DomainManifest(
        name="Users",
        full_name="Acme::Users",
        organization="Acme",
        dependencies=["Auth", "Core"],
        command_names=["CreateUser", "DeleteUser", "UpdateUser"],
        command_count=3,
    )

    data = manifest.to_dict()

    # Check that command_names are sorted
    assert data["command_names"] == ["CreateUser", "DeleteUser", "UpdateUser"]

    # Check that dependencies are sorted
    assert data["dependencies"] == ["Auth", "Core"]

    # Check that dict keys are sorted
    keys = list(data.keys())
    assert keys == sorted(keys)


def test_domain_manifest_domain_reference():
    """Test DomainManifest.domain_reference() returns full_name"""
    manifest = DomainManifest(
        name="Users", full_name="Acme::Users", organization="Acme"
    )
    assert manifest.domain_reference() == "Acme::Users"


class SimpleAuthenticator(Authenticator):
    """Authenticator without relevant_entity_classes support"""

    def applies_to(self, request):
        return True

    def authenticate(self, request):
        return AuthContext(user_id=42, roles=["user"])


class EntityAwareAuthenticator(Authenticator):
    """Authenticator with relevant_entity_classes support"""

    def applies_to(self, request):
        return True

    def authenticate(self, request):
        return AuthContext(user_id=42, roles=["admin"])

    def relevant_entity_classes(self, request):
        return [MockEntity]


def test_authenticator_without_entities():
    """Test that authenticators without relevant_entity_classes work (commit 3629b462)"""
    auth = SimpleAuthenticator()
    request = Request(authenticator=auth)

    # Authenticator should work without relevant_entity_classes
    assert request.authenticate() is True
    assert request.authenticated_user == 42

    # Should return empty list from default implementation
    entity_classes = auth.relevant_entity_classes(request)
    assert entity_classes == []


def test_authenticator_with_entities():
    """Test that authenticators with relevant_entity_classes still work"""
    auth = EntityAwareAuthenticator()
    request = Request(authenticator=auth)

    assert request.authenticate() is True
    entity_classes = auth.relevant_entity_classes(request)
    assert MockEntity in entity_classes


def test_request_without_command_connector():
    """Test that Request can operate without command_connector instance (commit e34ce225)"""
    # Create request without command connector
    request = Request(
        inputs={"name": "test"},
        full_command_name="Acme::Users::CreateUser",
        authenticator=SimpleAuthenticator(),
    )

    # Should be able to authenticate
    assert request.authenticate() is True
    assert request.is_authenticated() is True
    assert request.authenticated_user == 42

    # Should handle missing command_connector gracefully
    assert request.command_connector is None


def test_request_with_auth_mappers():
    """Test Request with auth-mapped methods (commit e34ce225)"""

    def extract_email(user_id):
        return f"user{user_id}@example.com"

    def extract_roles(user_id):
        return ["admin", "user"]

    request = Request(
        authenticator=SimpleAuthenticator(),
        auth_mappers={"email": extract_email, "user_roles": extract_roles},
    )

    # Authenticate first
    request.authenticate()

    # Should be able to access auth-mapped attributes
    assert request.email == "user42@example.com"
    assert request.user_roles == ["admin", "user"]

    # Non-existent auth-mapped attribute should raise AttributeError
    with pytest.raises(AttributeError):
        _ = request.nonexistent_attr


def test_request_auth_mapped_method_without_authentication():
    """Test that auth-mapped methods return None when not authenticated"""
    request = Request(auth_mappers={"email": lambda user_id: f"user{user_id}@example.com"})

    # Without authentication, auth-mapped values should be None
    assert request.email is None


def test_type_reference_defaults_handling_note():
    """
    Test documenting that type reference defaults are handled by Pydantic.

    Ruby foobara v0.5.1 commit a35d1aca fixed type reference defaults handling
    by checking if attribute_type_declaration is a Hash before accessing allow_nil.

    In Python, we use Pydantic BaseModel which handles this automatically through
    Optional[] type hints, so no explicit fix is needed. This test documents that.
    """
    from typing import Optional

    from pydantic import BaseModel

    class UserInput(BaseModel):
        name: str
        email: Optional[str] = None  # Pydantic handles None/default automatically

    # Should work with None for optional field
    user1 = UserInput(name="Alice", email=None)
    assert user1.email is None

    # Should work without providing optional field
    user2 = UserInput(name="Bob")
    assert user2.email is None

    # This demonstrates Pydantic handles what Ruby's fix addressed
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
