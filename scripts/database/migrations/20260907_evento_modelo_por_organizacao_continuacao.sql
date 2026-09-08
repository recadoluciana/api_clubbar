-- Continuação no desenvolvimento após a remoção isolada da chave estrangeira.
ALTER TABLE eventomodelo ADD INDEX idx_eventomodelo_org_status (organizacao_id, statusevento);
ALTER TABLE eventomodelo DROP INDEX idx_eventomodelo_org_loja_status;
ALTER TABLE eventomodelo DROP COLUMN loja_id;
