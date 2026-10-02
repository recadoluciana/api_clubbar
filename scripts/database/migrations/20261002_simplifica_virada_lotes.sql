-- Lotes passam a representar somente faixas de preço.
-- O primeiro começa quando o evento é publicado e os seguintes viram pela
-- primeira condição atingida: cota comercial ou data limite opcional.
UPDATE eventoloteglobal
SET dtiniciovenda = NULL,
    gatilhovirada = 'HIBRIDO';
