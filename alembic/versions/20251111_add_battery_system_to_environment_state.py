"""Add battery system fields to environment state.

Adds battery_percentage, is_charging, distance_to_charging_station,
charging_station_position_x, and charging_station_position_y columns
to support battery management in playback and monitoring.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251111_add_battery_system_to_environment_state"
down_revision: str | None = "20251030_convert_timestamps_to_timestamptz"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
  """Add battery system columns to environmentstate table."""
  op.add_column(
    "environmentstate",
    sa.Column("battery_percentage", sa.Float(), nullable=True),
  )
  op.add_column(
    "environmentstate",
    sa.Column("is_charging", sa.Boolean(), nullable=False, server_default="false"),
  )
  op.add_column(
    "environmentstate",
    sa.Column("distance_to_charging_station", sa.Integer(), nullable=True),
  )
  op.add_column(
    "environmentstate",
    sa.Column("charging_station_position_x", sa.Integer(), nullable=True),
  )
  op.add_column(
    "environmentstate",
    sa.Column("charging_station_position_y", sa.Integer(), nullable=True),
  )


def downgrade() -> None:
  """Remove battery system columns from environmentstate table."""
  op.drop_column("environmentstate", "charging_station_position_y")
  op.drop_column("environmentstate", "charging_station_position_x")
  op.drop_column("environmentstate", "distance_to_charging_station")
  op.drop_column("environmentstate", "is_charging")
  op.drop_column("environmentstate", "battery_percentage")
