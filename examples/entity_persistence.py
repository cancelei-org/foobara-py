#!/usr/bin/env python3
"""
Entity Persistence Example

Demonstrates entity definition, repository pattern, and
automatic entity loading in commands.
"""

from pydantic import BaseModel, Field
from foobara_py import Command
from foobara_py.persistence.entity import EntityBase, load
from foobara_py.persistence.repository import (
    InMemoryRepository,
    TransactionalInMemoryRepository,
    RepositoryRegistry
)


# Define an entity
class User(EntityBase):
    """User entity with persistence support"""
    _primary_key_field = 'id'

    id: int = None  # Auto-assigned on save
    name: str
    email: str
    balance: float = 0.0


# Input models
class CreateUserInputs(BaseModel):
    name: str = Field(..., min_length=1)
    email: str


class UpdateBalanceInputs(BaseModel):
    user_id: int = Field(..., description="User ID to update")
    amount: float = Field(..., description="Amount to add (can be negative)")


class TransferInputs(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: float = Field(..., gt=0)


# Commands with entity loading
class CreateUser(Command[CreateUserInputs, User]):
    """Create a new user"""

    def execute(self) -> User:
        user = User(name=self.inputs.name, email=self.inputs.email)
        repo = RepositoryRegistry.get(User)
        return repo.save(user)


class UpdateBalance(Command[UpdateBalanceInputs, User]):
    """Update a user's balance with automatic entity loading"""

    # Automatically load user entity from user_id input
    _loads = [load(User, from_input='user_id', into='user', required=True)]

    def execute(self) -> User:
        # self.user is automatically loaded
        self.user.balance += self.inputs.amount
        repo = RepositoryRegistry.get(User)
        return repo.save(self.user)


class TransferFunds(Command[TransferInputs, dict]):
    """Transfer funds between users (demonstrates transactions)"""

    _loads = [
        load(User, from_input='from_user_id', into='from_user', required=True),
        load(User, from_input='to_user_id', into='to_user', required=True),
    ]

    _possible_errors = [
        ('insufficient_funds', 'Source account has insufficient funds'),
    ]

    def execute(self) -> dict:
        if self.from_user.balance < self.inputs.amount:
            self.add_runtime_error('insufficient_funds', 'Source account has insufficient funds')
            return None

        self.from_user.balance -= self.inputs.amount
        self.to_user.balance += self.inputs.amount

        repo = RepositoryRegistry.get(User)
        repo.save(self.from_user)
        repo.save(self.to_user)

        return {
            'from_user': self.from_user.name,
            'to_user': self.to_user.name,
            'amount': self.inputs.amount,
            'from_balance': self.from_user.balance,
            'to_balance': self.to_user.balance
        }


if __name__ == "__main__":
    # Setup repository (use transactional for production)
    repo = TransactionalInMemoryRepository()
    RepositoryRegistry.set_default(repo)

    print("=== Creating Users ===")
    outcome = CreateUser.run(name="Alice", email="alice@example.com")
    alice = outcome.unwrap()
    print(f"Created: {alice.name} (ID: {alice.id})")

    outcome = CreateUser.run(name="Bob", email="bob@example.com")
    bob = outcome.unwrap()
    print(f"Created: {bob.name} (ID: {bob.id})")

    print("\n=== Initial Balances ===")
    # Give Alice some money
    outcome = UpdateBalance.run(user_id=alice.id, amount=1000.0)
    alice = outcome.unwrap()
    print(f"Alice balance: ${alice.balance:.2f}")
    print(f"Bob balance: ${bob.balance:.2f}")

    print("\n=== Transfer with Transaction ===")
    with repo.transaction():
        outcome = TransferFunds.run(
            from_user_id=alice.id,
            to_user_id=bob.id,
            amount=250.0
        )
        if outcome.is_success():
            result = outcome.unwrap()
            print(f"Transferred ${result['amount']:.2f}")
            print(f"  {result['from_user']}: ${result['from_balance']:.2f}")
            print(f"  {result['to_user']}: ${result['to_balance']:.2f}")

    print("\n=== Transfer with Insufficient Funds ===")
    outcome = TransferFunds.run(
        from_user_id=bob.id,
        to_user_id=alice.id,
        amount=500.0  # Bob only has $250
    )
    if outcome.is_failure():
        for error in outcome.errors:
            print(f"Error: {error.symbol} - {error.message}")

    print("\n=== Entity Not Found ===")
    outcome = UpdateBalance.run(user_id=999, amount=100.0)
    if outcome.is_failure():
        for error in outcome.errors:
            print(f"Error: {error.symbol} - {error.message}")

    # Cleanup
    RepositoryRegistry.clear()
