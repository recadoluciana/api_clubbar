-- Guarda a duração planejada para manter o horário final correto quando a
-- ocorrência do evento for deslocada na agenda.
ALTER TABLE eventoatracao
  ADD COLUMN nrminutoduracao INT NULL AFTER dtfimatracao;

UPDATE eventoatracao
SET nrminutoduracao = GREATEST(1, TIMESTAMPDIFF(MINUTE, dtinicioatracao, dtfimatracao))
WHERE nrminutoduracao IS NULL OR nrminutoduracao <= 0;

ALTER TABLE eventoatracao
  MODIFY COLUMN nrminutoduracao INT NOT NULL DEFAULT 120,
  ADD CONSTRAINT chk_eventoatracao_duracao CHECK (nrminutoduracao > 0);
