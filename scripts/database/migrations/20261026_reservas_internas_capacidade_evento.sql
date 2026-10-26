ALTER TABLE evento
  ADD COLUMN qtreservainterna INT NOT NULL DEFAULT 0 AFTER qtcapacidadeevento;

UPDATE evento e
LEFT JOIN (
  SELECT evento_id, SUM(qtcapacidade) AS capacidade_setores
  FROM eventosetor
  WHERE sitsetor = 'ATIVO'
  GROUP BY evento_id
) setores ON setores.evento_id = e.evento_id
SET e.qtcapacidadeevento = GREATEST(
      COALESCE(e.qtcapacidadeevento, 0),
      COALESCE(setores.capacidade_setores, 0)
    ),
    e.qtreservainterna = GREATEST(
      GREATEST(COALESCE(e.qtcapacidadeevento, 0), COALESCE(setores.capacidade_setores, 0))
      - COALESCE(setores.capacidade_setores, 0),
      0
    )
WHERE COALESCE(e.qtcapacidadeevento, 0) > 0
   OR COALESCE(setores.capacidade_setores, 0) > 0;
