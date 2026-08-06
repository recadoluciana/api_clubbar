CREATE TABLE IF NOT EXISTS lojaasaas (
    lojaasaas_id BIGINT NOT NULL AUTO_INCREMENT,
    organizacao_id BIGINT NOT NULL,
    loja_id BIGINT NOT NULL,
    ambiente VARCHAR(20) NOT NULL,
    asaas_account_id VARCHAR(100) NULL,
    asaas_wallet_id VARCHAR(100) NOT NULL,
    asaas_api_key_criptografada TEXT NOT NULL,
    webhook_token_hash CHAR(64) NOT NULL,
    statusintegracao VARCHAR(20) NOT NULL DEFAULT 'ATIVA',
    dtcriacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dtalteracao TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (lojaasaas_id),
    UNIQUE KEY uq_lojaasaas_loja_ambiente (loja_id, ambiente),
    UNIQUE KEY uq_lojaasaas_webhook_token_hash (webhook_token_hash),
    CONSTRAINT fk_lojaasaas_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao (organizacao_id),
    CONSTRAINT fk_lojaasaas_loja FOREIGN KEY (loja_id) REFERENCES loja (loja_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clienteasaas (
    clienteasaas_id BIGINT NOT NULL AUTO_INCREMENT,
    cliente_id BIGINT NOT NULL,
    loja_id BIGINT NOT NULL,
    asaas_customer_id VARCHAR(100) NOT NULL,
    dtcriacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dtalteracao TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (clienteasaas_id),
    UNIQUE KEY uq_clienteasaas_cliente_loja (cliente_id, loja_id),
    CONSTRAINT fk_clienteasaas_cliente FOREIGN KEY (cliente_id) REFERENCES cliente (cliente_id) ON DELETE CASCADE,
    CONSTRAINT fk_clienteasaas_loja FOREIGN KEY (loja_id) REFERENCES loja (loja_id) ON DELETE CASCADE
);

ALTER TABLE checkout_asaas
    ADD COLUMN vrtaxaclubbar DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    ADD COLUMN asaas_wallet_loja VARCHAR(100) NULL,
    ADD COLUMN asaas_wallet_clubbar VARCHAR(100) NULL;
