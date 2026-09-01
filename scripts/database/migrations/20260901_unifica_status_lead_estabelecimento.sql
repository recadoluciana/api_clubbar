-- Consolida decisao no status do estabelecimento antes de remover duplicidades.
UPDATE leadestabelecimento
SET status = CASE
  WHEN status = 'CONVERTIDO' THEN 'CONVERTIDO'
  WHEN decisao = 'ACEITOU' THEN 'ACEITOU_PARCERIA'
  WHEN decisao = 'RECUSOU' THEN 'RECUSOU_PARCERIA'
  WHEN decisao = 'ANALISANDO' THEN 'NEGOCIANDO'
  ELSE status
END;

ALTER TABLE leadestabelecimento
  DROP COLUMN decisao;

ALTER TABLE leadparceiro
  DROP INDEX idx_leadparceiro_status,
  DROP COLUMN status;
