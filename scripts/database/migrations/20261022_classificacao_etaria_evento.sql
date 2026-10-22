ALTER TABLE eventomodelo
    ADD COLUMN classificacaoetaria VARCHAR(80) NOT NULL DEFAULT 'Livre';

ALTER TABLE evento
    ADD COLUMN classificacaoetaria VARCHAR(80) NOT NULL DEFAULT 'Livre';
