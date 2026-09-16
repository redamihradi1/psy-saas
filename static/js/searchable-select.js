/* Enhance a <select data-searchable> into a searchable dropdown, keeping the
   original select in the DOM (hidden) so form submission is unchanged. */
(function () {
    function enhance(select) {
        if (select.dataset.searchableEnhanced) return;
        select.dataset.searchableEnhanced = '1';

        var wrapper = document.createElement('div');
        wrapper.className = 'searchable-select relative';
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        select.classList.add('hidden');

        var input = document.createElement('input');
        input.type = 'text';
        input.autocomplete = 'off';
        input.placeholder = select.dataset.placeholder || 'Rechercher...';
        input.className = select.className.replace('hidden', '').trim();
        wrapper.appendChild(input);

        var dropdown = document.createElement('div');
        dropdown.className = 'searchable-select-dropdown absolute z-20 left-0 right-0 bg-white border border-gray-200 rounded-lg shadow-lg mt-1 max-h-64 overflow-y-auto hidden';
        wrapper.appendChild(dropdown);

        function choices() {
            return Array.prototype.filter.call(select.options, function (o) { return o.value !== ''; });
        }

        function selectedText() {
            var opt = select.options[select.selectedIndex];
            return (opt && opt.value !== '') ? opt.textContent : '';
        }

        function highlight(items, idx) {
            items.forEach(function (i) { i.classList.remove('bg-primary', 'text-white'); });
            if (items[idx]) items[idx].classList.add('bg-primary', 'text-white');
        }

        function pick(option) {
            select.value = option.value;
            input.value = option.textContent;
            select.dispatchEvent(new Event('change', { bubbles: true }));
            close();
        }

        function render(term) {
            term = (term || '').toLowerCase();
            dropdown.innerHTML = '';
            var matches = choices().filter(function (o) {
                return o.textContent.toLowerCase().indexOf(term) !== -1;
            });
            if (matches.length === 0) {
                var empty = document.createElement('div');
                empty.className = 'px-4 py-2 text-sm text-gray-400';
                empty.textContent = 'Aucun résultat';
                dropdown.appendChild(empty);
                return;
            }
            matches.forEach(function (o) {
                var item = document.createElement('div');
                item.className = 'px-4 py-2 text-sm cursor-pointer hover:bg-primary hover:text-white';
                item.textContent = o.textContent;
                item.dataset.value = o.value;
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    pick(o);
                });
                dropdown.appendChild(item);
            });
        }

        function open() {
            render('');
            dropdown.classList.remove('hidden');
        }

        function close() {
            dropdown.classList.add('hidden');
        }

        input.value = selectedText();

        input.addEventListener('focus', function () {
            input.select();
            open();
        });
        input.addEventListener('input', function () {
            render(input.value);
            dropdown.classList.remove('hidden');
        });
        input.addEventListener('keydown', function (e) {
            var items = Array.prototype.slice.call(dropdown.querySelectorAll('[data-value]'));
            var idx = items.findIndex(function (i) { return i.classList.contains('bg-primary'); });
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (dropdown.classList.contains('hidden')) { open(); return; }
                highlight(items, Math.min(idx + 1, items.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                highlight(items, Math.max(idx - 1, 0));
            } else if (e.key === 'Enter') {
                e.preventDefault();
                var active = items[idx] || items[0];
                if (active) {
                    var opt = choices().filter(function (o) { return o.value === active.dataset.value; })[0];
                    if (opt) pick(opt);
                }
            } else if (e.key === 'Escape') {
                close();
            }
        });
        document.addEventListener('click', function (e) {
            if (!wrapper.contains(e.target)) {
                close();
                input.value = selectedText();
            }
        });
    }

    function init(root) {
        (root || document).querySelectorAll('select[data-searchable]').forEach(enhance);
    }

    document.addEventListener('DOMContentLoaded', function () { init(); });
    window.SearchableSelect = { init: init, enhance: enhance };
})();
