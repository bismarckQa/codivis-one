"""Name the user email constraint for deterministic conflict handling."""
from alembic import op


revision = "0009_user_management"
down_revision = "0008_stock_operation_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'users'::regclass AND conname = 'users_company_id_email_key'
            ) THEN
                ALTER TABLE users RENAME CONSTRAINT users_company_id_email_key TO uq_users_company_email;
            ELSIF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'users'::regclass AND conname = 'uq_users_company_email'
            ) THEN
                ALTER TABLE users ADD CONSTRAINT uq_users_company_email UNIQUE (company_id, email);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'users'::regclass AND conname = 'uq_users_company_email'
            ) THEN
                ALTER TABLE users RENAME CONSTRAINT uq_users_company_email TO users_company_id_email_key;
            END IF;
        END $$;
        """
    )
