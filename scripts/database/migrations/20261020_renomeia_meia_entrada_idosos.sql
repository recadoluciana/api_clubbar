-- Atualiza o catálogo padrão sem alterar os códigos internos nem os registros históricos.
UPDATE modalidadeingresso
SET nmmodalidade = 'Meia-entrada (idosos, professores e outros)'
WHERE cdmodalidade = 'MEIA_IDOSO';

UPDATE beneficioingresso
SET nmbeneficio = 'Meia-entrada (idosos, professores e outros)'
WHERE cdbeneficio = 'IDOSO';
