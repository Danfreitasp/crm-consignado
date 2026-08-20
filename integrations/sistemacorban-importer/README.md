# Sistemacorban para CRM Consignado

Extensão Chrome Manifest V3 para enviar manualmente os dados do benefício atualmente visível no Sistemacorban para **Simulador INSS**, **Nova Proposta** ou **Editar cliente** do CRM.

## Instalação

1. Abra `chrome://extensions` no Chrome.
2. Ative **Modo do desenvolvedor**.
3. Clique em **Carregar sem compactação**.
4. Se você baixou a extensão pelo CRM, descompacte o arquivo `.zip` e selecione a pasta `sistemacorban-importer`. No projeto, essa pasta fica em `integrations/sistemacorban-importer`.
5. Abra **Detalhes** da extensão e depois **Opções da extensão**.

## Configuração do CRM

O padrão é `http://127.0.0.1:5000`. Para usar outro computador da rede, informe a origem completa, por exemplo `http://192.168.1.20:5000`, e clique em **Salvar e autorizar esta origem**.

A extensão declara origens HTTP/HTTPS como permissões opcionais para suportar IPs locais variáveis, mas solicita ao Chrome somente a origem exata configurada. Ao trocar a URL, a permissão da origem anterior é removida. No armazenamento ficam apenas a URL e a preferência do diagnóstico; dados pessoais não são armazenados.

## Uso

1. No CRM, abra **Simulador INSS**, **Nova Proposta** ou **Editar cliente** e deixe a tela aguardando a importação.
2. Entre manualmente no Sistemacorban, consulte o CPF e selecione manualmente o benefício correto.
3. Na tela de detalhes do benefício, clique no botão flutuante **Enviar para o CRM**.
4. A extensão tenta clicar nos ícones de olho somente dentro de **Dados Cliente**, aguarda a atualização visual e lê os rótulos da tela. Telefones não são extraídos nem enviados ao CRM.
5. No Simulador INSS, escolha na lista qual contrato bancário deseja usar; o banco de destino fica fixo como Quali. Se a margem disponível de 40% estiver negativa, ela será deduzida da parcela do contrato para formar a nova parcela; com margem positiva ou zerada, a nova parcela fica vazia e o CRM usa a parcela atual. Nas demais telas, revise os campos destacados e salve somente se estiverem corretos.

A extensão não executa login, não pesquisa CPF, não escolhe benefício, não cria filas e não salva os dados.

## Seletores e ajustes do portal

Sem uma sessão real do portal, os seletores específicos não puderam ser confirmados. Toda a adaptação está centralizada no início de `content.js`:

- `PORTAL_SELECTORS.detalheRaiz`: containers exclusivos da tela de detalhe;
- `PORTAL_SELECTORS.areaDadosCliente`: container da área Dados Cliente;
- `PORTAL_SELECTORS.olho`: botões/ícones usados para revelar campos;
- `PORTAL_SELECTORS.valoresDiretos`: seletores diretos opcionais por campo;
- `LABELS`: variações textuais dos rótulos;
- `detectarTelaDetalhe()`: evita exibir o botão na seleção de benefícios;
- `encontrarValorPorRotulo()`: fallback de extração por rótulo visível.

Se o botão não aparecer ou algum campo não for lido, ative o modo de diagnóstico nas opções. Ele informa somente nomes/quantidades de rótulos encontrados ou ausentes, nunca os valores pessoais. Ajuste primeiro os seletores centralizados usando a inspeção de elementos do Chrome.

## Privacidade

- Dados são mantidos apenas em memória durante o clique e enviados diretamente entre a aba do portal e a aba do CRM.
- CPF, endereço e dados bancários não são gravados em `storage`, arquivos ou logs. Telefones não são importados.
- Nenhum dado é enviado a serviços externos.
- A extensão atua no portal somente após o clique explícito do usuário.
