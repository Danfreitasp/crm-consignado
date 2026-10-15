(() => {
    'use strict';

    const formGrid = document.getElementById('propostaFormGrid');
    const simulatorForm = document.getElementById('simuladorInssForm');
    const status = document.getElementById('portalImportStatus');
    if ((!formGrid && !simulatorForm) || !status) return;

    const contractPicker = document.getElementById('portalContractPicker');
    const contractSelect = document.getElementById('portalContractSelect');
    let importedData = {};

    let aguardando = false;

    const confirmacaoCorban = document.getElementById('corbanComplemento');
    const botaoComplementar = document.getElementById('corbanComplementoSim');
    const botaoDispensar = document.getElementById('corbanComplementoNao');
    const endpointComplemento = confirmacaoCorban?.dataset.corbanEndpoint || '';
    let modoComplementar = false;
    let decisaoCorban = !confirmacaoCorban;

    function atualizarEstado(novoEstado, mensagem) {
        aguardando = novoEstado;
        document.body.dataset.crmImportacaoPortal = novoEstado ? 'aguardando' : 'inativa';
        status.textContent = mensagem;
    }

    // Atualiza apenas a mensagem, preservando o estado de espera atual (usado
    // quando uma falha não deve descartar a tentativa de importação).
    function mostrarStatus(mensagem) {
        document.body.dataset.crmImportacaoPortal = aguardando ? 'aguardando' : 'inativa';
        status.textContent = mensagem;
    }

    window.crmImportacaoPortal = {
        estaAguardando: () => aguardando,
    };

    function setField(name, value, highlighted = []) {
        if (value === undefined || value === null || String(value).trim() === '') return;
        const field = document.querySelector(`[name="${name}"]`);
        if (!field) return;
        field.value = String(value);
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
        field.classList.add('portal-import-highlight');
        highlighted.push(field);
    }

    function parseMoney(value) {
        let text = String(value ?? '').replace(/R\$/gi, '').replace(/\s+/g, '').trim();
        const negative = text.startsWith('-') || /^\(.*\)$/.test(text);
        text = text.replace(/[()\-+]/g, '');
        const number = Number(text.replace(/\./g, '').replace(',', '.')) || 0;
        return negative ? -number : number;
    }

    function formatMoneyInput(value) {
        return Number(value || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function formatMoneyLabel(value) {
        const text = String(value ?? '').trim();
        return text ? `R$ ${formatMoneyInput(parseMoney(text))}` : '';
    }

    function formatRateLabel(value) {
        const text = String(value ?? '')
            .replace(/\s*a\.?\s*m\.?\s*$/i, '')
            .replace(/%+\s*$/, '')
            .trim();
        return text ? `${text}% a.m.` : '';
    }

    function firstBankName(value) {
        const parts = String(value || '').trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return '';
        if (['BANCO', 'BCO'].includes(parts[0].toUpperCase().replace(/\.$/, ''))) parts.shift();
        while (parts.length && ['DA', 'DAS', 'DE', 'DO', 'DOS'].includes(parts[0].toUpperCase().replace(/\.$/, ''))) {
            parts.shift();
        }
        const nome = (parts[0] || '').replace(/^[^A-ZÀ-Ü0-9]+|[^A-ZÀ-Ü0-9]+$/gi, '').toLocaleUpperCase('pt-BR');
        const nomesCorrigidos = {
            AGIBAN: 'AGIBANK',
            INBURS: 'INBURSA',
            PARAN: 'PARANÁ',
            SAFR: 'SAFRA',
        };
        return nomesCorrigidos[nome] || nome;
    }

    function applyContract(contract) {
        if (!contract) return;
        const highlighted = [];
        document.querySelector('input[name="modo_simulacao"][value="port_refin"]')?.click();
        setField('nome', importedData.nome, highlighted);
        setField('cpf', importedData.cpf, highlighted);
        setField('nascimento', importedData.nascimento, highlighted);
        setField('nb_matricula', importedData.nb, highlighted);
        setField('especie', importedData.especie, highlighted);
        setField('endereco', importedData.endereco, highlighted);
        setField('dados_bancarios', importedData.dados_bancarios, highlighted);
        setField('banco_atual', firstBankName(contract.banco), highlighted);
        setField('numero_contrato', contract.numero, highlighted);
        setField('data_averbacao', contract.data_averbacao, highlighted);
        setField('parcela_atual', contract.parcela, highlighted);
        setField('saldo_quitacao', contract.saldo_devedor, highlighted);
        setField('prazo_contrato', contract.prazo_total, highlighted);
        setField('parcelas_pagas', contract.parcelas_pagas, highlighted);
        setField('taxa_contrato_atual', contract.taxa, highlighted);
        setField('banco_destino', 'QUALI', highlighted);
        const margin = parseMoney(importedData.margem_disponivel);
        setField('margem_disponivel_importada', formatMoneyInput(margin), highlighted);
        const newInstallment = document.querySelector('[name="nova_parcela"]');
        if (newInstallment) {
            newInstallment.value = '';
            newInstallment.dispatchEvent(new Event('input', { bubbles: true }));
            newInstallment.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const marginMessage = margin < 0
            ? ` Margem negativa de ${formatMoneyInput(Math.abs(margin))} importada; escolha Sim para deduzi-la ou Não para ignorá-la.`
            : ' Margem positiva ou zerada: não há negativo para deduzir.';
        atualizarEstado(true, `Contrato ${contract.numero} selecionado.${marginMessage} Escolha a tabela Quali e revise os valores.`);
        window.setTimeout(() => highlighted.forEach((field) => field.classList.remove('portal-import-highlight')), 3500);
    }

    if (contractSelect) {
        contractSelect.addEventListener('change', () => {
            const contract = (importedData.contratos || []).find((item) => item.numero === contractSelect.value);
            applyContract(contract);
        });
    }

    document.addEventListener('crm:cliente-reaproveitado', (event) => {
        if (!decisaoCorban) return;
        const novaMatricula = Boolean(event.detail?.novaMatricula);
        if (novaMatricula) {
            atualizarEstado(false, 'Dados cadastrais reaproveitados. Informe somente a nova matrícula e os dados da nova proposta.');
            return;
        }
        atualizarEstado(false, 'Cadastro existente reaproveitado. Preencha somente os dados da nova proposta.');
    });

    document.addEventListener('crm:clientes-localizados', () => {
        if (!decisaoCorban) return;
        atualizarEstado(false, 'Cadastro existente encontrado. Selecione a matrícula para reaproveitar os dados.');
    });

    document.addEventListener('crm:cliente-nao-localizado', () => {
        if (!decisaoCorban) return;
        atualizarEstado(true, 'Cliente não cadastrado. Aguardando dados do Sistemacorban nesta aba.');
    });

    if (confirmacaoCorban) {
        // A proposta veio de um extrato: só consulta o Corban depois da escolha.
        atualizarEstado(false, 'O extrato preencheu os dados disponíveis. Escolha se deseja complementar com a base do Corban.');
    } else {
        atualizarEstado(true, 'Aguardando dados do Sistemacorban nesta aba.');
    }

    const CAMPOS_COMPLEMENTO = ['nome', 'cpf', 'nascimento', 'nb_matricula', 'especie', 'tipo_cliente', 'telefone', 'endereco', 'dados_bancarios'];

    function coletarPropostaParaComplemento() {
        const proposta = {};
        CAMPOS_COMPLEMENTO.forEach((name) => {
            const field = document.querySelector(`[name="${name}"]`);
            if (field) proposta[name] = field.value;
        });
        return proposta;
    }

    function aplicarCamposComplementares(campos) {
        const aplicados = [];
        Object.entries(campos || {}).forEach(([name, value]) => {
            if (value === undefined || value === null || String(value).trim() === '') return;
            const field = document.querySelector(`[name="${name}"]`);
            if (!field) return;
            // Defesa extra: nunca sobrescreve o que já está preenchido na tela.
            if (String(field.value || '').trim() !== '') return;
            field.value = String(value);
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));
            field.classList.add('portal-import-highlight');
            aplicados.push(field);
        });
        window.setTimeout(() => aplicados.forEach((field) => field.classList.remove('portal-import-highlight')), 3500);
        return aplicados;
    }

    function encerrarConfirmacao() {
        decisaoCorban = true;
        [botaoComplementar, botaoDispensar].forEach((botao) => {
            if (!botao) return;
            botao.disabled = true;
            botao.setAttribute('aria-disabled', 'true');
        });
        confirmacaoCorban?.classList.remove('is-aguardando');
    }

    async function complementarComCorban(dados) {
        if (!endpointComplemento) {
            mostrarStatus('A complementação pela base do Corban não está disponível nesta página. Os dados atuais foram preservados.');
            return { sucesso: false, motivo: 'Endpoint de complementação indisponível.' };
        }
        try {
            const response = await fetch(endpointComplemento, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ proposta: coletarPropostaParaComplemento(), corban: dados }),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.erro || 'Falha ao consultar a base do Corban.');
            const aplicados = aplicarCamposComplementares(payload.campos || {});
            modoComplementar = false;
            aguardando = false;
            encerrarConfirmacao();
            const mensagem = payload.mensagem || `${aplicados.length} campo(s) complementado(s) com a base do Corban.`;
            mostrarStatus(mensagem);
            return { sucesso: true, mensagem, camposPreenchidos: aplicados.length };
        } catch (error) {
            // Preserva os dados já preenchidos e permite uma nova tentativa.
            mostrarStatus(`Não foi possível complementar os dados (${error.message}). Os dados atuais foram preservados.`);
            return { sucesso: false, motivo: error.message };
        }
    }

    if (botaoComplementar) {
        botaoComplementar.addEventListener('click', () => {
            decisaoCorban = true;
            modoComplementar = true;
            confirmacaoCorban?.classList.add('is-aguardando');
            const cpf = (document.querySelector('[name="cpf"]')?.value || '').trim();
            const referencia = cpf ? ` do CPF ${cpf}` : '';
            atualizarEstado(true, `Abra o benefício${referencia} no Sistemacorban e clique em "Enviar para o CRM".`);
        });
    }

    if (botaoDispensar) {
        botaoDispensar.addEventListener('click', () => {
            modoComplementar = false;
            encerrarConfirmacao();
            atualizarEstado(false, 'Importação do Corban ignorada. Continue o cadastro normalmente.');
        });
    }

    // Ponte chamada pela extensão no contexto principal da aba do CRM.
    // Preenche campos, mas deliberadamente não dispara submit nem requisição.
    window.aplicarDadosConsultaINSS = function (dados = {}) {
        if (!aguardando) {
            return { sucesso: false, motivo: 'Esta tela do CRM não está aguardando importação.' };
        }

        if (modoComplementar) {
            return complementarComCorban(dados);
        }

        if (simulatorForm) {
            document.querySelector('input[name="fonte_simulacao"][value="corban_manual"]')?.click();
            importedData = dados;
            const contracts = Array.isArray(dados.contratos) ? dados.contratos : [];
            if (!contractPicker || !contractSelect || !contracts.length) {
                atualizarEstado(true, 'Nenhum contrato bancário foi encontrado no benefício aberto no Corban.');
                return { sucesso: false, motivo: 'Nenhum contrato bancário encontrado.' };
            }
            contractSelect.innerHTML = '<option value="">Selecione um contrato</option>';
            contracts.forEach((contract) => {
                const option = document.createElement('option');
                option.value = contract.numero;
                const banco = firstBankName(contract.banco) || contract.banco;
                const parcelasPagas = String(contract.parcelas_pagas ?? '').trim();
                const prazoTotal = String(contract.prazo_total ?? '').trim();
                const detalhes = [banco, `Contrato ${String(contract.numero || '').trim()}`];
                if (parcelasPagas && prazoTotal) detalhes.push(`${parcelasPagas}/${prazoTotal} pagas`);
                const parcela = formatMoneyLabel(contract.parcela);
                if (parcela) detalhes.push(`Parcela ${parcela}`);
                const taxa = formatRateLabel(contract.taxa);
                if (taxa) detalhes.push(`Taxa ${taxa}`);
                const saldo = formatMoneyLabel(contract.saldo_devedor);
                if (saldo) detalhes.push(`Saldo informado ${saldo}`);
                option.textContent = detalhes.join(' · ');
                const extras = [option.textContent];
                if (contract.banco) extras.push(`Banco no Corban: ${contract.banco}`);
                if (contract.prazo_restante) extras.push(`${contract.prazo_restante} parcelas restantes`);
                if (contract.data_averbacao) extras.push(`Averbação: ${contract.data_averbacao}`);
                option.title = extras.join(' · ');
                contractSelect.appendChild(option);
            });
            contractPicker.hidden = false;
            atualizarEstado(true, `${contracts.length} contrato(s) importado(s). Escolha qual deseja simular.`);
            return { sucesso: true, mensagem: 'Contratos enviados ao CRM. Escolha no simulador qual deseja utilizar.', contratosImportados: contracts.length };
        }

        const mapa = {
            nome: dados.nome,
            cpf: dados.cpf,
            nascimento: dados.nascimento,
            nb_matricula: dados.nb,
            especie: dados.especie,
            endereco: dados.endereco,
            dados_bancarios: dados.dados_bancarios,
        };
        const preenchidos = [];
        Object.entries(mapa).forEach(([name, value]) => {
            if (value === undefined || value === null || String(value).trim() === '') return;
            const field = document.querySelector(`[name="${name}"]`);
            if (!field) return;
            field.value = String(value);
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));
            field.classList.add('portal-import-highlight');
            preenchidos.push(field);
        });

        atualizarEstado(false, 'Dados importados. Revise antes de salvar.');
        window.setTimeout(() => preenchidos.forEach((field) => field.classList.remove('portal-import-highlight')), 3500);
        return { sucesso: true, camposPreenchidos: preenchidos.length };
    };
})();
