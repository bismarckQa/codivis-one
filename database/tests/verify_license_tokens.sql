DO $$
DECLARE
  token_hash_type text;
  token_hash_nullable text;
  company_ciphertext_type text;
  token_type_check boolean;
BEGIN
  IF to_regclass('public.license_tokens') IS NULL THEN
    RAISE EXCEPTION 'public.license_tokens does not exist';
  END IF;
  SELECT data_type, is_nullable INTO token_hash_type, token_hash_nullable
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'license_tokens' AND column_name = 'token_hash';
  IF token_hash_type <> 'bytea' OR token_hash_nullable <> 'NO' THEN
    RAISE EXCEPTION 'token_hash must be required bytea';
  END IF;
  SELECT data_type INTO company_ciphertext_type
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'license_tokens' AND column_name = 'company_name_ciphertext';
  IF company_ciphertext_type <> 'bytea' THEN
    RAISE EXCEPTION 'company_name_ciphertext must be bytea';
  END IF;
  SELECT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.license_tokens'::regclass
      AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%token_type%'
  ) INTO token_type_check;
  IF NOT token_type_check THEN
    RAISE EXCEPTION 'token_type check constraint is missing';
  END IF;
END $$;
SELECT 'license_tokens schema verified' AS result;
