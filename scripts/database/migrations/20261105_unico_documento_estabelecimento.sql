-- Execute somente depois de corrigir documentos duplicados.
-- NULL continua permitido para registros legados sem documento.
ALTER TABLE leadestabelecimento
  ADD CONSTRAINT uk_leadestabelecimento_cpfcnpj UNIQUE (cpfcnpj);
