ALTER TABLE loja ADD COLUMN qtcpdloja INT NULL AFTER nrtelloja;
ALTER TABLE loja ADD CONSTRAINT chk_loja_capacidade CHECK (qtcpdloja IS NULL OR qtcpdloja > 0);

CREATE TABLE lojaconteudo (
  lojaconteudo_id BIGINT AUTO_INCREMENT PRIMARY KEY, loja_id BIGINT NOT NULL,
  dsdetalhadaloja TEXT NULL, fotos JSON NULL, publicacoes JSON NULL, videos JSON NULL, configuracoes JSON NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_lojaconteudo_loja UNIQUE (loja_id),
  CONSTRAINT fk_lojaconteudo_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE lojapoliticaingresso (
  lojapoliticaingresso_id BIGINT AUTO_INCREMENT PRIMARY KEY, loja_id BIGINT NOT NULL,
  dspoliticaingresso TEXT NULL, urlmapaingressos VARCHAR(255) NULL, dsmapaingressos TEXT NULL,
  dsorientacoesacesso TEXT NULL, configuracoes JSON NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_lojapoliticaingresso_loja UNIQUE (loja_id),
  CONSTRAINT fk_lojapoliticaingresso_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
