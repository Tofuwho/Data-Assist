"""add dataset stats_json

Revision ID: b3c4d5e6f7a8
Revises: 8d2e5a1b3c4f
Create Date: 2026-11-10 23:12:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "8d2e5a1b3c4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("stats_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("datasets", schema=None) as batch_op:
        batch_op.drop_column("stats_json")
