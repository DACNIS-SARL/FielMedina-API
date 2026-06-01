
(function () {
    'use strict';

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement)) return;

        if (form.dataset.noGuard) return;

        if (form.dataset.submitting === 'true') {
            e.preventDefault();
            return;
        }

        form.dataset.submitting = 'true';

        var buttons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        buttons.forEach(function (btn) {
            btn.disabled = true;
            btn.style.opacity = '0.7';
            btn.style.cursor = 'not-allowed';

            if (btn.tagName === 'BUTTON') {
                var originalColor = window.getComputedStyle(btn).color;
                btn.dataset.originalColor = btn.style.color || '';
                btn.dataset.originalPosition = btn.style.position || '';
                btn.style.color = 'transparent';
                btn.style.position = 'relative';

                var spinner = document.createElement('span');
                spinner.className = 'submit-spinner-overlay';
                spinner.style.position = 'absolute';
                spinner.style.left = '50%';
                spinner.style.top = '50%';
                spinner.style.transform = 'translate(-50%, -50%)';
                spinner.style.display = 'inline-flex';
                spinner.style.alignItems = 'center';
                spinner.style.color = originalColor;

                var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                svg.setAttribute('class', 'animate-spin w-5 h-5');
                svg.setAttribute('fill', 'none');
                svg.setAttribute('viewBox', '0 0 24 24');

                var circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('class', 'opacity-25');
                circle.setAttribute('cx', '12');
                circle.setAttribute('cy', '12');
                circle.setAttribute('r', '10');
                circle.setAttribute('stroke', 'currentColor');
                circle.setAttribute('stroke-width', '4');

                var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('class', 'opacity-75');
                path.setAttribute('fill', 'currentColor');
                path.setAttribute('d', 'M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z');

                svg.appendChild(circle);
                svg.appendChild(path);
                spinner.appendChild(svg);
                btn.appendChild(spinner);
            }
        });
    }, /* useCapture */ true);

    window.addEventListener('pageshow', function (e) {
        if (e.persisted) {
            document.querySelectorAll('form[data-submitting="true"]').forEach(function (form) {
                delete form.dataset.submitting;
                form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (btn) {
                    btn.disabled = false;
                    btn.style.opacity = '';
                    btn.style.cursor = '';
                    if (btn.tagName === 'BUTTON') {
                        var spinner = btn.querySelector('.submit-spinner-overlay');
                        if (spinner) {
                            spinner.parentNode.removeChild(spinner);
                        }
                        if (btn.dataset.originalColor !== undefined) {
                            btn.style.color = btn.dataset.originalColor;
                            delete btn.dataset.originalColor;
                        }
                        if (btn.dataset.originalPosition !== undefined) {
                            btn.style.position = btn.dataset.originalPosition;
                            delete btn.dataset.originalPosition;
                        }
                    }
                });
            });
        }
    });
})();

var themeToggleDarkIcon = document.getElementById('theme-toggle-dark-icon');
var themeToggleLightIcon = document.getElementById('theme-toggle-light-icon');

if (localStorage.getItem('color-theme') === 'dark' || (!('color-theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    themeToggleLightIcon.classList.remove('hidden');
} else {
    themeToggleDarkIcon.classList.remove('hidden');
}

var themeToggleBtn = document.getElementById('theme-toggle');

themeToggleBtn.addEventListener('click', function () {

    themeToggleDarkIcon.classList.toggle('hidden');
    themeToggleLightIcon.classList.toggle('hidden');

    if (localStorage.getItem('color-theme')) {
        if (localStorage.getItem('color-theme') === 'light') {
            document.documentElement.classList.add('dark');
            localStorage.setItem('color-theme', 'dark');
        } else {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('color-theme', 'light');
        }

    } else {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('color-theme', 'light');
        } else {
            document.documentElement.classList.add('dark');
            localStorage.setItem('color-theme', 'dark');
        }
    }

});
