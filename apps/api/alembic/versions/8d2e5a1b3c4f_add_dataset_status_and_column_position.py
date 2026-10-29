"""add dataset status and column position

Revision ID: 8d2e5a1b3c4f
Revises: f4eeaef1a01c
Create Date: 2026-10-29 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d2e5a1b3c4f'
down_revision: Union[str, Sequence[str], None] = 'f4eeaef1a01c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('datasets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=False, server_default='processing'))
        batch_op.add_column(sa.Column('error_message', sa.Text(), nullable=True))

    with op.batch_alter_table('columns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('columns', schema=None) as batch_op:
        batch_op.drop_column('position')

    with op.batch_alter_table('datasets', schema=None) as batch_op:
        batch_op.drop_column('error_message')
        batch_op.drop_column('status')
