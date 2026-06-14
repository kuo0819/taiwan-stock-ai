let DATA = null;
const $ = (id) => document.getElementById(id);
function fmt(n, d=2){ return Number.isFinite(+n) ? (+n).toLocaleString('zh-TW',{maximumFractionDigits:d}) : '—'; }
function cls(code){ return code==='enter'?'ok':code==='wait'?'warn':'bad'; }
function decisionClass(code){ return code==='enter'?'enter':code==='wait'?'wait':'avoid'; }
function stockUrl(code){ return `https://tw.stock.yahoo.com/quote/${code}`; }
async function load(){
  const res = await fetch(`market-data.json?ts=${Date.now()}`, {cache:'no-store'});
  if(!res.ok) throw new Error('market-data.json 載入失敗');
  DATA = await res.json();
  render();
}
function filtered(){
  const g = $('groupSelect').value;
  let arr = DATA.stocks || [];
  if(g !== 'all') arr = arr.filter(x => x.sector_group === g);
  return arr;
}
function positionSize(s){
  const capital = +$('capital').value || 30000;
  const riskPct = +$('riskPct').value || 0.005;
  const riskMoney = capital * riskPct;
  const entry = ((+s.entry_low || +s.price) + (+s.entry_high || +s.price))/2;
  const perShareRisk = Math.max(entry - (+s.stop || 0), 0.01);
  const shares = Math.floor(riskMoney / perShareRisk);
  const cost = shares * entry;
  return {riskMoney, shares, cost, entry};
}
function renderCards(){
  const n = +$('topN').value || 5;
  const arr = filtered().filter(x => x.decision_code !== 'avoid').slice(0,n);
  const list = arr.length ? arr : filtered().slice(0,n);
  $('cards').innerHTML = list.map(s => {
    const p = positionSize(s);
    return `<article class="card ${decisionClass(s.decision_code)}">
      <span class="chip">${s.market}</span><span class="chip">${s.sector}</span><span class="chip score">Score ${s.score}</span>
      <h3>${s.code} ${s.name}</h3>
      <p class="${cls(s.decision_code)}"><b>${s.decision}</b></p>
      <p class="reason">${s.reason || ''}</p>
      <div class="plan">
        <div><span class="label">買進區</span>${fmt(s.entry_low)} – ${fmt(s.entry_high)}</div>
        <div><span class="label">建議股數</span>${p.shares} 股</div>
        <div><span class="label">停損</span>${fmt(s.stop)}</div>
        <div><span class="label">TP2</span>${fmt(s.tp2)}</div>
        <div><span class="label">RSI</span>${fmt(s.rsi14,1)}</div>
        <div><span class="label">資料源</span>${s.data_source || '—'}</div>
      </div>
      <p><a href="${stockUrl(s.code)}" target="_blank" rel="noopener" style="color:#54a6ff">查看 Yahoo 股價 →</a></p>
    </article>`;
  }).join('');
}
function renderTable(){
  const q = $('search').value.trim().toLowerCase();
  let arr = filtered();
  if(q) arr = arr.filter(s => `${s.code} ${s.name} ${s.sector} ${s.decision}`.toLowerCase().includes(q));
  $('stockRows').innerHTML = arr.slice(0,180).map(s => `<tr>
    <td>${s.code}</td><td>${s.name}</td><td>${s.sector}</td><td>${fmt(s.price)}</td><td>${s.score}</td>
    <td class="${cls(s.decision_code)}">${s.decision}</td><td>${fmt(s.entry_low)}–${fmt(s.entry_high)}</td><td>${fmt(s.stop)}</td><td>${fmt(s.tp2)}</td>
  </tr>`).join('');
}
function render(){
  $('marketDate').textContent = DATA.market_date || '—';
  $('generatedAt').textContent = DATA.generated_at ? new Date(DATA.generated_at).toLocaleString('zh-TW') : '—';
  $('marketState').textContent = `${DATA.market_filter?.state || '—'} · 建議曝險 ${DATA.market_filter?.exposure ?? '—'}%`;
  $('stockCount').textContent = `${DATA.history_count || 0} / ${DATA.universe_count || 0}`;
  const src = DATA.source_summary || {};
  $('sourceNote').textContent = `資料來源：${src.primary || '—'}；${src.note || ''}`;
  renderCards();
  renderTable();
}
['groupSelect','topN','capital','riskPct'].forEach(id => $(id).addEventListener('change', render));
$('search').addEventListener('input', renderTable);
$('refreshBtn').addEventListener('click', render);
load().catch(err => {
  document.body.innerHTML = `<main class="container"><section class="panel"><h1>資料載入失敗</h1><p>${err.message}</p><p>請確認 GitHub Actions 是否成功產生 outputs/market-data.json。</p></section></main>`;
});
