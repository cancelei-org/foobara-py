"""
Entities for the Auth domain.
"""

from datetime import datetime
from typing import Any, List, Optional

from foobara_py.persistence.entity import EntityBase, register_entity


@register_entity
class Token(EntityBase):
    """
    Authentication token entity.
    """

    id: str  # The public token ID
    secret_hash: str  # Hashed version of the token secret
    user_id: Any  # Reference to the user
    expires_at: datetime
    scopes: List[str] = []
    revoked: bool = False

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired
