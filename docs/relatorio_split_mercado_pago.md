# Relatório de vendas com split Mercado Pago

A funcionalidade usa relatórios manuais (`statements`) da aplicação de marketplace, não o token OAuth das lojas. Antes de disponibilizá-la, configure no Mercado Pago a estrutura e o notificador oficiais, e no servidor da API:

- `MERCADO_PAGO_REPORT_ACCESS_TOKEN`: access token de produção da aplicação do marketplace. É um segredo; nunca colocá-lo no Partner nem no repositório.
- `MERCADO_PAGO_REPORT_STRUCTURE_ID`: ID da estrutura criada para esse token.
- `MERCADO_PAGO_REPORT_NOTIFIER_ID`: ID do notificador criado para esse token. A geração pode enviar notificações para os destinatários configurados no Mercado Pago; use somente destinatários autorizados a receber informações de todas as empresas do marketplace.

Configure na estrutura `display_timezone: GMT-03`, `file_format.column_separator: ;`, `decimal_separator: .`, e sem aliases as colunas: `COLLECTOR`, `COLLECTOR_NICKNAME`, `PAYMENT`, `STATUS_DESCRIPTION`, `STATUS_DETAIL`, `PURCHASE_ORDER`, `PAYMENT_METHOD_TYPE`, `TRANSACTION_AMOUNT`, `DATE_CREATED`, `DATE_APPROVED`, `MARKETPLACE_FEE_AMOUNT`, `MERCADOPAGO_FEE_AMOUNT`, `TOTAL_PAID_AMOUNT`, `NET_RECEIVED_AMOUNT`. O endpoint rejeita estruturas incompletas. A criação da estrutura e do notificador deve seguir a documentação do provedor: https://www.mercadopago.com.br/developers/pt/docs/split-payments/split-1-1/additional-content/reports/sales-report/generate-report

Cada solicitação gera um relatório manual para até 91 dias, com datas no horário de Brasília. Apenas administradores da empresa podem solicitar e consultar. A API baixa o arquivo integral no servidor e retorna somente linhas cujo ID de pagamento esteja vinculado a um checkout de loja da empresa. Pagamentos sem ID vinculado não aparecem; isso também inclui operações que não possam ser associadas com segurança. O arquivo original e o token não são enviados ao Partner. O comprovante de consulta expira em 24 horas e é restrito à empresa. O Partner permite baixar os dados filtrados em CSV e JSON. Para privacidade, o download disponibilizado pela notificação geral do Mercado Pago não deve ser enviado diretamente aos parceiros.

Antes de ativar, valide em ambiente apropriado a configuração, a geração e o download com transações de teste e confirme os valores efetivamente liquidados. A resposta do Mercado Pago pode variar e o acesso aos relatórios depende da habilitação da conta marketplace.
