(() => {
  'use strict';

  if (location.origin !== 'https://gestao.sistemacorban.com.br') return;

  // Ajuste seletores específicos do portal somente neste objeto. Os fallbacks por
  // texto abaixo continuam funcionando quando classes e IDs mudam.
  const PORTAL_SELECTORS = {
    detalheRaiz: [
      '[data-beneficio-detalhe]',
      '#dados-beneficio',
      '.dados-beneficio',
      '.beneficio-detalhe',
    ],
    areaDadosCliente: [
      '[data-section="dados-cliente"]',
      '#dados-cliente',
      '.dados-cliente',
    ],
    olho: [
      'button[aria-label*="visual" i]',
      'button[aria-label*="exib" i]',
      'button[aria-label*="revel" i]',
      'button[title*="visual" i]',
      'button[title*="exib" i]',
      'button[title*="revel" i]',
      'button .fa-eye',
      'button .bi-eye',
      'button .material-icons',
    ],
    valoresDiretos: {
      // Exemplo para ajuste futuro: nome: '#campo-nome .valor'
    },
  };

  const LABELS = {
    nb: ['NB - UF', 'NB/UF', 'NB'],
    nome: ['Nome'],
    cpf: ['CPF'],
    nascimento: ['Nascimento', 'Data de Nascimento'],
    especie: ['Espécie', 'Especie'],
    banco: ['Banco'],
    agencia: ['Ag. Banco', 'Agência', 'Agencia'],
    conta: ['Conta Corrente', 'Conta'],
    endereco: ['Endereço', 'Endereco'],
    cep: ['CEP'],
    bairro: ['Bairro'],
    cidadeUf: ['Cidade - UF', 'Cidade/UF'],
  };

  const seletorRotulos = 'label, dt, th, td, span, strong, p, div';
  let diagnosticoAtivo = false;
  let timerDeteccao = 0;

  function normalizar(texto) {
    return String(texto || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, ' ')
      .replace(/\s*:\s*$/, '')
      .trim()
      .toLowerCase();
  }

  function textoLimpo(elemento) {
    return String(elemento?.innerText || elemento?.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function visivel(elemento) {
    if (!elemento || !elemento.isConnected) return false;
    const estilo = getComputedStyle(elemento);
    return estilo.display !== 'none' && estilo.visibility !== 'hidden' && elemento.getClientRects().length > 0;
  }

  function primeiroSeletor(seletores, raiz = document) {
    for (const seletor of seletores) {
      const encontrado = raiz.querySelector(seletor);
      if (visivel(encontrado)) return encontrado;
    }
    return null;
  }

  function encontrarAreaPorTitulo(titulos) {
    const normalizados = titulos.map(normalizar);
    const titulo = Array.from(document.querySelectorAll('h1, h2, h3, h4, legend, .card-title, .panel-title'))
      .find((item) => visivel(item) && normalizados.some((alvo) => normalizar(textoLimpo(item)).includes(alvo)));
    return titulo?.closest('section, article, fieldset, .card, .panel, .box, .row') || titulo?.parentElement || null;
  }

  function valorDeContainer(rotulo, container) {
    if (!container) return '';
    const controle = container.querySelector('input:not([type="hidden"]), textarea, select');
    if (controle && visivel(controle)) return String(controle.value || '').trim();
    if (rotulo.tagName === 'DT' && rotulo.nextElementSibling?.tagName === 'DD') return textoLimpo(rotulo.nextElementSibling);
    const irmao = rotulo.nextElementSibling;
    if (irmao && visivel(irmao)) return textoLimpo(irmao);
    const total = textoLimpo(container);
    const textoRotulo = textoLimpo(rotulo);
    if (total && textoRotulo && total !== textoRotulo) {
      return total.replace(textoRotulo, '').replace(/^\s*[:\-]\s*/, '').trim();
    }
    return '';
  }

  function encontrarValorPorRotulo(chave) {
    const seletorDireto = PORTAL_SELECTORS.valoresDiretos[chave];
    if (seletorDireto) {
      const direto = document.querySelector(seletorDireto);
      if (visivel(direto)) return textoLimpo(direto) || String(direto.value || '').trim();
    }

    const nomes = LABELS[chave] || [];
    const normalizados = nomes.map(normalizar);
    const candidatos = Array.from(document.querySelectorAll(seletorRotulos)).filter((item) => {
      if (!visivel(item) || item.children.length > 5) return false;
      const texto = normalizar(textoLimpo(item));
      if (!normalizados.some((nome) => texto === nome || texto.startsWith(`${nome}:`))) return false;

      // O portal também usa textos como "Conta Corrente" no lado do valor
      // (por exemplo, Meio Pagamento = Conta Corrente). Só aceitamos o texto
      // como rótulo quando ele está na primeira coluna útil da linha.
      const linha = item.closest('tr, .row, .form-row, .field, .campo, dl > div');
      if (!linha) return true;
      const colunas = Array.from(linha.children).filter((coluna) => visivel(coluna) && textoLimpo(coluna));
      if (colunas.length < 2) return true;
      const colunaDoItem = colunas.findIndex((coluna) => coluna === item || coluna.contains(item));
      return colunaDoItem <= 0;
    });
    for (const rotulo of candidatos) {
      const container = rotulo.closest('.form-group, .form-row, .field, .campo, .row, tr, dl') || rotulo.parentElement;
      const valor = valorDeContainer(rotulo, container);
      if (valor && !normalizados.includes(normalizar(valor))) return valor;
    }
    return '';
  }

  function contarRotulosVisiveis(chave) {
    const nomes = (LABELS[chave] || []).map(normalizar);
    return Array.from(document.querySelectorAll(seletorRotulos)).filter((item) => {
      if (!visivel(item) || item.children.length > 5) return false;
      const texto = normalizar(textoLimpo(item));
      return nomes.some((nome) => texto === nome || texto.startsWith(`${nome}:`));
    }).length;
  }

  function detectarTelaDetalhe() {
    if (primeiroSeletor(PORTAL_SELECTORS.detalheRaiz)) return true;
    const essenciais = ['nb', 'nome', 'cpf'];
    const presentes = Object.keys(LABELS).filter((chave) => contarRotulosVisiveis(chave) > 0);
    const acoesSelecao = Array.from(document.querySelectorAll('button, a')).filter((item) => {
      const texto = normalizar(textoLimpo(item));
      return visivel(item) && (texto.includes('selecionar beneficio') || texto.includes('ver beneficio'));
    });
    if (acoesSelecao.length > 1 || contarRotulosVisiveis('nb') > 2) return false;
    return essenciais.every((chave) => presentes.includes(chave)) && presentes.length >= 4;
  }

  function botoesOlhoNaArea(area) {
    if (!area) return [];
    const encontrados = new Set();
    PORTAL_SELECTORS.olho.forEach((seletor) => {
      area.querySelectorAll(seletor).forEach((item) => {
        const botao = item.closest('button, [role="button"]') || item;
        const descricao = normalizar([
          botao.getAttribute?.('aria-label'),
          botao.getAttribute?.('title'),
          item.className,
          textoLimpo(item),
        ].filter(Boolean).join(' '));
        const ehOlho = ['visual', 'exib', 'revel', 'eye', 'visibility'].some((termo) => descricao.includes(termo));
        if (ehOlho && visivel(botao) && !botao.disabled) encontrados.add(botao);
      });
    });
    return Array.from(encontrados);
  }

  async function revelarCamposMascarados() {
    const areaCliente = primeiroSeletor(PORTAL_SELECTORS.areaDadosCliente) || encontrarAreaPorTitulo(['Dados Cliente', 'Dados do Cliente']);
    const botoes = botoesOlhoNaArea(areaCliente);
    botoes.forEach((botao) => botao.click());
    if (botoes.length) await new Promise((resolve) => setTimeout(resolve, 900));
    return botoes.length;
  }

  function semMascara(valor) {
    return valor && !/[＊*]{2,}/.test(valor);
  }

  function montarEndereco(campos) {
    const linhas = ['Endereço'];
    if (campos.endereco) linhas.push(campos.endereco.replace(/^Endere[cç]o\s*/i, '').trim());
    if (campos.cep) linhas.push(`CEP ${campos.cep}`);
    if (campos.bairro) linhas.push(`Bairro ${campos.bairro}`);
    if (campos.cidadeUf) linhas.push(`Cidade - UF ${campos.cidadeUf}`);
    return linhas.length > 1 ? linhas.join('\n') : '';
  }

  function montarDadosBancarios(campos) {
    const linhas = [];
    if (campos.banco) linhas.push(campos.banco);
    if (campos.agencia) linhas.push(`Agência: ${campos.agencia}`);
    if (campos.conta) linhas.push(`Conta Corrente: ${campos.conta}`);
    return linhas.join('\n');
  }

  function normalizarNb(valor) {
    return String(valor || '').replace(/\s*[-–]\s*[A-Z]{2}\s*$/i, '').trim();
  }

  function valorDoTexto(texto, rotulo) {
    const escapado = rotulo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const correspondencia = String(texto || '').match(new RegExp(`${escapado}\\s*:\\s*([^\\n]+)`, 'i'));
    return correspondencia?.[1]?.trim() || '';
  }

  function extrairContratosBancarios() {
    const encontrados = new Map();
    const candidatos = document.querySelectorAll(
      '.container--consulta .content--consulta, .container--consulta .portlet-banco, [data-contrato-bancario]'
    );
    candidatos.forEach((elemento) => {
      const texto = String(elemento.innerText || '').replace(/\r/g, '').trim();
      if (!/saldo\s+devedor\s*:/i.test(texto) || !/prazo\s*:/i.test(texto) || !/contrato\s*:/i.test(texto)) return;
      const numero = valorDoTexto(texto, 'Contrato');
      if (!numero || encontrados.has(numero)) return;
      const prazoTexto = valorDoTexto(texto, 'Prazo');
      const prazo = prazoTexto.match(/(\d+)\s*\/\s*(\d+)(?:\s*\|\s*(\d+)\s*pagas?)?/i);
      encontrados.set(numero, {
        numero,
        banco: valorDoTexto(texto, 'Banco'),
        parcela: valorDoTexto(texto, 'Parcela'),
        saldo_devedor: valorDoTexto(texto, 'Saldo devedor'),
        prazo_restante: prazo?.[1] || '',
        prazo_total: prazo?.[2] || '',
        parcelas_pagas: prazo?.[3] || (prazo ? String(Math.max(0, Number(prazo[2]) - Number(prazo[1]))) : ''),
        taxa: valorDoTexto(texto, 'Taxa'),
        data_averbacao: valorDoTexto(texto, 'Data Averbação'),
      });
    });
    return Array.from(encontrados.values());
  }

  function extrairMargemDisponivel40() {
    const rotulo = Array.from(document.querySelectorAll('div, span, strong, p, label'))
      .find((elemento) => visivel(elemento) && normalizar(textoLimpo(elemento)) === 'margem disponivel (40%)');
    if (!rotulo) return '';
    let container = rotulo;
    for (let nivel = 0; nivel < 5 && container; nivel += 1) {
      const textoNivel = textoLimpo(container);
      if (/R\$\s*[+-]?\s*[\d.]+,\d{2}/i.test(textoNivel)) break;
      container = container.parentElement;
    }
    container ||= rotulo.parentElement;
    const texto = textoLimpo(container);
    const valor = texto.match(/R\$\s*([+-]?\s*[\d.]+,\d{2})/i);
    if (valor?.[1]) return valor[1].replace(/\s+/g, ' ').trim();
    const irmao = rotulo.nextElementSibling;
    return textoLimpo(irmao).replace(/^R\$\s*/i, '').trim();
  }

  function extrairDados() {
    const bruto = Object.fromEntries(Object.keys(LABELS).map((chave) => [chave, encontrarValorPorRotulo(chave)]));
    return {
      dados: {
        nome: bruto.nome,
        cpf: bruto.cpf,
        nascimento: bruto.nascimento,
        nb: normalizarNb(bruto.nb),
        especie: bruto.especie,
        endereco: montarEndereco(bruto),
        dados_bancarios: montarDadosBancarios(bruto),
        margem_disponivel: extrairMargemDisponivel40(),
        contratos: extrairContratosBancarios(),
      },
      encontrados: Object.keys(bruto).filter((chave) => Boolean(bruto[chave])),
    };
  }

  function mensagemDiagnostico(encontrados) {
    if (!diagnosticoAtivo) return '';
    const faltantes = Object.keys(LABELS).filter((chave) => !encontrados.includes(chave));
    return ` Diagnóstico: rótulos encontrados ${encontrados.length}; ausentes: ${faltantes.join(', ') || 'nenhum'}.`;
  }

  function criarPainel() {
    if (document.getElementById('crm-sistemacorban-importer')) return;
    const painel = document.createElement('aside');
    painel.id = 'crm-sistemacorban-importer';
    painel.innerHTML = '<button type="button">Enviar para o CRM</button><p data-status="info">Envio manual; os dados não serão salvos automaticamente.</p>';
    const botao = painel.querySelector('button');
    const status = painel.querySelector('p');
    botao.addEventListener('click', async () => {
      botao.disabled = true;
      status.dataset.status = 'info';
      status.textContent = 'Lendo os dados visíveis desta tela…';
      try {
        await revelarCamposMascarados();
        const extraido = extrairDados();
        const criticos = [extraido.dados.nome, extraido.dados.cpf, extraido.dados.nb];
        if (criticos.some((valor) => !semMascara(valor))) {
          status.dataset.status = 'erro';
          status.textContent = `Nome, CPF ou NB não foi encontrado ou continua mascarado.${mensagemDiagnostico(extraido.encontrados)}`;
          return;
        }
        const resposta = await chrome.runtime.sendMessage({ tipo: 'enviar-para-crm', dados: extraido.dados });
        status.dataset.status = resposta?.sucesso ? 'sucesso' : 'erro';
        status.textContent = `${resposta?.mensagem || 'Não foi possível enviar os dados.'}${mensagemDiagnostico(extraido.encontrados)}`;
      } catch (_) {
        status.dataset.status = 'erro';
        status.textContent = 'Não foi possível ler esta tela. Confirme que o benefício correto está aberto.';
      } finally {
        botao.disabled = false;
      }
    });
    document.body.appendChild(painel);
  }

  function atualizarPainel() {
    const painel = document.getElementById('crm-sistemacorban-importer');
    if (detectarTelaDetalhe()) criarPainel();
    else painel?.remove();
  }

  chrome.storage.local.get({ diagnostico: false }).then((config) => {
    diagnosticoAtivo = Boolean(config.diagnostico);
    atualizarPainel();
  });

  const observer = new MutationObserver(() => {
    clearTimeout(timerDeteccao);
    timerDeteccao = setTimeout(atualizarPainel, 450);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
