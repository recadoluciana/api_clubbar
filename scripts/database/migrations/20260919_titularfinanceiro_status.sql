ALTER TABLE titularfinanceiro
  ADD COLUMN IF NOT EXISTS sittitular VARCHAR(15) NOT NULL DEFAULT 'ATIVO';

CREATE INDEX IF NOT EXISTS ix_titularfinanceiro_sittitular
  ON titularfinanceiro (sittitular);
