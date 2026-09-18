ALTER TABLE loja
  ADD COLUMN cpfcnpjloja VARCHAR(14) NULL AFTER nmloja,
  ADD COLUMN cnpjraiz VARCHAR(8) NULL AFTER cpfcnpjloja,
  ADD COLUMN tipoestabelecimento VARCHAR(10) NULL AFTER cnpjraiz,
  ADD COLUMN nmrazaosocial VARCHAR(160) NULL AFTER tipoestabelecimento;

UPDATE loja l
JOIN leadestabelecimento e
  ON e.leadestabelecimento_id = l.leadestabelecimento_id
SET l.cpfcnpjloja = UPPER(REPLACE(REPLACE(REPLACE(REPLACE(e.cpfcnpj, '.', ''), '/', ''), '-', ''), ' ', '')),
    l.cnpjraiz = CASE
      WHEN CHAR_LENGTH(REPLACE(REPLACE(REPLACE(REPLACE(e.cpfcnpj, '.', ''), '/', ''), '-', ''), ' ', '')) = 14
      THEN LEFT(UPPER(REPLACE(REPLACE(REPLACE(REPLACE(e.cpfcnpj, '.', ''), '/', ''), '-', ''), ' ', '')), 8)
      ELSE NULL
    END,
    l.tipoestabelecimento = CASE
      WHEN SUBSTRING(REPLACE(REPLACE(REPLACE(REPLACE(e.cpfcnpj, '.', ''), '/', ''), '-', ''), ' ', ''), 9, 4) = '0001' THEN 'MATRIZ'
      WHEN CHAR_LENGTH(REPLACE(REPLACE(REPLACE(REPLACE(e.cpfcnpj, '.', ''), '/', ''), '-', ''), ' ', '')) = 14 THEN 'FILIAL'
      ELSE NULL
    END;

UPDATE loja l
JOIN (
  SELECT c.leadestabelecimento_id, c.nmrazaosocial
  FROM leadestabelecimentocontrato c
  JOIN (
    SELECT leadestabelecimento_id, MAX(leadestabelecimentocontrato_id) contrato_id
    FROM leadestabelecimentocontrato
    WHERE status = 'ACEITO'
    GROUP BY leadestabelecimento_id
  ) ultimo ON ultimo.contrato_id = c.leadestabelecimentocontrato_id
) contrato ON contrato.leadestabelecimento_id = l.leadestabelecimento_id
SET l.nmrazaosocial = contrato.nmrazaosocial;

UPDATE loja duplicada
JOIN loja principal
  ON principal.cpfcnpjloja = duplicada.cpfcnpjloja
 AND principal.loja_id < duplicada.loja_id
SET duplicada.cpfcnpjloja = NULL,
    duplicada.cnpjraiz = NULL,
    duplicada.tipoestabelecimento = NULL;

UPDATE loja l
JOIN titularfinanceiro duplicado ON duplicado.titularfinanceiro_id = l.titularfinanceiro_id
JOIN titularfinanceiro principal
  ON principal.cpfcnpj = duplicado.cpfcnpj
 AND principal.titularfinanceiro_id < duplicado.titularfinanceiro_id
SET l.titularfinanceiro_id = principal.titularfinanceiro_id;

UPDATE leadestabelecimentocontrato c
JOIN titularfinanceiro duplicado ON duplicado.titularfinanceiro_id = c.titularfinanceiro_id
JOIN titularfinanceiro principal
  ON principal.cpfcnpj = duplicado.cpfcnpj
 AND principal.titularfinanceiro_id < duplicado.titularfinanceiro_id
SET c.titularfinanceiro_id = principal.titularfinanceiro_id;

DELETE duplicado
FROM titularfinanceiro duplicado
JOIN titularfinanceiro principal
  ON principal.cpfcnpj = duplicado.cpfcnpj
 AND principal.titularfinanceiro_id < duplicado.titularfinanceiro_id;

ALTER TABLE titularfinanceiro
  ADD UNIQUE KEY uk_titularfinanceiro_cpfcnpj (cpfcnpj),
  ADD UNIQUE KEY uk_titularfinanceiro_asaas_account (asaas_account_id),
  ADD UNIQUE KEY uk_titularfinanceiro_asaas_wallet (asaas_wallet_id),
  ADD UNIQUE KEY uk_titularfinanceiro_org_id (organizacao_id, titularfinanceiro_id);

ALTER TABLE loja
  ADD UNIQUE KEY uk_loja_cpfcnpj (cpfcnpjloja),
  ADD KEY idx_loja_cnpjraiz (cnpjraiz),
  ADD KEY idx_loja_org_titular (organizacao_id, titularfinanceiro_id),
  ADD CONSTRAINT fk_loja_titular_org
    FOREIGN KEY (organizacao_id, titularfinanceiro_id)
    REFERENCES titularfinanceiro (organizacao_id, titularfinanceiro_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT chk_loja_tipo_estabelecimento
    CHECK (tipoestabelecimento IS NULL OR tipoestabelecimento IN ('MATRIZ', 'FILIAL'));
