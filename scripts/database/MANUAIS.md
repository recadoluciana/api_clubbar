# Manuais do ecossistema

O Admin apresenta três guias: Negociação e Venda (Clubbar e Lead), Roteiro de
Implantação (Clubbar) e Manual do Parceiro (Parceiro). Cada etapa informa público,
aplicativo, caminho, orientações, resultado esperado e observação opcional.

## Instalação em um ambiente existente

Confirme a conexão do ambiente antes de executar:

```powershell
python scripts/database/apply_sql_file.py scripts/database/migrations/20260909_create_manuais.sql
python scripts/database/seed/seed_manuais.py
```

O schema completo também contém as tabelas `manualguia` e `manualversao`. Após limpar
os dados para testes, inclua `seed_manuais.py` na carga dos seeds. O seed cria apenas
os guias ausentes; não substitui conteúdo nem versões publicadas no Admin.

## Atualização de funcionalidades

Revise os guias afetados no Admin em **Roteiro de Implantação e Manual do Parceiro**.
Edite etapas, público, aplicativo e caminho; registre o resumo da alteração e
publique. O servidor cria uma versão imutável. Edições concorrentes baseadas em
uma versão antiga recebem conflito para impedir perda de conteúdo.

Para instalações novas, mantenha também o conteúdo inicial do seed atualizado.
Alterar o seed não atualiza automaticamente ambientes que já possuem manuais.

Fluxogramas na tela e no PDF são derivados das etapas, sem imagens externas.
O PDF usa a versão e o público selecionados; a busca na tela não limita a
exportação. O PDF do Parceiro não inclui etapas internas da equipe Clubbar.

Todos os endpoints exigem o mesmo acesso de operador Clubbar do Admin. O arquivo
exportado pode ser encaminhado pelo operador; não há envio automático de mensagens.

## Backup e restauração

No painel administrativo, o card dos manuais oferece **Exportar backup** e
**Importar backup**. O JSON único contém os três guias, todas as versões, datas,
conteúdos e resumos de alteração. Guarde esse arquivo fora da base antes de zerá-la.

A importação valida o formato e substitui somente os dados de `manualguia` e
`manualversao`, em uma transação. Os IDs internos são recriados; números de versão
e histórico são preservados. As tabelas precisam existir (schema/migração aplicada).
É possível restaurar com as tabelas vazias ou após os seeds. Exporte um backup
atual antes de substituir um histórico que ainda deseja guardar. O seed posterior
preserva os guias restaurados. Um arquivo inválido ou uma falha de gravação não
deve deixar uma restauração parcial.

## Verificação

```powershell
python -m unittest tests.test_manuais
```

Os testes utilizam SQLite em memória e não alteram os dados de desenvolvimento.
