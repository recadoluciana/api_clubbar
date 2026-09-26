-- Lotação autorizada da ocorrência na agenda. Não pertence ao evento padrão.
ALTER TABLE evento
  ADD COLUMN qtcapacidadeevento INT NULL AFTER dtfimevento,
  ADD CONSTRAINT chk_evento_capacidade CHECK (
    qtcapacidadeevento IS NULL OR qtcapacidadeevento > 0
  );

-- Eventos já possuem seus setores cadastrados. Usa essa soma como ponto de
-- partida, preservando a lotação hoje efetivamente configurada para cada data.
UPDATE evento e
LEFT JOIN (
  SELECT evento_id, SUM(qtcapacidade) AS capacidade_setores
  FROM eventosetor
  WHERE sitsetor = 'ATIVO'
  GROUP BY evento_id
) s ON s.evento_id = e.evento_id
SET e.qtcapacidadeevento = s.capacidade_setores
WHERE e.qtcapacidadeevento IS NULL
  AND COALESCE(s.capacidade_setores, 0) > 0;
