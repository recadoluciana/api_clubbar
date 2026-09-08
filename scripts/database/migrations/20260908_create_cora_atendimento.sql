CREATE TABLE IF NOT EXISTS coraduvida (
    coraduvida_id BIGINT NOT NULL AUTO_INCREMENT,
    pergunta VARCHAR(255) NOT NULL,
    resposta TEXT NOT NULL,
    idordem INT NOT NULL DEFAULT 0,
    sitduvida VARCHAR(15) NOT NULL DEFAULT 'ATIVA',
    dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dtultatu DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (coraduvida_id),
    UNIQUE KEY uq_coraduvida_pergunta (pergunta),
    KEY ix_coraduvida_sitduvida (sitduvida)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS coramensagem (
    coramensagem_id BIGINT NOT NULL AUTO_INCREMENT,
    cliente_id BIGINT NOT NULL,
    coraduvida_id BIGINT NULL,
    origem ENUM('CLIENTE', 'CORA') NOT NULL,
    mensagem TEXT NOT NULL,
    lida CHAR(1) NOT NULL DEFAULT 'N',
    dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (coramensagem_id),
    KEY ix_coramensagem_cliente_id (cliente_id),
    KEY ix_coramensagem_dtcriacao (dtcriacao),
    KEY ix_coramensagem_coraduvida_id (coraduvida_id),
    CONSTRAINT fk_coramensagem_cliente FOREIGN KEY (cliente_id)
        REFERENCES cliente (cliente_id) ON DELETE CASCADE,
    CONSTRAINT fk_coramensagem_coraduvida FOREIGN KEY (coraduvida_id)
        REFERENCES coraduvida (coraduvida_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
