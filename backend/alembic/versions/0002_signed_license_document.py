"""Persist the signed license document for verification at runtime."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_signed_license_document"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("licenses", sa.Column("signed_payload", postgresql.JSONB(), nullable=True))
    op.add_column("licenses", sa.Column("signature", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("licenses", "signature")
    op.drop_column("licenses", "signed_payload")
