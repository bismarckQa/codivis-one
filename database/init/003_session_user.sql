ALTER TABLE public.license_tokens
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id);

CREATE INDEX IF NOT EXISTS ix_license_tokens_user_id
    ON public.license_tokens (user_id);
