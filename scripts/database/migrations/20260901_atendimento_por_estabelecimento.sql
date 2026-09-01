ALTER TABLE leadestabelecimento
  ADD COLUMN nmresponsavel VARCHAR(120) NULL AFTER nmestabelecimento,
  ADD COLUMN telefone_responsavel VARCHAR(30) NULL AFTER nmresponsavel,
  ADD COLUMN email_responsavel VARCHAR(160) NULL AFTER telefone_responsavel;

UPDATE leadestabelecimento e
JOIN leadparceiro p ON p.leadparceiro_id = e.leadparceiro_id
SET e.nmresponsavel = p.nmresponsavel,
    e.telefone_responsavel = p.telefone,
    e.email_responsavel = p.email
WHERE e.nmresponsavel IS NULL;

ALTER TABLE leadmensagem
  ADD COLUMN leadestabelecimento_id BIGINT NULL AFTER leadparceiro_id,
  ADD INDEX idx_leadmensagem_estabelecimento (leadestabelecimento_id),
  ADD CONSTRAINT fk_leadmensagem_estabelecimento
    FOREIGN KEY (leadestabelecimento_id) REFERENCES leadestabelecimento (leadestabelecimento_id);

ALTER TABLE leadagendamento
  ADD COLUMN leadestabelecimento_id BIGINT NULL AFTER leadparceiro_id,
  ADD INDEX idx_leadagendamento_estabelecimento (leadestabelecimento_id),
  ADD CONSTRAINT fk_leadagendamento_estabelecimento
    FOREIGN KEY (leadestabelecimento_id) REFERENCES leadestabelecimento (leadestabelecimento_id);

ALTER TABLE leadmaterial
  ADD COLUMN leadestabelecimento_id BIGINT NULL AFTER leadparceiro_id,
  ADD INDEX idx_leadmaterial_estabelecimento (leadestabelecimento_id),
  ADD CONSTRAINT fk_leadmaterial_estabelecimento
    FOREIGN KEY (leadestabelecimento_id) REFERENCES leadestabelecimento (leadestabelecimento_id);

UPDATE leadmensagem item
JOIN (
  SELECT leadparceiro_id, MIN(leadestabelecimento_id) AS leadestabelecimento_id
  FROM leadestabelecimento
  GROUP BY leadparceiro_id
) unico ON unico.leadparceiro_id = item.leadparceiro_id
SET item.leadestabelecimento_id = unico.leadestabelecimento_id;

UPDATE leadagendamento item
JOIN (
  SELECT leadparceiro_id, MIN(leadestabelecimento_id) AS leadestabelecimento_id
  FROM leadestabelecimento
  GROUP BY leadparceiro_id
) unico ON unico.leadparceiro_id = item.leadparceiro_id
SET item.leadestabelecimento_id = unico.leadestabelecimento_id;

UPDATE leadmaterial item
JOIN (
  SELECT leadparceiro_id, MIN(leadestabelecimento_id) AS leadestabelecimento_id
  FROM leadestabelecimento
  GROUP BY leadparceiro_id
) unico ON unico.leadparceiro_id = item.leadparceiro_id
SET item.leadestabelecimento_id = unico.leadestabelecimento_id;

ALTER TABLE leadmensagem MODIFY leadestabelecimento_id BIGINT NOT NULL;
ALTER TABLE leadagendamento MODIFY leadestabelecimento_id BIGINT NOT NULL;
ALTER TABLE leadmaterial MODIFY leadestabelecimento_id BIGINT NOT NULL;
