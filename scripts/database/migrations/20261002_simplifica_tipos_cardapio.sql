-- Simplifica os cardápios para PRINCIPAL e ESPECIAL e garante, no banco,
-- no máximo um principal por organização e por estabelecimento.

UPDATE cardapiomodelo
SET tipocardapio = 'ESPECIAL'
WHERE tipocardapio IN ('SAZONAL', 'EVENTO');

UPDATE cardapio
SET tipocardapio = 'ESPECIAL'
WHERE tipocardapio IN ('SAZONAL', 'EVENTO');

UPDATE cardapiomodelo cm
JOIN (
  SELECT organizacao_id, MIN(cardapiomodelo_id) AS principal_id
  FROM cardapiomodelo
  WHERE tipocardapio = 'PRINCIPAL'
  GROUP BY organizacao_id
) escolhido ON escolhido.organizacao_id = cm.organizacao_id
SET cm.tipocardapio = 'ESPECIAL'
WHERE cm.tipocardapio = 'PRINCIPAL'
  AND cm.cardapiomodelo_id <> escolhido.principal_id;

UPDATE cardapio c
JOIN (
  SELECT loja_id, MIN(cardapio_id) AS principal_id
  FROM cardapio
  WHERE tipocardapio = 'PRINCIPAL'
  GROUP BY loja_id
) escolhido ON escolhido.loja_id = c.loja_id
SET c.tipocardapio = 'ESPECIAL'
WHERE c.tipocardapio = 'PRINCIPAL'
  AND c.cardapio_id <> escolhido.principal_id;

ALTER TABLE cardapiomodelo
  MODIFY COLUMN tipocardapio ENUM('PRINCIPAL','ESPECIAL') NOT NULL DEFAULT 'PRINCIPAL',
  ADD COLUMN principal_organizacao_id BIGINT GENERATED ALWAYS AS (
    CASE WHEN tipocardapio = 'PRINCIPAL' THEN organizacao_id ELSE NULL END
  ) STORED,
  ADD UNIQUE KEY uk_cardapiomodelo_principal_org (principal_organizacao_id);

ALTER TABLE cardapio
  MODIFY COLUMN tipocardapio ENUM('PRINCIPAL','ESPECIAL') NOT NULL DEFAULT 'PRINCIPAL',
  ADD COLUMN principal_loja_id BIGINT GENERATED ALWAYS AS (
    CASE WHEN tipocardapio = 'PRINCIPAL' THEN loja_id ELSE NULL END
  ) STORED,
  ADD UNIQUE KEY uk_cardapio_principal_loja (principal_loja_id);
