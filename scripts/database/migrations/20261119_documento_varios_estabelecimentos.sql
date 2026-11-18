-- Remover unicidade não valida titularidade e não concede acesso a contas.
-- A aplicação deve ser implantada junto com esta migração.
ALTER TABLE leadestabelecimento DROP INDEX uk_leadestabelecimento_cpfcnpj;
ALTER TABLE loja DROP INDEX uk_loja_cpfcnpj, ADD INDEX idx_loja_cpfcnpj (cpfcnpjloja);
