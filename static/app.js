(() => {
const KEY = 'teti-app-v1';
const $ = id => document.getElementById(id);
const pad = n => String(n).padStart(2, '0');
const todayStr = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`; };
const nowTime = () => { const d = new Date(); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const toMin = t => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
const shift = (s, n) => { const d = new Date(s + 'T12:00'); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`; };
const fmtDate = s => new Date(s + 'T12:00').toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' });
const fmtDur = m => m >= 60 ? `${Math.floor(m/60)} h ${m%60} min` : `${m} min`;
const addMin = (t, n) => { const x = (toMin(t) + n) % 1440; return `${pad(Math.floor(x/60))}:${pad(x%60)}`; };
const hhmm = d => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
const say = t => { $('msg').textContent = t; setTimeout(() => $('msg').textContent = '', 3500); };

let data = [], editId = null;
const newId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const api = async (path, method = 'GET', body) => {
  const r = await fetch('api/' + path, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) throw new Error(r.status);
  return r.status === 204 ? null : r.json();
};
async function load() {
  try { data = await api('feedings'); $('offline').hidden = true; }
  catch { $('offline').hidden = false; }
  renderHero();
}
async function refresh() {
  if (document.hidden) return;
  await load();
  if ($('stats').classList.contains('active') && !$('fullDlg').open) renderStats();
}
const sorted = () => [...data].sort((a, b) => (b.date + b.start).localeCompare(a.date + a.start));
const span = r => { let d = toMin(r.end) - toMin(r.start); if (d < 0) d += 1440; return d; };
const secs = r => r.type !== 'teti' ? 0 : r.laps && r.laps.length ? r.laps.reduce((a, b) => a + b, 0) : span(r) * 60;
const dur = r => Math.round(secs(r) / 60);
const startDT = r => new Date(`${r.date}T${r.start}:00`);
const endDT = r => r.type === 'teti' ? new Date(startDT(r).getTime() + span(r) * 60000) : startDT(r);

/* Tabs */
document.querySelectorAll('.tab').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === b));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === b.dataset.tab));
  if (b.dataset.tab === 'stats') renderStats();
});

/* Formulario */
const typeVal = () => document.querySelector('input[name=type]:checked').value;
let manual = false;
function syncType() {
  const t = typeVal() === 'teti', ed = !!editId;
  $('stopwatch').hidden = !t || ed;
  $('manualBtn').hidden = ed;
  $('manualBtn').textContent = t ? (manual ? 'Ocultar carga manual' : 'Cargar a mano') : (manual ? 'Usar la hora de ahora' : 'Fue en otro momento');
  $('form').hidden = t && !manual && !ed;
  $('when').hidden = !(manual || ed);
  if (!ed) $('formTitle').textContent = t ? 'Toma de teti: carga manual' : 'Toma de leche de fórmula';
  $('saveBtn').textContent = ed ? 'Guardar cambios' : (t || manual) ? 'Guardar toma' : 'Registrar ahora';
  $('fTeti').hidden = !t; $('fFormula').hidden = t;
  $('m1').required = t; $('ml').required = !t;
  $('date').required = $('start').required = !$('when').hidden;
}
$('manualBtn').onclick = () => { manual = !manual; syncType(); };
document.querySelectorAll('input[name=type]').forEach(r => r.onchange = () => { manual = false; syncType(); });

function resetForm() {
  editId = null; manual = false; $('form').reset();
  $('date').value = todayStr();
  $('start').value = nowTime();
  $('cancelBtn').hidden = true; syncType();
}
$('cancelBtn').onclick = resetForm;

$('form').onsubmit = async e => {
  e.preventDefault();
  const type = typeVal();
  const rec = { id: editId || newId(), date: $('date').value, type };
  if (type === 'teti') {
    const m1 = +$('m1').value, m2 = +$('m2').value || 0;
    rec.start = $('start').value; rec.end = addMin(rec.start, m1 + m2);
    rec.laps = m2 ? [m1 * 60, m2 * 60] : [m1 * 60];
  } else { if (!manual && !editId) { rec.date = todayStr(); rec.start = nowTime(); }   // marca de tiempo del toque
    else rec.start = $('start').value;
    rec.ml = +$('ml').value; }
  const wasEdit = !!editId;
  try { await (wasEdit ? api('feedings/' + rec.id, 'PUT', rec) : api('feedings', 'POST', rec)); }
  catch { $('msg').textContent = 'No se pudo guardar. Revisá la conexión e intentá de nuevo.'; return; }
  await load();
  resetForm();
  $('msg').textContent = wasEdit ? 'Toma actualizada ✓' : 'Toma guardada ✓';
  setTimeout(() => $('msg').textContent = '', 2500);
};

function edit(id) {
  const r = data.find(x => x.id === id); if (!r) return;
  editId = id;
  document.querySelector('.tab[data-tab=entry]').click();
  $('date').value = r.date;
  $(r.type === 'teti' ? 't-teti' : 't-formula').checked = true;
  if (r.type === 'teti') {
    $('start').value = r.start;
    const l = r.laps && r.laps.length ? r.laps : [span(r) * 60];
    const rest = l.slice(1).reduce((a, b) => a + b, 0);
    $('m1').value = Math.max(1, Math.round(l[0] / 60));
    $('m2').value = rest ? Math.max(1, Math.round(rest / 60)) : '';
  }
  else { $('start').value = r.start; $('ml').value = r.ml; }
  $('formTitle').textContent = 'Editar toma';
  $('saveBtn').textContent = 'Guardar cambios';
  $('cancelBtn').hidden = false; syncType();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
async function del(id) {
  if (!confirm('¿Borrar esta toma?')) return;
  try { await api('feedings/' + id, 'DELETE'); } catch { alert('No se pudo borrar. Revisá la conexión.'); return; }
  await load(); renderStats(); renderFull();
}

/* Listas */
function itemHTML(r) {
  const t = r.type === 'teti';
  const main = t ? `Teti · ${fmtDur(dur(r))}` : `Fórmula · ${r.ml} ml`;
  const sub = t ? `${r.start} a ${r.end}${r.laps && r.laps.length > 1 ? ' · ' + r.laps.map(l => Math.round(l / 60)).join(' + ') + ' min' : ''}` : `desde ${r.start}`;
  return `<li class="item"><div class="dot ${r.type}">${t ? 'T' : 'F'}</div>
    <div class="main"><b>${main}</b><span>${fmtDate(r.date)} · ${sub}</span></div>
    <button data-edit="${r.id}">Editar</button><button class="del" data-del="${r.id}">Borrar</button></li>`;
}
function bindList(el) {
  el.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => { $('fullDlg').close(); edit(b.dataset.edit); });
  el.querySelectorAll('[data-del]').forEach(b => b.onclick = () => del(b.dataset.del));
}
function renderRecent() {
  const date = $('statDate').value || todayStr();
  const l = sorted().filter(r => r.date === date).slice(0, 4);
  $('recent').innerHTML = l.length ? l.map(itemHTML).join('') : `<p class="empty">${data.length ? 'No hay tomas este día.' : 'Todavía no hay tomas. Cargá la primera en la pestaña “Cargar toma”.'}</p>`;
  bindList($('recent'));
}
function renderFull() {
  const l = sorted(); let day = '', h = '';
  l.forEach(r => { if (r.date !== day) { day = r.date; h += `${h ? '</ul>' : ''}<div class="dayh">${fmtDate(day)}</div><ul class="list">`; } h += itemHTML(r); });
  $('fullList').innerHTML = h ? h + '</ul>' : '<p class="empty">Sin registros.</p>';
  bindList($('fullList'));
}
$('fullBtn').onclick = () => { renderFull(); $('fullDlg').showModal(); };
$('closeDlg').onclick = () => $('fullDlg').close();

/* Métricas */
function dayStats(date) {
  const rs = data.filter(r => r.date === date).sort((a, b) => a.start.localeCompare(b.start));
  const te = rs.filter(r => r.type === 'teti'), fo = rs.filter(r => r.type === 'formula');
  const min = Math.round(te.reduce((s, r) => s + secs(r), 0) / 60), ml = fo.reduce((s, r) => s + r.ml, 0);
  let gap = null;
  if (rs.length > 1) { let t = 0; for (let i = 1; i < rs.length; i++) t += toMin(rs[i].start) - toMin(rs[i-1].start); gap = Math.round(t / (rs.length - 1)); }
  return { rs, te, fo, min, ml, gap };
}
function renderMetrics() {
  const date = $('statDate').value || todayStr(), s = dayStats(date);
  $('metricsTitle').textContent = date === todayStr() ? 'Métricas de hoy' : 'Métricas del ' + fmtDate(date);
  const m = (v, l, c = '') => `<div class="m ${c}"><b>${v}</b><span>${l}</span></div>`;
  let h = m(s.rs.length, 'Tomas en total') + m(s.te.length, 'Tomas de teti', 'p') + m(s.fo.length, 'Tomas de fórmula', 'b') +
    m(fmtDur(s.min), 'Tiempo de teti', 'p') + m(s.ml + ' ml', 'Fórmula total', 'b') +
    m(s.te.length ? fmtDur(Math.round(s.min / s.te.length)) : '—', 'Promedio por teti', 'p') +
    m(s.fo.length ? Math.round(s.ml / s.fo.length) + ' ml' : '—', 'Promedio por mamadera', 'b') +
    m(s.gap !== null ? fmtDur(s.gap) : '—', 'Entre tomas (promedio)');
  $('metrics').innerHTML = h;
}
$('statDate').onchange = () => { if (!$('statDate').value) $('statDate').value = todayStr(); renderStats(); };
$('prevDay').onclick = () => { $('statDate').value = shift($('statDate').value || todayStr(), -1); renderStats(); };
$('nextDay').onclick = () => { $('statDate').value = shift($('statDate').value || todayStr(), 1); renderStats(); };
$('todayBtn').onclick = () => { $('statDate').value = todayStr(); renderStats(); };

/* Gráficos (SVG) */
function bars(el, labels, series, colors, unit = '') {
  const W = 320, H = 150, pb = 22, pt = 16, n = labels.length, bw = W / n;
  const totals = labels.map((_, i) => series.reduce((s, a) => s + a[i], 0));
  const max = Math.max(...totals, 1);
  let g = '';
  labels.forEach((l, i) => {
    let y = H - pb;
    series.forEach((a, k) => {
      const h = a[i] / max * (H - pb - pt);
      if (h > 0) g += `<rect x="${i*bw + bw*.2}" y="${y - h}" width="${bw*.6}" height="${h}" rx="4" fill="${colors[k]}"/>`;
      y -= h;
    });
    g += `<text x="${i*bw + bw/2}" y="${y - 4}" text-anchor="middle">${totals[i] ? totals[i] + unit : ''}</text>`;
    g += `<text x="${i*bw + bw/2}" y="${H - 6}" text-anchor="middle">${l}</text>`;
  });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
}
function renderCharts() {
  const end = $('statDate').value || todayStr();
  $('chartsTitle').textContent = end === todayStr() ? 'Últimos 7 días' : '7 días hasta el ' + fmtDate(end);
  const days = Array.from({ length: 7 }, (_, i) => shift(end, i - 6));
  const st = days.map(dayStats);
  const lab = days.map(d => new Date(d + 'T12:00').toLocaleDateString('es-AR', { weekday: 'short' }).slice(0, 3));
  bars($('chTomas'), lab, [st.map(s => s.te.length), st.map(s => s.fo.length)], ['#f4a9bd', '#8cc7ea']);
  bars($('chMin'), lab, [st.map(s => s.min)], ['#f4a9bd']);
  bars($('chMl'), lab, [st.map(s => s.ml)], ['#8cc7ea']);
}
function renderStats() { renderRecent(); renderMetrics(); renderCharts(); }

/* Última toma (teti o fórmula, cruzando días) */
const ALERT_MIN = 180;   // a partir de acá el indicador queda en rojo
// Colores por tramo: [desde el minuto, color 1, color 2, texto, borde]
const TINTS = [
  [0,   '#bfe8c8', '#8fd4a0', '#1d3b27', '#5cb872'],   // 1.ª hora: verde
  [60,  '#fbd7a6', '#f7b267', '#4a2a0a', '#e8913a'],   // 2.ª hora: naranja
  [120, '#f59a9a', '#ef7b7b', '#2b1212', '#e05a5a'],   // 3.ª hora en adelante: rojo
];
function heroTint(m) {
  const h = $('hero');
  if (m < 0) { h.removeAttribute('style'); h.classList.remove('late'); return; }
  const [, a, b, ink, line] = [...TINTS].reverse().find(t => m >= t[0]);
  h.style.background = `linear-gradient(135deg, ${a}, ${b})`;
  h.style.color = ink;
  h.style.borderColor = line;
  h.classList.toggle('late', m >= ALERT_MIN);   // el latido empieza a las 3 h
}

function renderHero() {
  const now = Date.now();
  let last = null, t = 0;
  data.forEach(r => { const e = startDT(r).getTime(); if (e <= now + 60000 && e > t) { t = e; last = r; } });
  if (!last) { heroTint(-1); $('heroNext').textContent = ''; $('heroTime').textContent = '—'; $('heroSub').textContent = 'Todavía no hay tomas cargadas'; return; }
  const m = Math.floor((now - t) / 60000);
  heroTint(Math.max(0, m));
  $('heroTime').textContent = m < 1 ? 'recién' : 'hace ' + fmtDur(m);
  const nt = new Date(t + ALERT_MIN * 60000), future = nt.getTime() > now;
  const day = ymd(nt) === todayStr() ? '' : future ? ' (mañana)' : ' (ayer)';
  $('heroNext').textContent = (future ? 'Próxima toma: ' : 'Toca desde las ') + hhmm(nt) + day;
  $('heroSub').textContent = last.type === 'teti'
    ? `Teti · ${fmtDur(dur(last))} · ${last.start} a ${last.end}`
    : `Fórmula · ${last.ml} ml · ${last.start}`;
}

/* Cronómetro: se guarda con marcas de tiempo, así sobrevive a bloquear el celular */
const TK = 'teti-timer-v1';
const blank = () => ({ startTs: 0, endTs: 0, acc: 0, seg: 0, marks: [] });
let sw = blank();
try { sw = { ...sw, ...JSON.parse(localStorage.getItem(TK)) }; } catch {}
const swSave = () => { try { localStorage.setItem(TK, JSON.stringify(sw)); } catch {} };
const elapsed = () => sw.acc + (sw.seg ? Date.now() - sw.seg : 0);
const clock = ms => { const s = Math.floor(ms / 1000), h = Math.floor(s / 3600); return `${h ? h + ':' : ''}${pad(Math.floor(s % 3600 / 60))}:${pad(s % 60)}`; };
function swRender() {
  const el = elapsed(), running = !!sw.seg;
  $('swTime').textContent = clock(el);
  $('swMain').textContent = running ? 'Pausar' : el ? 'Reanudar' : 'Iniciar';
  $('swMain').classList.toggle('on', running);
  const lastMark = sw.marks.length ? sw.marks[sw.marks.length - 1] : 0;
  $('swLap').disabled = !el || sw.marks.length >= 5 || (!running && el <= lastMark);
  $('swSave').disabled = $('swReset').disabled = !el;
  const cuts = [...sw.marks, el];
  $('swLaps').innerHTML = el ? cuts.map((c, i) => `<li><span>Vuelta ${i + 1}${i === cuts.length - 1 && running ? ' · en curso' : ''}</span><b>${clock(c - (cuts[i - 1] || 0))}</b></li>`).join('') : '';
}
$('swMain').onclick = () => {
  if (sw.seg) { sw.acc += Date.now() - sw.seg; sw.seg = 0; sw.endTs = Date.now(); }
  else { if (!sw.startTs) sw.startTs = Date.now(); sw.seg = Date.now(); }
  swSave(); swRender();
};
$('swLap').onclick = () => { sw.marks.push(elapsed()); swSave(); swRender(); };
$('swReset').onclick = () => { if (confirm('¿Reiniciar el cronómetro sin guardar?')) { sw = blank(); swSave(); swRender(); } };
$('swSave').onclick = async () => {
  const total = elapsed(), cuts = [...sw.marks, total];
  const laps = cuts.map((c, i) => Math.round((c - (cuts[i - 1] || 0)) / 1000)).filter(s => s > 0);
  if (total < 5000 || !laps.length) { say('Muy corto para guardar. Podés reiniciarlo.'); return; }
  const st = new Date(sw.startTs), en = new Date(sw.seg ? Date.now() : sw.endTs);
  const rec = { id: newId(), date: ymd(st), type: 'teti', start: hhmm(st), end: hhmm(en), laps };
  try { await api('feedings', 'POST', rec); }
  catch { say('No se pudo guardar. El cronómetro sigue acá: probá de nuevo.'); return; }
  sw = blank(); swSave(); swRender();
  await load();
  say(`Toma guardada ✓ ${fmtDur(Math.max(1, Math.round(laps.reduce((a, b) => a + b) / 60)))}`);
};
setInterval(() => { if (sw.seg && !document.hidden) swRender(); }, 250);
setInterval(renderHero, 20000);
document.addEventListener('visibilitychange', () => { swRender(); renderHero(); });

/* Diálogos de ayuda e información */
$('helpBtn').onclick = () => $('helpDlg').showModal();
$('infoBtn').onclick = () => $('infoDlg').showModal();
document.querySelectorAll('[data-close]').forEach(b => b.onclick = () => b.closest('dialog').close());
[$('helpDlg'), $('infoDlg')].forEach(d => d.addEventListener('click', e => { if (e.target === d) d.close(); }));

/* Backup */
$('exportBtn').onclick = () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 1)], { type: 'application/json' }));
  a.download = `teti-app-${todayStr()}.json`; a.click();
};
$('importFile').onchange = async e => {
  try {
    const arr = JSON.parse(await e.target.files[0].text());
    if (!Array.isArray(arr)) throw 0;
    await api('feedings/bulk', 'POST', arr);
    await load(); renderStats(); alert('Copia importada');
  } catch { alert('El archivo no es una copia válida'); }
  e.target.value = '';
};

$('statDate').value = todayStr();
resetForm(); swRender();
(async () => {
  await load();
  // Migra las tomas que se hayan guardado antes en este navegador
  try {
    const old = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (Array.isArray(old) && old.length) { await api('feedings/bulk', 'POST', old); localStorage.removeItem(KEY); await load(); }
  } catch {}
  renderStats();
})();
setInterval(refresh, 10000);
document.addEventListener('visibilitychange', refresh);
})();
