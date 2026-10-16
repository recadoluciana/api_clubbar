-- Mantém a primeira vinculação de cada atração no evento padrão e remove
-- duplicidades antigas antes de proteger a regra no banco.
DELETE duplicada
FROM eventomodeloatracao AS duplicada
INNER JOIN eventomodeloatracao AS mantida
  ON mantida.eventomodelo_id = duplicada.eventomodelo_id
 AND mantida.atracao_id = duplicada.atracao_id
 AND mantida.eventomodeloatracao_id < duplicada.eventomodeloatracao_id;

ALTER TABLE eventomodeloatracao
  ADD CONSTRAINT uq_eventomodeloatracao_atracao
  UNIQUE (eventomodelo_id, atracao_id);
