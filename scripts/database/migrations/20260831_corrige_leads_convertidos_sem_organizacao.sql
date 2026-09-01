-- Reabre conversoes incompletas. Uma conversao valida sempre cria a organizacao
-- na mesma transacao que altera os status do lead e do estabelecimento.
UPDATE leadestabelecimento e
SET e.status = 'ACEITOU_PARCERIA',
    e.dtconversao = NULL
WHERE e.status = 'CONVERTIDO'
  AND NOT EXISTS (
    SELECT 1
    FROM organizacao o
    WHERE o.leadparceiro_id = e.leadparceiro_id
  );

UPDATE leadparceiro l
SET l.status = CASE
  WHEN EXISTS (
    SELECT 1 FROM leadestabelecimento e
    WHERE e.leadparceiro_id = l.leadparceiro_id
      AND e.status = 'ACEITOU_PARCERIA'
  ) THEN 'ACEITOU_PARCERIA'
  WHEN EXISTS (
    SELECT 1 FROM leadestabelecimento e
    WHERE e.leadparceiro_id = l.leadparceiro_id
      AND e.status = 'NEGOCIANDO'
  ) THEN 'NEGOCIANDO'
  WHEN EXISTS (
    SELECT 1 FROM leadestabelecimento e
    WHERE e.leadparceiro_id = l.leadparceiro_id
      AND e.status = 'CONTATADO'
  ) THEN 'CONTATADO'
  WHEN EXISTS (
    SELECT 1 FROM leadestabelecimento e
    WHERE e.leadparceiro_id = l.leadparceiro_id
      AND e.status = 'NOVO'
  ) THEN 'NOVO'
  ELSE 'RECUSOU_PARCERIA'
END
WHERE l.status = 'CONVERTIDO'
  AND NOT EXISTS (
    SELECT 1
    FROM organizacao o
    WHERE o.leadparceiro_id = l.leadparceiro_id
  );
