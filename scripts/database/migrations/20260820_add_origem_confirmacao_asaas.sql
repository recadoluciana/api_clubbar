ALTER TABLE checkout_asaas
  ADD COLUMN dsorigemconfirmacao VARCHAR(20) NULL AFTER status,
  ADD COLUMN dtconfirmacao DATETIME NULL AFTER dsorigemconfirmacao;

CREATE INDEX idx_checkout_asaas_origem_confirmacao
  ON checkout_asaas (dsorigemconfirmacao, dtconfirmacao);
