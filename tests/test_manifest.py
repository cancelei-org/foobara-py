"""Tests for Foobara Manifest System"""

import pytest
from pydantic import BaseModel
from foobara_py.manifest import (
    BaseManifest,
    CommandManifest,
    DomainManifest,
    OrganizationManifest,
    TypeManifest,
    EntityManifest,
    ErrorManifest,
    RootManifest,
)


class TestCommandManifest:
    """Test CommandManifest"""

    def test_create_command_manifest(self):
        """Should create command manifest"""
        manifest = CommandManifest(
            name="CreateUser",
            full_name="Users::CreateUser",
            description="Create a new user",
            domain="Users",
        )

        assert manifest.name == "CreateUser"
        assert manifest.full_name == "Users::CreateUser"
        assert manifest.domain == "Users"

    def test_command_manifest_to_dict(self):
        """Should convert to dictionary"""
        manifest = CommandManifest(
            name="CreateUser",
            full_name="Users::CreateUser",
            description="Create a new user",
            inputs_schema={"type": "object", "properties": {"email": {"type": "string"}}},
        )

        data = manifest.to_dict()

        assert data["name"] == "CreateUser"
        assert data["inputs_schema"]["properties"]["email"]["type"] == "string"

    def test_command_manifest_to_json(self):
        """Should convert to JSON"""
        manifest = CommandManifest(
            name="CreateUser",
            full_name="CreateUser",
        )

        json_str = manifest.to_json()

        assert '"name": "CreateUser"' in json_str

    def test_command_manifest_from_command(self):
        """Should create manifest from command class"""
        from foobara_py import Command

        class TestInputs(BaseModel):
            value: str

        class TestCommand(Command[TestInputs, str]):
            """Test command description."""

            def execute(self) -> str:
                return self.inputs.value

        manifest = CommandManifest.from_command(TestCommand)

        assert manifest.name == "TestCommand"
        assert "Test command description" in manifest.description
        assert manifest.inputs_schema is not None


class TestDomainManifest:
    """Test DomainManifest"""

    def test_create_domain_manifest(self):
        """Should create domain manifest"""
        manifest = DomainManifest(
            name="Users",
            full_name="MyApp::Users",
            organization="MyApp",
            dependencies=["Auth"],
        )

        assert manifest.name == "Users"
        assert manifest.organization == "MyApp"
        assert "Auth" in manifest.dependencies

    def test_domain_manifest_from_domain(self):
        """Should create manifest from domain instance"""
        from foobara_py import Domain

        domain = Domain("Products", organization="Store")
        manifest = DomainManifest.from_domain(domain)

        assert manifest.name == "Products"
        assert manifest.organization == "Store"
        assert manifest.full_name == "Store::Products"


class TestOrganizationManifest:
    """Test OrganizationManifest"""

    def test_create_organization_manifest(self):
        """Should create organization manifest"""
        manifest = OrganizationManifest(
            name="MyCompany",
            domain_names=["Users", "Products", "Orders"],
            domain_count=3,
        )

        assert manifest.name == "MyCompany"
        assert len(manifest.domain_names) == 3

    def test_organization_manifest_from_domains(self):
        """Should create from domain list"""
        manifest = OrganizationManifest.from_domains(
            "MyApp",
            ["Users", "Products"]
        )

        assert manifest.name == "MyApp"
        assert manifest.domain_count == 2


class TestTypeManifest:
    """Test TypeManifest"""

    def test_create_type_manifest(self):
        """Should create type manifest"""
        manifest = TypeManifest(
            name="Address",
            full_name="Address",
            kind="model",
            is_mutable=False,
        )

        assert manifest.name == "Address"
        assert manifest.kind == "model"

    def test_type_manifest_from_model(self):
        """Should create manifest from Pydantic model"""

        class Address(BaseModel):
            """Address model."""
            street: str
            city: str

        manifest = TypeManifest.from_model(Address)

        assert manifest.name == "Address"
        assert manifest.json_schema is not None
        assert "street" in str(manifest.json_schema)


class TestEntityManifest:
    """Test EntityManifest"""

    def test_create_entity_manifest(self):
        """Should create entity manifest"""
        manifest = EntityManifest(
            name="User",
            full_name="User",
            primary_key_field="id",
            fields={
                "id": {"type": "int", "required": True, "is_primary_key": True},
                "email": {"type": "str", "required": True, "is_primary_key": False},
            },
        )

        assert manifest.name == "User"
        assert manifest.primary_key_field == "id"
        assert manifest.fields["email"]["type"] == "str"

    def test_entity_manifest_from_entity(self):
        """Should create manifest from entity class"""
        from foobara_py.persistence.entity import EntityBase, entity

        @entity(primary_key="id")
        class User(EntityBase):
            """User entity."""
            id: int
            email: str
            name: str

        manifest = EntityManifest.from_entity(User)

        assert manifest.name == "User"
        assert manifest.primary_key_field == "id"
        assert "id" in manifest.fields
        assert "email" in manifest.fields


class TestErrorManifest:
    """Test ErrorManifest"""

    def test_create_error_manifest(self):
        """Should create error manifest"""
        manifest = ErrorManifest(
            name="NotFoundError",
            code="not_found",
            description="Resource not found",
            category="not_found",
        )

        assert manifest.name == "NotFoundError"
        assert manifest.code == "not_found"
        assert manifest.category == "not_found"

    def test_error_manifest_from_class(self):
        """Should create manifest from error class"""

        class UserNotFoundError(Exception):
            """User was not found."""
            pass

        manifest = ErrorManifest.from_error_class(UserNotFoundError)

        assert manifest.name == "UserNotFoundError"
        assert manifest.category == "not_found"


class TestRootManifest:
    """Test RootManifest"""

    def test_create_root_manifest(self):
        """Should create root manifest"""
        manifest = RootManifest(
            commands=[
                CommandManifest(name="CreateUser", full_name="CreateUser"),
                CommandManifest(name="DeleteUser", full_name="DeleteUser"),
            ],
            domains=[
                DomainManifest(name="Users", full_name="Users"),
            ],
            command_count=2,
            domain_count=1,
        )

        assert manifest.command_count == 2
        assert manifest.domain_count == 1
        assert len(manifest.commands) == 2

    def test_root_manifest_find_command(self):
        """Should find command by name"""
        manifest = RootManifest(
            commands=[
                CommandManifest(name="CreateUser", full_name="Users::CreateUser", domain="Users"),
                CommandManifest(name="DeleteUser", full_name="Users::DeleteUser", domain="Users"),
            ],
        )

        cmd = manifest.find_command("CreateUser")
        assert cmd is not None
        assert cmd.name == "CreateUser"

        cmd = manifest.find_command("Users::DeleteUser")
        assert cmd is not None
        assert cmd.name == "DeleteUser"

        cmd = manifest.find_command("NonExistent")
        assert cmd is None

    def test_root_manifest_commands_by_domain(self):
        """Should filter commands by domain"""
        manifest = RootManifest(
            commands=[
                CommandManifest(name="CreateUser", full_name="CreateUser", domain="Users"),
                CommandManifest(name="CreateProduct", full_name="CreateProduct", domain="Products"),
                CommandManifest(name="DeleteUser", full_name="DeleteUser", domain="Users"),
            ],
        )

        user_cmds = manifest.commands_by_domain("Users")
        assert len(user_cmds) == 2

        product_cmds = manifest.commands_by_domain("Products")
        assert len(product_cmds) == 1

    def test_root_manifest_to_dict(self):
        """Should convert to dictionary"""
        manifest = RootManifest(
            commands=[
                CommandManifest(name="Test", full_name="Test"),
            ],
            command_count=1,
        )

        data = manifest.to_dict()

        assert "commands" in data
        assert "counts" in data
        assert data["counts"]["commands"] == 1

    def test_root_manifest_to_json(self):
        """Should convert to JSON"""
        manifest = RootManifest(
            version="1.0",
            foobara_version="0.1.0",
        )

        json_str = manifest.to_json()

        assert '"version": "1.0"' in json_str
        assert '"foobara_version": "0.1.0"' in json_str

    def test_root_manifest_from_registry(self):
        """Should build from registries"""
        # This tests the integration with registries
        manifest = RootManifest.from_registry()

        # Should return a valid manifest even if registries are empty
        assert manifest is not None
        assert manifest.version == "1.0"


class TestManifestJSON:
    """Test JSON serialization"""

    def test_manifest_json_schema(self):
        """Should generate JSON schema"""
        schema = CommandManifest.model_json_schema()

        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "full_name" in schema["properties"]
