-- Localidade de entrega normalizada pelos cadastros oficiais de cidade/estado.
ALTER TABLE pedidoentrega
  ADD COLUMN cidade_id BIGINT NULL AFTER bairroentrega,
  ADD COLUMN estado_id BIGINT NULL AFTER cidade_id;

-- Resolve primeiro a UF e as cidades que já estejam gravadas por nome,
-- código IBGE ou identificador válido do cadastro local.
UPDATE pedidoentrega pe
LEFT JOIN estado e ON UPPER(e.sgestado) = UPPER(pe.ufentrega)
SET pe.estado_id = e.estado_id
WHERE pe.estado_id IS NULL;

UPDATE pedidoentrega pe
JOIN cidade c ON c.estado_id = pe.estado_id
SET pe.cidade_id = c.cidade_id
WHERE pe.cidade_id IS NULL
  AND (
    LOWER(c.nmcidade) = LOWER(pe.cidadeentrega)
    OR c.cidade_id = CAST(pe.cidadeentrega AS UNSIGNED)
    OR c.cdibgecid = CAST(pe.cidadeentrega AS UNSIGNED)
  );

-- Fallback seguro para dados legados que continham um código de cidade não
-- pertencente ao cadastro Clubbar: usa a localidade do estabelecimento da venda.
UPDATE pedidoentrega pe
JOIN venda v ON v.venda_id = pe.venda_id
JOIN loja l ON l.loja_id = v.loja_id
SET pe.estado_id = COALESCE(pe.estado_id, l.estado_id),
    pe.cidade_id = COALESCE(pe.cidade_id, l.cidade_id)
WHERE pe.estado_id IS NULL OR pe.cidade_id IS NULL;

ALTER TABLE pedidoentrega
  MODIFY COLUMN cidade_id BIGINT NOT NULL,
  MODIFY COLUMN estado_id BIGINT NOT NULL,
  ADD CONSTRAINT fk_pedidoentrega_cidade
    FOREIGN KEY (cidade_id) REFERENCES cidade(cidade_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  ADD CONSTRAINT fk_pedidoentrega_estado
    FOREIGN KEY (estado_id) REFERENCES estado(estado_id)
    ON DELETE RESTRICT ON UPDATE CASCADE;
