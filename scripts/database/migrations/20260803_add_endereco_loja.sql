ALTER TABLE loja
  ADD COLUMN nrceploja VARCHAR(9) NULL AFTER endloja,
  ADD COLUMN nrendeloja VARCHAR(20) NULL AFTER nrceploja;

UPDATE loja AS l
JOIN organizacao AS o
  ON o.organizacao_id = l.organizacao_id
SET
  l.nrceploja = NULLIF(TRIM(o.ceporganizacao), ''),
  l.nrendeloja = NULLIF(TRIM(o.nrendorganizacao), '')
WHERE l.nrceploja IS NULL
   OR l.nrendeloja IS NULL;

-- Mantém a migration aplicável a registros legados cuja organização
-- ainda não possua CEP ou número. Esses casos devem ser revisados depois.
UPDATE loja
SET nrceploja = COALESCE(nrceploja, ''),
    nrendeloja = COALESCE(nrendeloja, 'S/N');

ALTER TABLE loja
  MODIFY COLUMN nrceploja VARCHAR(9) NOT NULL,
  MODIFY COLUMN nrendeloja VARCHAR(20) NOT NULL;
