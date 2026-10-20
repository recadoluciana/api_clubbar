-- Atualiza o catálogo padrão sem alterar os códigos internos nem os registros históricos.
UPDATE modalidadeingresso
SET nmmodalidade = 'Meia-entrada (idosos, professores e outros)'
WHERE cdmodalidade = 'MEIA_IDOSO';

UPDATE modalidadeingresso
SET nmmodalidade = 'Meia-entrada (estudantes, PCD e jovens de baixa renda)'
WHERE cdmodalidade = 'MEIA_LEGAL';

UPDATE beneficioingresso
SET nmbeneficio = 'Meia-entrada (idosos, professores e outros)'
WHERE cdbeneficio = 'IDOSO';

-- Os lotes já publicados guardam uma cópia do nome da modalidade.
-- Não altera snapshots de vendas e ingressos já emitidos.
UPDATE eventolotesetorpreco
SET nmpreco = 'Meia-entrada (idosos, professores e outros)'
WHERE tipopreco = 'MEIA_IDOSO' AND nmpreco = 'Pessoa idosa';

UPDATE eventolotesetorpreco
SET nmpreco = 'Meia-entrada (estudantes, PCD e jovens de baixa renda)'
WHERE tipopreco = 'MEIA_LEGAL' AND nmpreco = 'Meia-entrada';
