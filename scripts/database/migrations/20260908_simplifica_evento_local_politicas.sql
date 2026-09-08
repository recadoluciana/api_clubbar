ALTER TABLE eventomodelo
  DROP COLUMN dspoliticareembolso,
  DROP COLUMN dspoliticacashback,
  ADD COLUMN tipolocalevento ENUM('ESTABELECIMENTO','OUTRO') NOT NULL DEFAULT 'ESTABELECIMENTO' AFTER dspoliticacancelamento,
  ADD COLUMN nrceplocalevento VARCHAR(9) NULL AFTER tipolocalevento;

ALTER TABLE eventodescricao
  DROP COLUMN dspoliticareembolso,
  DROP COLUMN dspoliticacashback;
