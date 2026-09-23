-- A programação das atrações padrão passa a ser sequencial por ordem e duração.
ALTER TABLE eventomodeloatracao DROP CHECK chk_eventomodeloatracao_inicio;
ALTER TABLE eventomodeloatracao DROP COLUMN nrminutoinicio;
