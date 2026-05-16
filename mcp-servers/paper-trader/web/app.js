/* Backtest Dashboard - SPA */
const API = window.location.origin;

// State
let currentSession = null;
let cache = { equity: null, perf: null, trades: null, positions: null };

// === API ===
async function api(path) {
    const r = await fetch(path);
    return r.json();
}

async function loadSessions() {
    return api(`${API}/api/sessions`);
}

async function loadEquity(sessionId) {
    if (cache.equity) return cache.equity;
    cache.equity = await api(`${API}/api/sessions/${sessionId}/equity`);
    return cache.equity;
}

async function loadPerformance(sessionId) {
    if (cache.perf) return cache.perf;
    cache.perf = await api(`${API}/api/sessions/${sessionId}/performance`);
    return cache.perf;
}

async function loadTrades(sessionId) {
    if (cache.trades) return cache.trades;
    cache.trades = await api(`${API}/api/sessions/${sessionId}/trades`);
    return cache.trades;
}

async function loadPositions(sessionId) {
    if (cache.positions) return cache.positions;
    cache.positions = await api(`${API}/api/sessions/${sessionId}/positions/latest`);
    return cache.positions;
}

// === Session Selector ===
async function showSessions() {
    const sessions = await loadSessions();
    const list = document.getElementById('session-list');
    if (!sessions.length) {
        list.innerHTML = '<div class="empty-state">没有回测记录。请先通过 MCP 创建 session 并运行回测。</div>';
        return;
    }
    list.innerHTML = sessions.map(s => `
        <div class="session-item" onclick="selectSession('${s.session_id}')">
            <span class="status"><span class="status-badge status-${s.status}">${s.status}</span></span>
            <div class="name">${s.name || s.session_id}</div>
            <div class="detail">${s.start_date} ~ ${s.end_date} | 初始资金 ${(s.initial_capital / 10000).toFixed(0)}万 | ${s.strategy || '-'}</div>
        </div>
    `).join('');
}

async function selectSession(sessionId) {
    currentSession = sessionId;
    cache = { equity: null, perf: null, trades: null, positions: null };

    document.getElementById('session-panel').style.display = 'none';
    document.getElementById('tabs').style.display = 'flex';
    showPanel('equity');

    // Load session meta
    const status = await api(`${API}/api/sessions/${sessionId}/status`);
    const s = status.session || status;
    document.getElementById('session-name').textContent = s.name || sessionId;
    document.getElementById('session-meta').innerHTML = `
        <span>${s.start_date} ~ ${s.end_date}</span>
        <span>初始 ${(s.initial_capital / 10000).toFixed(0)}万</span>
        <span>状态: ${s.status}</span>
    `;
}

// === Tab Navigation ===
function showPanel(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.panel === name));
    document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === `panel-${name}`));

    if (name === 'equity') renderEquity();
    else if (name === 'performance') renderPerformance();
    else if (name === 'trades') renderTrades();
    else if (name === 'positions') renderPositions();
}

document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => showPanel(t.dataset.panel)));

// === Renderers ===
function fmtPct(v) { return v == null ? '-' : (v * 100).toFixed(2) + '%'; }
function fmtNum(v, d = 2) { return v == null ? '-' : v.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d }); }
function fmtDate(d) { if (!d || d.length !== 8) return d; return `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)}`; }
function pnlClass(v) { return v > 0 ? 'positive' : v < 0 ? 'negative' : ''; }

// Equity Curve
async function renderEquity() {
    const data = await loadEquity(currentSession);
    if (!data.length) return;

    const dates = data.map(d => fmtDate(d.trade_date));
    const nav = data.map(d => d.nav);
    const bm = data.map(d => d.benchmark_value * (data[0]?.nav || 1));
    const excess = data.map(d => d.excess_return);

    // Drawdown
    const peak = [];
    let p = 0;
    const dd = nav.map((v, i) => {
        p = Math.max(p, v);
        return (p - v) / p;
    });

    // Equity chart
    const eqChart = echarts.init(document.getElementById('chart-equity'));
    eqChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', textStyle: { fontSize: 12 } },
        legend: { data: ['策略净值', '基准净值'], top: 0, textStyle: { color: '#8b8fa3' } },
        grid: { left: 60, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: dates, axisLabel: { color: '#8b8fa3', fontSize: 10 }, boundaryGap: false },
        yAxis: { type: 'value', scale: true, axisLabel: { color: '#8b8fa3' }, splitLine: { lineStyle: { color: '#2a2d3a' } } },
        series: [
            { name: '策略净值', type: 'line', data: nav, lineStyle: { width: 2 }, itemStyle: { color: '#5b8ff9' }, showSymbol: false },
            { name: '基准净值', type: 'line', data: bm, lineStyle: { width: 1.5 }, itemStyle: { color: '#8b8fa3' }, showSymbol: false },
        ]
    });

    // Drawdown chart
    const ddChart = echarts.init(document.getElementById('chart-drawdown'));
    ddChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue}<br/>回撤: ${(p[0].value * 100).toFixed(2)}%` },
        grid: { left: 60, right: 20, top: 10, bottom: 30 },
        xAxis: { type: 'category', data: dates, axisLabel: { color: '#8b8fa3', fontSize: 10 }, boundaryGap: false },
        yAxis: { type: 'value', axisLabel: { color: '#8b8fa3', formatter: v => (v * 100).toFixed(0) + '%' }, splitLine: { lineStyle: { color: '#2a2d3a' } } },
        series: [{
            type: 'line', data: dd, lineStyle: { width: 1, color: '#f6544e' }, itemStyle: { color: '#f6544e' },
            showSymbol: false, areaStyle: { color: 'rgba(246,84,78,0.2)' }
        }]
    });

    window.addEventListener('resize', () => { eqChart.resize(); ddChart.resize(); });
}

// Performance Metrics
async function renderPerformance() {
    const perf = await loadPerformance(currentSession);
    if (!perf || perf.error) return;
    const m = perf.metrics || perf;

    const metrics = [
        { label: '总收益', value: fmtPct(m.total_return), cls: pnlClass(m.total_return) },
        { label: '年化收益', value: fmtPct(m.annual_return), cls: pnlClass(m.annual_return) },
        { label: '年化波动', value: fmtPct(m.annual_volatility) },
        { label: 'Sharpe', value: m.sharpe_ratio?.toFixed(2) },
        { label: 'Sortino', value: m.sortino_ratio?.toFixed(2) },
        { label: 'MaxDD', value: fmtPct(m.max_drawdown), cls: 'negative' },
        { label: 'Calmar', value: m.calmar_ratio?.toFixed(2) },
        { label: 'Win Rate', value: fmtPct(m.win_rate) },
        { label: 'Profit Factor', value: m.profit_factor?.toFixed(2) },
        { label: '换手率', value: fmtPct(m.annual_turnover) },
        { label: '交易笔数', value: m.total_trades },
        { label: '信息比率', value: m.information_ratio?.toFixed(2) },
        { label: '超额收益', value: fmtPct(m.excess_annual_return), cls: pnlClass(m.excess_annual_return) },
        { label: '跟踪误差', value: fmtPct(m.tracking_error) },
    ];

    document.getElementById('perf-metrics').innerHTML = metrics.map(m =>
        `<div class="metric-card"><div class="label">${m.label}</div><div class="value ${m.cls || ''}">${m.value}</div></div>`
    ).join('');

    // Cost breakdown
    const costChart = echarts.init(document.getElementById('chart-cost'));
    costChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        series: [{
            type: 'pie', radius: ['40%', '70%'],
            itemStyle: { borderRadius: 6 },
            label: { color: '#8b8fa3' },
            data: [
                { value: m.total_commission, name: '佣金', itemStyle: { color: '#5b8ff9' } },
                { value: m.total_stamp_duty, name: '印花税', itemStyle: { color: '#f6bd16' } },
                { value: m.total_slippage, name: '滑点', itemStyle: { color: '#f6544e' } },
            ]
        }]
    });

    // Monthly returns bar chart
    const equity = await loadEquity(currentSession);
    const monthly = {};
    equity.forEach(d => {
        const key = d.trade_date.slice(0, 6);
        monthly[key] = (monthly[key] || 0) + d.daily_return;
    });
    const mKeys = Object.keys(monthly).sort();
    const mLabels = mKeys.map(k => k.slice(0, 4) + '-' + k.slice(4));
    const mValues = mKeys.map(k => +(monthly[k] * 100).toFixed(2));

    const mChart = echarts.init(document.getElementById('chart-monthly'));
    mChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue}<br/>收益: ${p[0].value}%` },
        grid: { left: 50, right: 20, top: 10, bottom: 30 },
        xAxis: { type: 'category', data: mLabels, axisLabel: { color: '#8b8fa3', fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { color: '#8b8fa3', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#2a2d3a' } } },
        series: [{
            type: 'bar', data: mValues.map(v => ({
                value: v,
                itemStyle: { color: v >= 0 ? '#5ad8a6' : '#f6544e' }
            }))
        }]
    });

    window.addEventListener('resize', () => { costChart.resize(); mChart.resize(); });
}

// Trades Table
async function renderTrades() {
    const trades = await loadTrades(currentSession);
    if (!trades.length) return;

    const filterDir = document.getElementById('filter-direction').value;
    const filterStock = document.getElementById('filter-stock').value.trim();

    let filtered = trades;
    if (filterDir) filtered = filtered.filter(t => t.direction === filterDir);
    if (filterStock) filtered = filtered.filter(t => t.stock_code.includes(filterStock));

    document.getElementById('trades-tbody').innerHTML = filtered.map(t => `
        <tr>
            <td>${fmtDate(t.trade_date)}</td>
            <td>${t.stock_code}</td>
            <td><span class="tag tag-${t.direction}">${t.direction === 'buy' ? '买入' : '卖出'}</span></td>
            <td>${t.shares.toLocaleString()}</td>
            <td>${fmtNum(t.price)}</td>
            <td>${fmtNum(t.amount, 0)}</td>
            <td>${fmtNum(t.commission)}</td>
            <td>${fmtNum(t.stamp_duty)}</td>
            <td>${fmtNum(t.slippage_cost)}</td>
            <td>${fmtNum(t.total_cost)}</td>
            <td class="${pnlClass(t.realized_pnl)}">${t.realized_pnl != null ? fmtNum(t.realized_pnl) : '-'}</td>
        </tr>
    `).join('');
}

document.getElementById('filter-direction').addEventListener('change', () => renderTrades());
document.getElementById('filter-stock').addEventListener('input', () => renderTrades());

// Positions
async function renderPositions() {
    const positions = await loadPositions(currentSession);
    if (!positions.length) return;

    // Weight pie chart
    const wChart = echarts.init(document.getElementById('chart-weight'));
    wChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
        series: [{
            type: 'pie', radius: ['30%', '65%'],
            roseType: 'area',
            label: { color: '#8b8fa3', formatter: '{b}\n{d}%' },
            data: positions.map(p => ({
                value: +(p.weight * 100).toFixed(1),
                name: p.stock_code
            }))
        }]
    });

    // PnL bar chart
    const pChart = echarts.init(document.getElementById('chart-pnl'));
    pChart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: 60, right: 20, top: 10, bottom: 30 },
        xAxis: { type: 'category', data: positions.map(p => p.stock_code), axisLabel: { color: '#8b8fa3' } },
        yAxis: { type: 'value', axisLabel: { color: '#8b8fa3' }, splitLine: { lineStyle: { color: '#2a2d3a' } } },
        series: [{
            type: 'bar',
            data: positions.map(p => ({
                value: +p.unrealized_pnl.toFixed(0),
                itemStyle: { color: p.unrealized_pnl >= 0 ? '#5ad8a6' : '#f6544e' }
            }))
        }]
    });

    // Table
    document.getElementById('positions-tbody').innerHTML = positions.map(p => `
        <tr>
            <td>${fmtDate(p.trade_date)}</td>
            <td>${p.stock_code}</td>
            <td>${p.shares.toLocaleString()}</td>
            <td>${fmtNum(p.cost_basis)}</td>
            <td>${fmtNum(p.market_value, 0)}</td>
            <td>${fmtPct(p.weight)}</td>
            <td class="${pnlClass(p.unrealized_pnl)}">${fmtNum(p.unrealized_pnl, 0)}</td>
            <td class="${pnlClass(p.unrealized_pnl_pct)}">${fmtPct(p.unrealized_pnl_pct)}</td>
        </tr>
    `).join('');

    window.addEventListener('resize', () => { wChart.resize(); pChart.resize(); });
}

// === Init ===
showSessions();
