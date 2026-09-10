CREATE TABLE IF NOT EXISTS manualguia (
    manual_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    slug VARCHAR(60) NOT NULL,
    ordem INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_manual_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS manualversao (
    manualversao_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    manual_id INT NOT NULL,
    versao INT NOT NULL,
    titulo VARCHAR(160) NOT NULL,
    descricao TEXT NOT NULL,
    etapas JSON NOT NULL,
    resumo_alteracao VARCHAR(500) NOT NULL,
    operador_id INT NULL,
    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_manual_versao UNIQUE (manual_id, versao),
    CONSTRAINT fk_manualversao_manual FOREIGN KEY (manual_id) REFERENCES manualguia(manual_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
