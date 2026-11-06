"""Add pet photo metadata.

Revision ID: 0002_pet_photos
Revises: 0001_initial
Create Date: 2026-11-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_pet_photos"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pets", sa.Column("photo_filename", sa.String(), nullable=True))
    op.add_column(
        "pets", sa.Column("photo_updated_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("pets", "photo_updated_at")
    op.drop_column("pets", "photo_filename")
