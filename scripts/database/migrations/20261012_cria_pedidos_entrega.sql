CREATE TABLE IF NOT EXISTS pedidoentrega (
  pedidoentrega_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  venda_id BIGINT NOT NULL,
  situacaopedido ENUM('AGUARDANDO_ACEITE','ACEITO','EM_ROTA','ENTREGUE','RECUSADO','CANCELADO')
    NOT NULL DEFAULT 'AGUARDANDO_ACEITE',
  qrcode_token VARCHAR(120) NOT NULL,
  cepentrega VARCHAR(10) NOT NULL,
  enderecoentrega VARCHAR(255) NOT NULL,
  numeroentrega VARCHAR(20) NOT NULL,
  complementoentrega VARCHAR(120) NULL,
  bairroentrega VARCHAR(120) NOT NULL,
  cidadeentrega VARCHAR(120) NOT NULL,
  ufentrega VARCHAR(2) NOT NULL,
  observacaoentrega VARCHAR(255) NULL,
  dtaceite DATETIME NULL,
  dtdespacho DATETIME NULL,
  dtrecebimento DATETIME NULL,
  dtrecusa DATETIME NULL,
  motivorecusa VARCHAR(255) NULL,
  usuarioaceite_id BIGINT NULL,
  usuariodespacho_id BIGINT NULL,
  usuariorecebimento_id BIGINT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_pedidoentrega_venda (venda_id),
  UNIQUE KEY uq_pedidoentrega_qrcode_token (qrcode_token),
  KEY idx_pedidoentrega_situacao (situacaopedido, dtcriacao),
  CONSTRAINT fk_pedidoentrega_venda FOREIGN KEY (venda_id) REFERENCES venda(venda_id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_pedidoentrega_aceite FOREIGN KEY (usuarioaceite_id) REFERENCES usuario(usuario_id) ON DELETE SET NULL,
  CONSTRAINT fk_pedidoentrega_despacho FOREIGN KEY (usuariodespacho_id) REFERENCES usuario(usuario_id) ON DELETE SET NULL,
  CONSTRAINT fk_pedidoentrega_recebimento FOREIGN KEY (usuariorecebimento_id) REFERENCES usuario(usuario_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE usuario MODIFY COLUMN dscargo ENUM(
  'SUPERADMIN','ADMIN','MANAGER','CASHIER','TOTEM','BARMAN','WAITER','TICKETMAN','MOTOBOY'
) NOT NULL DEFAULT 'BARMAN';
