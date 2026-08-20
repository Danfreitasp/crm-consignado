const CRM_URL_PADRAO = 'http://127.0.0.1:5000';

function normalizarOrigem(url) {
  const parsed = new URL(url || CRM_URL_PADRAO);
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('A URL do CRM deve usar HTTP ou HTTPS.');
  return parsed.origin;
}

function remetenteEhPortal(sender) {
  try {
    return new URL(sender?.url || '').origin === 'https://gestao.sistemacorban.com.br';
  } catch (_) {
    return false;
  }
}

async function enviarParaCrm(dados) {
  const configuracao = await chrome.storage.local.get({ crmBaseUrl: CRM_URL_PADRAO });
  const origem = normalizarOrigem(configuracao.crmBaseUrl);
  const permissao = `${origem}/*`;
  const permitido = await chrome.permissions.contains({ origins: [permissao] });
  if (!permitido) {
    return { sucesso: false, mensagem: 'Autorize a URL do CRM nas configurações da extensão.' };
  }

  const abas = await chrome.tabs.query({ url: permissao });
  const candidatas = abas.filter((aba) => {
    try {
      const caminho = new URL(aba.url).pathname.replace(/\/$/, '');
      return caminho === '/nova' || caminho === '/simulador-inss' || /^\/cliente\/\d+\/editar$/.test(caminho);
    } catch (_) {
      return false;
    }
  }).sort((a, b) => {
    const caminhoA = new URL(a.url).pathname.replace(/\/$/, '');
    const caminhoB = new URL(b.url).pathname.replace(/\/$/, '');
    const prioridadeA = Array.isArray(dados?.contratos) && dados.contratos.length && caminhoA === '/simulador-inss' ? 1 : 0;
    const prioridadeB = Array.isArray(dados?.contratos) && dados.contratos.length && caminhoB === '/simulador-inss' ? 1 : 0;
    return prioridadeB - prioridadeA || (b.lastAccessed || 0) - (a.lastAccessed || 0);
  });
  if (!candidatas.length) {
    return { sucesso: false, mensagem: 'Abra o Simulador INSS, a Nova Proposta ou a edição de um cliente no CRM configurado.' };
  }

  for (const aba of candidatas) {
    const resultados = await chrome.scripting.executeScript({
      target: { tabId: aba.id },
      world: 'MAIN',
      func: (payload) => {
        if (!window.crmImportacaoPortal?.estaAguardando?.()) {
          return { sucesso: false, motivo: 'A aba não está aguardando importação.' };
        }
        if (typeof window.aplicarDadosConsultaINSS !== 'function') {
          return { sucesso: false, motivo: 'A integração não está disponível nesta página.' };
        }
        return window.aplicarDadosConsultaINSS(payload);
      },
      args: [dados],
    });
    const retorno = resultados?.[0]?.result;
    if (retorno?.sucesso) {
      return { sucesso: true, mensagem: retorno.mensagem || 'Dados enviados ao CRM. Revise os dados antes de salvar.' };
    }
  }
  return { sucesso: false, mensagem: 'Deixe o Simulador INSS, a Nova Proposta ou a edição do cliente aberta e aguardando a importação.' };
}

chrome.runtime.onMessage.addListener((mensagem, sender, responder) => {
  if (mensagem?.tipo !== 'enviar-para-crm') return false;
  if (!remetenteEhPortal(sender)) {
    responder({ sucesso: false, mensagem: 'Origem não autorizada.' });
    return false;
  }
  enviarParaCrm(mensagem.dados || {})
    .then(responder)
    .catch(() => responder({ sucesso: false, mensagem: 'Não foi possível concluir a importação. Verifique a configuração do CRM.' }));
  return true;
});
