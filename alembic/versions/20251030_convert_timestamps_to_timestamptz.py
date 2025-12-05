"""Convert timestamp columns to timezone-aware types.

This migration aligns persisted columns with the updated SQLAlchemy models that
now emit timezone-aware ``datetime`` objects.  Without this change, inserting
UTC-aware timestamps into PostgreSQL results in ``DataError`` complaining about
mixing offset-naive and offset-aware datetimes.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251030_timestamps"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


BASE_TABLES: tuple[str, ...] = (
  "trainingjob",
  "trainingmetric",
  "environmentdefinition",
  "environmentstate",
  "filemetadata",
)


def _alter_timestamp_column(
  table: str,
  column: str,
  *,
  existing_nullable: bool,
  to_timezone: bool,
) -> None:
  """Switch a column between naive and timezone-aware timestamp types."""

  target_type = sa.TIMESTAMP(timezone=to_timezone)
  existing_type = sa.TIMESTAMP(timezone=not to_timezone)
  using_clause = f"{column} AT TIME ZONE 'UTC'"

  op.alter_column(
    table,
    column,
    type_=target_type,
    existing_type=existing_type,
    existing_nullable=existing_nullable,
    postgresql_using=using_clause,
  )


def upgrade() -> None:
  bind = op.get_bind()
  if bind.dialect.name != "postgresql":
    # SQLite (used in tests) does not differentiate timezone-aware timestamps.
    return

  for table in BASE_TABLES:
    _alter_timestamp_column(table, "created_at", existing_nullable=True, to_timezone=True)
    _alter_timestamp_column(table, "updated_at", existing_nullable=True, to_timezone=True)

  _alter_timestamp_column("trainingjob", "started_at", existing_nullable=True, to_timezone=True)
  _alter_timestamp_column("trainingjob", "completed_at", existing_nullable=True, to_timezone=True)
  _alter_timestamp_column("trainingmetric", "timestamp", existing_nullable=True, to_timezone=True)


def downgrade() -> None:
  bind = op.get_bind()
  if bind.dialect.name != "postgresql":
    return

  _alter_timestamp_column("trainingmetric", "timestamp", existing_nullable=True, to_timezone=False)
  _alter_timestamp_column("trainingjob", "completed_at", existing_nullable=True, to_timezone=False)
  _alter_timestamp_column("trainingjob", "started_at", existing_nullable=True, to_timezone=False)

  for table in reversed(BASE_TABLES):
    _alter_timestamp_column(table, "updated_at", existing_nullable=True, to_timezone=False)
    _alter_timestamp_column(table, "created_at", existing_nullable=True, to_timezone=False)
