-- A publicação deixa de ser controlada pela agenda inteira. Eventos que já
-- estavam em uma agenda publicada permanecem ativos; os demais voltam ao
-- rascunho até serem publicados individualmente no Clubbar Partner.
UPDATE evento AS evento
INNER JOIN agendamensal AS agenda
  ON agenda.agendamensal_id = evento.agendamensal_id
SET evento.statusevento = 'RASCUNHO'
WHERE evento.statusevento = 'ATIVO'
  AND agenda.statusagenda <> 'PUBLICADA';
