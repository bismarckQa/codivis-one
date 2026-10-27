"""Create the Codivis One activation schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table("companies", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name_ciphertext", sa.LargeBinary(), nullable=False), sa.Column("name_fingerprint", sa.LargeBinary(), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), if_not_exists=True)
    op.create_table("licenses", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False), sa.Column("edition", sa.String(), nullable=False), sa.Column("max_users", sa.Integer(), nullable=False), sa.Column("max_branches", sa.Integer(), nullable=False), sa.Column("modules", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False), sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False), sa.Column("installation_id", sa.String(), nullable=False), sa.Column("key_id", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), if_not_exists=True)
    op.create_table("branches", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), if_not_exists=True)
    op.create_table("users", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False), sa.Column("email", sa.String(), nullable=False), sa.Column("password_hash", sa.String(), nullable=False), sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("company_id", "email"), if_not_exists=True)
    op.create_table("license_tokens", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("license_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("licenses.id"), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")), sa.Column("token_type", sa.String(), nullable=False), sa.Column("token_hash", sa.LargeBinary(), nullable=False, unique=True), sa.Column("company_fingerprint", sa.LargeBinary(), nullable=False), sa.Column("company_name_ciphertext", sa.LargeBinary(), nullable=False), sa.Column("license_payload_ciphertext", sa.LargeBinary()), sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("last_used_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), if_not_exists=True)


def downgrade() -> None:
    op.drop_table("license_tokens")
    op.drop_table("users")
    op.drop_table("branches")
    op.drop_table("licenses")
    op.drop_table("companies")
