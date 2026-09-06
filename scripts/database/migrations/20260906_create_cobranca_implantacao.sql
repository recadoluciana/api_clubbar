ALTER TABLE leadestabelecimentocontrato
  ADD COLUMN vrimplantacao DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER vrtaxaing;

UPDATE leadestabelecimentocontrato lc
JOIN contratopadrao cp ON cp.contratopadrao_id = lc.contratopadrao_id
SET lc.vrimplantacao = cp.vrimplantacao
WHERE lc.vrimplantacao = 0;

CREATE TABLE cobrancaimplantacao (
  cobrancaimplantacao_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  leadestabelecimentocontrato_id BIGINT NOT NULL,
  leadestabelecimento_id BIGINT NOT NULL,
  organizacao_id BIGINT NULL,
  valor DECIMAL(10,2) NOT NULL,
  status VARCHAR(15) NOT NULL DEFAULT 'PENDENTE',
  asaas_checkout_id VARCHAR(100) NULL,
  asaas_payment_id VARCHAR(100) NULL,
  asaas_checkout_url TEXT NULL,
  billing_type VARCHAR(30) NULL,
  external_reference VARCHAR(100) NOT NULL,
  justificativaisencao VARCHAR(500) NULL,
  operadorisencao_id BIGINT NULL,
  dtvencimento DATETIME NULL,
  dtpagamento DATETIME NULL,
  dtisencao DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_cobrancaimplantacao_contrato (leadestabelecimentocontrato_id),
  UNIQUE KEY uk_cobrancaimplantacao_checkout (asaas_checkout_id),
  UNIQUE KEY uk_cobrancaimplantacao_payment (asaas_payment_id),
  UNIQUE KEY uk_cobrancaimplantacao_referencia (external_reference),
  KEY idx_cobrancaimplantacao_estabelecimento (leadestabelecimento_id),
  KEY idx_cobrancaimplantacao_organizacao (organizacao_id),
  KEY idx_cobrancaimplantacao_status (status),
  CONSTRAINT fk_cobrancaimplantacao_contrato FOREIGN KEY (leadestabelecimentocontrato_id) REFERENCES leadestabelecimentocontrato(leadestabelecimentocontrato_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_cobrancaimplantacao_estabelecimento FOREIGN KEY (leadestabelecimento_id) REFERENCES leadestabelecimento(leadestabelecimento_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_cobrancaimplantacao_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_cobrancaimplantacao_status CHECK (status IN ('PENDENTE','PAGA','VENCIDA','CANCELADA','ISENTA'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
