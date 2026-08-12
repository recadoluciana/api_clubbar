ALTER TABLE cliente
  ADD COLUMN cliente_padrao CHAR(1) NOT NULL DEFAULT 'N' AFTER emailconf,
  ADD CONSTRAINT chk_cliente_padrao CHECK (cliente_padrao IN ('S', 'N'));

UPDATE cliente
SET cliente_padrao = 'S',
    nmcliente = 'Consumidor nao identificado'
WHERE emailcliente = 'clubbar_caixa@clubbar.app';

INSERT INTO cliente (
  nmcliente,
  emailcliente,
  senhahashcli,
  sitcliente,
  emailconf,
  cliente_padrao
)
SELECT
  'Consumidor nao identificado',
  'consumidor.nao.identificado@clubbar.app',
  UUID(),
  'ATIVO',
  'S',
  'S'
WHERE NOT EXISTS (
  SELECT 1 FROM cliente WHERE cliente_padrao = 'S'
);

ALTER TABLE carrinho
  ADD COLUMN usuario_id BIGINT NULL AFTER cliente_id,
  ADD CONSTRAINT fk_carrinho_usuario
    FOREIGN KEY (usuario_id) REFERENCES usuario(usuario_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  ADD INDEX idx_carrinho_usuario (usuario_id);

ALTER TABLE venda
  ADD COLUMN usuario_id BIGINT NULL AFTER cliente_id,
  ADD CONSTRAINT fk_venda_usuario
    FOREIGN KEY (usuario_id) REFERENCES usuario(usuario_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  ADD INDEX idx_venda_usuario_data (usuario_id, dtcriacao);

ALTER TABLE usuario
  MODIFY COLUMN dscargo ENUM(
    'ADMIN',
    'GERENTE',
    'CAIXA',
    'TOTEM',
    'BARMAN',
    'GARCOM',
    'PORTEIRO',
    'SUPERADMIN'
  ) NOT NULL DEFAULT 'BARMAN';
