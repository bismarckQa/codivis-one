"""Add branch active state and uniqueness for the single installation."""
from alembic import op
import sqlalchemy as sa


revision = "0004_branch_controls"
down_revision = "0003_directory_customers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_index("uq_branches_company_name", "branches", ["company_id", "name"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_branches_company_name", table_name="branches")
    op.drop_column("branches", "is_active")
