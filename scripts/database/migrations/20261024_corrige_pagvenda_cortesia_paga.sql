-- Cortesias confirmadas são pagamentos internos de valor zero. Esta migração
-- também é executada de forma idempotente na inicialização da API.
UPDATE pagvenda AS pag
INNER JOIN venda AS venda ON venda.venda_id = pag.venda_id
SET pag.dsmetodopag = 'CORTESIA',
    pag.provedor = 'CORTESIA',
    pag.vrpagvenda = 0.00,
    pag.sitpagvenda = 'PAGO',
    pag.idtransacaopagvenda = COALESCE(
        NULLIF(pag.idtransacaopagvenda, ''),
        CONCAT('CORTESIA-', pag.venda_id)
    ),
    pag.dtconftranspagvenda = COALESCE(
        pag.dtconftranspagvenda,
        venda.dtultatu,
        venda.dtcriacao,
        NOW()
    )
WHERE venda.sitvenda = 'PAGA'
  AND COALESCE(venda.totalvenda, 0) = 0
  AND (
    UPPER(COALESCE(pag.dsmetodopag, '')) = 'CORTESIA'
    OR UPPER(COALESCE(pag.provedor, '')) = 'CORTESIA'
  );
