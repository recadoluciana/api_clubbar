RENAME TABLE contratolead TO leadestabelecimentocontrato;

ALTER TABLE leadestabelecimentocontrato
  CHANGE COLUMN contratolead_id leadestabelecimentocontrato_id BIGINT NOT NULL AUTO_INCREMENT,
  CHANGE COLUMN urlcontrato conteudocontrato TEXT NULL,
  ADD COLUMN dtdisponibilizacao DATETIME NULL AFTER dtaceite;

UPDATE leadestabelecimentocontrato
SET conteudocontrato = CONCAT(
  'Contrato legado. O documento originalmente disponibilizado estava em: ',
  conteudocontrato
)
WHERE conteudocontrato IS NOT NULL
  AND TRIM(conteudocontrato) <> '';

UPDATE leadestabelecimentocontrato
SET conteudocontrato = 'Contrato legado sem conteúdo textual disponível.'
WHERE conteudocontrato IS NULL
   OR TRIM(conteudocontrato) = '';

UPDATE leadestabelecimentocontrato
SET dtdisponibilizacao = dtcriacao
WHERE dtdisponibilizacao IS NULL
  AND status <> 'RASCUNHO';

ALTER TABLE leadestabelecimentocontrato
  MODIFY COLUMN conteudocontrato TEXT NOT NULL;

