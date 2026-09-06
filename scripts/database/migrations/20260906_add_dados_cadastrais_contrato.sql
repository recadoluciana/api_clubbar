ALTER TABLE leadestabelecimentocontrato
  ADD COLUMN tipopessoa VARCHAR(2) NULL AFTER vrimplantacao,
  ADD COLUMN cpfcnpjcontratante VARCHAR(14) NULL AFTER tipopessoa,
  ADD COLUMN nmrazaosocial VARCHAR(160) NULL AFTER cpfcnpjcontratante,
  ADD COLUMN cepcontratante VARCHAR(9) NULL AFTER nmrazaosocial,
  ADD COLUMN enderecocontratante VARCHAR(255) NULL AFTER cepcontratante,
  ADD COLUMN numerocontratante VARCHAR(20) NULL AFTER enderecocontratante,
  ADD COLUMN complementocontratante VARCHAR(120) NULL AFTER numerocontratante,
  ADD COLUMN bairrocontratante VARCHAR(120) NULL AFTER complementocontratante,
  ADD COLUMN estado_id_contratante BIGINT NULL AFTER bairrocontratante,
  ADD COLUMN cidade_id_contratante BIGINT NULL AFTER estado_id_contratante;

UPDATE leadestabelecimentocontrato c
JOIN leadestabelecimento e ON e.leadestabelecimento_id = c.leadestabelecimento_id
SET c.tipopessoa = CASE WHEN CHAR_LENGTH(REGEXP_REPLACE(COALESCE(e.cpfcnpj, ''), '[^0-9]', '')) = 14 THEN 'PJ' WHEN CHAR_LENGTH(REGEXP_REPLACE(COALESCE(e.cpfcnpj, ''), '[^0-9]', '')) = 11 THEN 'PF' ELSE NULL END,
    c.cpfcnpjcontratante = NULLIF(REGEXP_REPLACE(COALESCE(e.cpfcnpj, ''), '[^0-9]', ''), ''),
    c.nmrazaosocial = CASE WHEN CHAR_LENGTH(REGEXP_REPLACE(COALESCE(e.cpfcnpj, ''), '[^0-9]', '')) = 11 THEN COALESCE(NULLIF(e.nmresponsavel, ''), e.nmestabelecimento) ELSE NULL END,
    c.cepcontratante = e.cep,
    c.enderecocontratante = e.endereco,
    c.numerocontratante = e.numero,
    c.complementocontratante = e.complemento,
    c.bairrocontratante = e.bairro,
    c.estado_id_contratante = e.estado_id,
    c.cidade_id_contratante = e.cidade_id
WHERE c.cpfcnpjcontratante IS NULL;
