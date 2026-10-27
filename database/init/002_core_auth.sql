CREATE TABLE IF NOT EXISTS public.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name_ciphertext BYTEA NOT NULL,
    name_fingerprint BYTEA NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.licenses (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES public.companies(id),
    edition TEXT NOT NULL,
    max_users INTEGER NOT NULL CHECK (max_users > 0),
    max_branches INTEGER NOT NULL CHECK (max_branches > 0),
    modules JSONB NOT NULL DEFAULT '[]'::jsonb,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL CHECK (valid_until > valid_from),
    installation_id TEXT NOT NULL,
    key_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id),
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, email)
);

CREATE INDEX IF NOT EXISTS ix_licenses_company_id ON public.licenses(company_id);
CREATE INDEX IF NOT EXISTS ix_branches_company_id ON public.branches(company_id);
CREATE INDEX IF NOT EXISTS ix_users_company_id ON public.users(company_id);
