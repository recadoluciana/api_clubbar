CREATE TABLE organizacaoestilomusical (
  organizacaoestilomusical_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  estilomusical_id BIGINT NULL,
  nmestilomusical VARCHAR(120) NOT NULL,
  sitestilomusical VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_orgestilo_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_orgestilo_padrao FOREIGN KEY (estilomusical_id) REFERENCES estilomusical(estilomusical_id) ON DELETE SET NULL ON UPDATE CASCADE,
  UNIQUE KEY uk_orgestilo_nome (organizacao_id, nmestilomusical),
  UNIQUE KEY uk_orgestilo_padrao (organizacao_id, estilomusical_id),
  INDEX idx_orgestilo_situacao_nome (organizacao_id, sitestilomusical, nmestilomusical)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE atracaoorganizacaoestilomusical (
  atracao_id BIGINT NOT NULL,
  organizacaoestilomusical_id BIGINT NOT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (atracao_id, organizacaoestilomusical_id),
  CONSTRAINT fk_atracaoorgestilo_atracao FOREIGN KEY (atracao_id) REFERENCES atracao(atracao_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_atracaoorgestilo_estilo FOREIGN KEY (organizacaoestilomusical_id) REFERENCES organizacaoestilomusical(organizacaoestilomusical_id) ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_atracaoorgestilo_estilo (organizacaoestilomusical_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO organizacaoestilomusical (organizacao_id, estilomusical_id, nmestilomusical, sitestilomusical)
SELECT DISTINCT a.organizacao_id, e.estilomusical_id, e.nmestilomusical, e.sitestilomusical
FROM atracaoestilomusical ae
JOIN atracao a ON a.atracao_id=ae.atracao_id
JOIN estilomusical e ON e.estilomusical_id=ae.estilomusical_id;

INSERT IGNORE INTO atracaoorganizacaoestilomusical (atracao_id, organizacaoestilomusical_id)
SELECT ae.atracao_id, oe.organizacaoestilomusical_id
FROM atracaoestilomusical ae
JOIN atracao a ON a.atracao_id=ae.atracao_id
JOIN organizacaoestilomusical oe ON oe.organizacao_id=a.organizacao_id AND oe.estilomusical_id=ae.estilomusical_id;

DROP TABLE atracaoestilomusical;
