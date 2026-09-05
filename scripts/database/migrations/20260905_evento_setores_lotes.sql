ALTER TABLE evento
  ADD COLUMN urlmapaingressos VARCHAR(255) NULL AFTER urlbannerevento,
  ADD COLUMN dsmapaingressos VARCHAR(255) NULL AFTER urlmapaingressos;

CREATE TABLE eventosetor (
  eventosetor_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  evento_id BIGINT NOT NULL,
  nmsetor VARCHAR(100) NOT NULL,
  dssetor VARCHAR(255) NULL,
  qtcapacidade INT NOT NULL,
  nrordem INT NOT NULL DEFAULT 1,
  sitsetor VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_eventosetor_nome (evento_id, nmsetor),
  INDEX idx_eventosetor_evento (evento_id, sitsetor, nrordem),
  CONSTRAINT fk_eventosetor_evento FOREIGN KEY (evento_id)
    REFERENCES evento(evento_id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_eventosetor_loja FOREIGN KEY (loja_id)
    REFERENCES loja(loja_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CHECK (qtcapacidade > 0),
  CHECK (nrordem > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE eventolote
  ADD COLUMN eventosetor_id BIGINT NULL AFTER evento_id,
  ADD COLUMN nrlote INT NOT NULL DEFAULT 1 AFTER eventosetor_id,
  ADD COLUMN tipoingresso VARCHAR(15) NOT NULL DEFAULT 'UNICO' AFTER nrlote,
  ADD INDEX idx_eventolote_setor (eventosetor_id, nrlote, tipoingresso),
  ADD CONSTRAINT fk_eventolote_setor FOREIGN KEY (eventosetor_id)
    REFERENCES eventosetor(eventosetor_id) ON DELETE RESTRICT ON UPDATE CASCADE;
