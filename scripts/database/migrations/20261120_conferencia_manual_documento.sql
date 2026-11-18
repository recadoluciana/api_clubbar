-- Não marca registros existentes como conferidos automaticamente.
ALTER TABLE leadestabelecimento
  ADD COLUMN documento_conferido VARCHAR(14) NULL,
  ADD COLUMN nome_titular_conferido VARCHAR(160) NULL,
  ADD COLUMN dtconferencia_documento DATETIME NULL;
