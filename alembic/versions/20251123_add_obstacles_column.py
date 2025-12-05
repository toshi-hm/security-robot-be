"""Add obstacles column to environment state.

Adds obstacles column to store terrain information (mazes, caves, etc.)
for the Playback API.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251123_add_obstacles_column"
down_revision: str | None = "20251111_battery"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
  """Add obstacles column to environmentstate table."""
  op.add_column(
    "environmentstate",
    sa.Column("obstacles", sa.JSON(), nullable=True),
  )


def downgrade() -> None:
  """Remove obstacles column from environmentstate table."""
  op.drop_column("environmentstate", "obstacles")
