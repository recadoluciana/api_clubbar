ALTER TABLE itvenda
  ADD COLUMN sititvenda ENUM('ATIVO','CANCELAMENTO_SOLICITADO','CANCELADO')
    NOT NULL DEFAULT 'ATIVO' AFTER vrtaxaitvenda,
  ADD COLUMN dtcancelamento DATETIME NULL AFTER sititvenda,
  ADD COLUMN vrreembolso DECIMAL(10,2) NULL AFTER dtcancelamento,
  ADD COLUMN idreembolso VARCHAR(120) NULL AFTER vrreembolso;

CREATE INDEX idx_itvenda_situacao
  ON itvenda(sititvenda);
