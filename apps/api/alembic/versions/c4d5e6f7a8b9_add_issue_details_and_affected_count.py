"""add issue details_json, affected_count, and source

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-11-10 23:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("issues", schema=None) as batch_op:
        batch_op.add_column(sa.Column("affected_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("details_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=20), nullable=False, server_default="auto"))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("issues", schema=None) as batch_op:
        batch_op.drop_column("source")
        batch_op.drop_column("details_json")
        batch_op.drop_column("affected_count")
