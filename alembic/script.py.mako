"""${message}"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${upgrades if upgrades else ''}

def upgrade() -> None:
    ${upgrades or 'pass'}

def downgrade() -> None:
    ${downgrades or 'pass'}
