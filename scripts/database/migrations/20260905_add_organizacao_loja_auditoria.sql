ALTER TABLE auditoria
  ADD COLUMN organizacao_id BIGINT NULL AFTER auditoria_id,
  ADD COLUMN loja_id BIGINT NULL AFTER organizacao_id;

UPDATE auditoria a
INNER JOIN usuario u ON u.usuario_id = a.usuario_id
SET a.organizacao_id = u.organizacao_id,
    a.loja_id = u.loja_id
WHERE a.organizacao_id IS NULL;

UPDATE auditoria
SET organizacao_id = COALESCE(
      NULLIF(JSON_UNQUOTE(JSON_EXTRACT(dados_novos, '$.organizacao_id')), 'null'),
      NULLIF(JSON_UNQUOTE(JSON_EXTRACT(dados_anteriores, '$.organizacao_id')), 'null')
    )
WHERE organizacao_id IS NULL
  AND COALESCE(
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(dados_novos, '$.organizacao_id')), 'null'),
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(dados_anteriores, '$.organizacao_id')), 'null')
      ) IS NOT NULL;

UPDATE auditoria
SET loja_id = COALESCE(
      NULLIF(JSON_UNQUOTE(JSON_EXTRACT(dados_novos, '$.loja_id')), 'null'),
      NULLIF(JSON_UNQUOTE(JSON_EXTRACT(dados_anteriores, '$.loja_id')), 'null')
    )
WHERE loja_id IS NULL
  AND COALESCE(
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(dados_novos, '$.loja_id')), 'null'),
        NULLIF(JSON_UNQUOTE(JSON_EXTRACT(dados_anteriores, '$.loja_id')), 'null')
      ) IS NOT NULL;

ALTER TABLE auditoria
  ADD INDEX idx_auditoria_organizacao (organizacao_id, dtcriacao),
  ADD INDEX idx_auditoria_loja (loja_id, dtcriacao),
  ADD CONSTRAINT fk_auditoria_organizacao
    FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT fk_auditoria_loja
    FOREIGN KEY (loja_id) REFERENCES loja(loja_id)
    ON DELETE SET NULL ON UPDATE CASCADE;
