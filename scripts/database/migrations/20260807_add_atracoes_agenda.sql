CREATE TABLE atracao (
  atracao_id BIGINT AUTO_INCREMENT PRIMARY KEY, organizacao_id BIGINT NOT NULL,
  nmatracao VARCHAR(120) NOT NULL, dsestilomusical VARCHAR(255) NULL,
  urlbanneratracao VARCHAR(255) NULL, dsatracao TEXT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_atracao_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao (organizacao_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  INDEX idx_atracao_organizacao_nome (organizacao_id, nmatracao)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE eventoatracao (
  eventoatracao_id BIGINT AUTO_INCREMENT PRIMARY KEY, evento_id BIGINT NOT NULL, atracao_id BIGINT NOT NULL,
  dtinicioatracao DATETIME NOT NULL, dtfimatracao DATETIME NOT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_eventoatracao_evento FOREIGN KEY (evento_id) REFERENCES evento (evento_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_eventoatracao_atracao FOREIGN KEY (atracao_id) REFERENCES atracao (atracao_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_eventoatracao_periodo CHECK (dtfimatracao > dtinicioatracao),
  CONSTRAINT uq_eventoatracao_evento_atracao_inicio UNIQUE (evento_id, atracao_id, dtinicioatracao),
  INDEX idx_eventoatracao_periodo (dtinicioatracao, dtfimatracao)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
