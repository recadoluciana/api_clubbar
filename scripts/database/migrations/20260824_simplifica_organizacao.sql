-- Dados fiscais pertencem a titularfinanceiro; enderecos comerciais pertencem a loja.
ALTER TABLE organizacao
  DROP FOREIGN KEY fk_organizacao_estado,
  DROP FOREIGN KEY fk_organizacao_cidade,
  DROP INDEX uk_organizacao_cnpj,
  DROP INDEX idx_organizacao_cidade,
  DROP COLUMN rzsocialorganizacao,
  DROP COLUMN cnpjorganizacao,
  DROP COLUMN ceporganizacao,
  DROP COLUMN endorganizacao,
  DROP COLUMN nrendorganizacao,
  DROP COLUMN complorganizacao,
  DROP COLUMN estado_id,
  DROP COLUMN cidade_id,
  DROP COLUMN nmbairro;
