UPDATE leadestabelecimento le
JOIN (
    SELECT c.leadestabelecimento_id, MAX(c.leadestabelecimentocontrato_id) AS contrato_id
    FROM leadestabelecimentocontrato c
    WHERE c.tipoinstrumento = 'ORIGINAL'
      AND c.status = 'ACEITO'
    GROUP BY c.leadestabelecimento_id
) ultimo ON ultimo.leadestabelecimento_id = le.leadestabelecimento_id
JOIN leadestabelecimentocontrato contrato
  ON contrato.leadestabelecimentocontrato_id = ultimo.contrato_id
SET le.status = 'ACEITOU_PARCERIA',
    le.dtaceite = COALESCE(le.dtaceite, contrato.dtaceite)
WHERE le.status NOT IN ('ACEITOU_PARCERIA', 'CONVERTIDO', 'RECUSOU_PARCERIA');
