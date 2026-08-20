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

    function atualizarEstado(novoEstado, mensagem) {
        aguardando = novoEstado;
        document.body.dataset.crmImportacaoPortal = novoEstado ? 'aguardando' : 'inativa';
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

    function firstBankName(value) {
        const parts = String(value || '').trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return '';
        if (['BANCO', 'BCO'].includes(parts[0].toUpperCase().replace(/\.$/, ''))) parts.shift();
        while (parts.length && ['DA', 'DAS', 'DE', 'DO', 'DOS'].includes(parts[0].toUpperCase().replace(/\.$/, ''))) {
            parts.shift();
        }
        return (parts[0] || '').replace(/^[^A-ZÀ-Ü0-9]+|[^A-ZÀ-Ü0-9]+$/gi, '').toLocaleUpperCase('pt-BR');
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
        setField('parcela_atual', contract.parcela, highlighted);
        setField('saldo_quitacao', contract.saldo_devedor, highlighted);
        setField('prazo_contrato', contract.prazo_total, highlighted);
        setField('parcelas_pagas', contract.parcelas_pagas, highlighted);
        setField('banco_destino', 'QUALI', highlighted);
        const margin = parseMoney(importedData.margem_disponivel);
        if (margin < 0) {
            const adjustedInstallment = Math.max(0, parseMoney(contract.parcela) + margin);
            setField('nova_parcela', formatMoneyInput(adjustedInstallment), highlighted);
        } else {
            const newInstallment = document.querySelector('[name="nova_parcela"]');
            if (newInstallment) {
                newInstallment.value = '';
                newInstallment.dispatchEvent(new Event('input', { bubbles: true }));
                newInstallment.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        const marginMessage = margin < 0
            ? ` Margem negativa de ${formatMoneyInput(margin)} deduzida da nova parcela.`
            : ' Margem positiva ou zerada: será usada a parcela atual.';
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
        const novaMatricula = Boolean(event.detail?.novaMatricula);
        if (novaMatricula) {
            atualizarEstado(false, 'Dados cadastrais reaproveitados. Informe somente a nova matrícula e os dados da nova proposta.');
            return;
        }
        atualizarEstado(false, 'Cadastro existente reaproveitado. Preencha somente os dados da nova proposta.');
    });

    document.addEventListener('crm:clientes-localizados', () => {
        atualizarEstado(false, 'Cadastro existente encontrado. Selecione a matrícula para reaproveitar os dados.');
    });

    document.addEventListener('crm:cliente-nao-localizado', () => {
        atualizarEstado(true, 'Cliente não cadastrado. Aguardando dados do Sistemacorban nesta aba.');
    });

    atualizarEstado(true, 'Aguardando dados do Sistemacorban nesta aba.');

    // Ponte chamada pela extensão no contexto principal da aba do CRM.
    // Preenche campos, mas deliberadamente não dispara submit nem requisição.
    window.aplicarDadosConsultaINSS = function (dados = {}) {
        if (!aguardando) {
            return { sucesso: false, motivo: 'Esta tela do CRM não está aguardando importação.' };
        }

        if (simulatorForm) {
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
                option.textContent = `${contract.banco} · Contrato ${contract.numero} · Parcela ${contract.parcela} · Saldo ${contract.saldo_devedor}`;
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
