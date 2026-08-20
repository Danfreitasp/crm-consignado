const CRM_URL_PADRAO = 'http://127.0.0.1:5000';
const form = document.getElementById('configForm');
const urlField = document.getElementById('crmBaseUrl');
const diagnosticoField = document.getElementById('diagnostico');
const statusField = document.getElementById('status');

function mostrarStatus(mensagem, kind) {
  statusField.textContent = mensagem;
  statusField.dataset.kind = kind;
}

function origemValida(valor) {
  const parsed = new URL(valor);
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('Use uma URL HTTP ou HTTPS.');
  return parsed.origin;
}

async function carregar() {
  const config = await chrome.storage.local.get({ crmBaseUrl: CRM_URL_PADRAO, diagnostico: false });
  urlField.value = config.crmBaseUrl;
  diagnosticoField.checked = Boolean(config.diagnostico);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const origem = origemValida(urlField.value.trim());
    const anterior = await chrome.storage.local.get({ crmBaseUrl: CRM_URL_PADRAO });
    const origemAnterior = origemValida(anterior.crmBaseUrl);
    const concedida = await chrome.permissions.request({ origins: [`${origem}/*`] });
    if (!concedida) {
      mostrarStatus('A permissão para esta origem não foi concedida.', 'erro');
      return;
    }
    await chrome.storage.local.set({ crmBaseUrl: origem, diagnostico: diagnosticoField.checked });
    urlField.value = origem;
    if (origemAnterior !== origem) {
      await chrome.permissions.remove({ origins: [`${origemAnterior}/*`] });
    }
    mostrarStatus('Configuração salva. A extensão tem acesso somente à origem autorizada.', 'sucesso');
  } catch (_) {
    mostrarStatus('Informe uma URL válida, incluindo http:// ou https:// e a porta do CRM.', 'erro');
  }
});

carregar();
