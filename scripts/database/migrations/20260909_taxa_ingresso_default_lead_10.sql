ALTER TABLE leadestabelecimento
  MODIFY COLUMN vrtaxaing DECIMAL(10,2) NOT NULL DEFAULT 10.00;

ALTER TABLE leadestabelecimentocontrato
  MODIFY COLUMN vrtaxaing DECIMAL(10,2) NOT NULL DEFAULT 10.00;

UPDATE leadestabelecimento le
LEFT JOIN leadestabelecimentocontrato lc
  ON lc.leadestabelecimento_id = le.leadestabelecimento_id
SET le.vrtaxaing = 10.00
WHERE lc.leadestabelecimentocontrato_id IS NULL
  AND le.vrtaxaing = 5.00;
