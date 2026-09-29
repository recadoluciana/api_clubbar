-- Remove a funcionalidade de publicações do conteúdo do estabelecimento.
-- Execute uma única vez em cada banco MySQL existente.
UPDATE lojaconteudo
SET configuracoes = JSON_REMOVE(configuracoes, '$.mostrar_publicacoes')
WHERE configuracoes IS NOT NULL
  AND JSON_CONTAINS_PATH(configuracoes, 'one', '$.mostrar_publicacoes');

ALTER TABLE lojaconteudo DROP COLUMN publicacoes;
