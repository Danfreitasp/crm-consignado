# CRM Consignado

Sistema de gestão desenvolvido para centralizar o atendimento e o acompanhamento de propostas de crédito consignado.

Este é meu principal projeto em desenvolvimento atualmente. Ele nasceu de uma necessidade operacional real e evolui continuamente a partir do uso diário.

> Este repositório é uma vitrine pública. O código-fonte operacional, o banco de dados e as integrações privadas não são publicados para proteger dados, regras de negócio e credenciais.

## O projeto

O CRM reúne em um único ambiente o cadastro de clientes, o acompanhamento de propostas e as rotinas de atendimento. A interface foi planejada para reduzir retrabalho e oferecer uma visão clara de cada operação, desde o primeiro contato até o encerramento.

## Principais recursos

- Funil Kanban com etapas configuráveis e movimentação por arrastar e soltar.
- Cadastro e acompanhamento completo de clientes e propostas.
- Operações vinculadas de portabilidade e refinanciamento.
- Agenda e acompanhamento diário de retornos.
- Dashboard mensal de produção e comissões.
- Histórico de alterações, anotações e notificações.
- Simulador para pré-atendimento de clientes INSS.
- Importação e exportação de planilhas.
- Gerador de mensagens comerciais para atendimento.
- Temas claro e escuro e interface responsiva.
- Backups locais e cuidados específicos com a integridade dos dados.

## Tecnologias

- Python
- Flask
- SQLite
- Jinja
- HTML, CSS e JavaScript
- OpenPyXL

## Decisões importantes

- Aplicação local, sem dependência de serviços externos para os dados principais.
- Banco SQLite protegido e mantido fora do versionamento.
- Validações realizadas em cópias do banco antes de mudanças estruturais.
- Interface otimizada para um fluxo operacional rápido e de alta densidade.
- Evolução incremental para preservar os processos já consolidados.

## Status

Em desenvolvimento ativo e uso operacional.

Novos recursos, melhorias de experiência e integrações são incorporados continuamente conforme as necessidades reais do negócio.

## Privacidade e segurança

Este repositório não contém:

- dados de clientes;
- propostas ou documentos;
- bancos de dados e backups;
- chaves, senhas ou credenciais;
- código-fonte operacional;
- configurações privadas de integrações.

## Autor

Desenvolvido por [Daniel Pinto](https://github.com/Danfreitasp).
