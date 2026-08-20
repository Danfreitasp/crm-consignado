# Design System do CRM Consig

Este documento define o padrão visual oficial do CRM. O objetivo é manter uma interface profissional e consistente sem alterar o fluxo operacional, a densidade das telas ou as regras de negócio.

## Princípio de decisão

Antes de modificar um componente, pergunte:

> Estou deixando este componente mais bonito ou estou mudando a forma como o usuário trabalha?

Se a alteração mudar a forma de trabalhar, exigir reaprendizado ou reduzir a velocidade operacional, ela não pertence a uma Sprint de Design.

## Ícones

Bootstrap Icons é a biblioteca oficial, carregada por CDN em `templates/base.html`.

- Use `<i class="bi bi-nome-do-icone" aria-hidden="true"></i>` em elementos que já possuem texto.
- Preserve o texto existente dos botões; o ícone é apoio visual, não substituto do rótulo.
- Não use emojis em menus ou botões padronizados.
- Ícones isolados devem ter `aria-label` no botão ou link.

## Paleta

As cores são centralizadas em variáveis no início de `static/style.css`:

- `--primary`, `--primary-hover` e `--primary-soft`: ações principais e estados ativos.
- `--bg`, `--bg-secondary`, `--surface`, `--surface-soft` e `--panel`: fundos e superfícies.
- `--text` e `--muted`: texto principal e texto de apoio.
- `--line` e `--border`: divisórias e contornos.
- `--ok`, `--warning`, `--danger` e `--info`: estados semânticos.
- Variantes `*-soft`: fundos suaves para estados semânticos.

O modo escuro redefine os mesmos tokens em `html[data-theme="escuro"]`. Componentes novos devem consumir variáveis, evitando cores literais quando já existir um token equivalente.

## Tipografia

- Família: `Inter`, com fallback para `Segoe UI`, `Arial` e `sans-serif`.
- Títulos usam peso seminegrito e hierarquia existente.
- Textos de apoio usam `--muted`.
- Não aumente nem reduza significativamente os tamanhos atuais.

## Botões

- `.btn`: ação neutra ou secundária.
- `.btn-primary`: ação principal da tela.
- `.btn-success`: confirmação positiva específica.
- `.btn-danger` ou `.danger`: ação destrutiva.
- `.mini-btn`: ações compactas dentro de cards e tabelas.
- `.notification-button`: botão quadrado apenas com ícone no cabeçalho.

Botões devem manter texto, ícone Bootstrap quando apropriado, foco visível e altura consistente. Não transforme ações conhecidas em controles sem rótulo.

## Inputs

Inputs, selects e textareas compartilham altura mínima, padding, raio, borda, hover e foco. Novos campos devem usar os elementos nativos e as regras globais existentes, sem criar alturas isoladas.

## Tabelas

- Cabeçalho com superfície suave e peso seminegrito.
- Linhas separadas por `--line`.
- Hover discreto, sem ocultar ou reorganizar conteúdo.
- A rolagem horizontal deve preservar todas as colunas.

## Cards e superfícies

- `.card` e `.metric-card`: superfícies principais.
- `.summary-card`: resumo compacto.
- `.kanban-card`: card operacional do Funil.
- Raios oficiais: `--radius-sm`, `--radius-md` e `--radius`.
- Sombras oficiais: `--shadow`, `--shadow-soft` e `--shadow-hover`.

Melhorias permitidas: borda, sombra, raio, hover e transição suave. Não mover, adicionar ou remover informações em cards consolidados.

## Funil e densidade operacional

Os cards do Funil são um componente operacional validado. Preserve:

- largura e altura;
- conteúdo e posição das informações;
- Valor e Comissão;
- botão Copiar;
- bolinhas verde e laranja;
- contadores, totais e colunas;
- drag-and-drop;
- densidade visual atual.

Mudanças futuras no Funil devem ser limitadas a acabamentos discretos e testadas no fluxo real.

## Sidebar e cabeçalho

A sidebar mantém largura, ordem e estrutura. Itens usam `.nav-link`, `.nav-icon` e Bootstrap Icons. O item ativo deve continuar claramente identificável.

O cabeçalho preserva título, descrição, Voltar, pesquisa, ajuda contextual, notificações, tema e Nova Proposta. Não adicione indicadores sem uma Sprint funcional específica.

## Toasts e alertas

Estados oficiais:

- `.ok`: sucesso, com `bi-check-circle`.
- `.aviso`: atenção, com `bi-exclamation-triangle`.
- `.erro`: erro, com `bi-exclamation-circle`.
- `.info`: informação, com `bi-info-circle`.

Mensagens devem ser curtas e não bloquear o trabalho. O comportamento existente de exibição e remoção permanece no JavaScript.

## Espaçamentos

Use os espaçamentos já recorrentes no projeto: 6, 8, 10, 12, 14, 16 e 18 pixels. Evite aumentar a ocupação vertical e preserve layouts compactos nas telas operacionais.

## Componentes futuros

1. Reutilize classes e tokens existentes antes de criar uma variação.
2. Valide modo claro e escuro.
3. Mantenha rótulos e posições de ações consolidadas.
4. Não associe uma mudança visual a alteração de rota, banco ou regra de negócio.
5. Teste teclado, foco, ícones, responsividade e ausência de regressões.
