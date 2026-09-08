CREATE TABLE lojaestilomusical (
  loja_id BIGINT NOT NULL,
  organizacaoestilomusical_id BIGINT NOT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (loja_id, organizacaoestilomusical_id),
  CONSTRAINT fk_lojaestilo_loja FOREIGN KEY (loja_id)
    REFERENCES loja(loja_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_lojaestilo_estilo FOREIGN KEY (organizacaoestilomusical_id)
    REFERENCES organizacaoestilomusical(organizacaoestilomusical_id) ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_lojaestilo_estilo (organizacaoestilomusical_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
