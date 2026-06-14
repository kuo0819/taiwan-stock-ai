let DATA = null;
let SELECTED = null;
const $ = (id) => document.getElementById(id);
const GROUP_LABELS = {
  all:'全部類型', etf:'ETF', etf_core:'ETF｜大盤 / 高股息', semiconductor:'半導體', electronics_ai_server:'電子 / AI / 伺服器',
  finance:'金融', shipping:'航運', petrochemical_materials:'塑化 / 原物料', defensive_telecom:'電信 / 防禦型', construction_assets:'營建 / 資產', biotech:'生技醫療'
};
function fmt(n, d=2){ return Number.isFinite(+n) ? (+n).toLocaleString('zh-TW',{maximumFractionDigits:d}) : '—'; }
function cls(code){ return code==='enter'?'ok':code==='wait'?'warn':'bad'; }
function decisionClass(code){ return code==='enter'?'enter':code==='wait'?'wait':'avoid'; }
function stockUrl(code){ return `https://tw.stock.yahoo.com/quote/${code}`; }
function groupLabel(k){ return GROUP_LABELS[k] || (DATA?.groups?.[k]?.label) || k || '未分類'; }

async function load(){
  const res = await fetch(`market-data.json?ts=${Date.now()}`, {cache:'no-store'});
  if(!res.ok) throw new Error('market-data.json 載入失敗');
  DATA = await res.json();
  initGroups();
  render();
}
function initGroups(){
  const groups = new Set(['all']);
  (DATA.stocks || []).forEach(s => groups.add(s.sector_group || 'other'));
  const preferred = ['all','etf','etf_core','semiconductor','electronics_ai_server','finance','shipping','petrochemical_materials','defensive_telecom','construction_assets','biotech'];
  const ordered = [...preferred.filter(g=>groups.has(g)), ...[...groups].filter(g=>!preferred.includes(g)).sort()];
  $('groupSelect').innerHTML = ordered.map(g => `<option value="${g}">${groupLabel(g)}</option>`).join('');
}
function filtered(){
  const g = $('groupSelect').value;
  let arr = DATA.stocks || [];
  if(g !== 'all') arr = arr.filter(x => (x.sector_group || 'other') === g);
  return arr;
}
function positionSize(s){
  const capital = +$('capital').value || 30000;
  const riskPct = +$('riskPct').value || 0.005;
  const riskMoney = capital * riskPct;
  const entry = ((+s.entry_low || +s.price) + (+s.entry_high || +s.price))/2;
  const perShareRisk = Math.max(entry - (+s.stop || 0), 0.01);
  const shares = Math.max(0, Math.floor(riskMoney / perShareRisk));
  const cost = shares * entry;
  return {riskMoney, shares, cost, entry, perShareRisk};
}
function copyPlan(s){
  const p = positionSize(s);
  const text = `台股日線波段｜不當沖｜${s.code} ${s.name}｜限價買進區 ${fmt(s.entry_low)}-${fmt(s.entry_high)}｜建議 ${p.shares} 股｜停損 ${fmt(s.stop)}｜TP1 ${fmt(s.tp1)} 出50%｜TP2 ${fmt(s.tp2)} 出30%｜TP3 ${fmt(s.tp3)} 出20%｜資料日期 ${DATA.market_date}`;
  navigator.clipboard?.writeText(text);
  alert('已複製下單參數');
}
function selectStock(code){
  SELECTED = (DATA.stocks || []).find(s => s.code === code) || null;
  renderSelected();
  $('backtestSummary').className = 'backtest-summary empty';
  $('backtestSummary').textContent = '尚未回測。';
  $('backtestTrades').innerHTML = '';
  window.scrollTo({top: document.querySelector('.selected-panel').offsetTop - 20, behavior:'smooth'});
}
window.selectStock = selectStock;
window.copyPlanByCode = (code) => { const s = (DATA.stocks||[]).find(x=>x.code===code); if(s) copyPlan(s); };

function renderCards(){
  const n = +$('topN').value || 10;
  const arr = filtered();
  const primary = arr.filter(x => x.decision_code !== 'avoid');
  const list = (primary.length ? primary : arr).slice(0,n);
  $('cards').innerHTML = list.length ? list.map((s,idx) => {
    const p = positionSize(s);
    return `<article class="card ${decisionClass(s.decision_code)}">
      <div class="rank">#${idx+1}</div>
      <span class="chip">${s.market || 'TW'}</span><span class="chip">${s.sector || groupLabel(s.sector_group)}</span><span class="chip score">Score ${s.score ?? '—'}</span>
      <h3>${s.code} ${s.name}</h3>
      <p class="${cls(s.decision_code)}"><b>${s.decision || '觀察'}</b></p>
      <p class="reason">${s.reason || ''}</p>
      <div class="plan">
        <div><span class="label">買進區</span>${fmt(s.entry_low)} – ${fmt(s.entry_high)}</div>
        <div><span class="label">建議股數</span>${p.shares} 股</div>
        <div><span class="label">停損</span>${fmt(s.stop)}</div>
        <div><span class="label">TP2</span>${fmt(s.tp2)}</div>
        <div><span class="label">RSI</span>${fmt(s.rsi14,1)}</div>
        <div><span class="label">資料源</span>${s.data_source || '—'}</div>
      </div>
      <div class="actions compact-actions">
        <button onclick="selectStock('${s.code}')">套用 / 回測</button>
        <button onclick="copyPlanByCode('${s.code}')">複製參數</button>
        <a href="${stockUrl(s.code)}" target="_blank" rel="noopener">Yahoo 股價</a>
      </div>
    </article>`;
  }).join('') : '<div class="empty">目前沒有資料。請確認 GitHub Actions 是否成功產生 market-data.json。</div>';
}
function renderSelected(){
  if(!SELECTED){ $('selectedPlan').className = 'selectedPlan empty'; $('selectedPlan').textContent = '尚未選取股票。'; return; }
  const s = SELECTED, p = positionSize(s);
  $('selectedPlan').className = 'selectedPlan';
  $('selectedPlan').innerHTML = `<div class="ticket-head"><h3>${s.code} ${s.name}</h3><span class="chip ${cls(s.decision_code)}">${s.decision || '觀察'}</span></div>
    <div class="ticket-grid">
      <div><span class="label">交易方式</span><b>現股日線波段，不當沖</b></div>
      <div><span class="label">委託類型</span><b>限價買進</b></div>
      <div><span class="label">買進區</span><b>${fmt(s.entry_low)} – ${fmt(s.entry_high)}</b></div>
      <div><span class="label">建議股數</span><b>${p.shares} 股</b></div>
      <div><span class="label">估算成本</span><b>${fmt(p.cost,0)} TWD</b></div>
      <div><span class="label">本筆風險</span><b>${fmt(p.riskMoney,0)} TWD</b></div>
      <div><span class="label">停損</span><b>${fmt(s.stop)}</b></div>
      <div><span class="label">TP1</span><b>${fmt(s.tp1)} 出 50%</b></div>
      <div><span class="label">TP2</span><b>${fmt(s.tp2)} 出 30%</b></div>
      <div><span class="label">TP3</span><b>${fmt(s.tp3)} 出 20%</b></div>
    </div>
    <p class="reason">${s.reason || ''}</p>
    <div class="actions"><button onclick="copyPlanByCode('${s.code}')">複製下單參數</button><a href="${stockUrl(s.code)}" target="_blank" rel="noopener">開啟 Yahoo 股價</a></div>`;
}
function renderTable(){
  const q = $('search').value.trim().toLowerCase();
  let arr = filtered();
  if(q) arr = arr.filter(s => `${s.code} ${s.name} ${s.sector} ${s.decision} ${s.sector_group}`.toLowerCase().includes(q));
  $('stockRows').innerHTML = arr.slice(0,240).map(s => `<tr>
    <td><button class="mini" onclick="selectStock('${s.code}')">套用</button></td><td>${s.code}</td><td>${s.name}</td><td>${s.sector || groupLabel(s.sector_group)}</td><td>${fmt(s.price)}</td><td>${s.score ?? '—'}</td>
    <td class="${cls(s.decision_code)}">${s.decision || '—'}</td><td>${fmt(s.entry_low)}–${fmt(s.entry_high)}</td><td>${fmt(s.stop)}</td><td>${fmt(s.tp2)}</td>
  </tr>`).join('');
}
function render(){
  $('marketDate').textContent = DATA.market_date || '—';
  $('generatedAt').textContent = DATA.generated_at ? new Date(DATA.generated_at).toLocaleString('zh-TW') : '—';
  $('marketState').textContent = `${DATA.market_filter?.state || '—'} · 建議曝險 ${DATA.market_filter?.exposure ?? '—'}%`;
  $('stockCount').textContent = `${DATA.history_count || 0} / ${DATA.universe_count || 0}`;
  const src = DATA.source_summary || {};
  $('sourceNote').textContent = `資料來源：${src.primary || '—'}；${src.note || DATA.method || ''}`;
  renderCards(); renderSelected(); renderTable();
}

function ma(arr, idx, len, key='close') { if(idx < len-1) return null; let s=0; for(let i=idx-len+1;i<=idx;i++) s += +arr[i][key]; return s/len; }
function rsi(arr, idx, len=14){ if(idx < len) return null; let gain=0, loss=0; for(let i=idx-len+1;i<=idx;i++){ const ch=+arr[i].close - +arr[i-1].close; if(ch>=0) gain+=ch; else loss-=ch; } if(loss===0) return 100; const rs=gain/loss; return 100 - 100/(1+rs); }
function atr(arr, idx, len=14){ if(idx < len) return null; let sum=0; for(let i=idx-len+1;i<=idx;i++){ const h=+arr[i].max, l=+arr[i].min, pc=+arr[i-1].close; sum += Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc)); } return sum/len; }
async function fetchFinMind(code){
  const token = $('token').value.trim();
  const end = new Date();
  const start = new Date(end.getTime() - 430*24*3600*1000);
  const qs = new URLSearchParams({dataset:'TaiwanStockPrice', data_id: code, start_date: start.toISOString().slice(0,10), end_date: end.toISOString().slice(0,10)});
  if(token) qs.set('token', token);
  const url = `https://api.finmindtrade.com/api/v4/data?${qs.toString()}`;
  const res = await fetch(url);
  if(!res.ok) throw new Error(`FinMind HTTP ${res.status}`);
  const json = await res.json();
  if(json.status !== 200 || !Array.isArray(json.data) || json.data.length < 90) throw new Error(json.msg || 'FinMind 回傳資料不足');
  return json.data.map(x=>({date:x.date, open:+x.open, max:+x.max, min:+x.min, close:+x.close, Trading_Volume:+x.Trading_Volume})).filter(x=>Number.isFinite(x.close));
}
function runBacktest(data){
  const trades=[]; const maxHold=20; let i=80;
  while(i < data.length - 2){
    const close=+data[i].close, m20=ma(data,i,20), m60=ma(data,i,60), R=rsi(data,i,14), A=atr(data,i,14);
    if(!m20 || !m60 || !R || !A){ i++; continue; }
    const trend = close > m60 && m20 > m60;
    const notChase = close <= m20 * 1.08;
    const pullback = close >= m20 * 0.97 && close <= m20 * 1.04;
    const momentum = R >= 45 && R <= 68;
    if(!(trend && notChase && pullback && momentum)){ i++; continue; }
    const entry = +data[i+1].open;
    const recentLow = Math.min(...data.slice(Math.max(0,i-10), i+1).map(x=>+x.min));
    const stop = Math.min(recentLow*0.985, entry - A*1.2);
    const risk = entry - stop;
    if(risk <= 0 || risk/entry > 0.08){ i++; continue; }
    const tp1=entry+risk, tp2=entry+risk*2, tp3=entry+risk*3;
    let remain=1, rTotal=0, exitDate=data[Math.min(data.length-1,i+maxHold)].date, outcome='Time';
    let hit1=false, hit2=false;
    let j=i+1;
    for(; j<Math.min(data.length, i+1+maxHold); j++){
      const hi=+data[j].max, lo=+data[j].min;
      if(lo <= stop){ rTotal += remain * -1; outcome='SL'; exitDate=data[j].date; break; }
      if(!hit1 && hi >= tp1){ rTotal += 0.5 * 1; remain -= 0.5; hit1=true; outcome='TP1'; exitDate=data[j].date; }
      if(!hit2 && hi >= tp2){ rTotal += 0.3 * 2; remain -= 0.3; hit2=true; outcome='TP2'; exitDate=data[j].date; }
      if(hi >= tp3){ rTotal += remain * 3; remain=0; outcome='TP3'; exitDate=data[j].date; break; }
    }
    if(remain > 0 && outcome==='Time'){
      const exit = +data[Math.min(data.length-1, i+maxHold)].close;
      rTotal += remain * ((exit - entry) / risk);
    }
    // 手續費與滑價粗估：每筆扣 0.08R
    rTotal -= 0.08;
    trades.push({entryDate:data[i+1].date, exitDate, entry, stop, tp1, tp2, tp3, outcome, r:rTotal});
    i = Math.max(i+5, j);
  }
  return trades;
}
function maxDrawdownByR(trades){ let eq=0, peak=0, mdd=0; for(const t of trades){ eq += t.r; peak=Math.max(peak,eq); mdd=Math.min(mdd, eq-peak); } return mdd; }
async function backtestSelected(){
  if(!SELECTED) return alert('請先套用一檔股票');
  $('backtestSummary').className = 'backtest-summary'; $('backtestSummary').textContent = '回測資料載入中...'; $('backtestTrades').innerHTML='';
  try{
    const data = await fetchFinMind(SELECTED.code);
    const trades = runBacktest(data);
    if(!trades.length){ $('backtestSummary').innerHTML = `<b>沒有足夠交易樣本</b><br>這代表最近一年這檔股票很少符合目前保守波段條件。`; return; }
    const wins = trades.filter(t=>t.r>0).length;
    const totalR = trades.reduce((a,b)=>a+b.r,0);
    const avgR = totalR / trades.length;
    const mdd = maxDrawdownByR(trades);
    const capital = +$('capital').value || 30000;
    const riskPct = +$('riskPct').value || 0.005;
    const twd = totalR * capital * riskPct;
    $('backtestSummary').innerHTML = `<div class="bt-grid">
      <div><span class="label">交易次數</span><b>${trades.length}</b></div>
      <div><span class="label">勝率</span><b>${fmt(wins/trades.length*100,1)}%</b></div>
      <div><span class="label">總 R</span><b class="${totalR>=0?'ok':'bad'}">${fmt(totalR,2)}R</b></div>
      <div><span class="label">平均 R</span><b>${fmt(avgR,2)}R</b></div>
      <div><span class="label">最大回撤</span><b class="bad">${fmt(mdd,2)}R</b></div>
      <div><span class="label">估算損益</span><b class="${twd>=0?'ok':'bad'}">${fmt(twd,0)} TWD</b></div>
    </div>`;
    $('backtestTrades').innerHTML = trades.slice(-12).reverse().map(t=>`<div class="trade-row"><b>${t.entryDate}</b> → ${t.exitDate}<span>${t.outcome}</span><span class="${t.r>=0?'ok':'bad'}">${fmt(t.r,2)}R</span></div>`).join('');
  }catch(err){
    $('backtestSummary').innerHTML = `<b>回測失敗</b><br>${err.message}<br><small>可能是 FinMind 免費額度、Token、假日資料或瀏覽器連線問題。</small>`;
  }
}
['groupSelect','topN','capital','riskPct'].forEach(id => $(id).addEventListener('change', render));
$('search').addEventListener('input', renderTable);
$('refreshBtn').addEventListener('click', render);
$('backtestBtn').addEventListener('click', backtestSelected);
load().catch(err => { document.body.innerHTML = `<main class="container"><section class="panel"><h1>資料載入失敗</h1><p>${err.message}</p><p>請確認 GitHub Actions 是否成功產生 outputs/market-data.json。</p></section></main>`; });
