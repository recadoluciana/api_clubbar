-- Não executa DELETE nem altera os horários existentes.
-- Se houver duplicidades, a criação da UNIQUE falhará para que sejam
-- revisadas manualmente, sem perda automática de dados.

SET @schema_atual = DATABASE();

SET @sql_unique = IF(
    EXISTS (
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = @schema_atual
          AND table_name = 'lojahorario'
          AND index_name = 'uq_lojahorario_dia'
    ),
    'SELECT 1',
    'ALTER TABLE lojahorario ADD CONSTRAINT uq_lojahorario_dia UNIQUE (loja_id, diasemana)'
);
PREPARE stmt_unique FROM @sql_unique;
EXECUTE stmt_unique;
DEALLOCATE PREPARE stmt_unique;

SET @sql_check = IF(
    EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_schema = @schema_atual
          AND table_name = 'lojahorario'
          AND constraint_name = 'ck_lojahorario_dia'
          AND constraint_type = 'CHECK'
    ),
    'SELECT 1',
    'ALTER TABLE lojahorario ADD CONSTRAINT ck_lojahorario_dia CHECK (diasemana BETWEEN 1 AND 7)'
);
PREPARE stmt_check FROM @sql_check;
EXECUTE stmt_check;
DEALLOCATE PREPARE stmt_check;

SET @sql_fk = IF(
    EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_schema = @schema_atual
          AND table_name = 'lojahorario'
          AND constraint_name = 'fk_lojahorario_loja'
          AND constraint_type = 'FOREIGN KEY'
    ),
    'SELECT 1',
    'ALTER TABLE lojahorario ADD CONSTRAINT fk_lojahorario_loja FOREIGN KEY (loja_id) REFERENCES loja (loja_id) ON UPDATE CASCADE ON DELETE CASCADE'
);
PREPARE stmt_fk FROM @sql_fk;
EXECUTE stmt_fk;
DEALLOCATE PREPARE stmt_fk;
