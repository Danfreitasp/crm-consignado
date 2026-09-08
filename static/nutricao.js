document.addEventListener('DOMContentLoaded', () => {
    const feedback = document.getElementById('nutricaoFeedback');
    const forms = [...document.querySelectorAll('.nutricao-retorno')];
    forms.forEach((form) => {
        const checkbox = form.querySelector('[name="nutrido"]');
        checkbox.addEventListener('change', async () => {
            const checked = checkbox.checked;
            checkbox.disabled = true;
            const body = new FormData(form);
            body.set('nutrido', checked ? 'SIM' : 'NÃO');
            try {
                const response = await fetch(form.action, { method: 'POST', body });
                const result = await response.json();
                if (!response.ok) throw new Error(result.erro || 'Não foi possível salvar.');
                checkbox.checked = result.nutrido;
                checkbox.nextElementSibling.textContent = result.nutrido ? 'Nutrido hoje' : 'Não nutrido hoje';
                form.querySelector('[data-ultimo-retorno]').textContent = result.ultimo;
                const count = forms.filter(f => f.querySelector('[name="nutrido"]').checked).length;
                document.getElementById('nutricaoNutridos').textContent = count;
                document.getElementById('nutricaoPendentes').textContent = forms.length - count;
                feedback.textContent = result.nutrido ? 'Retorno de hoje registrado.' : 'Marcação de hoje desfeita.';
            } catch (error) {
                checkbox.checked = !checked;
                feedback.textContent = `Não foi possível confirmar a gravação. Recarregue a página para conferir. ${error.message}`;
            } finally {
                checkbox.disabled = false;
            }
        });
    });
});
