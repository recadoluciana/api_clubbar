ALTER TABLE leadestabelecimento
  DROP CHECK chk_leadestabelecimento_tipo,
  ADD CONSTRAINT chk_leadestabelecimento_tipo CHECK (
    tipo IN ('BAR','CASA_NOTURNA','PRODUTOR_EVENTOS','CASA_EVENTOS','RESTAURANTE','CONVENIENCIA','HAMBURGUERIA','PIZZARIA','LANCHONETE')
  );
