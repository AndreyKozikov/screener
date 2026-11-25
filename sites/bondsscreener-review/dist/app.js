const bonds = [
  { code: 'DEMO-01', name: 'Линия 01', type: 'Корпоративная', rating: 'A+', yield: 16.4, term: 2.2 },
  { code: 'DEMO-02', name: 'Север 02', type: 'Корпоративная', rating: 'AA−', yield: 15.7, term: 1.8 },
  { code: 'DEMO-03', name: 'Магистраль 03', type: 'Корпоративная', rating: 'AA', yield: 14.9, term: 3.5 },
  { code: 'DEMO-04', name: 'ОФЗ · пример 04', type: 'ОФЗ', rating: '—', yield: 13.9, term: 5.1 },
  { code: 'DEMO-05', name: 'ОФЗ · пример 05', type: 'ОФЗ', rating: '—', yield: 13.4, term: 2.7 },
  { code: 'DEMO-06', name: 'ОФЗ · пример 06', type: 'ОФЗ', rating: '—', yield: 12.8, term: 1.2 },
];

const byId = (id) => document.getElementById(id);
const search = byId('search');
const term = byId('term');
const minimumYield = byId('yield');
const sort = byId('sort');
const rows = byId('rows');
const dialog = byId('dialog');
const typeButtons = [...document.querySelectorAll('[data-type]')];
const selected = new Set();
const number = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
let type = 'all';

function updateSelection() {
  byId('selected').textContent = 'Выбрано для сравнения: ' + selected.size;
  byId('compare').disabled = selected.size < 2;
}

function render() {
  const query = search.value.trim().toLocaleLowerCase('ru');
  const shown = bonds.filter((bond) =>
    (type === 'all' || bond.type === type) &&
    (!term.value || bond.term <= Number(term.value)) &&
    (!minimumYield.value || bond.yield >= Number(minimumYield.value)) &&
    (bond.name + ' ' + bond.code).toLocaleLowerCase('ru').includes(query)
  );
  shown.sort((a, b) => sort.value === 'term' ? a.term - b.term : b.yield - a.yield);
  byId('count').textContent = 'Найдено ' + shown.length + ' из ' + bonds.length;
  const active = byId('active');
  active.replaceChildren();
  const removeFilter = (label, clear) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label + ' ×';
    button.setAttribute('aria-label', 'Убрать условие: ' + label);
    button.addEventListener('click', () => {
      clear();
      render();
      (active.querySelector('button') || search).focus();
    });
    active.append(button);
  };
  if (type !== 'all') removeFilter(type, () => { type = 'all'; });
  if (term.value) removeFilter(term.selectedOptions[0].textContent, () => { term.value = ''; });
  if (minimumYield.value) removeFilter('От ' + number.format(minimumYield.value) + ' %', () => { minimumYield.value = ''; });
  if (query) removeFilter('Поиск', () => { search.value = ''; });
  typeButtons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.type === type)));
  rows.innerHTML = shown.map((bond) =>
    '<tr><td><input type="checkbox" data-code="' + bond.code + '" aria-label="Выбрать ' + bond.name + '"' +
    (selected.has(bond.code) ? ' checked' : '') + '></td><td><button class="bond" type="button" data-detail="' +
    bond.code + '">' + bond.name + '</button><div class="secondary">' + bond.type + ' · ' + bond.code +
    '</div></td><td><span class="rating">' + bond.rating + '</span></td><td class="yield">' +
    number.format(bond.yield) + ' %</td><td>' + number.format(bond.term) + ' г.</td></tr>'
  ).join('') || '<tr><td colspan="5">Выпусков по этим условиям нет.</td></tr>';
  updateSelection();
}

function showBonds(title, items) {
  byId('dialog-title').textContent = title;
  byId('dialog-content').innerHTML = '<table><thead><tr><th scope="col">Выпуск</th><th scope="col">Рейтинг</th>' +
    '<th scope="col">Доходность</th><th scope="col">До погашения</th></tr></thead><tbody>' +
    items.map((bond) => '<tr><th scope="row">' + bond.name + '</th><td>' + bond.rating + '</td><td>' +
      number.format(bond.yield) + ' %</td><td>' + number.format(bond.term) + ' г.</td></tr>').join('') +
    '</tbody></table>';
  dialog.showModal();
}

typeButtons.forEach((button) => button.addEventListener('click', () => {
  type = button.dataset.type;
  render();
}));
[search, minimumYield].forEach((input) => input.addEventListener('input', render));
[term, sort].forEach((input) => input.addEventListener('change', render));
byId('reset').addEventListener('click', () => {
  type = 'all';
  search.value = term.value = minimumYield.value = '';
  render();
});
rows.addEventListener('change', ({ target }) => {
  if (!target.matches('[data-code]')) return;
  if (target.checked) selected.add(target.dataset.code);
  else selected.delete(target.dataset.code);
  updateSelection();
});
rows.addEventListener('click', ({ target }) => {
  const bond = bonds.find(({ code }) => code === target.dataset.detail);
  if (bond) showBonds(bond.name, [bond]);
});
byId('compare').addEventListener('click', () =>
  showBonds('Сравнение выпусков', bonds.filter(({ code }) => selected.has(code))));
render();
