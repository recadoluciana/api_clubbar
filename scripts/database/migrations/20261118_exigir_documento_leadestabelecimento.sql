-- Antes de executar, regularize manualmente os documentos vazios:
-- SELECT leadestabelecimento_id, nmestabelecimento FROM leadestabelecimento
-- WHERE cpfcnpj IS NULL OR CHAR_LENGTH(TRIM(cpfcnpj)) = 0;
-- Confirme a identidade fiscal e conflitos com a restrição de unicidade.
-- Esta migração não copia documentos automaticamente.
ALTER TABLE leadestabelecimento
  MODIFY COLUMN cpfcnpj VARCHAR(14) NOT NULL,
  ADD CONSTRAINT ck_leadestabelecimento_cpfcnpj_preenchido
    CHECK (CHAR_LENGTH(TRIM(cpfcnpj)) > 0);
