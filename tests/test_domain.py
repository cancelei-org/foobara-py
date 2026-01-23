"""Tests for Domain module"""

import pytest
from pydantic import BaseModel
from foobara_py.domain.domain import Domain, Organization, create_domain
from foobara_py.core.command import Command


class TestDomain:
    def test_domain_creation(self):
        domain = Domain("Users")
        assert domain.name == "Users"
        assert domain.organization is None

    def test_domain_with_organization(self):
        domain = Domain("Users", organization="MyApp")
        assert domain.full_name() == "MyApp::Users"

    def test_command_decorator(self):
        domain = Domain("TestDomain")

        class TestInputs(BaseModel):
            value: int

        @domain.command
        class TestCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return self.inputs.value * 2

        assert TestCommand._domain == "TestDomain"
        assert "TestCommand" in domain._commands

    def test_register_command(self):
        domain = Domain("TestDomain2")

        class TestInputs(BaseModel):
            x: int

        class MyCommand(Command[TestInputs, int]):
            def execute(self) -> int:
                return self.inputs.x

        domain.register_command(MyCommand)
        assert domain.get_command("MyCommand") == MyCommand

    def test_list_commands(self):
        domain = Domain("TestDomain3")

        class Inputs(BaseModel):
            x: int

        @domain.command
        class Cmd1(Command[Inputs, int]):
            def execute(self) -> int:
                return 1

        @domain.command
        class Cmd2(Command[Inputs, int]):
            def execute(self) -> int:
                return 2

        commands = domain.list_commands()
        assert len(commands) == 2

    def test_type_decorator(self):
        domain = Domain("TestDomain4")

        @domain.type()
        class User(BaseModel):
            id: int
            name: str

        assert "User" in domain._types

    def test_manifest(self):
        domain = Domain("TestDomain5", organization="TestOrg")

        class Inputs(BaseModel):
            x: int

        @domain.command
        class TestCmd(Command[Inputs, int]):
            def execute(self) -> int:
                return 1

        manifest = domain.manifest()
        assert manifest["name"] == "TestDomain5"
        assert manifest["organization"] == "TestOrg"
        assert "TestCmd" in manifest["commands"]

    def test_domain_registry(self):
        domain = Domain("RegisteredDomain", organization="Org")
        retrieved = Domain.get("Org::RegisteredDomain")
        assert retrieved == domain


class TestOrganization:
    def test_organization_creation(self):
        org = Organization("MyCompany")
        assert org.name == "MyCompany"

    def test_create_domain(self):
        org = Organization("TestOrg")
        users = org.domain("Users")
        billing = org.domain("Billing")

        assert users.organization == "TestOrg"
        assert billing.organization == "TestOrg"
        assert len(org.list_domains()) == 2

    def test_get_domain(self):
        org = Organization("TestOrg2")
        org.domain("Users")
        retrieved = org.get_domain("Users")
        assert retrieved is not None
        assert retrieved.name == "Users"

    def test_manifest(self):
        org = Organization("TestOrg3")
        org.domain("Domain1")
        org.domain("Domain2")

        manifest = org.manifest()
        assert manifest["name"] == "TestOrg3"
        assert "Domain1" in manifest["domains"]
        assert "Domain2" in manifest["domains"]

    def test_organization_registry(self):
        org = Organization("RegisteredOrg")
        retrieved = Organization.get("RegisteredOrg")
        assert retrieved == org


class TestCreateDomain:
    def test_create_domain_function(self):
        domain = create_domain("MyDomain", organization="MyOrg")
        assert domain.name == "MyDomain"
        assert domain.organization == "MyOrg"
