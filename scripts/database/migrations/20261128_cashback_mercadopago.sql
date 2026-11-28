ALTER TABLE checkout_mercadopago
  ADD COLUMN vrcashbackusado DECIMAL(10,2) NOT NULL DEFAULT 0.00;

ALTER TABLE cashback_movimento
  ADD COLUMN checkout_mercadopago_id BIGINT NULL,
  ADD INDEX idx_cashback_movimento_checkout_mp (checkout_mercadopago_id),
  ADD CONSTRAINT fk_cashback_movimento_checkout_mp FOREIGN KEY (checkout_mercadopago_id)
    REFERENCES checkout_mercadopago(checkout_mercadopago_id);
