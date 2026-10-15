ALTER TABLE cardapioitem
  ADD COLUMN qtcortesia INT NULL AFTER dtfimdesconto,
  ADD COLUMN dtinicortesia DATETIME NULL AFTER qtcortesia,
  ADD COLUMN dtfimcortesia DATETIME NULL AFTER dtinicortesia;
