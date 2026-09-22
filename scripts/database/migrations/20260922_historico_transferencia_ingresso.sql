-- Auditoria e adequação da transferência gratuita de ingressos.
CREATE TABLE IF NOT EXISTS itvendaparticipantehistorico (
    historico_id BIGINT NOT NULL AUTO_INCREMENT,
    itvenda_id BIGINT NOT NULL,
    cliente_id BIGINT NOT NULL,
    nmparticipanteanterior VARCHAR(150) NULL,
    cpfparticipanteanterior VARCHAR(11) NULL,
    nmparticipantenovo VARCHAR(150) NOT NULL,
    cpfparticipantenovo VARCHAR(11) NOT NULL,
    tipopreco VARCHAR(30) NULL,
    tipobeneficio VARCHAR(30) NULL,
    confirmoumeiaentrada BOOLEAN NOT NULL DEFAULT FALSE,
    dttransferencia DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (historico_id),
    INDEX ix_itvendaparticipantehistorico_itvenda (itvenda_id),
    INDEX ix_itvendaparticipantehistorico_cliente (cliente_id),
    CONSTRAINT fk_itvendaparticipantehistorico_itvenda
        FOREIGN KEY (itvenda_id) REFERENCES itvenda(itvenda_id),
    CONSTRAINT fk_itvendaparticipantehistorico_cliente
        FOREIGN KEY (cliente_id) REFERENCES cliente(cliente_id)
);

-- Esta chave deixava uma obrigação legal como escolha da loja.
UPDATE lojapoliticaingresso
SET configuracoes = JSON_REMOVE(configuracoes, '$.permite_transferencia')
WHERE configuracoes IS NOT NULL
  AND JSON_CONTAINS_PATH(configuracoes, 'one', '$.permite_transferencia');
