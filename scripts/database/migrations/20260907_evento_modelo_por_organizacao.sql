-- Eventos padrão pertencem à organização e podem ser usados em qualquer loja.
ALTER TABLE eventomodelo ADD INDEX idx_eventomodelo_org_status (organizacao_id, statusevento);
ALTER TABLE eventomodelo DROP FOREIGN KEY eventomodelo_ibfk_2;
ALTER TABLE eventomodelo DROP INDEX idx_eventomodelo_org_loja_status;
ALTER TABLE eventomodelo DROP COLUMN loja_id;
