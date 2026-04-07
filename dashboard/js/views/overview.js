// ══════════════════════════════════════════════
//  PAGE: OVERVIEW
// ══════════════════════════════════════════════
async function loadOverview() {
  if (!HOTEL_ID) return;
  const pendCount = (GLOBAL_DATA.pending_res || []).length;
  const compCount = (GLOBAL_DATA.open_comps || []).length;

  destroyCharts();
  document.getElementById('content').innerHTML = `
    <div class="kpi-grid">
      <div class="kpi-card purple" id="kpi-income"><div class="kpi-icon">💰</div><div class="kpi-label">الدخل الشهري</div>
        <div class="kpi-value"><span class="skeleton pulse" style="display:inline-block;width:90px;height:24px"></span></div>
        <div class="kpi-sub"><span class="skeleton pulse" style="display:inline-block;width:110px;height:12px"></span></div></div>
      <div class="kpi-card blue" id="kpi-occ"><div class="kpi-icon">📊</div><div class="kpi-label">نسبة الإشغال</div>
        <div class="kpi-value"><span class="skeleton pulse" style="display:inline-block;width:60px;height:24px"></span></div>
        <div class="kpi-sub">هذا الشهر</div></div>
      <div class="kpi-card orange"><div class="kpi-icon">⏳</div><div class="kpi-label">حجوزات معلقة</div>
        <div class="kpi-value">${pendCount}</div><div class="kpi-sub">تنتظر موافقة</div></div>
      <div class="kpi-card red"><div class="kpi-icon">⚠️</div><div class="kpi-label">شكاوى مفتوحة</div>
        <div class="kpi-value">${compCount}</div><div class="kpi-sub">تحتاج متابعة</div></div>
    </div>
    <div class="charts-grid">
      <div class="chart-card"><h3>📈 توزيع الدخل بنوع الغرفة</h3>
        <div class="chart-wrap" id="wrap-income"><div class="loading-text">جاري تحميل البيانات...</div><canvas id="chart-income-type"></canvas></div></div>
    </div>
    <div class="table-card">
      <div class="table-header"><h3>🕐 آخر الحجوزات</h3>
        <button class="btn btn-primary btn-sm" onclick="nav('reservations')">عرض الكل</button></div>
      <table><thead><tr><th>رقم الحجز</th><th>نوع الغرفة</th><th>الدخول</th><th>الخروج</th><th>السعر</th><th>الحالة</th></tr></thead>
      <tbody id="ov-res-tbody"><tr><td colspan="6"><div class="loading-text">جاري جلب الحجوزات...</div></td></tr></tbody></table>
    </div>`;

  const COLORS = ['#7c3aed', '#2563eb', '#10b981', '#f59e0b', '#ef4444', '#06b6d4'];

  function renderFallbackList(container, labels, values, color) {
    if (!container) return;
    if (!labels.length) {
      container.innerHTML = '<div class="empty-state"><div class="emoji">📊</div>لا توجد بيانات</div>';
      return;
    }
    const maxVal = Math.max(...values.map(v => Number(v) || 0), 1);
    container.innerHTML = `
      <div style="padding:10px 8px;display:grid;gap:10px">
        ${labels.map((label, i) => {
          const raw = Number(values[i]) || 0;
          const pct = Math.max(4, Math.round((raw / maxVal) * 100));
          return `
            <div>
              <div style="display:flex;justify-content:space-between;gap:8px;font-size:12px;color:var(--text-muted);margin-bottom:5px">
                <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${label || '—'}</span>
                <strong style="color:var(--text)">${fmtMoney(raw)}</strong>
              </div>
              <div style="height:8px;background:rgba(148,163,184,.15);border-radius:999px;overflow:hidden">
                <div style="height:100%;width:${pct}%;background:${color};border-radius:999px"></div>
              </div>
            </div>`;
        }).join('')}
      </div>`;
  }

  // Background: monthly report (KPIs + charts)
  apiFetch(`/hotels/${HOTEL_ID}/reports/monthly`).then(res => {
    const md = res?.data || {};
    const ki = document.getElementById('kpi-income');
    if (ki) ki.innerHTML = `<div class="kpi-icon">💰</div><div class="kpi-label">الدخل الشهري</div><div class="kpi-value">${fmtMoney(md.total_income)}</div><div class="kpi-sub">صافي: ${fmtMoney(md.net_profit)}</div>`;
    const ko = document.getElementById('kpi-occ');
    if (ko) ko.innerHTML = `<div class="kpi-icon">📊</div><div class="kpi-label">نسبة الإشغال</div><div class="kpi-value">${(md.occupancy_rate || 0).toFixed(1)}%</div><div class="kpi-sub">هذا الشهر</div>`;

    const ibt = md.income_by_room_type || {};
    const tL = Object.keys(ibt).map(roomTypeLabel);
    const tV = Object.values(ibt).map(v => Number(v) || 0);
    const w1 = document.getElementById('wrap-income');
    if (w1) w1.querySelector('.loading-text')?.remove();
    if (tL.length > 0) {
      try {
        if (typeof Chart === 'undefined') throw new Error('Chart.js not loaded');
        charts.incomeType = new Chart(document.getElementById('chart-income-type'), {
          type: 'doughnut', data: { labels: tL, datasets: [{ data: tV, backgroundColor: COLORS, borderColor: 'transparent', borderWidth: 0, hoverOffset: 6 }] },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#8b949e', font: { family: 'IBM Plex Sans Arabic', size: 11 }, padding: 12 } } } }
        });
      } catch (e) {
        renderFallbackList(w1, tL, tV, 'linear-gradient(90deg,#2563eb,#7c3aed)');
      }
    } else { if (w1) w1.innerHTML = '<div class="empty-state"><div class="emoji">📊</div>لا توجد بيانات</div>'; }

  }).catch((err) => {
    const errText = String(err?.message || err || '');
    const permissionDenied = errText.includes('Not enough permissions') || errText.includes('403');
    const msg = permissionDenied ? 'غير متاح حسب الصلاحية' : 'فشل تحميل التقرير';
    const w1 = document.getElementById('wrap-income');
    if (w1) w1.innerHTML = `<div class="empty-state">${msg}</div>`;
  });

  // Background: recent reservations
  apiFetch(`/hotels/${HOTEL_ID}/reservations?limit=6`).then(data => {
    const list = (data.reservations || []).slice(0, 6);
    const tb = document.getElementById('ov-res-tbody');
    if (!tb) return;
    tb.innerHTML = list.length ? list.map(r => `
      <tr><td style="font-family:monospace;color:var(--accent)">#${String(r.id).slice(0, 6).toUpperCase()}</td>
      <td>${roomTypeLabel(r.room_type_id || '')}</td>
      <td>${fmtDate(r.check_in)}</td><td>${fmtDate(r.check_out)}</td>
      <td>${fmtMoney(r.total_price)}</td><td>${badgeHtml(r.status)}</td></tr>`).join('')
      : '<tr><td colspan="6"><div class="empty-state"><div class="emoji">📭</div>لا توجد حجوزات</div></td></tr>';
  }).catch(() => {
    const tb = document.getElementById('ov-res-tbody');
    if (tb) tb.innerHTML = '<tr><td colspan="6"><div class="empty-state">فشل تحميل الحجوزات</div></td></tr>';
  });
}


