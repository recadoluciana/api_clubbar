-- Usa o nome da empresa cadastrado no lead para organizações originadas de conversão.
UPDATE organizacao o
JOIN leadparceiro l ON l.leadparceiro_id = o.leadparceiro_id
SET o.nmorganizacao = TRIM(l.nmorganizacao)
WHERE l.nmorganizacao IS NOT NULL
  AND TRIM(l.nmorganizacao) <> ''
  AND CHAR_LENGTH(TRIM(l.nmorganizacao)) <= 120
  AND o.nmorganizacao <> TRIM(l.nmorganizacao);

-- Usa o nome do estabelecimento de origem para lojas já convertidas.
UPDATE loja s
JOIN leadestabelecimento e ON e.leadestabelecimento_id = s.leadestabelecimento_id
SET s.nmloja = TRIM(e.nmestabelecimento)
WHERE e.status = 'CONVERTIDO'
  AND TRIM(e.nmestabelecimento) <> ''
  AND CHAR_LENGTH(TRIM(e.nmestabelecimento)) <= 120
  AND s.nmloja <> TRIM(e.nmestabelecimento);
