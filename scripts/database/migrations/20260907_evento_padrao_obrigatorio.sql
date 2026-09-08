-- Toda ocorrência da agenda deve nascer de um evento padrão.
-- A remodelagem anterior já removeu os eventos legados sem origem.
ALTER TABLE evento
  MODIFY COLUMN eventomodelo_id BIGINT NOT NULL;
