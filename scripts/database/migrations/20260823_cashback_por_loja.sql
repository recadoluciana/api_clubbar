ALTER TABLE cashback_config
  MODIFY nrdiapliberacao INT NOT NULL DEFAULT 7,
  MODIFY pcmaxusocompra DECIMAL(10,2) NOT NULL DEFAULT 30.00;

ALTER TABLE cashback_movimento
  ADD COLUMN checkout_asaas_id BIGINT NULL AFTER venda_uso_id,
  ADD COLUMN cashback_movimento_origem_id BIGINT NULL AFTER checkout_asaas_id,
  ADD INDEX idx_cashback_movimento_checkout (checkout_asaas_id),
  ADD INDEX idx_cashback_movimento_origem (cashback_movimento_origem_id),
  ADD CONSTRAINT fk_cashback_movimento_checkout FOREIGN KEY (checkout_asaas_id) REFERENCES checkout_asaas(checkout_asaas_id),
  ADD CONSTRAINT fk_cashback_movimento_origem FOREIGN KEY (cashback_movimento_origem_id) REFERENCES cashback_movimento(cashback_movimento_id);

ALTER TABLE checkout_asaas ADD COLUMN vrcashbackusado DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER vrtaxaclubbar;
ALTER TABLE produto ADD COLUMN pccashback DECIMAL(10,2) NULL AFTER vrdesconto,
  ADD CONSTRAINT chk_produto_pccashback CHECK (pccashback IS NULL OR (pccashback >= 0 AND pccashback <= 100));
