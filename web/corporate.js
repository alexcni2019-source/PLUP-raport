/* NRG PLUP workspace. Canonical values remain owned by the existing controllers. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = value => Number(value || 0).toLocaleString('ro-RO', {maximumFractionDigits: 2});
  const icons = {
    dashboard:'M3 10 12 3l9 7v11h-6v-8H9v8H3Z',
    weekday:'M4 21V10l6 3V6l6 4V3h4v18ZM8 17h1m4 0h1m3 0h1',
    plan:'M4 4h16v17H4ZM8 2v4m8-4v4M4 9h16M8 13h3m3 0h2m-8 4h3m3 0h2',
    forecast:'M4 20V4m0 16h17M7 15l4-5 4 2 5-7m-4 0h4v4',
    history:'M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v6l4 2',
    arrow:'M5 12h14m-6-6 6 6-6 6',
    search:'m16 16 5 5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z'
  };
  const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${icons[name] || icons.weekday}"/></svg>`;
  const numeric = new Set(['al','cu','backlogAl','backlogCu','wasteAl','wasteCu','planned','handed','wire','spool','bar','vane','cable','mi','armored','mf','goods','km','tons','drumLength']);
  const tableFilters = new Map();
  const selectedDays = new Map();
  const savedAt = new Map();

  function input(kind, row, index, field, review) {
    const [key, label] = field;
    const uncertain = review.has(index + ':' + key);
    const attributes = `data-index="${index}" data-key="${key}" aria-label="${esc(label)}, rândul ${index + 1}"`;
    let control;
    if (key === 'priority') {
      control = `<select ${attributes}><option value="" ${String(row.priority).toLowerCase() !== 'urgent' ? 'selected' : ''}>Normal</option><option value="urgent" ${String(row.priority).toLowerCase() === 'urgent' ? 'selected' : ''}>Urgent</option></select>`;
    } else {
      control = `<input ${attributes} type="text" ${numeric.has(key) ? 'inputmode="decimal"' : key === 'order' ? 'inputmode="numeric"' : 'autocomplete="off"'} maxlength="120" value="${esc(row[key])}" placeholder="${numeric.has(key) ? '0,00' : '—'}">`;
    }
    return `<label class="plan-field ${uncertain ? 'needs-review' : ''}"><span>${esc(label)}${uncertain ? ' · verifică' : ''}</span>${control}</label>`;
  }

  // One set of native fields serves both the desktop table and mobile product cards.
  function renderRows(kind, rows, fields, review) {
    const byKey = new Map(fields.map(field => [field[0], field]));
    const primary = kind === 'plan' ? ['product','client','planned','handed'] : ['product','client','km','tons','status'];
    const secondary = fields.filter(([key]) => !primary.includes(key));
    return ['AL','CU'].map(material => {
      const group = rows.map((row, index) => ({row, index})).filter(({row}) => row.material === material);
      return `<section class="plan-group"><h3><span class="metal-label ${material.toLowerCase()}">${material === 'AL' ? 'Al' : 'Cu'}</span>${material === 'AL' ? 'Aluminiu' : 'Cupru'} <small>${group.length} produse</small></h3><div class="workspace-table-scroll"><table class="workspace-table"><thead><tr>${primary.map(key => `<th scope="col">${esc(byKey.get(key)[1])}</th>`).join('')}<th scope="col"><span class="sr-only">Acțiuni</span></th></tr></thead><tbody>${group.map(({row, index}) => {
        const id = `${kind}-detail-${index}`;
        return `<tr class="workspace-product" data-work-row="${index}">${primary.map(key => `<td class="${key === 'product' ? 'product-column' : ''}">${input(kind, row, index, byKey.get(key), review)}</td>`).join('')}<td class="workspace-row-actions"><button type="button" class="text-button" data-product-details="${id}" aria-expanded="false" aria-controls="${id}">Detalii <span aria-hidden="true">⌄</span></button><button type="button" class="text-button destructive" data-remove="${index}" aria-label="Șterge produsul ${index + 1}">Șterge</button></td></tr><tr id="${id}" class="workspace-product-details" data-work-detail="${index}" hidden><td colspan="${primary.length + 1}"><div class="plan-field-grid">${secondary.map(field => input(kind, row, index, field, review)).join('')}</div></td></tr>`;
      }).join('')}</tbody></table></div></section>`;
    }).join('');
  }
  window.PLUPWorkspace = {renderRows};

  function applyFilter(kind) {
    const root = $(kind + '-rows');
    const filter = tableFilters.get(kind) || {query:'', material:'all'};
    let count = 0;
    root.querySelectorAll('[data-work-row]').forEach(row => {
      const index = row.dataset.workRow;
      const group = row.closest('.plan-group');
      const material = group.querySelector('.metal-label')?.classList.contains('cu') ? 'CU' : 'AL';
      const text = [...row.querySelectorAll('[data-key]')].map(field => field.value).join(' ').toLocaleLowerCase('ro');
      const matches = (filter.material === 'all' || material === filter.material) && text.includes(filter.query.toLocaleLowerCase('ro'));
      row.hidden = !matches;
      const detail = root.querySelector(`[data-work-detail="${index}"]`);
      const expanded = row.querySelector('[data-product-details]').getAttribute('aria-expanded') === 'true';
      detail.hidden = !matches || !expanded;
      if (matches) count++;
    });
    const countNode = $(kind + '-filter-count');
    if (countNode) countNode.textContent = count + ' produse afișate';
    $(kind + '-no-results').hidden = count > 0 || !root.querySelector('[data-work-row]');
  }

  function mountFilters(kind) {
    const bar = document.createElement('div');
    bar.className = 'workspace-filters';
    bar.id = kind + '-filters';
    bar.innerHTML = `<label class="workspace-search">${icon('search')}<span class="sr-only">Caută produs, client sau stadiu</span><input id="${kind}-search" type="search" placeholder="Caută produs, client sau stadiu…"></label><label><span class="sr-only">Material</span><select id="${kind}-material"><option value="all">Toate materialele</option><option value="AL">Aluminiu</option><option value="CU">Cupru</option></select></label><span id="${kind}-filter-count" class="workspace-filter-count" role="status"></span>`;
    $(kind + '-rows').before(bar);
    const empty = document.createElement('p');
    empty.id = kind + '-no-results'; empty.className = 'workspace-empty'; empty.hidden = true;
    empty.textContent = 'Niciun produs pentru filtrele alese.';
    $(kind + '-rows').after(empty);
    const filter = () => {
      tableFilters.set(kind, {query:$(kind + '-search').value, material:$(kind + '-material').value});
      applyFilter(kind);
    };
    $(kind + '-search').addEventListener('input', filter);
    $(kind + '-material').addEventListener('change', filter);
    new MutationObserver(() => applyFilter(kind)).observe($(kind + '-rows'), {childList:true});
    applyFilter(kind);
  }

  function productionSummary() {
    const payload = window.PLUPReport.payload();
    const values = Object.values(payload.values || {});
    const n = value => Number(String(value || '0').replace(',', '.')) || 0;
    const sum = key => values.reduce((total, value) => total + n(value[key]), 0);
    const al = sum('al'), cu = sum('cu'), handed = al + cu;
    const backlog = sum('backlogAl') + sum('backlogCu');
    const waste = sum('wasteAl') + sum('wasteCu'), processed = handed + waste;
    $('production-summary').innerHTML = [
      ['Total predat', fmt(handed), 't', `Al ${fmt(al)} · Cu ${fmt(cu)}`],
      ['Backlog', fmt(backlog), 't', 'Comparat separat cu predările'],
      ['Procent deșeu', fmt(processed ? waste / processed * 100 : 0), '%', `${fmt(waste)} t din ${fmt(processed)} t procesate`]
    ].map(([label, value, unit, note]) => `<div class="workspace-kpi"><span>${label}</span><strong>${value} <small>${unit}</small></strong><small>${note}</small></div>`).join('');
  }

  function updateState() {
    const current = window.PLUPDashboard?.current();
    const mode = ['weekday','weekend'].includes(current) ? window.PLUPReport.payload().mode : current;
    const suffix = ['weekday','weekend'].includes(mode) ? 'report' : mode;
    const node = $('workspace-state-' + suffix);
    if (!node) return;
    const dirty = window.PLUPUI.isDirty(mode);
    node.classList.toggle('is-dirty', dirty);
    const controller = mode === 'plan' ? window.PLUPPlan : mode === 'forecast' ? window.PLUPForecast : window.PLUPReport;
    const loaded = controller?.draft().metadata.id;
    node.textContent = dirty ? 'Modificări nesalvate în istoric' : savedAt.has(mode) ? 'Salvat în istoric la ' + savedAt.get(mode) : loaded ? 'Raport încărcat din istoric' : 'Ciornă · salvează în istoric când este gata';
  }

  function syncDays() {
    const entries = [...$('entry-list').querySelectorAll('.day-entry')];
    const mode = window.PLUPReport.payload().mode;
    const tabs = $('production-days');
    tabs.hidden = mode !== 'weekend' || entries.length < 2;
    const current = Math.min(selectedDays.get(mode) || 0, entries.length - 1);
    entries.forEach((entry, i) => entry.hidden = mode === 'weekend' && i !== current);
    tabs.innerHTML = entries.map((entry, i) => `<button type="button" data-production-day="${i}" aria-pressed="${i === current}" class="${i === current ? 'selected' : ''}">${esc(entry.querySelector('.day-title strong').textContent)}</button>`).join('');
  }

  function wrapDisclosure(nodes, title, anchor) {
    const disclosure = document.createElement('details');
    disclosure.className = 'workspace-disclosure';
    const summary = document.createElement('summary'); summary.textContent = title;
    disclosure.append(summary); anchor.before(disclosure);
    nodes.forEach(node => disclosure.append(node));
    return disclosure;
  }

  function homeDrafts(event) {
    const drafts = event.detail;
    const preferred = [...drafts].sort((a,b) => b[1].updated_at.localeCompare(a[1].updated_at));
    const candidate = preferred.find(([mode]) => ['weekday','weekend'].includes(mode)) || preferred[0];
    const button = $('home-continue');
    const title = $('home-draft-title');
    if (candidate) {
      const [mode, draft] = candidate;
      button.dataset.resume = mode;
      button.removeAttribute('data-view'); button.classList.remove('dashboard-card');
      button.innerHTML = 'Continuă ciorna ' + icon('arrow');
      title.textContent = {weekday:'Raportul de dimineață',weekend:'Raport de weekend',plan:'Plan de producție',forecast:'Previz zilnic'}[mode];
      $('home-draft-note').textContent = draft.payload.date + ' · Ultima modificare ' + new Date(draft.updated_at).toLocaleString('ro-RO');
      $('home-draft-badge').textContent = 'Ciornă de continuat';
    } else {
      delete button.dataset.resume; button.dataset.view = 'weekday'; button.classList.add('dashboard-card');
      button.innerHTML = 'Începe raportul ' + icon('arrow');
      title.textContent = 'Raportul de dimineață';
      $('home-draft-note').textContent = 'Pornește de la ultimele valori salvate și verifică data raportului.';
      $('home-draft-badge').textContent = 'Producție zilnică';
    }
  }

  function homeMetrics(event) {
    const home = event.detail;
    $('home-period').textContent = home.start + ' – ' + home.end;
    $('home-handed').textContent = home.current.count ? fmt(home.current.handed) : '—';
    $('home-metric-note').textContent = home.current.count ? `${home.current.count} zile cu raport · total predat în perioada selectată` : 'Nu există încă rapoarte în această perioadă.';
    $('home-backlog').textContent = home.current.count ? fmt(home.current.backlog) + ' t backlog' : 'Fără valori salvate';
    $('home-waste').textContent = home.current.count ? fmt(home.current.percent) + '% deșeu' : '';
  }

  function initialize() {
    document.querySelectorAll('.primary-nav [data-view]').forEach(button => {
      const label = document.createElement('span'); label.textContent = button.textContent;
      button.innerHTML = icon(button.dataset.view); button.append(label);
    });
    document.querySelectorAll('.dashboard-grid .dashboard-card').forEach(button => {
      const glyph = document.createElement('span'); glyph.className = 'module-icon'; glyph.innerHTML = icon(button.dataset.view);
      button.prepend(glyph);
    });
    for (const kind of ['plan','forecast']) {
      mountFilters(kind);
      const panel = $(kind + '-view');
      const imported = [...panel.querySelectorAll('.plan-import,.plan-paste-zone')];
      if (imported.length) wrapDisclosure(imported, 'Importă o imagine', imported[0]);
      // The source-table editor remains intact and keeps every imported column.
      const source = $('source-editor-' + kind);
      if (source) new MutationObserver(() => {$(kind + '-filters').hidden = !source.hidden;}).observe(source, {attributes:true, attributeFilter:['hidden']});
    }
    document.querySelectorAll('.plan-insights,.forecast-work').forEach(section => {
      const title = section.querySelector('h3')?.textContent || 'Detalii suplimentare';
      const disclosure = wrapDisclosure([section], title, section);
      if (section.contains($('plan-analyze'))) {
        const analyze = $('plan-analyze');
        analyze.addEventListener('click', () => {disclosure.open = true;});
      }
    });
    document.querySelectorAll('.smart-excel').forEach(node => node.open = false);
    document.querySelectorAll('.smart-assistant details').forEach(node => node.open = false);
    const tabs = document.createElement('div'); tabs.id = 'production-days'; tabs.className = 'production-day-tabs'; tabs.setAttribute('aria-label','Ziua de editat');
    $('entry-list').before(tabs);
    new MutationObserver(() => {syncDays(); productionSummary(); updateState();}).observe($('entry-list'), {childList:true});
    const paper = $('print-report');
    const charts = paper.querySelector('.paper-charts');
    paper.before(charts);
    wrapDisclosure([paper], 'Vezi toate valorile raportului', paper);
    document.querySelectorAll('.workspace-disclosure>summary').forEach(summary => {
      if (summary.parentElement.contains(paper)) summary.textContent = 'Vezi toate valorile raportului';
    });
    for (const [suffix, anchor] of [['report',$('save-report-button')],['plan',$('save-plan')],['forecast',$('forecast-save')]]) {
      const state = document.createElement('p'); state.id = 'workspace-state-' + suffix; state.className = 'workspace-save-state'; state.setAttribute('role','status'); state.setAttribute('aria-live','polite');
      anchor.parentElement.before(state);
    }
    syncDays(); productionSummary(); updateState();
    // Imported-source edits affect canonical totals too, without rewriting the source.
    document.addEventListener('input', event => {
      if (event.target.closest('#report-view')) productionSummary();
      updateState();
    });
  }

  document.addEventListener('plup:drafts', homeDrafts);
  document.addEventListener('plup:home', homeMetrics);
  document.addEventListener('plup:view', event => {
    const view = event.detail;
    document.body.dataset.workspaceView = view;
    $('production-summary').hidden = !['weekday','weekend'].includes(view);
    $('workspace-breadcrumb').textContent = {dashboard:'Spațiu de lucru',weekday:'Producție',weekend:'Producție',plan:'Plan de producție',forecast:'Previz zilnic',history:'Istoric rapoarte'}[view] || 'PLUP';
    updateState();
  });
  document.addEventListener('plup:state', event => {
    if (event.detail.saved) savedAt.set(event.detail.mode, new Date().toLocaleTimeString('ro-RO',{hour:'2-digit',minute:'2-digit'}));
    else if (Object.hasOwn(event.detail, 'saved')) savedAt.delete(event.detail.mode);
    updateState();
  });
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-product-details],[data-production-day]');
    if (!button) return;
    if (button.dataset.productDetails) {
      const expanded = button.getAttribute('aria-expanded') === 'true';
      button.setAttribute('aria-expanded', String(!expanded));
      $(button.dataset.productDetails).hidden = expanded;
    } else {
      selectedDays.set(window.PLUPReport.payload().mode, Number(button.dataset.productionDay));
      syncDays();
    }
  });

  // Invalid text stays visible; no save/export can silently reuse the old value.
  document.addEventListener('input', event => {
    const input = event.target;
    if (!input.matches('input[data-key],#plan-incoming') || !(numeric.has(input.dataset.key) || input.id === 'plan-incoming')) return;
    const raw = input.value.trim();
    const valid = !raw || /^(?:\d{1,7}(?:[.,]\d{0,12})?|[.,]\d{1,12})$/.test(raw);
    input.setAttribute('aria-invalid', String(!valid));
    let message = input.parentElement.querySelector('.workspace-field-error');
    if (!message && !valid) {
      message = document.createElement('span'); message.className = 'workspace-field-error'; message.setAttribute('role','status');
      message.id = 'field-error-' + (input.dataset.date || input.dataset.index || 'incoming') + '-' + (input.dataset.key || 'metal');
      input.setAttribute('aria-describedby', message.id); input.after(message);
    }
    if (message) message.textContent = valid ? '' : 'Introdu un număr pozitiv sau 0, ex. 12,5 (cel mult 12 zecimale).';
    if (!valid) {
      event.stopImmediatePropagation();
      const current = window.PLUPDashboard.current();
      window.PLUPUI.markDirty(['weekday','weekend'].includes(current) ? window.PLUPReport.payload().mode : current);
    }
  }, true);
  function stopInvalid(event) {
    if (!event.target.closest('button,[data-view]') && event.type !== 'change') return;
    const bad = document.querySelector('input[aria-invalid="true"]');
    if (!bad) return;
    if (event.type === 'click' && event.target.closest('[data-product-details],[data-production-day],#theme-toggle,#theme-system,.workspace-disclosure summary')) return;
    if (event.type === 'change' && !event.target.matches('input[name=mode],#report-date,#plan-date,#forecast-date')) return;
    if (event.type === 'change') {
      if (event.target.matches('input[name=mode]')) event.target.checked = event.target.value === window.PLUPReport.payload().mode;
      else if (event.target.id === 'report-date') event.target.value = window.PLUPReport.draft().metadata.selectedDate;
      else event.target.value = (event.target.id === 'plan-date' ? window.PLUPPlan : window.PLUPForecast).payload().date;
    }
    event.preventDefault(); event.stopImmediatePropagation(); bad.focus(); bad.scrollIntoView({block:'center',behavior:'instant'});
  }
  document.addEventListener('click', stopInvalid, true);
  document.addEventListener('change', stopInvalid, true);
  document.addEventListener('DOMContentLoaded', initialize);
})();
