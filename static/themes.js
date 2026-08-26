// Seletor independente de temas visuais. Regras, rotas e dados permanecem compartilhados.
document.addEventListener('DOMContentLoaded', () => {
    const menu = document.getElementById('visualThemeMenu');
    const options = Array.from(document.querySelectorAll('[data-visual-theme-option]'));
    if (!menu || !options.length) return;

    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    const validThemes = ['classico', 'lite', 'newsprint', 'retro-90s', 'dopamine', 'soft-ui', 'neo-brutalism'];
    const themeColors = {
        classico: '#111827',
        lite: '#f4f6f8',
        newsprint: '#f9f9f7',
        'retro-90s': '#c0c0c0',
        dopamine: '#0d0d1a',
        'soft-ui': '#e0e5ec',
        'neo-brutalism': '#fffdf5',
    };

    function applyVisualTheme(theme, persist = true) {
        const activeTheme = validThemes.includes(theme) ? theme : 'classico';
        document.documentElement.setAttribute('data-visual-theme', activeTheme);

        if (persist) {
            try {
                localStorage.setItem('crmVisualTheme', activeTheme);
            } catch (error) {
                // A troca continua válida durante a página atual sem armazenamento local.
            }
        }

        options.forEach((option) => {
            const selected = option.dataset.visualThemeOption === activeTheme;
            option.setAttribute('aria-pressed', String(selected));
        });
        if (metaThemeColor) metaThemeColor.content = themeColors[activeTheme];
    }

    applyVisualTheme(document.documentElement.getAttribute('data-visual-theme') || 'classico', false);

    options.forEach((option) => {
        option.addEventListener('click', () => {
            applyVisualTheme(option.dataset.visualThemeOption);
            menu.removeAttribute('open');
            menu.querySelector('summary')?.focus();
        });
    });

    document.addEventListener('click', (event) => {
        if (!menu.contains(event.target)) menu.removeAttribute('open');
    });
});
