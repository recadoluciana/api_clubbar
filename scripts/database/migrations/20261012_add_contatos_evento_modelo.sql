ALTER TABLE eventomodelo
  ADD COLUMN emailcontatoevento VARCHAR(255) NULL AFTER dspoliticacancelamento,
  ADD COLUMN whatsappevento VARCHAR(30) NULL AFTER emailcontatoevento;
