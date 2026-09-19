ALTER TABLE taxapadrao
  MODIFY COLUMN vrtaxaminimaingresso DECIMAL(10,2) NOT NULL DEFAULT 2.99;

ALTER TABLE leadestabelecimento
  MODIFY COLUMN vrtaxaminimaingresso DECIMAL(10,2) NOT NULL DEFAULT 2.99;

ALTER TABLE leadestabelecimentocontrato
  MODIFY COLUMN vrtaxaminimaingresso DECIMAL(10,2) NOT NULL DEFAULT 2.99;

ALTER TABLE loja
  MODIFY COLUMN vrtaxaminimaingresso DECIMAL(10,2) NOT NULL DEFAULT 2.99;

UPDATE leadestabelecimento estabelecimento
JOIN (
  SELECT contrato.leadestabelecimento_id,
         contrato.vrtaxaprod,
         contrato.vrtaxaing,
         contrato.vrtaxaminimaingresso
  FROM leadestabelecimentocontrato contrato
  JOIN (
    SELECT leadestabelecimento_id,
           MAX(leadestabelecimentocontrato_id) AS contrato_id
    FROM leadestabelecimentocontrato
    WHERE tipoinstrumento = 'ORIGINAL'
      AND status IN ('RASCUNHO', 'ENVIADO', 'ACEITO')
    GROUP BY leadestabelecimento_id
  ) ultimo
    ON ultimo.contrato_id = contrato.leadestabelecimentocontrato_id
) contrato_vigente
  ON contrato_vigente.leadestabelecimento_id = estabelecimento.leadestabelecimento_id
SET estabelecimento.vrtaxaprod = contrato_vigente.vrtaxaprod,
    estabelecimento.vrtaxaing = contrato_vigente.vrtaxaing,
    estabelecimento.vrtaxaminimaingresso = contrato_vigente.vrtaxaminimaingresso;

UPDATE leadestabelecimento estabelecimento
JOIN taxapadrao taxa
  ON taxa.sittaxapadrao = 'VIGENTE'
LEFT JOIN leadestabelecimentocontrato contrato
  ON contrato.leadestabelecimento_id = estabelecimento.leadestabelecimento_id
SET estabelecimento.vrtaxaprod = taxa.pctaxaproduto,
    estabelecimento.vrtaxaing = taxa.pctaxaingresso,
    estabelecimento.vrtaxaminimaingresso = taxa.vrtaxaminimaingresso
WHERE contrato.leadestabelecimentocontrato_id IS NULL;

UPDATE loja
JOIN leadestabelecimento
  ON leadestabelecimento.leadestabelecimento_id = loja.leadestabelecimento_id
SET loja.vrtaxaprod = leadestabelecimento.vrtaxaprod,
    loja.vrtaxaing = leadestabelecimento.vrtaxaing,
    loja.vrtaxaminimaingresso = leadestabelecimento.vrtaxaminimaingresso;
