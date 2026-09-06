CREATE TABLE IF NOT EXISTS contratopadrao (
  contratopadrao_id BIGINT NOT NULL AUTO_INCREMENT,
  versao VARCHAR(30) NOT NULL,
  titulo VARCHAR(160) NOT NULL,
  conteudomodelo LONGTEXT NOT NULL,
  vrimplantacao DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  sitcontrato VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  operador_id BIGINT NULL,
  dtvigencia DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (contratopadrao_id),
  UNIQUE KEY uk_contratopadrao_versao (versao),
  KEY idx_contratopadrao_situacao (sitcontrato),
  CONSTRAINT ck_contratopadrao_situacao CHECK (sitcontrato IN ('ATIVO','INATIVO'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @coluna_contratopadrao = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'leadestabelecimentocontrato'
    AND COLUMN_NAME = 'contratopadrao_id'
);
SET @sql_contratopadrao = IF(
  @coluna_contratopadrao = 0,
  'ALTER TABLE leadestabelecimentocontrato ADD COLUMN contratopadrao_id BIGINT NULL AFTER titularfinanceiro_id, ADD INDEX idx_leadcontrato_padrao (contratopadrao_id), ADD CONSTRAINT fk_leadcontrato_padrao FOREIGN KEY (contratopadrao_id) REFERENCES contratopadrao(contratopadrao_id) ON DELETE RESTRICT ON UPDATE CASCADE',
  'SELECT 1'
);
PREPARE stmt_contratopadrao FROM @sql_contratopadrao;
EXECUTE stmt_contratopadrao;
DEALLOCATE PREPARE stmt_contratopadrao;
