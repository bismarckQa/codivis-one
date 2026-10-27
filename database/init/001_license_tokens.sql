CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.license_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_id UUID NOT NULL,
    token_type TEXT NOT NULL,
    token_hash BYTEA NOT NULL,
    company_fingerprint BYTEA NOT NULL,
    company_name_ciphertext BYTEA NOT NULL,
    license_payload_ciphertext BYTEA,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT license_tokens_token_type_check CHECK (token_type IN ('license_activation', 'session')),
    CONSTRAINT license_tokens_expiry_check CHECK (expires_at > issued_at),
    CONSTRAINT license_tokens_revocation_check CHECK (revoked_at IS NULL OR revoked_at >= issued_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_license_tokens_token_hash ON public.license_tokens (token_hash);
CREATE INDEX IF NOT EXISTS ix_license_tokens_license_id ON public.license_tokens (license_id);
CREATE INDEX IF NOT EXISTS ix_license_tokens_company_fingerprint ON public.license_tokens (company_fingerprint);

COMMENT ON TABLE public.license_tokens IS
    'Opaque license/session token records. Plaintext tokens and plaintext company data are never stored.';
COMMENT ON COLUMN public.license_tokens.token_hash IS
    'SHA-256/HMAC digest of the token, calculated by the backend; never the plaintext token.';
COMMENT ON COLUMN public.license_tokens.company_fingerprint IS
    'Non-reversible lookup fingerprint for the company identity.';
COMMENT ON COLUMN public.license_tokens.company_name_ciphertext IS
    'Authenticated-encrypted company name; encryption key remains outside PostgreSQL.';
COMMENT ON COLUMN public.license_tokens.license_payload_ciphertext IS
    'Authenticated-encrypted license claims; encryption key remains outside PostgreSQL.';
