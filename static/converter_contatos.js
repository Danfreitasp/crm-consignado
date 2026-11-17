(() => {
    const form = document.getElementById('contatos-form');
    const arquivo = document.getElementById('contatos-arquivo');
    const colados = document.getElementById('contatos-colados');
    const drop = document.getElementById('contatos-drop');
    const status = document.getElementById('contatos-status');
    const resultado = document.getElementById('contatos-resultado');
    const estatisticas = document.getElementById('contatos-estatisticas');
    const previa = document.getElementById('contatos-previa');
    const avisoSucesso = document.getElementById('contatos-aviso-sucesso');
    let avisoFlutuante = null;
    let tempoAviso = null;
    let fonte = null;
    let sequencia = 0;
    function mensagem(texto, erro = false) { status.textContent = texto; status.classList.toggle('erro', erro); }
    function ocultarAviso() { avisoSucesso.hidden = true; if (avisoFlutuante) avisoFlutuante.remove(); avisoFlutuante = null; clearTimeout(tempoAviso); }
    function limpar() { sequencia++; fonte = null; arquivo.value = ''; colados.value = ''; resultado.hidden = true; ocultarAviso(); mensagem('Aguardando uma planilha para começar.'); }
    async function processar(file) {
        const atual = ++sequencia;
        fonte = null; resultado.hidden = true; ocultarAviso();
        if (!file) return;
        if (!/\.(csv|xlsx)$/i.test(file.name)) { mensagem('Selecione um arquivo CSV ou XLSX.', true); return; }
        mensagem('Processando contatos...');
        const dados = new FormData(); dados.append('arquivo', file); dados.append('acao', 'previsualizar');
        try {
            const resposta = await fetch(form.action || location.href, {method: 'POST', body: dados});
            const dadosResposta = await resposta.json();
            if (atual !== sequencia) return;
            if (!resposta.ok) throw new Error(dadosResposta.erro || 'Não foi possível processar a planilha.');
            fonte = file;
            estatisticas.replaceChildren();
            for (const [texto, atencao] of [[`${dadosResposta.total} contatos`, false], [`${dadosResposta.ignorados} linhas ignoradas`, dadosResposta.ignorados > 0], [`${dadosResposta.incomuns} com tamanho incomum`, dadosResposta.incomuns > 0]]) {
                const item = document.createElement('span'); item.textContent = texto;
                if (atencao) item.classList.add('atencao'); estatisticas.append(item);
            }
            previa.replaceChildren();
            for (const contato of dadosResposta.contatos) {
                const linha = document.createElement('tr');
                for (const valor of [contato.nome, contato.numero]) { const celula = document.createElement('td'); celula.textContent = valor; linha.append(celula); }
                previa.append(linha);
            }
            resultado.hidden = false;
            avisoSucesso.hidden = false;
            mensagem(`${dadosResposta.total} ${dadosResposta.total === 1 ? 'contato processado' : 'contatos processados'}. O resultado está pronto abaixo.`);
            avisoFlutuante = document.createElement('div');
            avisoFlutuante.className = 'crm-toast ok';
            avisoFlutuante.textContent = 'Planilha pronta! Confira o resultado abaixo.';
            avisoFlutuante.setAttribute('aria-hidden', 'true');
            document.body.appendChild(avisoFlutuante);
            tempoAviso = setTimeout(() => { avisoFlutuante?.remove(); avisoFlutuante = null; }, 5000);
        } catch (erro) { if (atual === sequencia) mensagem(erro.message || 'Não foi possível processar a planilha.', true); }
    }
    async function baixar(formato) {
        if (!fonte) return;
        const dados = new FormData(); dados.append('arquivo', fonte); dados.append('formato', formato);
        try {
            const resposta = await fetch(form.action || location.href, {method: 'POST', body: dados});
            if (!resposta.ok || resposta.redirected) throw new Error('Não foi possível baixar a planilha. Processe os dados novamente.');
            const link = document.createElement('a'); const url = URL.createObjectURL(await resposta.blob());
            link.href = url; link.download = `contatos_convertidos.${formato}`; link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (erro) { mensagem(erro.message, true); }
    }
    arquivo.addEventListener('change', () => { colados.value = ''; processar(arquivo.files[0]); });
    function contemArquivos(evento) {
        return Array.from(evento.dataTransfer?.types || []).includes('Files');
    }
    document.addEventListener('dragover', evento => {
        if (!contemArquivos(evento)) return;
        evento.preventDefault();
        evento.dataTransfer.dropEffect = 'copy';
        drop.classList.add('is-dragging');
    });
    document.addEventListener('dragleave', evento => {
        if (!evento.relatedTarget) drop.classList.remove('is-dragging');
    });
    document.addEventListener('drop', evento => {
        if (!contemArquivos(evento)) return;
        evento.preventDefault();
        drop.classList.remove('is-dragging');
        arquivo.value = '';
        colados.value = '';
        const arquivos = evento.dataTransfer.files;
        if (arquivos.length !== 1) {
            sequencia++; fonte = null; resultado.hidden = true; ocultarAviso();
            mensagem('Arraste um arquivo CSV ou XLSX por vez.', true);
            return;
        }
        processar(arquivos[0]);
    });
    document.getElementById('contatos-colar').addEventListener('click', () => {
        arquivo.value = '';
        if (!colados.value.trim()) { fonte = null; sequencia++; resultado.hidden = true; ocultarAviso(); mensagem('Cole os dados com os cabeçalhos antes de processar.', true); return; }
        processar(new File([colados.value], 'contatos.csv', {type: 'text/csv'}));
    });
    colados.addEventListener('input', () => { if (fonte && fonte.name === 'contatos.csv') { sequencia++; fonte = null; resultado.hidden = true; ocultarAviso(); mensagem('Dados alterados. Processe novamente.'); } });
    document.getElementById('contatos-ver-resultado').addEventListener('click', () => {
        resultado.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
        resultado.focus({preventScroll: true});
    });
    document.getElementById('contatos-limpar').addEventListener('click', limpar);
    document.getElementById('contatos-baixar').addEventListener('click', () => baixar('xlsx'));
    document.getElementById('contatos-csv').addEventListener('click', () => baixar('csv'));
    form.addEventListener('submit', e => { e.preventDefault(); if (arquivo.files[0]) processar(arquivo.files[0]); });
})();
