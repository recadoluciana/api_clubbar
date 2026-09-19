ALTER TABLE titularfinanceiro
  ADD COLUMN sittitular VARCHAR(15) NOT NULL DEFAULT 'ATIVO';

CREATE INDEX ix_titularfinanceiro_sittitular
  ON titularfinanceiro (sittitular);
