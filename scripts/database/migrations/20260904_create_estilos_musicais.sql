CREATE TABLE estilomusical (
  estilomusical_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  nmestilomusical VARCHAR(120) NOT NULL,
  sitestilomusical VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_estilomusical_nome (nmestilomusical),
  INDEX idx_estilomusical_situacao_nome (sitestilomusical, nmestilomusical)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE atracaoestilomusical (
  atracao_id BIGINT NOT NULL,
  estilomusical_id BIGINT NOT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (atracao_id, estilomusical_id),
  CONSTRAINT fk_atracaoestilo_atracao FOREIGN KEY (atracao_id)
    REFERENCES atracao(atracao_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_atracaoestilo_estilo FOREIGN KEY (estilomusical_id)
    REFERENCES estilomusical(estilomusical_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  INDEX idx_atracaoestilo_estilo (estilomusical_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
