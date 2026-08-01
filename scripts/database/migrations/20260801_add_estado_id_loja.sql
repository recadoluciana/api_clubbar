ALTER TABLE loja
  ADD COLUMN estado_id BIGINT NULL AFTER nrdiavalidade;

UPDATE loja AS l
JOIN cidade AS c ON c.cidade_id = l.cidade_id
SET l.estado_id = c.estado_id;

ALTER TABLE loja
  MODIFY COLUMN estado_id BIGINT NOT NULL,
  ADD INDEX idx_loja_estado (estado_id),
  ADD CONSTRAINT fk_loja_estado
    FOREIGN KEY (estado_id) REFERENCES estado(estado_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;
