# CRM Consignado Local

CRM local em Flask + SQLite para acompanhar propostas de crédito consignado, organizar o funil de atendimento e reduzir retrabalho no dia a dia.

Este repositório contém o código-fonte do projeto. Bancos de dados, backups,
anexos, credenciais, chaves e pacotes gerados permanecem fora do versionamento.

O sistema foi pensado para uso operacional em rede local: rápido, simples de abrir, com dados salvos em banco SQLite local e interface focada em produtividade.

## Recursos principais

- Cadastro, edição, pesquisa e exclusão controlada de propostas.
- Funil Kanban com etapas configuráveis, filtro mensal opcional e movimentação por arrastar e soltar.
- Tela de detalhes da proposta com resumo, edição rápida, anotações, anexos, mensagens e histórico.
- Retorno inteligente para preservar a origem da navegação, como Funil, Encerradas, Hoje ou Propostas.
- Botões de produtividade como `Salvar` e `Salvar e voltar`.
- Toasts de confirmação para ações salvas sem bloquear a tela.
- Destaque temporário do card ao voltar para o Funil ou para a página Hoje.
- Sino de notificações com contador, leitura geral e avisos de etapas alteradas, propostas criadas, pagas, reprovadas, em reapresentação e leads excluídos.
- Página Encerradas para propostas pagas, perdidas ou canceladas.
- Dashboard mensal com indicadores de produção e comissão e opção de excluir propostas ativas trazidas de meses anteriores.
- Página Hoje para acompanhamento de propostas que precisam de atenção.
- Importação e exportação CSV/XLSX.
- Simulador INSS para pré-atendimento.
- Gerador de mensagens comerciais com modelos editáveis.
- Gerenciamento de modelos de mensagens da proposta.
- Conversor de contatos.
- Tema claro e modo escuro salvos no navegador.
- Histórico automático de status e alterações relevantes.
- Cadastro auxiliar de clientes alimentado a partir das propostas.
- Vínculo manual e criação rápida de refinanciamento vinculado à portabilidade.

## Telas principais

- `Funil`: visão Kanban das propostas em andamento.
- `Nova Proposta`: cadastro completo de uma proposta.
- `Propostas`: lista pesquisável com filtros e importação/exportação.
- `Hoje`: acompanhamento diário das propostas que precisam de atenção.
- `Encerradas`: propostas pagas, perdidas ou canceladas.
- `Dashboard`: visão mensal de produção.
- `Simulador INSS`: cálculo estimado para pré-atendimento.
- `Gerador de Mensagens`: mensagens comerciais prontas para WhatsApp.
- `Converter Contatos`: formatação de contatos para uso operacional.
- `Editar Etapas`: configuração das etapas do funil.

## Tecnologias

- Python
- Flask
- SQLite
- Jinja templates
- HTML, CSS e JavaScript
- Bootstrap Icons via CDN
- OpenPyXL para arquivos XLSX

Dependências atuais:

```text
Flask==3.0.3
openpyxl==3.1.5
```

## Como rodar no Windows

No terminal, dentro da pasta do CRM:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
```

Acesse no navegador:

```text
http://127.0.0.1:5000
```

Para acessar de outro computador na mesma rede, use o IP da máquina onde o CRM está rodando:

```text
http://IP-DA-MAQUINA:5000
```

## Dados locais

O CRM usa o arquivo `database.db` na raiz do projeto. Esse arquivo guarda propostas, clientes, histórico, anotações, modelos, notificações importantes e configurações criadas pelo uso do sistema.

O sino de notificações usa o próprio banco local para registrar avisos importantes e controlar até quando as notificações foram marcadas como lidas. Como o CRM não possui usuários individuais, a ação `Marcar todos como lido` vale para o uso geral da instalação local.

Arquivos e pastas locais que não devem ser enviados ao Git:

- `database.db`
- `backups/`
- `.venv/`
- `__pycache__/`
- anexos e documentos de clientes
- arquivos `.env`
- arquivos temporários ou logs

O sistema cria o banco automaticamente se `database.db` não existir, mas isso inicia uma base vazia.

## Backups

Ao iniciar, o CRM cria backups automáticos do banco na pasta `backups/`, mantendo apenas os backups mais recentes configurados no código.

Esses backups são dados locais e não devem ser versionados.

## Anexos

Os anexos são salvos na pasta definida em `Configurações > Documentos` dentro do CRM.
Alterar essa pasta afeta os novos uploads; arquivos já cadastrados continuam vinculados
ao caminho em que foram originalmente salvos.

Como fallback da instalação, também é possível definir a variável de ambiente:

```text
CRM_ANEXOS_DIR
```

## Como atualizar mantendo seus dados

Ao atualizar o sistema, substitua apenas os arquivos de código e interface:

```text
app.py
requirements.txt
README.md
templates/
static/
data/modelos_mensagens.json
```

Não substitua:

```text
database.db
backups/
.venv/
```

Os modelos editados pelo CRM ficam salvos no banco. O arquivo `data/modelos_mensagens.json` funciona como fallback legível.

## Estrutura do projeto

```text
CRM Consignado/
├─ app.py
├─ requirements.txt
├─ README.md
├─ data/
│  └─ modelos_mensagens.json
├─ static/
│  ├─ favicon.svg
│  ├─ script.js
│  └─ style.css
└─ templates/
   ├─ base.html
   ├─ _form.html
   ├─ detalhe_proposta.html
   ├─ funil.html
   ├─ hoje.html
   └─ ...
```

## Rotas úteis

- `/funil`
- `/propostas`
- `/nova`
- `/hoje`
- `/encerradas`
- `/dashboard`
- `/simulador-inss`
- `/gerador-mensagens`
- `/converter-contatos`
- `/configuracoes/status`

## Observações para desenvolvimento

- Preserve `database.db` em qualquer atualização.
- Evite mudanças diretas no banco sem migração segura.
- Não versionar bancos reais, backups, anexos ou arquivos locais de ferramenta.
- Antes de alterar fluxos importantes, validar Funil, Propostas, Hoje, Encerradas, Dashboard e edição de proposta.
- O histórico detalhado de versões deve ficar no Git, não no README.
