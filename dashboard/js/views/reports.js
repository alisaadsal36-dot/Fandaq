// ══════════════════════════════════════════════
//  PAGE: REPORTS
// ══════════════════════════════════════════════
let reportType = 'monthly';
async function loadReports() {
  if (!HOTEL_ID) return;
  const data = await apiFetch(`/hotels/${HOTEL_ID}/reports/${reportType}`).catch(() => null);
  const d = data?.data || {};
  const incomeByType = d.income_by_room_type || {};
  const COLORS = ['#7c3aed', '#2563eb', '#10b981', '#f59e0b', '#ef4444'];

  destroyCharts();
  document.getElementById('content').innerHTML = `
    <div class="report-tabs">
      <button class="report-tab ${reportType === 'daily' ? 'active' : ''}" onclick="setReportType('daily')">📅 يومي</button>
      <button class="report-tab ${reportType === 'weekly' ? 'active' : ''}" onclick="setReportType('weekly')">📆 أسبوعي</button>
      <button class="report-tab ${reportType === 'monthly' ? 'active' : ''}" onclick="setReportType('monthly')">🗓️ شهري</button>
    </div>
    <div style="color:var(--muted);font-size:13px;margin-bottom:20px">
      📅 الفترة: ${data?.period_start || '—'} ← ${data?.period_end || '—'}
    </div>
    <div class="kpi-grid">
      <div class="kpi-card green"><div class="kpi-icon">💰</div><div class="kpi-label">إجمالي الدخل</div>
        <div class="kpi-value">${fmtMoney(d.total_income)}</div></div>
      <div class="kpi-card purple"><div class="kpi-icon">📈</div><div class="kpi-label">صافي الربح</div>
        <div class="kpi-value" style="color:${d.net_profit >= 0 ? 'var(--success)' : 'var(--danger)'}">${fmtMoney(d.net_profit)}</div></div>
      <div class="kpi-card blue"><div class="kpi-icon">📊</div><div class="kpi-label">نسبة الإشغال</div>
        <div class="kpi-value">${(d.occupancy_rate || 0).toFixed(1)}%</div></div>
    </div>
    <div class="charts-grid">
      <div class="chart-card"><h3>🏨 الدخل بنوع الغرفة</h3>
        <div class="chart-wrap"><canvas id="chart-rtype"></canvas></div></div>
    </div>`;

  const tl = Object.keys(incomeByType).map(roomTypeLabel); const tv = Object.values(incomeByType);
  if (tl.length) charts.rtype = new Chart(document.getElementById('chart-rtype'), {
    type: 'doughnut', data: {
      labels: tl, datasets: [{
        data: tv, backgroundColor: COLORS,
        borderColor: 'transparent', borderWidth: 0
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#8b949e', font: { family: 'IBM Plex Sans Arabic', size: 11 }, padding: 12 }
        }
      }
    }
  });
}
function setReportType(t) { reportType = t; destroyCharts(); loadReports(); }

