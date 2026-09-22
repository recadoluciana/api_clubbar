CREATE TABLE IF NOT EXISTS politicacompra (
  politicacompra_id BIGINT NOT NULL AUTO_INCREMENT,
  versao VARCHAR(30) NOT NULL,
  titulo VARCHAR(160) NOT NULL,
  conteudo TEXT NOT NULL,
  sitpolitica VARCHAR(20) NOT NULL DEFAULT 'VIGENTE',
  operador_id BIGINT NULL,
  dtiniciovigencia DATETIME NULL,
  dtfimvigencia DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (politicacompra_id),
  UNIQUE KEY uq_politicacompra_versao (versao),
  KEY ix_politicacompra_situacao (sitpolitica),
  CONSTRAINT fk_politicacompra_operador FOREIGN KEY (operador_id) REFERENCES operador(operador_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO politicacompra (versao, titulo, conteudo, sitpolitica, dtiniciovigencia)
SELECT
  '1.0',
  'Política de Compra Clubbar',
  'Ao realizar uma compra pelo Clubbar, o cliente declara estar ciente das condições de uso, retirada, consumo e validade dos produtos e ingressos adquiridos.\n\nCancelamentos seguem a legislação aplicável e as condições apresentadas pelo estabelecimento e pelo evento. Itens já utilizados, retirados ou consumidos não podem ser cancelados.\n\nPara ingressos, a identificação do participante deve estar correta e poderá ser alterada apenas conforme as regras divulgadas para o evento.',
  'VIGENTE',
  CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM politicacompra WHERE sitpolitica = 'VIGENTE');
