-- Regularize documentos vazios antes de aplicar; não atribua documentos por suposição.
ALTER TABLE loja
  MODIFY COLUMN cpfcnpjloja VARCHAR(14) NOT NULL,
  ADD CONSTRAINT ck_loja_cpfcnpj_preenchido CHECK (CHAR_LENGTH(TRIM(cpfcnpjloja)) > 0);
