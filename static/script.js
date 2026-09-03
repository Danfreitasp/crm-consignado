function normalizarMatricula(value) {
    return String(value || '').replace(/[.\-\s]+/g, '').toLocaleUpperCase('pt-BR');
}

function formatarMoedaContrato(value) {
    return Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function taxaContratoExtrato(contrato) {
    const taxa = Number(contrato?.taxa);
    if (!Number.isFinite(taxa) || taxa <= 0) return '';
    return `${taxa.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}% a.m.`;
}

function textoContratoExtrato(contrato) {
    const detalhes = [
        contrato.banco || contrato.banco_descricao || 'Banco não informado',
        `Contrato ${String(contrato.numero || '').trim()}`,
        `${contrato.parcelas_pagas}/${contrato.prazo_total} pagas`,
        `Parcela ${formatarMoedaContrato(contrato.parcela)}`,
    ];
    const taxa = taxaContratoExtrato(contrato);
    if (taxa) detalhes.push(`Taxa ${taxa}`);
    detalhes.push(`Saldo estimado ${formatarMoedaContrato(contrato.saldo_calculado)}`);
    return detalhes.join(' · ');
}

function tituloContratoExtrato(contrato, textoPrincipal) {
    const detalhes = [textoPrincipal];
    if (contrato.banco_descricao) detalhes.push(`Banco no extrato: ${contrato.banco_descricao}`);
    if (contrato.situacao) detalhes.push(`Situação: ${contrato.situacao}`);
    if (contrato.competencia_inicio) detalhes.push(`Início: ${contrato.competencia_inicio}`);
    if (contrato.competencia_fim) detalhes.push(`Fim: ${contrato.competencia_fim}`);
    detalhes.push(`${contrato.parcelas_restantes} parcelas restantes`);
    return detalhes.join(' · ');
}

document.addEventListener('DOMContentLoaded', () => {
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        const atualizarSidebar = (recolhida) => {
            document.documentElement.classList.toggle('sidebar-collapsed', recolhida);
            sidebarToggle.setAttribute('aria-expanded', String(!recolhida));
            sidebarToggle.setAttribute('aria-label', recolhida ? 'Expandir menu' : 'Minimizar menu');
            sidebarToggle.title = recolhida ? 'Expandir menu' : 'Minimizar menu';
            const texto = sidebarToggle.querySelector('span');
            if (texto) texto.textContent = recolhida ? 'Expandir menu' : 'Minimizar menu';
        };
        atualizarSidebar(document.documentElement.classList.contains('sidebar-collapsed'));
        sidebarToggle.addEventListener('click', () => {
            const recolhida = !document.documentElement.classList.contains('sidebar-collapsed');
            atualizarSidebar(recolhida);
            try {
                localStorage.setItem('crmSidebarRecolhida', String(recolhida));
            } catch (error) {
                // A alternância continua funcionando durante a sessão atual.
            }
        });
    }

    const propostaFormGrid = document.getElementById('propostaFormGrid');
    if (propostaFormGrid) {
        const labels = Array.from(propostaFormGrid.children).filter((item) => item.tagName === 'LABEL');
        const localizarCampo = (name) => labels.find((label) => label.querySelector(`[name="${name}"]`));
        const grupos = [
            ['Dados do cliente', ['nome', 'cpf', 'nascimento', 'nb_matricula', 'especie', 'tipo_cliente', 'telefone']],
            ['Dados da proposta', ['numero_proposta', 'produto', 'banco_atual', 'banco_digitado', 'status', 'parcela_atual', 'nova_parcela', 'margem_apos', 'troco', 'comissao_percentual', 'comissao', 'refin_troco', 'reutilizar_percentual_refin', 'refin_comissao_percentual', 'refin_comissao', 'data_retorno']],
            ['Dados da promotora', ['promotora', 'beneficio_bloqueado', 'valor_caiu_promotora', 'valor_sacado']],
        ];
        const usados = new Set();
        const fragment = document.createDocumentFragment();
        grupos.forEach(([titulo, campos]) => {
            const camposEncontrados = campos
                .map((name) => localizarCampo(name))
                .filter(Boolean);
            if (!camposEncontrados.length) return;
            const coluna = document.createElement('section');
            coluna.className = 'proposal-form-column';
            coluna.innerHTML = `<h3>${titulo}</h3><div class="proposal-form-column-fields"></div>`;
            const destino = coluna.querySelector('.proposal-form-column-fields');
            camposEncontrados.forEach((campo) => {
                destino.appendChild(campo);
                usados.add(campo);
            });

            if (titulo === 'Dados da proposta') {
                const criarGrupoRecolhivel = (rotulo, nomes, atributo) => {
                    const camposDoGrupo = nomes
                        .map((name) => destino.querySelector(`label:has([name="${name}"])`))
                        .filter(Boolean);
                    if (!camposDoGrupo.length) return null;

                    const grupo = document.createElement('details');
                    grupo.className = 'proposal-operation-group';
                    grupo.open = true;
                    grupo.setAttribute(atributo, '');
                    grupo.innerHTML = `
                        <summary>
                            <span>${rotulo}</span>
                            <i class="bi bi-chevron-down" aria-hidden="true"></i>
                        </summary>
                        <div class="proposal-operation-group-fields"></div>
                    `;
                    const camposContainer = grupo.querySelector('.proposal-operation-group-fields');
                    camposDoGrupo.forEach((campo) => camposContainer.appendChild(campo));
                    destino.appendChild(grupo);
                    return grupo;
                };

                criarGrupoRecolhivel(
                    'Informações da portabilidade',
                    ['banco_atual', 'nova_parcela', 'troco', 'comissao_percentual', 'comissao'],
                    'data-portability-group',
                );
                criarGrupoRecolhivel(
                    'Informações do refinanciamento',
                    ['refin_troco', 'reutilizar_percentual_refin', 'refin_comissao_percentual', 'refin_comissao'],
                    'data-refinancing-group',
                );
            }
            fragment.appendChild(coluna);
        });
        labels.filter((label) => !usados.has(label)).forEach((label) => fragment.appendChild(label));
        propostaFormGrid.replaceChildren(fragment);
        propostaFormGrid.classList.add('proposal-form-columns');
    }

    const produtoSelect = document.getElementById('propostaProduto');
    if (produtoSelect) {
        const atualizarCamposPortabilidade = () => {
            const produto = (produtoSelect.value || '').toLocaleLowerCase('pt-BR');
            const portabilidade = ['portabilidade', 'portabilidade com refinanciamento'].includes(produto);
            const portabilidadeComRefin = produto === 'portabilidade com refinanciamento';
            document.querySelectorAll('[data-portability-field]').forEach((campo) => { campo.hidden = !portabilidade; });
            document.querySelectorAll('[data-port-refin-finance-field]').forEach((campo) => { campo.hidden = !portabilidadeComRefin; });
            const grupoPortabilidade = document.querySelector('[data-portability-group]');
            const grupoRefinanciamento = document.querySelector('[data-refinancing-group]');
            if (grupoPortabilidade) {
                const titulo = grupoPortabilidade.querySelector('summary span');
                if (titulo) titulo.textContent = portabilidade ? 'Informações da portabilidade' : 'Informações financeiras';
            }
            if (grupoRefinanciamento) grupoRefinanciamento.hidden = !portabilidadeComRefin;
            const rotulos = {
                '[data-port-value-label]': portabilidadeComRefin ? 'Valor da portabilidade' : 'Valor',
                '[data-port-percent-label]': portabilidadeComRefin ? '% comissão da portabilidade' : '% comissão',
                '[data-port-commission-label]': portabilidadeComRefin ? 'Comissão da portabilidade' : 'Comissão',
            };
            Object.entries(rotulos).forEach(([seletor, texto]) => {
                const elemento = document.querySelector(seletor);
                if (elemento) elemento.textContent = texto;
            });
        };
        produtoSelect.addEventListener('change', atualizarCamposPortabilidade);
        atualizarCamposPortabilidade();
    }

    const weekTimeline = document.querySelector('[data-week-timeline]');
    if (weekTimeline) {
        const esconderDestaquesSemana = () => {
            weekTimeline.querySelectorAll('.week-hover-slot').forEach((item) => { item.hidden = true; });
        };
        const now = new Date();
        const localDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
        const minute = now.getHours() * 60 + now.getMinutes();
        const top = Math.max(0, (minute - 420) * 64 / 60);
        const todayLane = weekTimeline.querySelector(`[data-week-day="${localDate}"]`);
        const nowLine = todayLane?.querySelector('[data-week-now-line]');
        if (nowLine && minute >= 420 && minute <= 1260) nowLine.style.setProperty('--now-top', `${top}px`);
        if (todayLane && minute >= 420 && minute <= 1260) weekTimeline.scrollTop = Math.max(0, top - 170);

        weekTimeline.querySelectorAll('.week-empty-slot').forEach((slot) => {
            const lane = slot.closest('.week-day-lane');
            if (!lane) return;
            const hoverSlot = document.createElement('span');
            hoverSlot.className = 'week-hover-slot';
            hoverSlot.hidden = true;
            lane.appendChild(hoverSlot);

            function horarioDoPonteiro(event) {
                const offset = event.clientY - lane.getBoundingClientRect().top;
                const rawMinute = 420 + (offset * 60 / 64);
                return Math.max(420, Math.min(1245, Math.round(rawMinute / 15) * 15));
            }

            function mostrarHorario(event) {
                weekTimeline.querySelectorAll('.week-hover-slot').forEach((item) => {
                    if (item !== hoverSlot) item.hidden = true;
                });
                const rounded = horarioDoPonteiro(event);
                const horario = `${String(Math.floor(rounded / 60)).padStart(2, '0')}:${String(rounded % 60).padStart(2, '0')}`;
                hoverSlot.style.setProperty('--hover-top', `${(rounded - 420) * 64 / 60}px`);
                hoverSlot.textContent = `${horario} · Criar compromisso`;
                hoverSlot.hidden = false;
            }

            slot.addEventListener('mouseenter', mostrarHorario);
            slot.addEventListener('mousemove', mostrarHorario);
            slot.addEventListener('mouseleave', () => { hoverSlot.hidden = true; });
            lane.addEventListener('mouseleave', () => { hoverSlot.hidden = true; });
            slot.addEventListener('click', (event) => {
                event.preventDefault();
                const rounded = horarioDoPonteiro(event);
                const horario = `${String(Math.floor(rounded / 60)).padStart(2, '0')}:${String(rounded % 60).padStart(2, '0')}`;
                const target = new URL(slot.href, window.location.origin);
                target.searchParams.set('horario', horario);
                window.location.href = target.toString();
            });
        });
        weekTimeline.addEventListener('mouseleave', esconderDestaquesSemana);
    }

    const notifyCheckbox = document.getElementById('taskNotify');
    const notificationPermission = document.getElementById('notificationPermission');
    const notificationTest = document.getElementById('notificationTest');
    function atualizarEstadoNotificacao() {
        if (!notificationPermission) return;
        if (!('Notification' in window)) {
            notificationPermission.textContent = 'Este navegador não oferece notificações. O CRM exibirá o alerta dentro da página.';
        } else if (Notification.permission === 'granted') {
            notificationPermission.textContent = 'Permissão concedida: o alerta aparecerá no CRM e como notificação do navegador.';
        } else if (Notification.permission === 'denied') {
            notificationPermission.textContent = 'Notificações do navegador estão bloqueadas. O lembrete aparecerá dentro do CRM.';
        } else {
            notificationPermission.textContent = 'Ao marcar esta opção, permita as notificações quando o navegador solicitar.';
        }
    }

    async function pedirPermissaoNotificacao() {
        if (!('Notification' in window) || Notification.permission !== 'default') return;
        await Notification.requestPermission();
        atualizarEstadoNotificacao();
    }

    if (notifyCheckbox) {
        notifyCheckbox.addEventListener('change', () => {
            if (notifyCheckbox.checked) pedirPermissaoNotificacao();
        });
    }
    atualizarEstadoNotificacao();
    if (notificationTest) {
        notificationTest.addEventListener('click', async () => {
            await pedirPermissaoNotificacao();
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification('CRM: teste de notificação', { body: 'As notificações do navegador estão funcionando.', icon: '/static/favicon.svg' });
                mostrarAvisoCopiado('Teste enviado também como notificação do navegador.');
            } else {
                mostrarAvisoCopiado('O navegador bloqueou o alerta externo. O CRM continuará exibindo os lembretes dentro da página.', 'erro');
            }
        });
    }

    const agendaNavLink = document.querySelector('[data-agenda-nav]');
    const agendaNavAlert = document.querySelector('[data-agenda-alert]');
    function atualizarIndicadorAgenda(ativo, total = 0) {
        if (!agendaNavLink || !agendaNavAlert || typeof ativo !== 'boolean') return;
        const quantidade = Number(total || 0);
        agendaNavAlert.hidden = !ativo;
        const descricao = ativo
            ? `Agenda: ${quantidade} compromisso(s) com horário próximo(s) ou vencido(s)`
            : 'Agenda';
        agendaNavLink.title = descricao;
        agendaNavLink.setAttribute('aria-label', descricao);
    }

    async function verificarLembretesAgenda() {
        if (document.hidden) return;
        try {
            const response = await fetch('/api/agenda/lembretes', { headers: { Accept: 'application/json' } });
            if (!response.ok) return;
            const payload = await response.json();
            const lembretes = Array.isArray(payload.lembretes) ? payload.lembretes : [];
            atualizarIndicadorAgenda(Boolean(payload.agenda_alerta_ativo), payload.agenda_alerta_total);
            if (!lembretes.length) return;
            const ids = [];
            lembretes.forEach((lembrete) => {
                const vinculo = lembrete.proposta_nome ? ` — ${lembrete.proposta_nome}` : '';
                const mensagem = `Lembrete ${lembrete.horario}: ${lembrete.titulo}${vinculo}`;
                mostrarAvisoCopiado(mensagem, 'erro');
                if ('Notification' in window && Notification.permission === 'granted') {
                    new Notification(`CRM: ${lembrete.titulo}`, {
                        body: `${lembrete.horario}${vinculo}${lembrete.descricao ? `\n${lembrete.descricao}` : ''}`,
                        icon: '/static/favicon.svg', tag: `crm-lembrete-${lembrete.id}`,
                    });
                }
                ids.push(lembrete.id);
            });
            await fetch('/api/agenda/lembretes/confirmar', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids }),
            });
        } catch (error) {
            console.warn('Não foi possível verificar os lembretes da agenda.', error);
        }
    }
    verificarLembretesAgenda();
    window.setInterval(verificarLembretesAgenda, 30000);

    const notificationMenu = document.querySelector('.notification-menu');
    if (notificationMenu) {
        document.addEventListener('click', (event) => {
            if (!notificationMenu.contains(event.target)) notificationMenu.open = false;
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') notificationMenu.open = false;
        });
    }

    const funnelFilterMenu = document.getElementById('funnelFilterMenu');
    if (funnelFilterMenu) {
        document.addEventListener('click', (event) => {
            if (!funnelFilterMenu.contains(event.target)) funnelFilterMenu.open = false;
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && funnelFilterMenu.open) {
                funnelFilterMenu.open = false;
                funnelFilterMenu.querySelector('summary')?.focus();
            }
        });
    }

    const notificationPanelContent = document.getElementById('notificationPanelContent');
    const notificationBadge = document.querySelector('.notification-badge');
    async function atualizarNotificacoesAutomaticamente() {
        if (!notificationPanelContent || document.hidden) return;
        try {
            const url = new URL('/api/notificacoes', window.location.origin);
            url.searchParams.set('origem', `${window.location.pathname}${window.location.search}`);
            const response = await fetch(url, { headers: { Accept: 'application/json' } });
            if (!response.ok) return;
            const payload = await response.json();
            notificationPanelContent.innerHTML = payload.html || '';
            if (notificationBadge) {
                notificationBadge.textContent = String(payload.total || '');
                notificationBadge.hidden = !payload.total;
            }
        } catch (error) {
            console.warn('Não foi possível atualizar as notificações.', error);
        }
    }
    window.setInterval(atualizarNotificacoesAutomaticamente, 15000);
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            verificarLembretesAgenda();
            atualizarNotificacoesAutomaticamente();
        }
    });

    document.querySelectorAll('.cpf-mask').forEach((input) => {
        input.addEventListener('input', () => {
            let v = input.value.replace(/\D/g, '').slice(0, 11);
            v = v.replace(/(\d{3})(\d)/, '$1.$2');
            v = v.replace(/(\d{3})(\d)/, '$1.$2');
            v = v.replace(/(\d{3})(\d{1,2})$/, '$1-$2');
            input.value = v;
        });
    });

    // v32: sugestões de cliente por CPF + matrícula.
    const cpfField = document.querySelector('input[name="cpf"]');
    const matriculaField = document.querySelector('input[name="nb_matricula"]');
    const matriculaSelect = document.getElementById('cliente-matricula-select');
    const clienteAjuda = document.querySelector('.cliente-sugestao-ajuda');

    function setFieldValue(name, value, preservarPreenchido = false) {
        const field = document.querySelector(`[name="${name}"]`);
        if (field && value !== undefined && value !== null) {
            if (preservarPreenchido && String(field.value || '').trim()) return;
            field.value = value;
        }
    }

    function preencherDadosCliente(cliente, novaMatricula = false, preservarMatricula = false, preenchimentoAutomatico = false) {
        if (!cliente) return;
        setFieldValue('nome', cliente.nome || '', preenchimentoAutomatico);
        setFieldValue('nascimento', cliente.nascimento || '', preenchimentoAutomatico);
        // Nunca substitui um telefone que já foi digitado nesta proposta.
        setFieldValue('telefone', cliente.telefone || '', true);
        if (!novaMatricula) setFieldValue('especie', cliente.especie || '', preenchimentoAutomatico);
        setFieldValue('tipo_cliente', cliente.tipo_cliente || '', preenchimentoAutomatico);
        setFieldValue('endereco', cliente.endereco || '', preenchimentoAutomatico);
        setFieldValue('dados_bancarios', cliente.dados_bancarios || '', preenchimentoAutomatico);
        if (!novaMatricula) {
            setFieldValue('nb_matricula', cliente.nb_matricula || '');
            setFieldValue('beneficio_bloqueado', cliente.beneficio_bloqueado || 'NÃO');
        } else if (matriculaField && !preservarMatricula) {
            matriculaField.value = '';
            matriculaField.focus();
        }
        document.dispatchEvent(new CustomEvent('crm:cliente-reaproveitado', {
            detail: { cliente, novaMatricula, matriculaPreservada: preservarMatricula },
        }));
    }

    function clienteCorrespondente(clientes) {
        const matriculaInformada = normalizarMatricula(matriculaField?.value);
        if (matriculaInformada) {
            const correspondencia = clientes.find(
                (cliente) => normalizarMatricula(cliente.nb_matricula) === matriculaInformada,
            );
            if (correspondencia) return correspondencia;
            // Um NB informado que não existe é uma nova matrícula. Nunca o
            // substitui automaticamente pelo único benefício antigo do CPF.
            return null;
        }
        return clientes.length === 1 ? clientes[0] : null;
    }

    let clientesCPFCache = [];
    let ultimaConsultaClientes = 0;

    function montarSelectMatriculas(clientes) {
        matriculaSelect.innerHTML = '';

        clientes.forEach((cliente, index) => {
            const option = document.createElement('option');
            option.value = String(index);
            option.textContent = cliente.label || `Matrícula ${index + 1}`;
            matriculaSelect.appendChild(option);
        });

        const nova = document.createElement('option');
        nova.value = 'nova';
        nova.textContent = 'Nova matrícula';
        matriculaSelect.appendChild(nova);
    }

    async function buscarClientesPorCpf() {
        if (!cpfField || !matriculaSelect) return;
        const consultaAtual = ++ultimaConsultaClientes;
        const digits = cpfField.value.replace(/\D/g, '');

        matriculaSelect.classList.add('hidden');
        matriculaSelect.innerHTML = '';
        clientesCPFCache = [];

        if (digits.length !== 11) {
            if (clienteAjuda) clienteAjuda.textContent = 'Digite o CPF para consultar matrículas já cadastradas.';
            return;
        }

        try {
            const response = await fetch(`/api/clientes/por-cpf?cpf=${encodeURIComponent(cpfField.value)}`);
            if (!response.ok) throw new Error('Falha ao consultar clientes.');
            const clientes = await response.json();

            // Evita duplicação quando blur/change disparam consultas quase ao mesmo tempo.
            if (consultaAtual !== ultimaConsultaClientes) return;

            clientesCPFCache = clientes;

            if (!clientesCPFCache.length) {
                if (clienteAjuda) clienteAjuda.textContent = 'Nenhum cliente cadastrado para este CPF. Cadastre normalmente.';
                document.dispatchEvent(new CustomEvent('crm:cliente-nao-localizado'));
                return;
            }

            montarSelectMatriculas(clientesCPFCache);
            matriculaSelect.classList.remove('hidden');
            const cliente = clienteCorrespondente(clientesCPFCache);
            if (cliente) {
                const index = clientesCPFCache.indexOf(cliente);
                matriculaSelect.value = String(index);
                preencherDadosCliente(cliente, false, false, true);
                if (clienteAjuda) clienteAjuda.textContent = 'Cliente encontrado · cadastro reaproveitado automaticamente.';
            } else if (normalizarMatricula(matriculaField?.value)) {
                // Reaproveita somente dados compartilhados, mantendo o novo NB e
                // os dados do benefício/proposta que já chegaram da importação.
                matriculaSelect.value = 'nova';
                preencherDadosCliente(clientesCPFCache[0], true, true, true);
                if (clienteAjuda) clienteAjuda.textContent = 'Cliente encontrado · nova matrícula mantida.';
            } else {
                if (clienteAjuda) clienteAjuda.textContent = 'Cliente encontrado · selecione a matrícula para reaproveitar o cadastro.';
                document.dispatchEvent(new CustomEvent('crm:clientes-localizados', {
                    detail: { total: clientesCPFCache.length },
                }));
            }
        } catch (error) {
            console.error(error);
            if (consultaAtual === ultimaConsultaClientes && clienteAjuda) clienteAjuda.textContent = 'Não foi possível consultar matrículas agora.';
        }
    }

    if (cpfField && matriculaSelect) {
        cpfField.addEventListener('blur', buscarClientesPorCpf);
        cpfField.addEventListener('change', buscarClientesPorCpf);
        if (cpfField.value.replace(/\D/g, '').length === 11) {
            buscarClientesPorCpf();
        }

        matriculaSelect.addEventListener('change', () => {
            const value = matriculaSelect.value;
            if (value === 'nova') {
                const base = clientesCPFCache[0];
                const manterMatricula = Boolean(normalizarMatricula(matriculaField?.value))
                    && !clientesCPFCache.some(
                        (cliente) => normalizarMatricula(cliente.nb_matricula) === normalizarMatricula(matriculaField.value),
                    );
                preencherDadosCliente(base, true, manterMatricula, false);
                if (clienteAjuda) clienteAjuda.textContent = 'Cliente encontrado · nova matrícula';
                return;
            }
            const cliente = clientesCPFCache[Number(value)];
            if (cliente) {
                preencherDadosCliente(cliente, false);
                if (clienteAjuda) clienteAjuda.textContent = 'Cliente encontrado · dados preenchidos automaticamente.';
            }
        });
    }


    function parseMoneyInputValue(value) {
        let text = String(value || '').replace('R$', '').replace(/\s/g, '').trim();
        if (!text) return 0;

        // Quando o usuário digita 5000, interpretar como 5000,00 e não 50,00.
        // Quando digita 5.000, interpretar como milhar brasileiro.
        // Quando digita 5000,50 ou 5.000,50, respeitar a vírgula decimal.
        if (text.includes(',')) {
            text = text.replace(/\./g, '').replace(',', '.');
            return Number(text) || 0;
        }

        if (/^\d{1,3}(\.\d{3})+$/.test(text)) {
            text = text.replace(/\./g, '');
            return Number(text) || 0;
        }

        return Number(text.replace(',', '.')) || 0;
    }

    document.querySelectorAll('.money-mask').forEach((input) => {
        input.addEventListener('blur', () => {
            const number = parseMoneyInputValue(input.value);
            input.value = number.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        });
    });



    document.querySelectorAll('.percent-mask').forEach((input) => {
        input.addEventListener('blur', () => {
            let value = input.value.trim().replace('%', '').replace(',', '.');
            if (!value) return;
            const number = Number(value);
            if (Number.isNaN(number)) {
                input.value = '';
                return;
            }
            input.value = String(number).replace('.', ',');
        });
    });

    function parseBRNumber(value) {
        const text = String(value || '').replace('R$', '').replace('%', '').trim();
        if (!text) return 0;
        return Number(text.replace(/\./g, '').replace(',', '.')) || 0;
    }

    function parsePercentInputValue(value) {
        let text = String(value || '').replace('%', '').replace(/\s/g, '').trim();
        if (!text) return 0;
        if (text.includes(',')) {
            text = text.replace(/\./g, '').replace(',', '.');
        }
        return Number(text) || 0;
    }

    function formatBRL(number) {
        return Number(number || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    // Calcula comissão em qualquer formulário/tela que tenha Valor + % comissão + Comissão.
    // Isso cobre os formulários administrativos de edição da proposta.
    function calcularComissaoNoEscopo(escopo, nomes = ['troco', 'comissao_percentual', 'comissao']) {
        if (!escopo) return;
        const [nomeValor, nomePercentual, nomeComissao] = nomes;
        const trocoInput = escopo.querySelector(`input[name="${nomeValor}"]`);
        const percentualInput = escopo.querySelector(`input[name="${nomePercentual}"]`);
        const comissaoInput = escopo.querySelector(`input[name="${nomeComissao}"]`);
        if (!trocoInput || !percentualInput || !comissaoInput) return;

        const percentualTexto = percentualInput.value.trim();
        if (!percentualTexto) return;

        const valor = parseBRNumber(trocoInput.value);
        const percentual = parsePercentInputValue(percentualTexto);
        const comissao = valor * (percentual / 100);
        comissaoInput.value = formatBRL(comissao);
    }

    document.querySelectorAll('form').forEach((form) => {
        [
            ['troco', 'comissao_percentual', 'comissao'],
            ['refin_troco', 'refin_comissao_percentual', 'refin_comissao'],
        ].forEach((nomes) => {
            const [nomeValor, nomePercentual, nomeComissao] = nomes;
            const trocoInput = form.querySelector(`input[name="${nomeValor}"]`);
            const percentualInput = form.querySelector(`input[name="${nomePercentual}"]`);
            const comissaoInput = form.querySelector(`input[name="${nomeComissao}"]`);

            if (!trocoInput || !percentualInput || !comissaoInput) return;

            percentualInput.addEventListener('input', () => calcularComissaoNoEscopo(form, nomes));
            percentualInput.addEventListener('change', () => calcularComissaoNoEscopo(form, nomes));
            percentualInput.addEventListener('blur', () => calcularComissaoNoEscopo(form, nomes));
            trocoInput.addEventListener('input', () => {
                if (percentualInput.value.trim()) calcularComissaoNoEscopo(form, nomes);
            });
            trocoInput.addEventListener('change', () => calcularComissaoNoEscopo(form, nomes));
            trocoInput.addEventListener('blur', () => calcularComissaoNoEscopo(form, nomes));
        });
    });

    document.querySelectorAll('form').forEach((form) => {
        const reutilizarInput = form.querySelector('[data-refin-percent-reuse] input[type="checkbox"]');
        const percentualPortInput = form.querySelector('input[name="comissao_percentual"]');
        const percentualRefinInput = form.querySelector('input[name="refin_comissao_percentual"]');
        if (!reutilizarInput || !percentualPortInput || !percentualRefinInput) return;

        const percentualRefinLabel = percentualRefinInput.closest('label');
        const sincronizarPercentuais = () => {
            const reutilizar = reutilizarInput.checked;
            percentualRefinInput.readOnly = reutilizar;
            percentualRefinLabel?.classList.toggle('refin-percent-reused', reutilizar);
            if (!reutilizar) return;

            percentualRefinInput.value = percentualPortInput.value;
            calcularComissaoNoEscopo(
                form,
                ['refin_troco', 'refin_comissao_percentual', 'refin_comissao'],
            );
        };

        reutilizarInput.checked = Math.abs(
            parsePercentInputValue(percentualPortInput.value)
            - parsePercentInputValue(percentualRefinInput.value)
        ) < 0.0001;
        reutilizarInput.addEventListener('change', sincronizarPercentuais);
        ['input', 'change', 'blur'].forEach((evento) => {
            percentualPortInput.addEventListener(evento, () => {
                if (reutilizarInput.checked) sincronizarPercentuais();
            });
        });
        sincronizarPercentuais();
    });

    function mostrarAvisoCopiado(mensagem, tipo = 'ok') {
        const aviso = document.createElement('div');
        aviso.textContent = mensagem;
        aviso.className = `crm-toast toast-copiado ${tipo === 'erro' ? 'toast-erro' : 'toast-ok'}`;
        document.body.appendChild(aviso);
        setTimeout(() => aviso.remove(), tipo === 'erro' ? 3200 : 1800);
    }

    document.querySelectorAll('[data-toast="true"]').forEach((alerta, index) => {
        alerta.classList.add('crm-toast');
        document.body.appendChild(alerta);
        alerta.style.marginTop = `${index * 58}px`;
        setTimeout(() => alerta.remove(), 3200);
    });

    document.querySelectorAll('.alerts').forEach((alerts) => {
        if (!alerts.querySelector('.alert')) alerts.remove();
    });

    function copiarTextoFallback(texto, button = null) {
        const campoTemporario = document.createElement('textarea');
        campoTemporario.value = texto;
        campoTemporario.setAttribute('readonly', '');
        campoTemporario.style.position = 'fixed';
        campoTemporario.style.left = '-9999px';
        campoTemporario.style.top = '0';

        document.body.appendChild(campoTemporario);
        campoTemporario.focus();
        campoTemporario.select();
        campoTemporario.setSelectionRange(0, campoTemporario.value.length);

        try {
            const copiou = document.execCommand('copy');
            if (copiou) {
                if (button) {
                    const original = button.innerHTML;
                    button.innerHTML = '<i class="bi bi-check-circle" aria-hidden="true"></i><span>Copiado</span>';
                    setTimeout(() => button.innerHTML = original, 1300);
                }
                mostrarAvisoCopiado('Copiado!');
            } else {
                alert('Não foi possível copiar automaticamente. Texto: ' + texto);
            }
        } catch (error) {
            alert('Não foi possível copiar automaticamente. Texto: ' + texto);
        } finally {
            document.body.removeChild(campoTemporario);
        }
    }

    function copiarTexto(texto, button = null) {
        if (!texto) {
            alert('Nada para copiar.');
            return;
        }

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(texto)
                .then(() => {
                    if (button) {
                        const original = button.innerHTML;
                        button.innerHTML = '<i class="bi bi-check-circle" aria-hidden="true"></i><span>Copiado</span>';
                        setTimeout(() => button.innerHTML = original, 1300);
                    }
                    mostrarAvisoCopiado('Copiado!');
                })
                .catch(() => copiarTextoFallback(texto, button));
        } else {
            copiarTextoFallback(texto, button);
        }
    }

    document.querySelectorAll('.copy-btn').forEach((button) => {
        button.addEventListener('click', () => {
            const alvo = button.dataset.copyTarget
                ? document.querySelector(button.dataset.copyTarget)
                : null;
            const texto = alvo ? (alvo.innerText || alvo.textContent || '') : (button.dataset.copy || '');
            copiarTexto(texto, button);
        });
    });

    let draggedCard = null;
    const funilContextKey = 'crmFunilContext';

    function funilUrlSemDestaque() {
        const url = new URL(window.location.href);
        url.searchParams.delete('destaque_proposta');
        return `${url.pathname}${url.search}`;
    }

    function limparDestaqueDaUrl() {
        const url = new URL(window.location.href);
        if (!url.searchParams.has('destaque_proposta')) return;
        url.searchParams.delete('destaque_proposta');
        const limpa = `${url.pathname}${url.search}${url.hash}`;
        window.history.replaceState({}, '', limpa);
    }

    function salvarContextoFunil(card = null) {
        const kanban = document.querySelector('.kanban[data-modulo="funil"]');
        if (!kanban) return;

        const colunas = {};
        kanban.querySelectorAll('.kanban-cards[data-status]').forEach((area) => {
            colunas[area.dataset.status] = area.scrollTop || 0;
        });

        try {
            sessionStorage.setItem(funilContextKey, JSON.stringify({
                url: funilUrlSemDestaque(),
                at: Date.now(),
                pageX: window.scrollX || 0,
                pageY: window.scrollY || 0,
                kanbanX: kanban.scrollLeft || 0,
                colunas,
                propostaId: card?.dataset.propostaId || '',
            }));
        } catch (error) {
            // Se o navegador bloquear sessionStorage, o CRM apenas segue sem restaurar posição.
        }
    }

    function destacarCardRecemSalvo(card) {
        if (!card) return;
        card.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
        card.classList.add('card-recently-saved');
        setTimeout(() => card.classList.remove('card-recently-saved'), 3500);
    }

    function propostaSelector(propostaId) {
        const seguro = String(propostaId || '').replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        return `[data-proposta-id="${seguro}"]`;
    }

    function destacarCardDaPaginaAtual() {
        const params = new URLSearchParams(window.location.search);
        const destaqueId = params.get('destaque_proposta');
        if (!destaqueId) return;
        const card = document.querySelector(`.today-card${propostaSelector(destaqueId)}`) || document.querySelector(propostaSelector(destaqueId));
        if (card) destacarCardRecemSalvo(card);
        limparDestaqueDaUrl();
    }

    function restaurarContextoFunil() {
        const kanban = document.querySelector('.kanban[data-modulo="funil"]');
        if (!kanban) return;

        const params = new URLSearchParams(window.location.search);
        const destaqueId = params.get('destaque_proposta');
        let estado = null;

        try {
            estado = JSON.parse(sessionStorage.getItem(funilContextKey) || 'null');
        } catch (error) {
            estado = null;
        }

        const estadoRecente = estado && (Date.now() - Number(estado.at || 0)) < 30 * 60 * 1000;
        const mesmaUrl = estadoRecente && estado.url === funilUrlSemDestaque();
        const propostaIdContexto = mesmaUrl ? estado.propostaId : '';
        const propostaIdDestaque = destaqueId || propostaIdContexto;

        if (mesmaUrl) {
            requestAnimationFrame(() => {
                window.scrollTo(estado.pageX || 0, estado.pageY || 0);
                kanban.scrollLeft = estado.kanbanX || 0;
                kanban.querySelectorAll('.kanban-cards[data-status]').forEach((area) => {
                    area.scrollTop = estado.colunas?.[area.dataset.status] || 0;
                });
            });
            try { sessionStorage.removeItem(funilContextKey); } catch (error) {}
        }

        if (propostaIdDestaque) {
            const card = kanban.querySelector(`.kanban-card${propostaSelector(propostaIdDestaque)}`);
            if (card) {
                setTimeout(() => destacarCardRecemSalvo(card), mesmaUrl ? 120 : 0);
            }
            if (destaqueId) limparDestaqueDaUrl();
        }
    }

    document.querySelectorAll('.kanban[data-modulo="funil"] .kanban-card a[href]').forEach((link) => {
        link.addEventListener('click', () => {
            salvarContextoFunil(link.closest('.kanban-card'));
        });
    });

    const abreviarNomesLongosDosCards = () => {
        const conectores = new Set(['da', 'das', 'de', 'do', 'dos', 'e']);
        document.querySelectorAll('.kanban[data-modulo="funil"] [data-card-client-name]').forEach((link) => {
            const nomeCompleto = (link.dataset.cardClientName || '').trim();
            if (!nomeCompleto) return;

            link.textContent = nomeCompleto;
            link.title = nomeCompleto;
            link.setAttribute('aria-label', nomeCompleto);
            if (link.scrollWidth <= link.clientWidth) return;

            const palavras = nomeCompleto.split(/\s+/);
            const indices = palavras
                .map((palavra, indice) => ({ palavra, indice }))
                .filter(({ indice }) => indice > 0)
                .sort((a, b) => {
                    const aConector = conectores.has(a.palavra.toLocaleLowerCase('pt-BR'));
                    const bConector = conectores.has(b.palavra.toLocaleLowerCase('pt-BR'));
                    if (aConector !== bConector) return aConector ? 1 : -1;
                    return b.indice - a.indice;
                })
                .map(({ indice }) => indice);

            for (const indice of indices) {
                const palavra = palavras[indice];
                palavras[indice] = palavra.slice(0, 1).toLocaleUpperCase('pt-BR');
                link.textContent = palavras.join(' ');
                if (link.scrollWidth <= link.clientWidth) break;
            }
        });
    };

    abreviarNomesLongosDosCards();
    let quadroNomesResizeFrame;
    window.addEventListener('resize', () => {
        window.cancelAnimationFrame(quadroNomesResizeFrame);
        quadroNomesResizeFrame = window.requestAnimationFrame(abreviarNomesLongosDosCards);
    });

    restaurarContextoFunil();
    destacarCardDaPaginaAtual();

    function updateTodayCount(name, delta) {
        document.querySelectorAll(`[data-today-count="${name}"]`).forEach((el) => {
            const current = Number(el.textContent || 0);
            el.textContent = String(Math.max(0, current + delta));
        });
    }

    function refreshTodaySection(section) {
        if (!section) return;
        const count = section.querySelectorAll('.today-card').length;
        const countEl = section.querySelector('[data-section-count]');
        if (countEl) countEl.textContent = String(count);
        const grid = section.querySelector('.today-card-grid');
        if (grid && count === 0 && !grid.querySelector('[data-empty-message]')) {
            const empty = document.createElement('p');
            empty.className = 'empty small';
            empty.dataset.emptyMessage = 'true';
            empty.textContent = section.dataset.todaySection === 'verificar'
                ? 'Nenhuma proposta para verificar.'
                : 'Nenhuma proposta nesta seção.';
            grid.appendChild(empty);
        }
    }

    function setTodayCardVerified(card, statusText) {
        const dot = card.querySelector('.verification-dot');
        if (dot) {
            dot.classList.remove('dot-pending');
            dot.classList.add('dot-ok');
            dot.title = statusText || 'Verificado hoje';
        }
        const form = card.querySelector('.today-verify-form');
        if (form) {
            const label = document.createElement('span');
            label.className = 'today-verified-label';
            label.textContent = statusText || 'Verificada hoje';
            form.replaceWith(label);
        }
    }

    document.querySelectorAll('.today-verify-form').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const button = form.querySelector('button');
            if (button) button.disabled = true;

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'fetch' },
                    body: new FormData(form),
                });
                const payload = await response.json();
                if (!response.ok || payload.success === false) {
                    throw new Error(payload.message || 'Não foi possível marcar como verificada.');
                }

                const params = new URLSearchParams(window.location.search);
                const somentePendentes = params.get('verificacao') === 'pendente';
                let removidasVerificar = 0;
                let propostasAtualizadas = 0;
                let propostasRemovidas = 0;
                const propostaIds = Array.isArray(payload.proposta_ids) && payload.proposta_ids.length
                    ? payload.proposta_ids
                    : [payload.proposta_id];
                propostaIds.forEach((propostaId) => {
                    const cardsDaProposta = Array.from(document.querySelectorAll(propostaSelector(propostaId)));
                    cardsDaProposta.forEach((card) => {
                        setTodayCardVerified(card, payload.status_texto);
                        if (somentePendentes || card.dataset.section === 'verificar') {
                            const section = card.closest('[data-today-section]');
                            if (card.dataset.section === 'verificar') removidasVerificar += 1;
                            card.remove();
                            refreshTodaySection(section);
                        }
                    });
                    if (cardsDaProposta.length) {
                        propostasAtualizadas += 1;
                    }
                    if (cardsDaProposta.length && !document.querySelector(propostaSelector(propostaId))) {
                        propostasRemovidas += 1;
                    }
                });
                if (removidasVerificar) {
                    updateTodayCount('verificar', -removidasVerificar);
                }
                if (propostasRemovidas) {
                    updateTodayCount('total', -propostasRemovidas);
                }
                if (propostasAtualizadas) {
                    updateTodayCount('verificadas', propostasAtualizadas);
                    updateTodayCount('pendentes', -propostasAtualizadas);
                }
                mostrarAvisoCopiado(payload.message || 'Verificação diária atualizada.');
            } catch (error) {
                console.error(error);
                if (button) button.disabled = false;
                mostrarAvisoCopiado(error.message || 'Não foi possível marcar como verificada.', 'erro');
            }
        });
    });

    document.querySelectorAll('.today-contact-form').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const button = form.querySelector('button');
            const card = form.closest('.today-card');
            const section = card?.closest('[data-today-section]');
            if (button) button.disabled = true;

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'fetch' },
                    body: new FormData(form),
                });
                const payload = await response.json();
                if (!response.ok || payload.success === false) {
                    throw new Error(payload.message || 'Não foi possível registrar o contato.');
                }

                const lastInteraction = card?.querySelector('[data-last-interaction]');
                if (lastInteraction) lastInteraction.textContent = `Última interação: ${payload.ultima_interacao || 'Hoje'}`;

                const label = document.createElement('span');
                label.className = 'today-verified-label';
                label.textContent = 'Contatado hoje';
                form.replaceWith(label);

                updateTodayCount('interacoes_hoje', 1);
                updateTodayCount('pendentes', -1);

                const params = new URLSearchParams(window.location.search);
                const somentePendentes = params.get('verificacao') === 'pendente';
                if (card && (somentePendentes || card.dataset.section === 'paradas')) {
                    const sectionKey = card.dataset.section;
                    card.remove();
                    refreshTodaySection(section);
                    updateTodayCount('total', -1);
                    if (sectionKey === 'paradas') updateTodayCount('paradas', -1);
                }

                mostrarAvisoCopiado(payload.message || 'Contato registrado.');
            } catch (error) {
                console.error(error);
                if (button) button.disabled = false;
                mostrarAvisoCopiado(error.message || 'Não foi possível registrar o contato.', 'erro');
            }
        });
    });

    function updateAgendaCount(name, delta) {
        document.querySelectorAll(`[data-agenda-count="${name}"]`).forEach((el) => {
            const current = Number(el.textContent || 0);
            el.textContent = String(Math.max(0, current + delta));
        });
    }

    function refreshAgendaSection(section) {
        if (!section) return;
        const count = section.querySelectorAll('.agenda-item').length;
        const countEl = section.querySelector('[data-agenda-section-count]');
        if (countEl) countEl.textContent = String(count);
        const list = section.querySelector('.agenda-list');
        if (list && count === 0 && !list.querySelector('[data-empty-message]')) {
            const empty = document.createElement('p');
            empty.className = 'empty small';
            empty.dataset.emptyMessage = 'true';
            empty.textContent = 'Nenhuma proposta nesta seção.';
            list.appendChild(empty);
        }
    }

    function agendaCountName(sectionKey) {
        if (sectionKey === 'agenda_atrasadas') return 'atrasadas';
        if (sectionKey === 'agenda_hoje') return 'hoje';
        if (sectionKey === 'agenda_proximas') return 'proximas';
        if (sectionKey === 'agenda_concluidas') return 'concluidas_hoje';
        return '';
    }

    document.querySelectorAll('.agenda-action-form, .agenda-delay-form').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const item = form.closest('.agenda-item');
            const section = item?.closest('[data-agenda-section]');
            const button = form.querySelector('button');
            if (button) button.disabled = true;
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'fetch' },
                    body: new FormData(form),
                });
                const payload = await response.json();
                if (!response.ok || payload.success === false) {
                    throw new Error(payload.message || 'Não foi possível atualizar a tarefa.');
                }
                if (item) item.remove();
                refreshAgendaSection(section);
                const countName = agendaCountName(section?.dataset.agendaSection || '');
                if (countName) updateAgendaCount(countName, -1);
                if (payload.status === 'concluida') updateAgendaCount('concluidas_hoje', 1);
                atualizarIndicadorAgenda(payload.agenda_alerta_ativo, payload.agenda_alerta_total);
                mostrarAvisoCopiado(payload.message || 'Tarefa atualizada.');
            } catch (error) {
                console.error(error);
                if (button) button.disabled = false;
                mostrarAvisoCopiado(error.message || 'Não foi possível atualizar a tarefa.', 'erro');
            }
        });
    });

    document.querySelectorAll('.agenda-delete-form').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (!window.confirm('Excluir esta tarefa?')) return;
            const item = form.closest('.agenda-item');
            const section = item?.closest('[data-agenda-section]');
            const button = form.querySelector('button');
            if (button) button.disabled = true;
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'fetch' },
                    body: new FormData(form),
                });
                const payload = await response.json();
                if (!response.ok || payload.success === false) {
                    throw new Error(payload.message || 'Não foi possível excluir a tarefa.');
                }
                if (item) item.remove();
                refreshAgendaSection(section);
                const countName = agendaCountName(section?.dataset.agendaSection || '');
                if (countName) updateAgendaCount(countName, -1);
                atualizarIndicadorAgenda(payload.agenda_alerta_ativo, payload.agenda_alerta_total);
                mostrarAvisoCopiado(payload.message || 'Tarefa excluída.');
            } catch (error) {
                console.error(error);
                if (button) button.disabled = false;
                mostrarAvisoCopiado(error.message || 'Não foi possível excluir a tarefa.', 'erro');
            }
        });
    });

    const taskLinkBox = document.querySelector('.task-link-box');
    if (taskLinkBox) {
        const searchInput = document.getElementById('taskProposalSearch');
        const results = document.getElementById('taskProposalResults');
        const propostaInput = document.getElementById('taskPropostaId');
        const selected = document.getElementById('taskSelectedProposal');
        const clearButton = document.getElementById('clearTaskProposal');
        const searchUrl = taskLinkBox.dataset.propostaSearchUrl;
        let timer = null;

        function escapeHtmlTask(value) {
            return String(value || '')
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#039;');
        }

        function hideTaskResults() {
            if (!results) return;
            results.hidden = true;
            results.innerHTML = '';
        }

        function selectTaskProposal(item) {
            if (propostaInput) propostaInput.value = item.id || '';
            if (selected) selected.textContent = `${item.nome || 'Proposta'}${item.cpf ? ' · ' + item.cpf : ''}`;
            hideTaskResults();
        }

        if (clearButton) {
            clearButton.addEventListener('click', () => {
                if (propostaInput) propostaInput.value = '';
                if (selected) selected.textContent = 'Nenhuma proposta vinculada.';
                if (searchInput) searchInput.value = '';
                hideTaskResults();
            });
        }

        if (searchInput && results && searchUrl) {
            searchInput.addEventListener('input', () => {
                clearTimeout(timer);
                const q = searchInput.value.trim();
                if (q.length < 2) {
                    hideTaskResults();
                    return;
                }
                timer = setTimeout(async () => {
                    try {
                        const response = await fetch(`${searchUrl}?q=${encodeURIComponent(q)}`);
                        if (!response.ok) throw new Error('Falha ao buscar proposta.');
                        const items = await response.json();
                        if (!items.length) {
                            results.innerHTML = '<div class="quick-search-empty">Nenhuma proposta encontrada.</div>';
                            results.hidden = false;
                            return;
                        }
                        results.innerHTML = items.map((item) => `
                            <button type="button" class="task-proposal-result" data-proposta='${escapeHtmlTask(JSON.stringify(item))}'>
                                <strong>${escapeHtmlTask(item.nome)}</strong>
                                <small>${escapeHtmlTask(item.cpf || 'CPF não informado')} · ${escapeHtmlTask(item.status || '')}</small>
                                <span>${escapeHtmlTask(item.match_campo || 'Resultado')}: ${escapeHtmlTask(item.match_valor || '')}</span>
                            </button>
                        `).join('');
                        results.hidden = false;
                    } catch (error) {
                        console.error(error);
                        hideTaskResults();
                    }
                }, 180);
            });

            results.addEventListener('click', (event) => {
                const button = event.target.closest('.task-proposal-result');
                if (!button) return;
                try {
                    selectTaskProposal(JSON.parse(button.dataset.proposta || '{}'));
                } catch (error) {
                    hideTaskResults();
                }
            });
        }
    }

    function getColumn(cardsArea) {
        return cardsArea?.closest('.kanban-column') || null;
    }

    function refreshEmptyState(cardsArea) {
        if (!cardsArea) return;
        const empty = cardsArea.querySelector('[data-empty-message]');
        const hasCards = Boolean(cardsArea.querySelector('.kanban-card'));
        if (hasCards && empty) {
            empty.remove();
        } else if (!hasCards && !empty) {
            const message = document.createElement('p');
            message.className = 'empty small';
            message.dataset.emptyMessage = 'true';
            message.textContent = 'Sem propostas.';
            cardsArea.appendChild(message);
        }
    }

    function appendCard(cardsArea, card) {
        const empty = cardsArea.querySelector('[data-empty-message]');
        if (empty) empty.remove();
        cardsArea.appendChild(card);
    }

    function restoreCard(card, sourceArea, nextSibling) {
        if (nextSibling && nextSibling.parentElement === sourceArea) {
            sourceArea.insertBefore(card, nextSibling);
        } else {
            sourceArea.appendChild(card);
        }
    }

    function updateColumnCounter(column, dados = null) {
        if (!column) return;
        const countEl = column.querySelector('[data-column-count]') || column.querySelector('.column-title small');
        const commissionEl = column.querySelector('[data-column-commission]');
        if (countEl) {
            const count = dados ? dados.quantidade : column.querySelectorAll('.kanban-card').length;
            countEl.textContent = `${count} ${count === 1 ? 'operação' : 'operações'}`;
        }
        if (commissionEl && dados?.comissao) {
            commissionEl.textContent = dados.comissao;
        }
    }

    function formatarMoeda(valor) {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(valor) || 0);
    }

    function atualizarResumoEncerradas(coluna) {
        if (!coluna?.closest('.kanban[data-modulo="encerradas"]')) return;
        const cards = coluna.querySelectorAll('.encerrada-card');
        const total = Array.from(cards).reduce((soma, card) => soma + (Number(card.dataset.comissao) || 0), 0);
        updateColumnCounter(coluna);
        const comissao = coluna.querySelector('[data-column-commission]');
        if (comissao) comissao.textContent = formatarMoeda(total);
    }

    function atualizarVisualStatusEncerrada(card, destino) {
        if (!card?.classList.contains('encerrada-card')) return;
        const perdido = destino === 'Perdido / Cancelado';
        card.classList.toggle('card-paid', !perdido);
        card.classList.toggle('card-lost', perdido);
    }

    document.querySelectorAll('.encerrada-finance-form').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const card = form.closest('.encerrada-card');
            const button = form.querySelector('button[type="submit"]');
            if (!card || !button) return;
            button.disabled = true;

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'fetch' },
                    body: new FormData(form),
                });
                const payload = await response.json();
                if (!response.ok || payload.success === false) throw new Error(payload.message || 'Não foi possível atualizar os valores.');

                const comissaoVinculada = Number(card.dataset.comissaoVinculada) || 0;
                const comissaoTotal = (Number(payload.comissao_numero) || 0) + comissaoVinculada;
                card.dataset.comissao = String(comissaoTotal);
                card.querySelector('[data-finance-value]').textContent = payload.troco;
                card.querySelector('[data-finance-commission]').textContent = formatarMoeda(comissaoTotal);
                card.querySelector('[data-finance-percent]').textContent = payload.comissao_percentual;
                card.querySelector('.encerrada-finance-editor').open = false;
                atualizarResumoEncerradas(card.closest('.kanban-column'));
                card.classList.add('card-recently-saved');
                setTimeout(() => card.classList.remove('card-recently-saved'), 1400);
                mostrarAvisoCopiado(payload.message || 'Valores atualizados.');
            } catch (error) {
                console.error(error);
                mostrarAvisoCopiado(error.message || 'Não foi possível atualizar os valores.', 'erro');
            } finally {
                button.disabled = false;
            }
        });
    });

    function restoreScroll(kanban, scrollLeft, sourceArea, sourceScrollTop, targetArea, targetScrollTop) {
        requestAnimationFrame(() => {
            if (kanban) kanban.scrollLeft = scrollLeft;
            if (sourceArea) sourceArea.scrollTop = sourceScrollTop;
            if (targetArea) targetArea.scrollTop = targetScrollTop;
        });
    }

    const dragAutoScroll = {
        kanban: null,
        velocidade: 0,
        frame: null,
        ultimoTempo: 0,
    };

    function pararRolagemAutomaticaDoFunil() {
        if (dragAutoScroll.frame) cancelAnimationFrame(dragAutoScroll.frame);
        dragAutoScroll.kanban = null;
        dragAutoScroll.velocidade = 0;
        dragAutoScroll.frame = null;
        dragAutoScroll.ultimoTempo = 0;
    }

    function executarRolagemAutomaticaDoFunil(tempo) {
        const { kanban, velocidade } = dragAutoScroll;
        if (!draggedCard || !kanban || !velocidade) {
            pararRolagemAutomaticaDoFunil();
            return;
        }

        const anterior = dragAutoScroll.ultimoTempo || tempo;
        const intervalo = Math.min(32, Math.max(0, tempo - anterior));
        dragAutoScroll.ultimoTempo = tempo;
        const scrollAnterior = kanban.scrollLeft;
        kanban.scrollLeft += velocidade * intervalo;

        if (kanban.scrollLeft === scrollAnterior) {
            dragAutoScroll.velocidade = 0;
        }
        dragAutoScroll.frame = requestAnimationFrame(executarRolagemAutomaticaDoFunil);
    }

    function atualizarRolagemAutomaticaDoFunil(event) {
        if (!draggedCard) return;
        const kanban = draggedCard.closest('.kanban[data-modulo="funil"]');
        if (!kanban) return;

        const limites = kanban.getBoundingClientRect();
        const zonaDeAtivacao = Math.min(120, Math.max(72, limites.width * 0.09));
        let velocidade = 0;

        if (event.clientX <= limites.left + zonaDeAtivacao) {
            const intensidade = Math.min(1, Math.max(0, (limites.left + zonaDeAtivacao - event.clientX) / zonaDeAtivacao));
            velocidade = -(0.18 + intensidade * 0.72);
        } else if (event.clientX >= limites.right - zonaDeAtivacao) {
            const intensidade = Math.min(1, Math.max(0, (event.clientX - (limites.right - zonaDeAtivacao)) / zonaDeAtivacao));
            velocidade = 0.18 + intensidade * 0.72;
        }

        dragAutoScroll.kanban = kanban;
        dragAutoScroll.velocidade = velocidade;

        if (velocidade) {
            const passoPorEvento = Math.sign(velocidade) * (3 + Math.abs(velocidade) * 10);
            kanban.scrollLeft += passoPorEvento;
        }

        if (velocidade && !dragAutoScroll.frame) {
            dragAutoScroll.frame = requestAnimationFrame(executarRolagemAutomaticaDoFunil);
        } else if (!velocidade && dragAutoScroll.frame) {
            pararRolagemAutomaticaDoFunil();
        }
    }

    document.addEventListener('dragover', atualizarRolagemAutomaticaDoFunil);
    document.addEventListener('dragenter', atualizarRolagemAutomaticaDoFunil);
    document.addEventListener('drop', pararRolagemAutomaticaDoFunil, true);
    window.addEventListener('blur', pararRolagemAutomaticaDoFunil);

    document.querySelectorAll('.kanban-card[draggable="true"]').forEach((card) => {
        card.addEventListener('dragstart', (event) => {
            if (card.dataset.busy === 'true') {
                event.preventDefault();
                return;
            }
            draggedCard = card;
            card.classList.add('dragging');
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', card.dataset.propostaId || '');
        });

        card.addEventListener('drag', atualizarRolagemAutomaticaDoFunil);

        card.addEventListener('dragend', () => {
            pararRolagemAutomaticaDoFunil();
            card.classList.remove('dragging');
            draggedCard = null;
            document.querySelectorAll('.kanban-cards.drop-target').forEach((column) => {
                column.classList.remove('drop-target');
            });
        });
    });

    document.querySelectorAll('.kanban-cards[data-status]').forEach((cardsArea) => {
        cardsArea.addEventListener('dragover', (event) => {
            event.preventDefault();
            cardsArea.classList.add('drop-target');
        });

        cardsArea.addEventListener('dragleave', () => {
            cardsArea.classList.remove('drop-target');
        });

        cardsArea.addEventListener('drop', async (event) => {
            event.preventDefault();
            cardsArea.classList.remove('drop-target');

            const propostaId = event.dataTransfer.getData('text/plain');
            const novoStatus = cardsArea.dataset.status;
            const card = draggedCard || document.querySelector(`.kanban-card[data-proposta-id="${propostaId}"]`);

            if (!propostaId || !novoStatus || !card || card.dataset.busy === 'true') return;

            const sourceArea = card.closest('.kanban-cards');
            const statusAtual = sourceArea?.dataset.status;
            if (!sourceArea || statusAtual === novoStatus) return;

            const sourceColumn = getColumn(sourceArea);
            const targetColumn = getColumn(cardsArea);
            const nextSibling = card.nextElementSibling;
            const kanban = cardsArea.closest('.kanban');
            const kanbanScrollLeft = kanban?.scrollLeft || 0;
            const sourceScrollTop = sourceArea.scrollTop;
            const targetScrollTop = cardsArea.scrollTop;
            const modulo = kanban?.dataset.modulo || 'funil';

            const formData = new URLSearchParams();
            formData.append('status', novoStatus);
            formData.append('origem', modulo);
            formData.append('observacao', 'Movido no funil por arrastar e soltar');
            if (modulo === 'funil' && kanban?.dataset.mes) {
                formData.append('mes_funil', kanban.dataset.mes);
            }

            card.dataset.busy = 'true';
            card.classList.add('is-processing');
            card.setAttribute('draggable', 'false');
            appendCard(cardsArea, card);
            refreshEmptyState(sourceArea);
            refreshEmptyState(cardsArea);
            restoreScroll(kanban, kanbanScrollLeft, sourceArea, sourceScrollTop, cardsArea, targetScrollTop);

            try {
                const response = await fetch(`/proposta/${propostaId}/status`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                        'X-Requested-With': 'fetch'
                    },
                    body: formData.toString(),
                    redirect: 'follow'
                });

                let payload = null;
                const contentType = response.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    payload = await response.json();
                }

                const success = payload ? (payload.success ?? payload.ok) : response.ok;
                if (!response.ok || success === false) {
                    const msg = payload?.message || payload?.erro || `Falha ao mover proposta. Código: ${response.status}`;
                    throw new Error(msg);
                }

                if (modulo === 'funil' && payload?.colunas) {
                    updateColumnCounter(sourceColumn, payload.colunas.origem);
                    updateColumnCounter(targetColumn, payload.colunas.destino);
                } else {
                    atualizarResumoEncerradas(sourceColumn);
                    atualizarResumoEncerradas(targetColumn);
                }
                atualizarVisualStatusEncerrada(card, novoStatus);
                card.classList.add('move-success');
                mostrarAvisoCopiado(payload?.message || 'Proposta movida com sucesso');
                setTimeout(() => card.classList.remove('move-success'), 1400);
            } catch (error) {
                console.error(error);
                restoreCard(card, sourceArea, nextSibling);
                refreshEmptyState(sourceArea);
                refreshEmptyState(cardsArea);
                if (modulo === 'funil') {
                    updateColumnCounter(sourceColumn);
                    updateColumnCounter(targetColumn);
                } else {
                    atualizarResumoEncerradas(sourceColumn);
                    atualizarResumoEncerradas(targetColumn);
                }
                card.classList.add('move-error');
                mostrarAvisoCopiado(error.message || 'Não foi possível mover a proposta', 'erro');
                setTimeout(() => card.classList.remove('move-error'), 1800);
            } finally {
                card.dataset.busy = 'false';
                card.classList.remove('is-processing');
                card.setAttribute('draggable', 'true');
                restoreScroll(kanban, kanbanScrollLeft, sourceArea, sourceScrollTop, cardsArea, targetScrollTop);
            }
        });
    });

});

// v11 - Pesquisa rápida com sugestões por nome, CPF ou telefone.
document.addEventListener('DOMContentLoaded', () => {
    const searchWrap = document.querySelector('.quick-search');
    const input = document.getElementById('quickSearchInput');
    const results = document.getElementById('quickSearchResults');
    if (!searchWrap || !input || !results) return;

    const searchUrl = searchWrap.dataset.searchUrl;
    let timer = null;
    let lastItems = [];

    function hideResults() {
        results.hidden = true;
        results.innerHTML = '';
    }

    function renderResults(items) {
        lastItems = items || [];
        if (!lastItems.length) {
            results.innerHTML = '<div class="quick-search-empty">Nenhum cliente encontrado.</div>';
            results.hidden = false;
            return;
        }

        results.innerHTML = lastItems.map((item) => `
            <a class="quick-search-item" href="${appendOrigin(item.url)}">
                <strong>${escapeHtml(item.nome)}</strong>
                <small>${escapeHtml(item.cpf || 'CPF não informado')} · ${escapeHtml(item.status || '')}</small>
                <span>${item.tipo_resultado === 'cliente'
                    ? `${escapeHtml(item.matricula ? 'Matrícula: ' + item.matricula : 'Sem matrícula')}${item.telefone ? ' · ' + escapeHtml(item.telefone) : ''}`
                    : `${escapeHtml(item.produto || '')}${item.banco ? ' · Banco: ' + escapeHtml(item.banco) : ''}`
                }</span>
                <em class="quick-search-match">Encontrado em ${escapeHtml(item.match_campo || 'resultado')}: ${escapeHtml(item.match_valor || '')}</em>
            </a>
        `).join('');
        results.hidden = false;
    }

    function escapeHtml(value) {
        return String(value || '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
    }

    function appendOrigin(url) {
        const separator = String(url || '').includes('?') ? '&' : '?';
        const origem = window.location.pathname + window.location.search;
        return `${url}${separator}origem=${encodeURIComponent(origem || '/propostas')}`;
    }

    input.addEventListener('input', () => {
        clearTimeout(timer);
        const q = input.value.trim();
        if (q.length < 2) {
            hideResults();
            return;
        }
        timer = setTimeout(async () => {
            try {
                const response = await fetch(`${searchUrl}?q=${encodeURIComponent(q)}`);
                if (!response.ok) throw new Error('Falha na pesquisa');
                renderResults(await response.json());
            } catch (error) {
                console.error(error);
                hideResults();
            }
        }, 180);
    });

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && lastItems.length) {
            event.preventDefault();
            window.location.href = appendOrigin(lastItems[0].url);
        }
        if (event.key === 'Escape') hideResults();
    });

    document.addEventListener('click', (event) => {
        if (!searchWrap.contains(event.target)) hideResults();
    });
});

// v23 - Alternância de modo claro/escuro com preferência salva no navegador.
document.addEventListener('DOMContentLoaded', () => {
    const botaoTema = document.getElementById('themeToggle');
    const seletorTema = document.getElementById('settingsTheme');
    if (!botaoTema && !seletorTema) return;

    function aplicarTema(tema) {
        document.documentElement.setAttribute('data-theme', tema);
        localStorage.setItem('crmTema', tema);
        if (botaoTema) {
            botaoTema.innerHTML = tema === 'escuro'
                ? '<i class="bi bi-sun" aria-hidden="true"></i><span>Modo claro</span>'
                : '<i class="bi bi-moon" aria-hidden="true"></i><span>Modo escuro</span>';
            botaoTema.title = tema === 'escuro' ? 'Alternar para modo claro' : 'Alternar para modo escuro';
        }
        if (seletorTema) seletorTema.value = tema;
    }

    const temaAtual = localStorage.getItem('crmTema') || document.documentElement.getAttribute('data-theme') || 'claro';
    aplicarTema(temaAtual);

    if (botaoTema) {
        botaoTema.addEventListener('click', () => {
            const atual = document.documentElement.getAttribute('data-theme') || 'claro';
            aplicarTema(atual === 'escuro' ? 'claro' : 'escuro');
        });
    }
    if (seletorTema) seletorTema.addEventListener('change', () => aplicarTema(seletorTema.value));
});

// Campos personalizados do Dashboard.
document.addEventListener('DOMContentLoaded', () => {
    const modeSelect = document.getElementById('dashboardFieldMode');
    if (!modeSelect) return;
    const groups = document.querySelectorAll('[data-dashboard-mode]');
    const aggregation = document.getElementById('dashboardAggregation');
    const aggregationValueField = document.querySelector('[data-aggregation-value-field]');
    const filterField = document.getElementById('dashboardFilterField');
    const filterValue = document.getElementById('dashboardFilterValue');
    const filterValueWrap = document.getElementById('dashboardFilterValueWrap');
    const optionsElement = document.getElementById('dashboardFilterOptions');
    const formulaRows = document.getElementById('dashboardFormulaRows');
    const formulaTemplate = document.getElementById('dashboardFormulaRowTemplate');
    const addFormulaOperation = document.getElementById('addDashboardFormulaOperation');
    let filterOptions = {};
    try { filterOptions = JSON.parse(optionsElement?.textContent || '{}'); } catch (error) { filterOptions = {}; }

    function updateMode() {
        groups.forEach((group) => {
            const active = group.dataset.dashboardMode === modeSelect.value;
            group.hidden = !active;
            group.querySelectorAll('input, select').forEach((control) => { control.disabled = !active; });
        });
    }

    function updateAggregation() {
        if (!aggregationValueField || !aggregation) return;
        const hidden = aggregation.value === 'contagem';
        aggregationValueField.hidden = hidden;
        const select = aggregationValueField.querySelector('select');
        if (select) select.disabled = hidden || modeSelect.value !== 'agregado';
    }

    function updateFilterValues(resetSelection = false) {
        if (!filterField || !filterValue || !filterValueWrap) return;
        const field = filterField.value;
        let current = resetSelection
            ? []
            : Array.from(filterValue.querySelectorAll('input:checked')).map((input) => input.value);
        if (!current.length && filterValue.dataset.currentValues) {
            try { current = JSON.parse(filterValue.dataset.currentValues); } catch (error) { current = []; }
        }
        if (!Array.isArray(current)) current = [];
        filterValue.replaceChildren();
        const values = Array.from(filterOptions[field] || []);
        current.slice().reverse().forEach((value) => {
            if (value && !values.includes(value)) values.unshift(value);
        });
        values.forEach((value) => {
            const label = document.createElement('label');
            label.className = 'dashboard-filter-value-option';
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.name = 'filtro_valores';
            input.value = value;
            input.checked = current.includes(value);
            input.disabled = !field || modeSelect.value !== 'agregado';
            const text = document.createElement('span');
            text.textContent = value;
            label.append(input, text);
            filterValue.appendChild(label);
        });
        const hidden = !field;
        filterValueWrap.hidden = hidden;
        filterValue.dataset.currentValues = '[]';
    }

    function updateFormulaRow(row) {
        const type = row.querySelector('[data-formula-operand-type]')?.value || 'indicador';
        const indicatorWrap = row.querySelector('[data-formula-indicator-wrap]');
        const fixedWrap = row.querySelector('[data-formula-fixed-wrap]');
        const suffix = row.querySelector('[data-formula-fixed-suffix]');
        if (indicatorWrap) indicatorWrap.hidden = type !== 'indicador';
        if (fixedWrap) fixedWrap.hidden = type === 'indicador';
        if (suffix) suffix.textContent = type === 'percentual_fixo' ? '(%)' : '';
    }

    function refreshFormulaRows() {
        const rows = formulaRows ? Array.from(formulaRows.querySelectorAll('[data-formula-row]')) : [];
        rows.forEach(updateFormulaRow);
        rows.forEach((row) => {
            const remove = row.querySelector('[data-remove-formula-operation]');
            if (remove) remove.hidden = rows.length === 1;
        });
        if (addFormulaOperation) addFormulaOperation.hidden = rows.length >= 10;
    }

    modeSelect.addEventListener('change', () => { updateMode(); updateAggregation(); updateFilterValues(); });
    aggregation?.addEventListener('change', updateAggregation);
    filterField?.addEventListener('change', () => updateFilterValues(true));
    formulaRows?.addEventListener('change', (event) => {
        const row = event.target.closest('[data-formula-row]');
        if (row) updateFormulaRow(row);
    });
    formulaRows?.addEventListener('click', (event) => {
        const remove = event.target.closest('[data-remove-formula-operation]');
        if (!remove) return;
        const row = remove.closest('[data-formula-row]');
        if (row && formulaRows.querySelectorAll('[data-formula-row]').length > 1) row.remove();
        refreshFormulaRows();
    });
    addFormulaOperation?.addEventListener('click', () => {
        if (!formulaRows || !formulaTemplate || formulaRows.querySelectorAll('[data-formula-row]').length >= 10) return;
        formulaRows.appendChild(formulaTemplate.content.cloneNode(true));
        refreshFormulaRows();
    });
    updateMode();
    updateAggregation();
    updateFilterValues();
    refreshFormulaRows();
});

// v27 - Abas internas na tela de detalhes da proposta.
document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.proposal-tab[data-tab-target]');
    const panels = document.querySelectorAll('.proposal-tab-panel[data-tab-panel]');
    if (!tabs.length || !panels.length) return;

    function activateTab(target) {
        tabs.forEach((tab) => {
            tab.classList.toggle('is-active', tab.dataset.tabTarget === target);
        });
        panels.forEach((panel) => {
            const isActive = panel.dataset.tabPanel === target;
            panel.classList.toggle('is-active', isActive);
            panel.hidden = !isActive;
        });
    }

    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tabTarget;
            activateTab(target);
        });
    });

    const requestedTab = new URLSearchParams(window.location.search).get('aba');
    const initialTab = Array.from(tabs).some((tab) => tab.dataset.tabTarget === requestedTab)
        ? requestedTab
        : 'resumo';
    activateTab(initialTab);
});

// v35 - Editor visual de etapas: arrastar, reordenar e salvar tudo de uma vez.
document.addEventListener('DOMContentLoaded', () => {
    const list = document.getElementById('statusEditorList');
    const preview = document.getElementById('statusPreviewLine');
    if (!list || !preview) return;

    let dragging = null;

    function getCards() {
        return Array.from(list.querySelectorAll('[data-status-card="true"]'));
    }

    function atualizarOrdensEPreview() {
        const cards = getCards();
        preview.innerHTML = '';

        cards.forEach((card, index) => {
            const ordemInput = card.querySelector('input[name="ordem"]');
            const nomeInput = card.querySelector('[data-status-name-input]');
            const ativoSelect = card.querySelector('[data-status-active-select]');
            const nome = (nomeInput?.value || 'Sem nome').trim() || 'Sem nome';
            const ativo = (ativoSelect?.value || '1') === '1';

            if (ordemInput) ordemInput.value = String(index + 1);

            const step = document.createElement('div');
            step.className = 'status-preview-step' + (ativo ? '' : ' inactive');
            step.dataset.previewId = card.dataset.etapaId || '';

            const dot = document.createElement('div');
            dot.className = 'status-preview-dot';
            dot.textContent = String(index + 1);

            const label = document.createElement('span');
            label.textContent = nome;

            step.appendChild(dot);
            step.appendChild(label);
            preview.appendChild(step);
        });
    }

    function getDragAfterElement(container, y) {
        const cards = [...container.querySelectorAll('[data-status-card="true"]:not(.dragging)')];
        return cards.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closest.offset) {
                return { offset, element: child };
            }
            return closest;
        }, { offset: Number.NEGATIVE_INFINITY, element: null }).element;
    }

    getCards().forEach((card) => {
        card.addEventListener('dragstart', (event) => {
            dragging = card;
            card.classList.add('dragging');
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', card.dataset.etapaId || '');
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
            dragging = null;
            atualizarOrdensEPreview();
        });
    });

    list.addEventListener('dragover', (event) => {
        event.preventDefault();
        if (!dragging) return;
        const afterElement = getDragAfterElement(list, event.clientY);
        if (afterElement == null) {
            list.appendChild(dragging);
        } else {
            list.insertBefore(dragging, afterElement);
        }
    });

    list.addEventListener('input', (event) => {
        if (event.target.matches('[data-status-name-input]')) atualizarOrdensEPreview();
    });

    list.addEventListener('change', (event) => {
        if (event.target.matches('[data-status-active-select]')) atualizarOrdensEPreview();
    });

    atualizarOrdensEPreview();
});

// v41 - Simulador INSS: cálculo automático entre valor e parcela/margem.
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('simuladorInssForm');
    const dataTag = document.getElementById('inssCoeficientes');
    if (!form || !dataTag) return;

    let dados = { novo: {} };
    try { dados = JSON.parse(dataTag.textContent || '{}'); } catch (e) { return; }

    const tipo = document.getElementById('simTipoOperacao');
    const prazo = document.getElementById('simPrazo');
    const valorBase = document.getElementById('simValorBase');
    const margem = document.getElementById('simMargem');
    const valorOut = document.getElementById('simValorEstimado');
    const parcelaOut = document.getElementById('simParcelaEstimativa');
    const coefOut = document.getElementById('simCoeficiente');
    const adicionarPrazo = document.getElementById('simAdicionarPrazo');
    const editarCoeficiente = document.getElementById('simEditarCoeficiente');
    const prazoEditor = document.getElementById('simPrazoEditor');
    const prazoLabelInput = document.getElementById('simPrazoLabel');
    const prazoCoefInput = document.getElementById('simPrazoCoeficiente');
    const salvarPrazo = document.getElementById('simSalvarPrazo');
    const cancelarPrazo = document.getElementById('simCancelarPrazo');
    const prazoStatus = document.getElementById('simPrazoStatus');
    const resumoTexto = document.getElementById('simResumoTexto');
    // Este botão precisa receber sempre a mensagem recalculada do simulador.
    // Um seletor próprio evita que outro controle com data-copy seja escolhido
    // caso novos botões sejam adicionados ao formulário.
    const copiarResumo = document.getElementById('simCopiarResumo');
    const mensagemModelo = document.getElementById('simMensagemModelo');
    const restaurarMensagem = document.getElementById('simRestaurarMensagem');
    const mensagemModeloPadraoTag = document.getElementById('portMensagemModeloPadrao');
    let mensagemModeloPadrao = '';
    try { mensagemModeloPadrao = JSON.parse(mensagemModeloPadraoTag?.textContent || '""'); } catch (e) {}
    const mensagemModeloStorageKey = 'crmSimuladorPortRefinMensagemModelo';
    let prazoEmEdicao = null;

    if (mensagemModelo) {
        try {
            const modeloSalvo = localStorage.getItem(mensagemModeloStorageKey);
            if (modeloSalvo && mensagemModelo.value === mensagemModeloPadrao) {
                mensagemModelo.value = modeloSalvo;
            }
        } catch (e) {}
    }

    function parseBR(value) {
        const text = String(value || '').replace(/R\$/gi, '').replace('%', '').replace(/\s+/g, '').trim();
        if (!text) return 0;
        if (typeof parseMoneyInputValue === 'function') {
            return parseMoneyInputValue(text);
        }
        return Number(text.replace(/\./g, '').replace(',', '.')) || 0;
    }

    function brl(value) {
        return Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function valorBR(value) {
        return Number(value || 0).toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function parseCoeficiente(value) {
        return Number(String(value || '').trim().replace(',', '.')) || 0;
    }

    function atualizarOpcoesPrazo(valorSelecionado = null) {
        if (!prazo) return;
        const atual = valorSelecionado || prazo.value;
        Object.entries(dados.novo || {}).forEach(([codigo, item]) => {
            let option = prazo.querySelector(`option[value="${CSS.escape(codigo)}"]`);
            if (!option) {
                option = document.createElement('option');
                option.value = codigo;
                prazo.appendChild(option);
            }
            option.textContent = item.label || codigo;
            option.dataset.label = item.label || codigo;
            option.dataset.coef = item.coeficiente || '';
        });
        if (atual && prazo.querySelector(`option[value="${CSS.escape(atual)}"]`)) {
            prazo.value = atual;
        }
    }

    async function carregarPrazosGlobais() {
        try {
            const response = await fetch('/api/simulador-inss/prazos', { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error('Falha ao consultar os coeficientes globais.');
            const payload = await response.json();
            if (!payload.novo || typeof payload.novo !== 'object') return;
            dados.novo = payload.novo;
            atualizarOpcoesPrazo(prazo ? prazo.value : null);
            const modoSelecionado = form.querySelector('input[name="modo_simulacao"]:checked')?.value || 'novo';
            if (modoSelecionado === 'novo') {
                calcular(tipo && tipo.value === 'novo_margem' ? margem : valorBase);
            }
        } catch (error) {
            console.error(error);
            if (prazoStatus) prazoStatus.textContent = 'Não foi possível atualizar os coeficientes globais agora.';
        }
    }

    function prazoLabel() {
        const selected = prazo ? prazo.options[prazo.selectedIndex] : null;
        return selected ? (selected.dataset.label || selected.textContent || '') : '';
    }

    function montarMensagem(valor, parcela, descricao) {
        return `Simulação INSS - ${descricao}\n\n` +
            `Valor estimado: ${brl(valor)}\n` +
            `Parcela estimada: ${brl(parcela)}\n` +
            `Prazo: ${prazoLabel()}\n\n` +
            'Valores sujeitos à análise e confirmação do banco.';
    }

    function atualizarResumo(mensagem) {
        if (resumoTexto) resumoTexto.textContent = mensagem;
        if (copiarResumo) copiarResumo.dataset.copy = mensagem;
    }

    function preencherModeloMensagem(modelo, variaveis) {
        return Object.entries(variaveis).reduce(
            (texto, [nome, valor]) => texto.replaceAll(`{${nome}}`, String(valor)),
            modelo,
        );
    }

    function calcular(campoOrigem = null) {
        if (!tipo || !prazo || !valorBase || !margem) return;

        if (campoOrigem === valorBase) tipo.value = 'novo_valor';
        if (campoOrigem === margem) tipo.value = 'novo_margem';

        const item = dados.novo[prazo.value] || dados.novo['108_carencia'] || {};
        const coef = Number(item.coeficiente || 0);
        let valor = 0;
        let parcela = 0;
        let descricao = 'Novo INSS por valor';

        if (tipo.value === 'novo_margem') {
            parcela = parseBR(margem.value);
            valor = coef ? parcela / coef : 0;
            descricao = 'Novo INSS por margem';
            if (campoOrigem === margem && document.activeElement !== valorBase) {
                valorBase.value = brl(valor);
            }
        } else {
            valor = parseBR(valorBase.value);
            parcela = valor * coef;
            descricao = 'Novo INSS por valor';
            if (campoOrigem === valorBase && document.activeElement !== margem) {
                margem.value = brl(parcela);
            }
        }

        if (valorOut) valorOut.textContent = brl(valor);
        if (parcelaOut) parcelaOut.textContent = brl(parcela);
        if (coefOut) coefOut.textContent = coef ? coef.toFixed(6) : '-';
        atualizarResumo(montarMensagem(valor, parcela, descricao));
    }

    function abrirEditor(modo) {
        if (!prazoEditor || !prazoLabelInput || !prazoCoefInput) return;
        prazoEmEdicao = modo === 'novo' ? null : (prazo ? prazo.value : null);
        const item = prazoEmEdicao ? (dados.novo[prazoEmEdicao] || {}) : {};
        prazoLabelInput.value = item.label || '';
        prazoCoefInput.value = item.coeficiente ? Number(item.coeficiente).toFixed(6) : '';
        prazoEditor.classList.remove('hidden');
        prazoLabelInput.focus();
    }

    function fecharEditor() {
        if (prazoEditor) prazoEditor.classList.add('hidden');
        prazoEmEdicao = null;
    }

    async function salvarEdicaoPrazo() {
        if (!prazoLabelInput || !prazoCoefInput || !prazo) return;
        const label = prazoLabelInput.value.trim();
        const coeficiente = parseCoeficiente(prazoCoefInput.value);
        if (!label || !coeficiente) {
            window.alert('Informe o nome do prazo e um coeficiente válido.');
            return;
        }
        if (salvarPrazo) salvarPrazo.disabled = true;
        if (prazoStatus) prazoStatus.textContent = 'Salvando para todos os acessos...';
        try {
            const response = await fetch('/api/simulador-inss/prazos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({ codigo: prazoEmEdicao || '', label, coeficiente }),
            });
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.erro || 'Falha ao salvar o coeficiente global.');
            dados.novo = payload.novo || dados.novo;
            atualizarOpcoesPrazo(payload.codigo);
            prazo.value = payload.codigo;
            fecharEditor();
            calcular(tipo && tipo.value === 'novo_margem' ? margem : valorBase);
            if (prazoStatus) prazoStatus.textContent = 'Coeficiente salvo globalmente para todos os acessos.';
        } catch (error) {
            console.error(error);
            if (prazoStatus) prazoStatus.textContent = error.message;
        } finally {
            if (salvarPrazo) salvarPrazo.disabled = false;
        }
    }

    if (valorBase) {
        valorBase.addEventListener('input', () => calcular(valorBase));
        valorBase.addEventListener('blur', () => calcular(valorBase));
    }
    if (margem) {
        margem.addEventListener('input', () => calcular(margem));
        margem.addEventListener('blur', () => calcular(margem));
    }
    if (prazo) {
        prazo.addEventListener('change', () => calcular(tipo.value === 'novo_margem' ? margem : valorBase));
    }
    if (adicionarPrazo) adicionarPrazo.addEventListener('click', () => abrirEditor('novo'));
    if (editarCoeficiente) editarCoeficiente.addEventListener('click', () => abrirEditor('editar'));
    if (salvarPrazo) salvarPrazo.addEventListener('click', salvarEdicaoPrazo);
    if (cancelarPrazo) cancelarPrazo.addEventListener('click', fecharEditor);
    window.addEventListener('focus', carregarPrazosGlobais);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') carregarPrazosGlobais();
    });
    try { localStorage.removeItem('crmSimuladorInssPrazos'); } catch (e) {}
    atualizarOpcoesPrazo(prazo ? prazo.value : null);
    calcular(tipo && tipo.value === 'novo_margem' ? margem : valorBase);

    const modeInputs = Array.from(form.querySelectorAll('input[name="modo_simulacao"]'));
    const modePanels = Array.from(form.querySelectorAll('[data-simulator-panel]'));
    const sourceInputs = Array.from(form.querySelectorAll('input[name="fonte_simulacao"]'));
    const sourcePanels = Array.from(form.querySelectorAll('[data-simulator-source-panel]'));
    const portFields = {
        tabela: document.getElementById('portTabela'),
        parcelaAtual: document.getElementById('portParcelaAtual'),
        saldo: document.getElementById('portSaldoQuitacao'),
        prazoContrato: document.getElementById('portPrazoContrato'),
        parcelasPagas: document.getElementById('portParcelasPagas'),
        taxaContratoAtual: document.getElementById('portTaxaContratoAtual'),
        novoPrazo: document.getElementById('portNovoPrazo'),
        novaParcela: document.getElementById('portNovaParcela'),
        margemImportada: document.getElementById('portMargemImportada'),
        taxa: document.getElementById('portTaxaNova'),
        coeficiente: document.getElementById('portCoeficiente'),
    };
    const deduzirNegativoInputs = Array.from(form.querySelectorAll('input[name="deduzir_negativo"]'));
    const negativeHelp = document.getElementById('portNegativeHelp');
    const recalcularSaldo = document.getElementById('portRecalcularSaldo');
    const saldoRecalculadoStatus = document.getElementById('portSaldoRecalculadoStatus');
    const extratoArquivo = document.getElementById('portExtratoArquivo');
    const lerExtrato = document.getElementById('portLerExtrato');
    const extratoStatus = document.getElementById('portExtratoStatus');
    const extratoContractPicker = document.getElementById('portExtratoContractPicker');
    const extratoContractSelect = document.getElementById('portExtratoContractSelect');
    const bancoAtualInput = document.getElementById('portBancoAtual');
    const numeroContratoInput = document.getElementById('portNumeroContrato');
    let contratosDoExtrato = [];
    const portOutputs = {
        valorContrato: document.getElementById('portValorContrato'),
        troco: document.getElementById('portTroco'),
        comissaoPercentual: document.getElementById('portComissaoPercentual'),
        comissaoTotal: document.getElementById('portComissaoTotal'),
        coeficiente: document.getElementById('portCoeficienteUsado'),
        origem: document.getElementById('portOrigemCoeficiente'),
        viabilidade: document.getElementById('portViabilidade'),
        inserirProposta: document.getElementById('portInserirProposta'),
    };

    function modoAtual() {
        return modeInputs.find((input) => input.checked)?.value || 'novo';
    }

    function atualizarFonteSimulacao() {
        const fonte = sourceInputs.find((input) => input.checked)?.value || 'extrato';
        sourcePanels.forEach((panel) => {
            panel.hidden = panel.dataset.simulatorSourcePanel !== fonte;
        });
    }

    const camposBeneficiarioDaFonte = [
        'nome', 'cpf', 'nascimento', 'nb_matricula', 'especie', 'endereco', 'dados_bancarios',
    ];
    const camposContratoDaFonte = [
        'banco_atual', 'numero_contrato', 'parcela_atual', 'saldo_quitacao',
        'prazo_contrato', 'parcelas_pagas', 'taxa_contrato_atual', 'margem_disponivel_importada',
    ];

    function limparDadosDaFonteAnterior() {
        [...camposBeneficiarioDaFonte, ...camposContratoDaFonte].forEach((nome) => {
            preencherCampoExtrato(form.elements.namedItem(nome), '');
        });
        contratosDoExtrato = [];
        if (extratoContractSelect) {
            extratoContractSelect.innerHTML = '<option value="">Selecione um contrato</option>';
        }
        if (extratoContractPicker) extratoContractPicker.hidden = true;
        if (saldoRecalculadoStatus) {
            saldoRecalculadoStatus.textContent = 'O recálculo considera a parcela atual e as parcelas restantes. Confira o resultado com o extrato.';
        }
        calcularPortRefin();
    }

    function calcularPortRefin() {
        const parcelaAtual = parseBR(portFields.parcelaAtual?.value);
        const saldo = parseBR(portFields.saldo?.value);
        const prazoNovo = Math.max(0, Number(portFields.novoPrazo?.value || 0));
        const novaParcelaInformada = parseBR(portFields.novaParcela?.value);
        const margemImportada = parseBR(portFields.margemImportada?.value);
        const deduzirNegativo = deduzirNegativoInputs.find((input) => input.checked)?.value === 'sim';
        const negativoDeduzido = deduzirNegativo && margemImportada < 0 ? Math.abs(margemImportada) : 0;
        const novaParcela = negativoDeduzido
            ? Math.max(0, parcelaAtual - negativoDeduzido)
            : (novaParcelaInformada || parcelaAtual);
        const taxaMensal = parseCoeficiente(portFields.taxa?.value);
        const coeficienteInformado = parseCoeficiente(portFields.coeficiente?.value);
        const tabelaSelecionada = portFields.tabela?.selectedOptions?.[0];
        const fatorSaldo = Number(tabelaSelecionada?.dataset.fatorSaldo || 1);
        const comissaoPercentual = Number(tabelaSelecionada?.dataset.comissaoPercentual || 0);
        let coeficiente = coeficienteInformado;
        let origem = portFields.tabela?.value ? `Tabela Quali ${portFields.tabela.value}` : 'Coeficiente informado';

        if (!coeficiente && taxaMensal > 0 && prazoNovo > 0) {
            const taxa = taxaMensal / 100;
            coeficiente = taxa / (1 - Math.pow(1 + taxa, -prazoNovo));
            origem = 'Calculado pela taxa mensal';
        }

        const valorContrato = coeficiente > 0 && coeficiente <= 1 ? novaParcela / coeficiente : 0;
        const saldoConsiderado = saldo * fatorSaldo;
        const troco = valorContrato - saldoConsiderado;
        const comissaoPortabilidade = saldo * (comissaoPercentual / 100);
        const comissaoRefinanciamento = Math.max(0, troco) * (comissaoPercentual / 100);
        const comissaoTotal = comissaoPortabilidade + comissaoRefinanciamento;
        const erros = [];
        if (parcelaAtual <= 0) erros.push('Informe a parcela atual.');
        if (saldo <= 0) erros.push('Informe o saldo para quitação.');
        if (prazoNovo <= 0) erros.push('Informe o novo prazo.');
        if (coeficiente <= 0) erros.push('Informe a taxa ou o coeficiente.');
        if (coeficiente > 1) erros.push('O coeficiente precisa ser menor ou igual a 1.');

        if (portOutputs.valorContrato) portOutputs.valorContrato.textContent = brl(valorContrato);
        if (portOutputs.troco) portOutputs.troco.textContent = brl(troco);
        if (portOutputs.comissaoPercentual) {
            portOutputs.comissaoPercentual.textContent = comissaoPercentual
                ? `${comissaoPercentual.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
                : '-';
        }
        if (portOutputs.comissaoTotal) {
            portOutputs.comissaoTotal.textContent = comissaoPercentual ? brl(comissaoTotal) : '-';
        }
        if (portOutputs.coeficiente) portOutputs.coeficiente.textContent = coeficiente ? coeficiente.toFixed(8) : '-';
        if (portOutputs.origem) portOutputs.origem.textContent = coeficiente ? origem : 'Informe taxa ou coeficiente';

        let aviso = erros.join(' ');
        let estado = 'attention';
        if (!erros.length && troco >= 0) {
            aviso = 'Operação com troco positivo.';
            estado = 'ok';
        } else if (!erros.length) {
            aviso = 'O novo contrato não cobre o saldo para quitação.';
        }
        if (portOutputs.viabilidade) {
            portOutputs.viabilidade.dataset.state = estado;
            const texto = portOutputs.viabilidade.querySelector('span');
            if (texto) texto.textContent = aviso;
        }
        if (portOutputs.inserirProposta) {
            portOutputs.inserirProposta.hidden = modoAtual() !== 'port_refin' || Boolean(erros.length) || troco < 0;
        }
        if (negativeHelp) {
            if (margemImportada < 0 && deduzirNegativo) {
                negativeHelp.textContent = `${brl(Math.abs(margemImportada))} deduzidos: a nova parcela calculada é ${brl(novaParcela)}.`;
            } else if (margemImportada < 0) {
                negativeHelp.textContent = `Margem negativa de ${brl(Math.abs(margemImportada))} ignorada; a nova parcela não foi reduzida por ela.`;
            } else if (margemImportada > 0) {
                negativeHelp.textContent = `Margem positiva de ${brl(margemImportada)}: não há valor negativo para deduzir.`;
            } else {
                negativeHelp.textContent = 'Por padrão, a margem negativa importada não altera a nova parcela.';
            }
        }

        const bancoAtual = form.elements.namedItem('banco_atual')?.value.trim() || 'não informado';
        const saudacao = new Date().getHours() < 12 ? 'Bom dia' : 'Boa tarde';
        const modelo = mensagemModelo?.value || mensagemModeloPadrao;
        const mensagem = preencherModeloMensagem(modelo, {
            saudacao,
            banco_atual: bancoAtual,
            parcela_atual: valorBR(parcelaAtual),
            nova_parcela: valorBR(novaParcela),
            troco: valorBR(troco),
        });
        atualizarResumo(mensagem);
    }

    function aplicarTabelaPortRefin() {
        const option = portFields.tabela?.selectedOptions?.[0];
        if (!option?.value) {
            calcularPortRefin();
            return;
        }
        if (portFields.taxa) portFields.taxa.value = String(option.dataset.taxa || '').replace('.', ',');
        if (portFields.novoPrazo) portFields.novoPrazo.value = option.dataset.prazo || '';
        if (portFields.coeficiente) portFields.coeficiente.value = option.dataset.coeficiente || '';
        calcularPortRefin();
    }

    function recalcularSaldoContrato() {
        const parcela = parseBR(portFields.parcelaAtual?.value);
        const prazoOriginal = Math.max(0, Math.trunc(Number(portFields.prazoContrato?.value || 0)));
        const parcelasPagas = Math.max(0, Math.trunc(Number(portFields.parcelasPagas?.value || 0)));
        const parcelasRestantes = Math.max(0, prazoOriginal - parcelasPagas);
        const taxaPercentual = parseCoeficiente(portFields.taxaContratoAtual?.value);

        if (!parcela || !prazoOriginal || !parcelasRestantes || taxaPercentual <= 0) {
            if (saldoRecalculadoStatus) {
                saldoRecalculadoStatus.textContent = 'Informe parcela atual, prazo original, parcelas pagas e uma taxa maior que zero.';
            }
            return;
        }

        const taxaDecimal = taxaPercentual / 100;
        const saldoAtualizado = parcela * (1 - Math.pow(1 + taxaDecimal, -parcelasRestantes)) / taxaDecimal;
        if (portFields.saldo) portFields.saldo.value = brl(saldoAtualizado);
        if (saldoRecalculadoStatus) {
            saldoRecalculadoStatus.textContent = `Saldo recalculado em ${brl(saldoAtualizado)} para ${parcelasRestantes} parcelas restantes à taxa de ${taxaPercentual.toLocaleString('pt-BR')}% a.m. Confira com o extrato.`;
        }
        calcularPortRefin();
    }

    function preencherCampoExtrato(campo, valor) {
        if (!campo) return;
        campo.value = valor;
        campo.dispatchEvent(new Event('input', { bubbles: true }));
        campo.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function atualizarStatusExtrato(estado, mensagem) {
        if (!extratoStatus) return;
        extratoStatus.dataset.state = estado;
        extratoStatus.textContent = mensagem;
    }

    function definirLeituraExtratoEmAndamento(emAndamento) {
        if (!lerExtrato) return;
        lerExtrato.disabled = emAndamento;
        lerExtrato.setAttribute('aria-busy', emAndamento ? 'true' : 'false');
        const icone = lerExtrato.querySelector('i');
        const texto = lerExtrato.querySelector('span');
        if (icone) {
            icone.className = emAndamento
                ? 'bi bi-arrow-repeat statement-reader-spinner'
                : 'bi bi-file-earmark-arrow-up';
        }
        if (texto) texto.textContent = emAndamento ? 'Aguarde...' : 'Ler extrato';
    }

    function aplicarDadosBeneficiarioDoExtrato(payload) {
        preencherCampoExtrato(form.elements.namedItem('nome'), payload.nome || '');
        preencherCampoExtrato(form.elements.namedItem('nb_matricula'), normalizarMatricula(payload.nb_matricula));
        preencherCampoExtrato(form.elements.namedItem('especie'), payload.especie || '');
        preencherCampoExtrato(form.elements.namedItem('dados_bancarios'), payload.dados_bancarios || '');
        preencherCampoExtrato(portFields.margemImportada, brl(Number(payload.margem_disponivel) || 0));
    }

    function aplicarContratoDoExtrato() {
        const contrato = contratosDoExtrato[Number(extratoContractSelect?.value)];
        if (!contrato) return;
        preencherCampoExtrato(bancoAtualInput, contrato.banco || contrato.banco_descricao || '');
        preencherCampoExtrato(numeroContratoInput, contrato.numero || '');
        preencherCampoExtrato(portFields.parcelaAtual, brl(contrato.parcela));
        preencherCampoExtrato(portFields.saldo, brl(contrato.saldo_calculado));
        preencherCampoExtrato(portFields.prazoContrato, contrato.prazo_total);
        preencherCampoExtrato(portFields.parcelasPagas, contrato.parcelas_pagas);
        preencherCampoExtrato(portFields.taxaContratoAtual, Number(contrato.taxa).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 }));
        if (saldoRecalculadoStatus) {
            saldoRecalculadoStatus.textContent = `Saldo estimado em ${brl(contrato.saldo_calculado)} para ${contrato.parcelas_restantes} parcelas restantes à taxa de ${Number(contrato.taxa).toLocaleString('pt-BR')}% a.m.`;
        }
        if (extratoStatus) {
            atualizarStatusExtrato('success', `Extrato importado com sucesso. Contrato ${contrato.numero}: ${contrato.parcelas_pagas} de ${contrato.prazo_total} parcelas pagas. ${contrato.taxa_fonte}.`);
        }
        calcularPortRefin();
    }

    async function carregarExtrato() {
        const arquivo = extratoArquivo?.files?.[0];
        if (!arquivo) {
            atualizarStatusExtrato('error', 'Selecione primeiro um extrato do INSS em PDF.');
            return;
        }
        definirLeituraExtratoEmAndamento(true);
        atualizarStatusExtrato('loading', 'Aguarde, estamos lendo os dados e os contratos do extrato...');
        if (extratoContractPicker) extratoContractPicker.hidden = true;
        try {
            const dadosEnvio = new FormData();
            dadosEnvio.append('extrato', arquivo);
            const response = await fetch('/api/simulador-inss/ler-extrato', { method: 'POST', body: dadosEnvio });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload.erro || 'Não foi possível ler o extrato.');
            const contratosLidos = Array.isArray(payload.contratos) ? payload.contratos : [];
            if (!contratosLidos.length) throw new Error('Nenhum contrato ativo foi encontrado no extrato.');
            limparDadosDaFonteAnterior();
            contratosDoExtrato = contratosLidos;
            aplicarDadosBeneficiarioDoExtrato(payload);
            if (extratoContractSelect) {
                extratoContractSelect.innerHTML = '<option value="">Selecione um contrato</option>';
                contratosDoExtrato.forEach((contrato, indice) => {
                    const option = document.createElement('option');
                    option.value = String(indice);
                    option.textContent = textoContratoExtrato(contrato);
                    option.title = tituloContratoExtrato(contrato, option.textContent);
                    extratoContractSelect.appendChild(option);
                });
            }
            if (extratoContractPicker) extratoContractPicker.hidden = false;
            const especie = payload.especie
                ? ` Espécie ${payload.especie}${payload.especie_descricao ? ` - ${payload.especie_descricao}.` : '.'}`
                : '';
            const contratosEncontrados = contratosDoExtrato.length === 1
                ? '1 contrato encontrado'
                : `${contratosDoExtrato.length} contratos encontrados`;
            atualizarStatusExtrato('success', `Extrato importado com sucesso. ${contratosEncontrados} no extrato de ${payload.data_extrato}.${especie} Selecione o contrato que deseja simular.`);
        } catch (error) {
            contratosDoExtrato = [];
            atualizarStatusExtrato('error', error.message);
        } finally {
            definirLeituraExtratoEmAndamento(false);
        }
    }

    function atualizarModo() {
        const atual = modoAtual();
        modePanels.forEach((panel) => { panel.hidden = panel.dataset.simulatorPanel !== atual; });
        if (atual === 'port_refin') calcularPortRefin();
        else {
            if (portOutputs.inserirProposta) portOutputs.inserirProposta.hidden = true;
            calcular(tipo && tipo.value === 'novo_margem' ? margem : valorBase);
        }
    }

    modeInputs.forEach((input) => input.addEventListener('change', atualizarModo));
    sourceInputs.forEach((input) => input.addEventListener('change', () => {
        limparDadosDaFonteAnterior();
        atualizarFonteSimulacao();
    }));
    if (portFields.tabela) portFields.tabela.addEventListener('change', aplicarTabelaPortRefin);
    if (recalcularSaldo) recalcularSaldo.addEventListener('click', recalcularSaldoContrato);
    if (lerExtrato) lerExtrato.addEventListener('click', carregarExtrato);
    if (extratoContractSelect) extratoContractSelect.addEventListener('change', aplicarContratoDoExtrato);
    Object.values(portFields).forEach((field) => {
        if (!field) return;
        field.addEventListener('input', calcularPortRefin);
        field.addEventListener('change', calcularPortRefin);
    });
    deduzirNegativoInputs.forEach((input) => input.addEventListener('change', calcularPortRefin));
    if (mensagemModelo) {
        mensagemModelo.addEventListener('input', () => {
            try { localStorage.setItem(mensagemModeloStorageKey, mensagemModelo.value); } catch (e) {}
            calcularPortRefin();
        });
    }
    if (restaurarMensagem && mensagemModelo) {
        restaurarMensagem.addEventListener('click', () => {
            mensagemModelo.value = mensagemModeloPadrao;
            try { localStorage.removeItem(mensagemModeloStorageKey); } catch (e) {}
            calcularPortRefin();
            mensagemModelo.focus();
        });
    }
    atualizarFonteSimulacao();
    atualizarModo();
});

// v42 - Seleção de modelos de mensagem na aba Mensagens.
document.addEventListener('DOMContentLoaded', () => {
    const select = document.getElementById('modeloMensagemSelect');
    const items = document.querySelectorAll('.selected-message-item[data-message-index]');
    if (!select || !items.length) return;

    function atualizarModeloSelecionado() {
        const value = select.value;
        items.forEach((item) => {
            item.classList.toggle('hidden', item.dataset.messageIndex !== value);
        });
    }

    select.addEventListener('change', atualizarModeloSelecionado);
    atualizarModeloSelecionado();
});

// Comparativo interativo entre as promotoras no Dashboard.
document.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector('[data-promoter-comparison]');
    if (!root) return;

    const dataNode = root.querySelector('[data-promoter-comparison-data]');
    const slicesRoot = root.querySelector('[data-promoter-slices]');
    const legend = root.querySelector('[data-promoter-legend]');
    const totalNode = root.querySelector('[data-promoter-total]');
    const totalLabel = root.querySelector('[data-promoter-total-label]');
    const note = root.querySelector('[data-promoter-note]');
    const tooltip = root.querySelector('[data-promoter-tooltip]');
    const description = root.querySelector('#promoterPieDescription');
    const buttons = Array.from(root.querySelectorAll('[data-promoter-mode]'));
    const colors = ['#2563eb', '#f59e0b'];
    let data = {};
    let activeIndex = null;

    try { data = JSON.parse(dataNode?.textContent || '{}'); } catch (error) { data = {}; }

    const money = (value) => Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const quantity = (value) => `${Number(value || 0).toLocaleString('pt-BR')} proposta${Number(value || 0) === 1 ? '' : 's'}`;
    const percent = (value) => `${Number(value || 0).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
    const point = (angle, radius) => {
        const radians = (angle - 90) * Math.PI / 180;
        return { x: 110 + radius * Math.cos(radians), y: 110 + radius * Math.sin(radians) };
    };
    const piePath = (startAngle, endAngle) => {
        if (endAngle - startAngle >= 359.999) {
            return 'M 110 15 A 95 95 0 1 1 109.99 15 Z';
        }
        const start = point(startAngle, 95);
        const end = point(endAngle, 95);
        const largeArc = endAngle - startAngle > 180 ? 1 : 0;
        return `M 110 110 L ${start.x} ${start.y} A 95 95 0 ${largeArc} 1 ${end.x} ${end.y} Z`;
    };

    function highlight(index) {
        activeIndex = index;
        root.querySelectorAll('[data-promoter-index]').forEach((item) => {
            const itemIndex = Number(item.dataset.promoterIndex);
            item.classList.toggle('is-active', index === itemIndex);
            item.classList.toggle('is-muted', index !== null && index !== itemIndex);
        });
    }

    function render(mode) {
        const series = data[mode] || { total: 0, itens: [] };
        const isMoney = mode === 'comissao';
        activeIndex = null;
        slicesRoot.replaceChildren();
        legend.replaceChildren();

        buttons.forEach((button) => {
            const selected = button.dataset.promoterMode === mode;
            button.classList.toggle('is-active', selected);
            button.setAttribute('aria-pressed', String(selected));
        });

        totalNode.textContent = isMoney ? money(series.total) : quantity(series.total);
        totalLabel.textContent = isMoney ? 'comissão paga' : 'propostas no mês';
        note.textContent = isMoney
            ? 'Comissão paga considera as operações encerradas como Pago no mês selecionado, incluindo as duas comissões de Port + Refin vinculados. Todo nome iniciado por “Única” — como “Unica - Sub” ou “Unica - Adriano” — é agrupado em Única; Vieira permanece separada.'
            : 'Propostas no mês considera as criadas no período e, no mês atual, também as operações antigas que continuam ativas. Todo nome iniciado por “Única” é agrupado em Única; Vieira permanece separada. Portabilidade com Refinanciamento + Refin vinculado contam como uma única proposta.';

        let angle = 0;
        if (!Number(series.total)) {
            const empty = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            empty.setAttribute('class', 'promoter-pie-empty');
            empty.setAttribute('cx', '110');
            empty.setAttribute('cy', '110');
            empty.setAttribute('r', '95');
            slicesRoot.appendChild(empty);
        }

        series.itens.forEach((item, index) => {
            const share = Number(item.percentual || 0);
            const valueLabel = isMoney ? money(item.valor) : quantity(item.valor);
            const detail = `${item.nome}: ${valueLabel} (${percent(share)})`;

            if (share > 0) {
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', piePath(angle, angle + (share / 100 * 360)));
                path.setAttribute('fill', colors[index]);
                path.setAttribute('class', 'promoter-pie-slice');
                path.setAttribute('tabindex', '0');
                path.setAttribute('role', 'button');
                path.setAttribute('aria-label', detail);
                path.dataset.promoterIndex = String(index);
                path.addEventListener('mouseenter', () => { highlight(index); tooltip.textContent = detail; tooltip.hidden = false; });
                path.addEventListener('mouseleave', () => { highlight(null); tooltip.hidden = true; });
                path.addEventListener('focus', () => { highlight(index); tooltip.textContent = detail; tooltip.hidden = false; });
                path.addEventListener('blur', () => { highlight(null); tooltip.hidden = true; });
                slicesRoot.appendChild(path);
                angle += share / 100 * 360;
            }

            const itemButton = document.createElement('button');
            itemButton.type = 'button';
            itemButton.className = 'promoter-legend-item';
            itemButton.style.setProperty('--promoter-color', colors[index]);
            itemButton.dataset.promoterIndex = String(index);
            itemButton.setAttribute('aria-label', detail);
            itemButton.innerHTML = `
                <span class="promoter-legend-color" aria-hidden="true"></span>
                <span class="promoter-legend-copy"><strong>${item.nome}</strong><small>${valueLabel}</small></span>
                <span class="promoter-legend-percent">${percent(share)}</span>
            `;
            itemButton.addEventListener('mouseenter', () => highlight(index));
            itemButton.addEventListener('mouseleave', () => highlight(null));
            itemButton.addEventListener('focus', () => highlight(index));
            itemButton.addEventListener('blur', () => highlight(null));
            itemButton.addEventListener('click', () => highlight(activeIndex === index ? null : index));
            legend.appendChild(itemButton);
        });

        description.textContent = series.itens
            .map((item) => `${item.nome}: ${percent(item.percentual)}`)
            .join('; ');
    }

    buttons.forEach((button) => button.addEventListener('click', () => render(button.dataset.promoterMode)));
    render('comissao');
});

// v44 - Gerador de mensagens comercial separado, inspirado no gerador desktop antigo.
document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('geradorMensagens');
    if (!root) return;

    let modelos = {};
    try { modelos = JSON.parse(root.dataset.modelos || '{}'); } catch (error) { modelos = {}; }

    const modeloSelect = document.getElementById('gerModeloSelect');
    const nome = document.getElementById('gerNome');
    const cpf = document.getElementById('gerCpf');
    const banco = document.getElementById('gerBanco');
    const parcelaAntiga = document.getElementById('gerParcelaAntiga');
    const parcelaNova = document.getElementById('gerParcelaNova');
    const troco = document.getElementById('gerTroco');
    const prazo = document.getElementById('gerPrazo');
    const atendente = document.getElementById('gerAtendente');
    const economia = document.getElementById('gerEconomia');
    const saida = document.getElementById('gerMensagemResultado');
    const copiar = document.getElementById('copiarGeradorBtn');
    const gerar = document.getElementById('gerarMensagemBtn');
    const limpar = document.getElementById('limparGeradorBtn');

    function parseMoneyGerador(value) {
        let text = String(value || '').replace('R$', '').replace(/\s/g, '').trim();
        if (!text) return 0;
        if (text.includes(',')) {
            text = text.replace(/\./g, '').replace(',', '.');
            return Number(text) || 0;
        }
        if (/^\d{1,3}(\.\d{3})+$/.test(text)) {
            text = text.replace(/\./g, '');
            return Number(text) || 0;
        }
        return Number(text) || 0;
    }

    function brl(value) {
        return Number(value || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function calcularEconomia() {
        const antiga = parseMoneyGerador(parcelaAntiga?.value);
        const nova = parseMoneyGerador(parcelaNova?.value);
        const valor = antiga - nova;
        if (economia) economia.value = valor > 0 ? brl(valor) : brl(0);
        return valor > 0 ? valor : 0;
    }

    function preencherModelo(modelo, dados) {
        return String(modelo || '').replace(/\{(nome|nome_maiusculo|cpf|banco|parcela_antiga|parcela_nova|troco|valor|economia|atendente|prazo)\}/g, (match, key) => dados[key] ?? '');
    }

    function atualizarCamposVisiveis(modelo) {
        root.querySelectorAll('[data-ger-variables]').forEach((label) => {
            const variaveis = String(label.dataset.gerVariables || '').split('|').filter(Boolean);
            label.hidden = variaveis.length > 0 && !variaveis.some((variavel) => modelo.includes(variavel));
        });
    }

    function gerarMensagem() {
        const modeloNome = modeloSelect?.value || Object.keys(modelos)[0];
        const modelo = modelos[modeloNome] || '';
        atualizarCamposVisiveis(modelo);
        const eco = calcularEconomia();
        const dados = {
            nome: nome?.value.trim() || '',
            nome_maiusculo: nome?.value.trim().toLocaleUpperCase('pt-BR') || '',
            cpf: cpf?.value.trim() || '',
            banco: banco?.value.trim() || '',
            parcela_antiga: brl(parseMoneyGerador(parcelaAntiga?.value)),
            parcela_nova: brl(parseMoneyGerador(parcelaNova?.value)),
            troco: brl(parseMoneyGerador(troco?.value)),
            valor: brl(parseMoneyGerador(troco?.value)),
            economia: brl(eco),
            atendente: atendente?.value.trim() || '',
            prazo: prazo?.value.trim() || '108',
        };
        const mensagem = preencherModelo(modelo, dados);
        if (saida) saida.value = mensagem;
        if (copiar) copiar.dataset.copy = mensagem;
        return mensagem;
    }

    [modeloSelect, nome, cpf, banco, parcelaAntiga, parcelaNova, troco, prazo, atendente].forEach((field) => {
        if (!field) return;
        field.addEventListener('input', gerarMensagem);
        field.addEventListener('change', gerarMensagem);
        field.addEventListener('blur', gerarMensagem);
    });

    if (gerar) gerar.addEventListener('click', gerarMensagem);
    if (limpar) {
        limpar.addEventListener('click', () => {
            [nome, cpf, banco, parcelaAntiga, parcelaNova, troco].forEach((field) => { if (field) field.value = ''; });
            if (prazo) prazo.value = '108';
            if (atendente) atendente.value = 'Poliana';
            if (economia) economia.value = '';
            if (saida) saida.value = '';
            if (copiar) copiar.dataset.copy = '';
        });
    }

    gerarMensagem();
});
