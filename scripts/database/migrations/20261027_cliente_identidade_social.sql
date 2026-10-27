CREATE TABLE IF NOT EXISTS clienteidentidadesocial (
    clienteidentidadesocial_id BIGINT NOT NULL AUTO_INCREMENT,
    cliente_id BIGINT NOT NULL,
    provedor VARCHAR(20) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    email VARCHAR(160) NULL,
    dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dtultatu DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (clienteidentidadesocial_id),
    KEY ix_clienteidentidadesocial_cliente_id (cliente_id),
    UNIQUE KEY uq_clienteidentidadesocial_provedor_subject (provedor, subject),
    CONSTRAINT fk_clienteidentidadesocial_cliente
        FOREIGN KEY (cliente_id) REFERENCES cliente (cliente_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
