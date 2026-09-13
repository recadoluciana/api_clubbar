-- MySQL 8. Execute com a API parada e backup do banco.
-- Preserva conteúdo: versões em espera voltam a rascunho, sem publicação automática.
UPDATE cardapioversao SET statusversao = 'RASCUNHO'
WHERE statusversao = 'AGUARDANDO_ASAAS';

-- O nome do CHECK pode variar conforme a criação do banco.
SET @cardapio_drop_checks = (
  SELECT GROUP_CONCAT(CONCAT('DROP CHECK `', REPLACE(tc.CONSTRAINT_NAME, '`', '``'), '`') SEPARATOR ', ')
  FROM information_schema.TABLE_CONSTRAINTS tc
  JOIN information_schema.CHECK_CONSTRAINTS cc
    ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
    AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
  WHERE tc.CONSTRAINT_SCHEMA = DATABASE()
    AND tc.TABLE_NAME = 'cardapioversao'
    AND tc.CONSTRAINT_TYPE = 'CHECK'
    AND cc.CHECK_CLAUSE LIKE '%publicaraposaprovacao%'
);
SET @cardapio_sql = IF(@cardapio_drop_checks IS NULL, 'SELECT 1',
  CONCAT('ALTER TABLE cardapioversao ', @cardapio_drop_checks));
PREPARE cardapio_stmt FROM @cardapio_sql;
EXECUTE cardapio_stmt;
DEALLOCATE PREPARE cardapio_stmt;

SET @cardapio_sql = IF(
  EXISTS(SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cardapioversao'
      AND COLUMN_NAME = 'publicaraposaprovacao'),
  'ALTER TABLE cardapioversao DROP COLUMN publicaraposaprovacao', 'SELECT 1');
PREPARE cardapio_stmt FROM @cardapio_sql;
EXECUTE cardapio_stmt;
DEALLOCATE PREPARE cardapio_stmt;

ALTER TABLE cardapioversao MODIFY statusversao
  ENUM('RASCUNHO','PROGRAMADA','PUBLICADA','SUBSTITUIDA','CANCELADA')
  NOT NULL DEFAULT 'RASCUNHO';
