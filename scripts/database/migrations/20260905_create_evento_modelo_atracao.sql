CREATE TABLE eventomodeloatracao (
  eventomodeloatracao_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  eventomodelo_id BIGINT NOT NULL,
  atracao_id BIGINT NOT NULL,
  ordem INT NOT NULL,
  nrminutoinicio INT NOT NULL DEFAULT 0,
  nrminutoduracao INT NOT NULL DEFAULT 120,
  CONSTRAINT fk_eventomodeloatracao_modelo FOREIGN KEY (eventomodelo_id) REFERENCES eventomodelo(eventomodelo_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_eventomodeloatracao_atracao FOREIGN KEY (atracao_id) REFERENCES atracao(atracao_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT uq_eventomodeloatracao_ordem UNIQUE (eventomodelo_id, ordem),
  CONSTRAINT chk_eventomodeloatracao_inicio CHECK (nrminutoinicio >= 0),
  CONSTRAINT chk_eventomodeloatracao_duracao CHECK (nrminutoduracao > 0),
  INDEX idx_eventomodeloatracao_atracao (atracao_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
