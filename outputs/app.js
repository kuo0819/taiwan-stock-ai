let stocks = [];
let page = 1;
let marketFilter = null;
let pickCategory = "all";
const pageSize = 40;
const money = n => n >= 1000 ? n.toLocaleString("zh-TW", {maximumFractionDigits: 0}) : n.toLocaleString("zh-TW", {maximumFractionDigits: 2});
const grid = document.querySelector("#stock-grid");
const select = document.querySelector("#stock-select");
const btSelect = document.querySelector("#bt-stock");

function draw(canvas, data, color = "#65c59d") {
  const ctx = canvas.getContext("2d"), dpr = devicePixelRatio || 1, w = canvas.parentElement.clientWidth, h = canvas.parentElement.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr; ctx.scale(dpr, dpr); ctx.clearRect(0, 0, w, h);
  const min = Math.min(...data) * .97, max = Math.max(...data) * 1.03;
  ctx.strokeStyle = "#26342e";
  for (let i = 1; i < 5; i++) { const y = h * i / 5; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
  ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.beginPath();
  data.forEach((v, i) => { const x = i / (data.length - 1) * w, y = h - (v - min) / (max - min) * h; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.stroke();
}

function openStock(code) {
  ensureOption(select, code); ensureOption(btSelect, code);
  select.value = code; btSelect.value = code; update(code); backtest();
  document.querySelector("#analysis").scrollIntoView();
}

function ensureOption(element, code) {
  if ([...element.options].some(o => o.value === code)) return;
  const s = stocks.find(x => x.code === code);
  element.add(new Option(`${s.code} ${s.name}${element === select ? `｜${s.decision}` : ""}`, s.code));
}

function renderStocks() {
  grid.innerHTML = ""; select.innerHTML = ""; btSelect.innerHTML = "";
  const labels = {all: "全市場", ETF: "ETF", electronic: "電子類", financial: "金融類", traditional: "傳產／其他"};
  const picks = stocks.filter(s => pickCategory === "all" || stockCategory(s) === pickCategory).slice(0, 10);
  document.querySelector("#picks-title").textContent = `${labels[pickCategory]}前 10 名`;
  picks.forEach((s, i) => {
    grid.innerHTML += `<article class="stock" data-code="${s.code}"><div class="top"><span class="rank">#${String(i + 1).padStart(2, "0")}</span><span class="score">QMR ${s.score}</span></div><h3>${s.name}</h3><span class="code">${s.code} · ${s.market}</span><div class="price">NT$ ${money(s.price)}</div><span class="decision ${s.decision_code}">${s.decision}</span><span class="industry">${s.industry}</span></article>`;
  });
  stocks.slice(0, 100).forEach(s => {
    select.innerHTML += `<option value="${s.code}">${s.code} ${s.name}｜${s.decision}</option>`;
    btSelect.innerHTML += `<option value="${s.code}">${s.code} ${s.name}</option>`;
  });
  document.querySelectorAll(".stock").forEach(el => el.onclick = () => openStock(el.dataset.code));
}

function stockCategory(s) {
  if (s.asset_type === "ETF") return "ETF";
  const industry = s.industry || "";
  if (/半導體|電子|電腦|光電|通信|資訊|數位|網路/.test(industry)) return "electronic";
  if (/金融|保險|證券/.test(industry)) return "financial";
  return "traditional";
}

function filteredStocks() {
  const q = document.querySelector("#market-search").value.trim().toLowerCase();
  const decision = document.querySelector("#decision-filter").value;
  const market = document.querySelector("#market-filter").value;
  const type = document.querySelector("#type-filter").value;
  return stocks.filter(s => (!q || s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)) && (decision === "all" || s.decision_code === decision) && (market === "all" || s.market === market) && (type === "all" || s.asset_type === type));
}

function renderMarket() {
  const result = filteredStocks(), pages = Math.max(1, Math.ceil(result.length / pageSize));
  page = Math.min(page, pages);
  const rows = result.slice((page - 1) * pageSize, page * pageSize);
  document.querySelector("#market-body").innerHTML = rows.map(s => `<tr data-code="${s.code}"><td><b>#${s.rank} ${s.name}</b><small>${s.code} · ${s.market} · ${s.asset_type} · ${s.industry}</small></td><td><span class="decision ${s.decision_code}">${s.decision}</span></td><td>${money(s.price)}</td><td>${money(s.entry_low)} – ${money(s.entry_high)}</td><td>${money(s.take)}</td><td>${money(s.stop)}</td><td><b>${s.score}</b></td></tr>`).join("");
  document.querySelector("#result-count").textContent = `${result.length.toLocaleString()} 檔`;
  document.querySelector("#page-info").textContent = `第 ${page} / ${pages} 頁`;
  document.querySelector("#prev-page").disabled = page === 1;
  document.querySelector("#next-page").disabled = page === pages;
  document.querySelectorAll("#market-body tr").forEach(el => el.onclick = () => openStock(el.dataset.code));
}

function update(code) {
  const s = stocks.find(x => x.code === code);
  document.querySelector("#entry").textContent = `${money(s.entry_low)} – ${money(s.entry_high)}`;
  document.querySelector("#exit").textContent = money(s.exit); document.querySelector("#take").textContent = money(s.take); document.querySelector("#stop").textContent = money(s.stop);
  document.querySelector("#ai-title").textContent = `${s.name}｜${s.decision}`;
  document.querySelector("#ai-text").textContent = s.thesis;
  const cash = s.operating_cashflow == null ? "資料不足" : s.operating_cashflow > 0 ? "正值" : "負值";
  const quality = s.asset_type === "ETF" ? `<div class="signal"><span>ETF 品質評估</span><b>趨勢與風險模式</b></div>` : `<div class="signal"><span>EPS / 年化 ROE</span><b>${(s.eps || 0).toFixed(2)} / ${(s.roe || 0).toFixed(1)}%</b></div><div class="signal"><span>營業現金流 / 負債比</span><b>${cash} / ${(s.debt_ratio || 0).toFixed(1)}%</b></div><div class="signal"><span>品質條件通過</span><b>${s.quality_pass || 0} / 5</b></div>`;
  document.querySelector("#signals").innerHTML = `<div class="signal"><span>標的類型</span><b>${s.asset_type} · ${s.market}</b></div>${quality}<div class="signal"><span>全市場排名 / QMR</span><b>#${s.rank} · ${s.score} 分</b></div><div class="signal"><span>距離 20 日均線</span><b>${s.distance_ma20 >= 0 ? "+" : ""}${s.distance_ma20}%</b></div><div class="signal"><span>模型停損幅度</span><b>${s.risk_pct}%</b></div>`;
  draw(document.querySelector("#price-chart"), s.prices.slice(-180));
  calculateRisk();
}

function calculateRisk() {
  if (!stocks.length) return;
  const s = stocks.find(x => x.code === select.value) || stocks[0];
  const capital = Math.max(0, +document.querySelector("#capital").value || 0);
  const budget = +document.querySelector("#risk-budget").value;
  const riskPerShare = Math.max(.01, s.entry_high - s.stop);
  const riskShares = Math.floor(capital * budget / riskPerShare);
  const capShares = Math.floor(capital * .08 / s.entry_high);
  const shares = Math.min(riskShares, capShares);
  const lots = Math.floor(shares / 1000);
  document.querySelector("#max-position").textContent = lots > 0 ? `${lots} 張` : `${shares} 股`;
  document.querySelector("#risk-output-note").textContent = `約 NT$ ${Math.round(shares * s.entry_high).toLocaleString()}；單一標的不超過資金 8%`;
}

function ma(a, n, i) { if (i < n - 1) return null; let x = 0; for (let j = i - n + 1; j <= i; j++) x += a[j]; return x / n; }
function backtest() {
  const s = stocks.find(x => x.code === btSelect.value), prices = s.prices, fast = +document.querySelector("#fast-ma").value, slow = +document.querySelector("#slow-ma").value, stop = +document.querySelector("#stop-pct").value;
  let cash = 100, units = 0, entry = 0, wins = 0, trades = 0, equity = [];
  for (let i = 0; i < prices.length; i++) { const f = ma(prices, fast, i), l = ma(prices, slow, i), p = prices[i]; if (!units && f && f > l) { units = cash / p; entry = p; cash = 0; } if (units && ((f && f < l) || p < entry * (1 - stop))) { cash = units * p; if (p > entry) wins++; trades++; units = 0; } equity.push(cash + units * p); }
  if (units) { cash = units * prices.at(-1); if (prices.at(-1) > entry) wins++; trades++; }
  let peak = equity[0], dd = 0; equity.forEach(v => { peak = Math.max(peak, v); dd = Math.min(dd, (v - peak) / peak); });
  document.querySelector("#total-return").textContent = `${cash >= 100 ? "+" : ""}${(cash - 100).toFixed(1)}%`; document.querySelector("#drawdown").textContent = `${(dd * 100).toFixed(1)}%`; document.querySelector("#win-rate").textContent = `${trades ? Math.round(wins / trades * 100) : 0}%`; document.querySelector("#trades").textContent = trades; draw(document.querySelector("#equity-chart"), equity);
}

async function init() {
  try {
    let data = null, lastError = null;
    for (const path of ["market-data.json", "outputs/market-data.json"]) {
      try {
        const response = await fetch(path, {cache: "no-store"});
        if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
        const candidate = await response.json();
        if (!Array.isArray(candidate.stocks) || !candidate.stocks.length) throw new Error(`${path}: stocks 資料為空`);
        data = candidate;
        break;
      } catch (error) { lastError = error; }
    }
    if (!data) throw lastError || new Error("找不到市場資料");
    stocks = data.stocks;
    marketFilter = data.market_filter || {state: "資料更新中", exposure: 40, description: "目前使用舊版市場資料，建議採防守部位。"};
    document.querySelector("#market-date").textContent = data.market_date; document.querySelector("#universe-count").textContent = data.history_count.toLocaleString();
    document.querySelector("#method-text").textContent = `${data.method}。已完成 ${data.history_count} 檔 AI 分析，價格日期：${data.market_date}。`;
    document.querySelector("#market-state").textContent = marketFilter.state;
    document.querySelector("#market-description").textContent = marketFilter.description;
    document.querySelector("#market-exposure").textContent = `${marketFilter.exposure}% 以下`;
    const actions = marketFilter.state === "多頭"
      ? ["可依進場區間分批建立部位", "仍保留至少 20% 現金", "短線過熱或等待回測標的不追價"]
      : marketFilter.state === "中性"
        ? ["只買品質 4/5 以上且可分批進場標的", "新部位縮小至平常的一半", "保留約 45% 現金等待趨勢確認"]
        : ["暫停積極新增個股部位", "優先保留現金、短債或防禦型 ETF", "現有持股跌破風控條件時執行減碼"];
    document.querySelector("#market-actions").innerHTML = actions.map(x => `<li>${x}</li>`).join("");
    renderStocks(); renderMarket(); update(stocks[0].code); backtest();
  } catch (e) {
    grid.innerHTML = `<div class="load-error"><b>全市場資料載入失敗</b><p>${e.message || "請稍後重新整理。"}</p><button onclick="location.reload()">重新載入</button></div>`;
    console.error("市場資料初始化失敗", e);
  }
}

select.onchange = e => update(e.target.value);
document.querySelector("#run-test").onclick = backtest;
[btSelect, ...document.querySelectorAll(".controls select")].forEach(x => x.onchange = backtest);
["#market-search", "#decision-filter", "#market-filter", "#type-filter"].forEach(id => document.querySelector(id).oninput = () => { page = 1; renderMarket(); });
document.querySelector("#prev-page").onclick = () => { page--; renderMarket(); };
document.querySelector("#next-page").onclick = () => { page++; renderMarket(); };
document.querySelector("#capital").oninput = calculateRisk;
document.querySelector("#risk-budget").onchange = calculateRisk;
document.querySelectorAll("[data-pick-category]").forEach(button => button.onclick = () => {
  pickCategory = button.dataset.pickCategory;
  document.querySelectorAll("[data-pick-category]").forEach(x => x.classList.toggle("active", x === button));
  renderStocks();
});
window.onresize = () => { if (stocks.length) { update(select.value); backtest(); } };
init();
