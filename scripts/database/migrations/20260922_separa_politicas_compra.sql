ALTER TABLE politicacompra
  DROP INDEX versao,
  ADD COLUMN tipopolitica VARCHAR(20) NOT NULL DEFAULT 'INGRESSO' AFTER versao,
  ADD COLUMN qtd_dias_cancelamento INT NULL AFTER conteudo,
  ADD COLUMN qtd_horas_antecedencia_cancelamento INT NULL AFTER qtd_dias_cancelamento,
  ADD COLUMN qtd_alteracoes_participante INT NULL AFTER qtd_horas_antecedencia_cancelamento,
  ADD COLUMN qtd_horas_antecedencia_alteracao INT NULL AFTER qtd_alteracoes_participante,
  ADD UNIQUE KEY uq_politicacompra_tipo_versao (tipopolitica, versao);

UPDATE politicacompra
SET versao = CONCAT('LEGADA-', politicacompra_id),
    tipopolitica = 'INGRESSO',
    sitpolitica = 'ENCERRADA',
    dtfimvigencia = COALESCE(dtfimvigencia, CURRENT_TIMESTAMP)
WHERE tipopolitica = 'INGRESSO';

INSERT INTO politicacompra (
  versao, tipopolitica, titulo, conteudo, qtd_dias_cancelamento,
  qtd_horas_antecedencia_cancelamento, qtd_alteracoes_participante,
  qtd_horas_antecedencia_alteracao, sitpolitica, dtiniciovigencia
) VALUES (
  '1.0', 'INGRESSO', 'Política de compra de ingresso',
  'Texto gerado a partir dos parâmetros da política.', 7, 48, 1, 24,
  'VIGENTE', CURRENT_TIMESTAMP
);

INSERT INTO politicacompra (
  versao, tipopolitica, titulo, conteudo, qtd_dias_cancelamento,
  sitpolitica, dtiniciovigencia
) VALUES (
  '1.0', 'PRODUTO', 'Política de compra de produto',
  'Texto gerado a partir dos parâmetros da política.', 7,
  'VIGENTE', CURRENT_TIMESTAMP
);
