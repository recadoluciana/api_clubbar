-- Executar uma vez em cada banco, antes de publicar a API atualizada.
CREATE TABLE IF NOT EXISTS lojamercadopagopendente (
  loja_id BIGINT NOT NULL,
  ambiente VARCHAR(20) NOT NULL,
  confirmacao_id VARCHAR(64) NOT NULL,
  credenciais TEXT NOT NULL,
  expira_em DATETIME NOT NULL,
  PRIMARY KEY (loja_id, ambiente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE lojamercadopago
  ADD KEY idx_lojamercadopago_loja_ambiente (loja_id, ambiente),
  DROP INDEX uq_lojamercadopago_loja_ambiente,
  ADD UNIQUE KEY uq_lojamercadopago_loja_ambiente_usuario (loja_id, ambiente, mercadopago_user_id);

ALTER TABLE checkout_mercadopago
  ADD COLUMN lojamercadopago_id BIGINT NULL,
  ADD KEY idx_checkout_mp_lojamercadopago (lojamercadopago_id),
  ADD CONSTRAINT fk_checkout_mp_lojamercadopago FOREIGN KEY (lojamercadopago_id)
    REFERENCES lojamercadopago (lojamercadopago_id);

ALTER TABLE pagvenda
  ADD COLUMN lojamercadopago_id BIGINT NULL,
  ADD KEY idx_pagvenda_lojamercadopago (lojamercadopago_id),
  ADD CONSTRAINT fk_pagvenda_lojamercadopago FOREIGN KEY (lojamercadopago_id)
    REFERENCES lojamercadopago (lojamercadopago_id);

-- Vendas anteriores permanecem sem vínculo até confirmação da conta original.
