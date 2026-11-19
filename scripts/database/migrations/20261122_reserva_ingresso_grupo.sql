ALTER TABLE reserva_ingresso ADD COLUMN grupo_reserva_id VARCHAR(36) NULL;
CREATE INDEX ix_reserva_ingresso_grupo_reserva_id ON reserva_ingresso (grupo_reserva_id);
