INSERT INTO cardapiomodelo (organizacao_id, nmcardapio, tipocardapio)
SELECT o.organizacao_id, 'Cardápio padrão', 'PRINCIPAL'
FROM organizacao o
WHERE NOT EXISTS (
  SELECT 1 FROM cardapiomodelo c WHERE c.organizacao_id = o.organizacao_id
);
