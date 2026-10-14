ALTER TABLE reserva_ingresso_participante
  ADD COLUMN beneficio_id BIGINT NULL AFTER cpfparticipante,
  ADD COLUMN tipobeneficio VARCHAR(30) NULL AFTER beneficio_id,
  ADD COLUMN nmbeneficiosnapshot VARCHAR(100) NULL AFTER tipobeneficio,
  ADD CONSTRAINT fk_reserva_participante_beneficio
    FOREIGN KEY (beneficio_id) REFERENCES beneficioingresso(beneficio_id)
    ON DELETE RESTRICT;
