-- Sincroniza somente lojas originadas de estabelecimentos convertidos.
-- O operador <=> compara valores NULL corretamente no MySQL.
UPDATE loja s
JOIN leadestabelecimento e ON e.leadestabelecimento_id = s.leadestabelecimento_id
SET s.endloja = e.endereco,
    s.nrceploja = e.cep,
    s.nrendeloja = e.numero,
    s.complementoloja = e.complemento,
    s.dsbairroloja = e.bairro,
    s.estado_id = e.estado_id,
    s.cidade_id = e.cidade_id
WHERE e.status = 'CONVERTIDO'
  AND NOT (
    s.endloja <=> e.endereco
    AND s.nrceploja <=> e.cep
    AND s.nrendeloja <=> e.numero
    AND s.complementoloja <=> e.complemento
    AND s.dsbairroloja <=> e.bairro
    AND s.estado_id <=> e.estado_id
    AND s.cidade_id <=> e.cidade_id
  );
