ALTER TABLE loja
  ADD COLUMN complementoloja VARCHAR(120) NULL AFTER nrendeloja;

UPDATE loja s
JOIN leadestabelecimento e ON e.leadestabelecimento_id = s.leadestabelecimento_id
SET s.complementoloja = e.complemento
WHERE s.complementoloja IS NULL
  AND e.complemento IS NOT NULL
  AND TRIM(e.complemento) <> '';
