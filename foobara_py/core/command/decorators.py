"""
Command decorators - @command and @async_command.

Provides decorator syntax for configuring command metadata.
"""

from typing import Tuple


def command(
    domain: str = None,
    organization: str = None,
    description: str = None,
    depends_on: Tuple[str, ...] = (),
):
    """
    Decorator for configuring commands.

    Usage:
        @command(domain="Users", organization="MyApp")
        class CreateUser(Command[CreateUserInputs, User]):
            def execute(self) -> User:
                ...
    """

    def decorator(cls):
        if domain:
            cls._domain = domain
        if organization:
            cls._organization = organization
        if description:
            cls._description = description
        if depends_on:
            cls._depends_on = depends_on
        return cls

    return decorator


def async_command(
    domain: str = None,
    organization: str = None,
    description: str = None,
    depends_on: Tuple[str, ...] = (),
):
    """Decorator for configuring async commands"""

    def decorator(cls):
        if domain:
            cls._domain = domain
        if organization:
            cls._organization = organization
        if description:
            cls._description = description
        if depends_on:
            cls._depends_on = depends_on
        return cls

    return decorator
