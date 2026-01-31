#!/usr/bin/env python3
"""
Lifecycle Hooks Example

Demonstrates before_execute callback for cross-cutting concerns
like authorization and logging.

Uses the enhanced callback DSL system.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from foobara_py import Command


# Simple audit log
audit_log = []


class TransferFundsInputs(BaseModel):
    from_account: str = Field(..., description="Source account ID")
    to_account: str = Field(..., description="Destination account ID")
    amount: float = Field(..., gt=0, description="Amount to transfer")


class TransferResult(BaseModel):
    transaction_id: str
    from_account: str
    to_account: str
    amount: float
    timestamp: str


class TransferFunds(Command[TransferFundsInputs, TransferResult]):
    """Transfer funds between accounts with authorization and auditing"""

    # Simulated current user (in real app, this would come from auth context)
    _current_user: str = "user_123"
    _authorized_users: set = {"user_123", "admin"}

    def execute(self) -> TransferResult:
        # Business logic - transfer funds
        result = TransferResult(
            transaction_id=f"TXN_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            from_account=self.inputs.from_account,
            to_account=self.inputs.to_account,
            amount=self.inputs.amount,
            timestamp=datetime.now().isoformat()
        )

        # Log successful transfer in execute (since after_execute runs before result is set)
        audit_log.append({
            'event': 'transfer_completed',
            'transaction_id': result.transaction_id,
            'user': self._current_user,
            'timestamp': datetime.now().isoformat()
        })

        return result


# Register authorization callback using DSL
def authorize(cmd):
    """Authorization check before transfer"""
    if cmd._current_user not in cmd._authorized_users:
        cmd.add_runtime_error(
            'unauthorized',
            f'User {cmd._current_user} is not authorized to transfer funds',
            halt=True
        )
        return

    # Log the attempt
    audit_log.append({
        'event': 'transfer_attempt',
        'user': cmd._current_user,
        'from': cmd.inputs.from_account,
        'to': cmd.inputs.to_account,
        'amount': cmd.inputs.amount,
        'timestamp': datetime.now().isoformat()
    })


TransferFunds.before_execute_transition(authorize)


if __name__ == "__main__":
    # Successful transfer with authorized user
    print("=== Authorized Transfer ===")
    TransferFunds._current_user = "user_123"

    outcome = TransferFunds.run(
        from_account="ACC001",
        to_account="ACC002",
        amount=100.00
    )

    if outcome.is_success():
        result = outcome.unwrap()
        print(f"Transfer successful: {result.transaction_id}")
        print(f"  From: {result.from_account}")
        print(f"  To: {result.to_account}")
        print(f"  Amount: ${result.amount:.2f}")
    else:
        print("Transfer failed:")
        for error in outcome.errors:
            print(f"  - {error.symbol}: {error.message}")

    # Unauthorized transfer attempt
    print("\n=== Unauthorized Transfer ===")
    TransferFunds._current_user = "hacker_456"

    outcome = TransferFunds.run(
        from_account="ACC001",
        to_account="ACC999",
        amount=10000.00
    )

    if outcome.is_failure():
        print("Transfer blocked:")
        for error in outcome.errors:
            print(f"  - {error.symbol}: {error.message}")
    else:
        print("Transfer unexpectedly succeeded!")

    # Show audit log
    print("\n=== Audit Log ===")
    for entry in audit_log:
        print(f"  {entry['event']}: {entry}")
