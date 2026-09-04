ALTER TABLE atracao
  ADD COLUMN dsatracao TEXT NULL AFTER dsestilomusical;

UPDATE atracao AS a
INNER JOIN atracaodescricao AS d
  ON d.atracao_id = a.atracao_id
SET a.dsatracao = d.dsatracao
WHERE d.dsatracao IS NOT NULL
  AND TRIM(d.dsatracao) <> '';

UPDATE atracao
SET dsatracao = CONCAT(
  nmatracao,
  ' apresenta um repertório envolvente e uma experiência especial para o público do evento.'
)
WHERE dsatracao IS NULL
   OR TRIM(dsatracao) = '';

DROP TABLE atracaodescricao;
