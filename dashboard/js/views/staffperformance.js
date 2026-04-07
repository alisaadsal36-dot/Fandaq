// ══════════════════════════════════════════════
//  PAGE: STAFF PERFORMANCE
// ══════════════════════════════════════════════
let staffPerfDays = 30;
let STAFF_EVALUATIONS = [];

async function loadStaffPerformance() {
  if (!HOTEL_ID) return;

  document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div> جاري تحميل تقييم الموظفين...</div>';

  const [data, evalData, eligibleData] = await Promise.all([
    apiFetch(`/hotels/${HOTEL_ID}/reports/staff-performance?days=${staffPerfDays}`)
      .catch(() => ({ summary: null, leaderboard: [] })),
    apiFetch(`/hotels/${HOTEL_ID}/employee-evaluations`).catch(() => ({ evaluations: [] })),
    apiFetch(`/hotels/${HOTEL_ID}/employee-evaluations/eligible-employees`).catch(() => ({ users: [] })),
  ]);

  const summary = data.summary || {
    total_staff: 0,
    active_staff: 0,
    total_complaints_resolved: 0,
    total_reservations_approved: 0,
    total_requests_completed: 0,
    avg_response_hours: 0,
    avg_approval_hours: 0,
    first_response_sla_rate: 0,
    resolution_sla_rate: 0,
    first_response_sla_breached: 0,
    resolution_sla_breached: 0,
    sla_first_response_target_minutes: 15,
    sla_resolution_target_hours: 4,
  };
  const leaderboard = data.leaderboard || [];
  const evaluations = evalData.evaluations || [];
  STAFF_EVALUATIONS = evaluations;
  const eligibleEmployees = (eligibleData.users || []).filter(u => u.role === 'employee' || u.role === 'supervisor');

  const canSubmitSurvey = CURRENT_USER && CURRENT_USER.role === 'supervisor';
  const canReviewSurvey = CURRENT_USER && CURRENT_USER.role === 'admin';

  document.getElementById('content').innerHTML = `
    <div class="filter-bar" style="justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="filter-btn ${staffPerfDays === 7 ? 'active' : ''}" onclick="setStaffPerfDays(7)">آخر 7 أيام</button>
        <button class="filter-btn ${staffPerfDays === 30 ? 'active' : ''}" onclick="setStaffPerfDays(30)">آخر 30 يوم</button>
        <button class="filter-btn ${staffPerfDays === 90 ? 'active' : ''}" onclick="setStaffPerfDays(90)">آخر 90 يوم</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <div style="font-size:12px;color:var(--muted)">الفترة: ${data.period_start || '—'} إلى ${data.period_end || '—'}</div>
        <button class="btn btn-sm btn-success" onclick="exportStaffPerformanceExcel()">📥 تصدير Excel</button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card purple">
        <div class="kpi-icon">👥</div>
        <div class="kpi-label">إجمالي الموظفين</div>
        <div class="kpi-value">${summary.total_staff || 0}</div>
        <div class="kpi-sub">موظف/مشرف</div>
      </div>
      <div class="kpi-card green">
        <div class="kpi-icon">🔥</div>
        <div class="kpi-label">الموظفين النشطين</div>
        <div class="kpi-value">${summary.active_staff || 0}</div>
        <div class="kpi-sub">لهم عمليات خلال الفترة</div>
      </div>
      <div class="kpi-card blue">
        <div class="kpi-icon">✅</div>
        <div class="kpi-label">مشاكل تم حلها</div>
        <div class="kpi-value">${summary.total_complaints_resolved || 0}</div>
        <div class="kpi-sub">إجمالي الشكاوى المغلقة</div>
      </div>
      <div class="kpi-card blue">
        <div class="kpi-icon">🛎️</div>
        <div class="kpi-label">طلبات مكتملة</div>
        <div class="kpi-value">${summary.total_requests_completed || 0}</div>
        <div class="kpi-sub">طلبات خدمة تم إنجازها</div>
      </div>
      <div class="kpi-card orange">
        <div class="kpi-icon">⚡</div>
        <div class="kpi-label">متوسط زمن الحل</div>
        <div class="kpi-value">${Number(summary.avg_response_hours || 0).toFixed(1)} س</div>
        <div class="kpi-sub">كل ما قل كان أفضل</div>
      </div>
      <div class="kpi-card green">
        <div class="kpi-icon">🎯</div>
        <div class="kpi-label">التزام SLA للاستجابة</div>
        <div class="kpi-value">${Number(summary.first_response_sla_rate || 0).toFixed(1)}%</div>
        <div class="kpi-sub">هدف ${summary.sla_first_response_target_minutes || 15} دقيقة</div>
      </div>
      <div class="kpi-card green">
        <div class="kpi-icon">🧩</div>
        <div class="kpi-label">التزام SLA للحل</div>
        <div class="kpi-value">${Number(summary.resolution_sla_rate || 0).toFixed(1)}%</div>
        <div class="kpi-sub">هدف ${summary.sla_resolution_target_hours || 4} ساعات</div>
      </div>
      <div class="kpi-card blue">
        <div class="kpi-icon">🕒</div>
        <div class="kpi-label">متوسط اعتماد الحجز</div>
        <div class="kpi-value">${Number(summary.avg_approval_hours || 0).toFixed(1)} س</div>
        <div class="kpi-sub">من وقت الإنشاء حتى الاعتماد</div>
      </div>
      <div class="kpi-card red">
        <div class="kpi-icon">🚫</div>
        <div class="kpi-label">معدل الرفض</div>
        <div class="kpi-value">${Number(summary.rejection_rate || 0).toFixed(1)}%</div>
        <div class="kpi-sub">نسبة الحجوزات المرفوضة</div>
      </div>
      <div class="kpi-card red">
        <div class="kpi-icon">⏱️</div>
        <div class="kpi-label">تجاوزات SLA</div>
        <div class="kpi-value">${(summary.first_response_sla_breached || 0) + (summary.resolution_sla_breached || 0)}</div>
        <div class="kpi-sub">استجابة: ${summary.first_response_sla_breached || 0} | حل: ${summary.resolution_sla_breached || 0}</div>
      </div>
    </div>

    <div class="table-card">
      <div class="table-header">
        <div>
          <h3>لوحة تقييم الموظفين</h3>
          <span style="color:var(--muted);font-size:12px">الترتيب حسب النقاط ثم النشاط</span>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>الترتيب</th>
            <th>الموظف</th>
            <th>الدور</th>
            <th>حل الشكاوى</th>
            <th>تأكيد الحجوزات</th>
            <th>إكمال الطلبات</th>
            <th>إجمالي العمليات</th>
            <th>متوسط زمن الحل (س)</th>
            <th>متوسط اعتماد الحجز (س)</th>
            <th>التزام SLA استجابة</th>
            <th>التزام SLA حل</th>
            <th>اتجاه 6 أسابيع</th>
            <th>آخر نشاط</th>
            <th>النقاط</th>
          </tr>
        </thead>
        <tbody>
          ${renderStaffLeaderboardRows(leaderboard)}
        </tbody>
      </table>
    </div>

    <div class="table-card" style="margin-top:16px;padding:16px">
      <div class="table-header" style="margin-bottom:12px">
        <div>
          <h3>📝 استبيان تقييم الموظفين</h3>
          <span style="color:var(--muted);font-size:12px">يعبّيه المشرف ويرفعه للإدارة للمراجعة</span>
        </div>
      </div>

      ${canSubmitSurvey ? renderEvaluationForm(eligibleEmployees) : '<div class="empty-state" style="margin-bottom:12px">نموذج التقييم متاح للمشرف فقط.</div>'}

      <div style="margin-top:16px">
        <h4 style="margin:0 0 8px 0">📨 التقييمات المرفوعة</h4>
        ${renderEvaluationsTable(evaluations, canReviewSurvey)}
      </div>
    </div>
  `;
}

function renderEvaluationForm(eligibleEmployees) {
  const options = eligibleEmployees.map(u => `<option value="${u.id}">${u.full_name} (${u.role === 'supervisor' ? 'مشرف' : 'موظف'})</option>`).join('');
  const today = new Date().toISOString().split('T')[0];
  const monthAgoDate = new Date();
  monthAgoDate.setDate(monthAgoDate.getDate() - 30);
  const monthAgo = monthAgoDate.toISOString().split('T')[0];

  return `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;align-items:end">
      <div class="form-group"><label>الموظف</label><select id="eval-employee" class="input">${options || '<option value="">لا يوجد موظفون</option>'}</select></div>
      <div class="form-group"><label>بداية الفترة</label><input id="eval-period-start" class="input" type="date" value="${monthAgo}"></div>
      <div class="form-group"><label>نهاية الفترة</label><input id="eval-period-end" class="input" type="date" value="${today}"></div>
      <div class="form-group"><label>الالتزام (1-5)</label><input id="eval-commitment" class="input" type="number" min="1" max="5" value="4"></div>
      <div class="form-group"><label>السرعة (1-5)</label><input id="eval-speed" class="input" type="number" min="1" max="5" value="4"></div>
      <div class="form-group"><label>التعامل (1-5)</label><input id="eval-communication" class="input" type="number" min="1" max="5" value="4"></div>
      <div class="form-group"><label>الجودة (1-5)</label><input id="eval-quality" class="input" type="number" min="1" max="5" value="4"></div>
      <div class="form-group" style="grid-column:1/-1"><label>نقاط القوة</label><textarea id="eval-strengths" class="input" rows="3" style="min-height:92px;resize:vertical" placeholder="اكتب أبرز نقاط القوة"></textarea></div>
      <div class="form-group" style="grid-column:1/-1"><label>فرص التحسين</label><textarea id="eval-improvements" class="input" rows="3" style="min-height:92px;resize:vertical" placeholder="اكتب فرص التحسين"></textarea></div>
      <div class="form-group" style="grid-column:1/-1"><label>ملاحظات المشرف</label><textarea id="eval-notes" class="input" rows="3" style="min-height:92px;resize:vertical" placeholder="ملاحظات إضافية للإدارة"></textarea></div>
    </div>
    <div style="margin-top:10px;display:flex;justify-content:flex-start">
      <button class="btn btn-primary" onclick="submitEmployeeEvaluation()">⬆️ رفع التقييم للإدارة</button>
    </div>
  `;
}

function renderEvaluationsTable(evaluations, canReviewSurvey) {
  if (!evaluations.length) {
    return '<div class="empty-state"><div class="emoji">📭</div>لا توجد تقييمات مرفوعة بعد</div>';
  }

  return `
    <table>
      <thead>
        <tr>
          <th>الموظف</th>
          <th>المشرف</th>
          <th>الفترة</th>
          <th>الدرجات</th>
          <th>الحالة</th>
          <th>ملاحظات</th>
          <th>الإجراء</th>
        </tr>
      </thead>
      <tbody>
        ${evaluations.map(ev => {
          const statusMap = {
            submitted: '<span class="badge" style="background:rgba(245,158,11,.2);color:#f59e0b;border:1px solid rgba(245,158,11,.35)">مرفوع</span>',
            approved: '<span class="badge" style="background:rgba(16,185,129,.2);color:#34d399;border:1px solid rgba(16,185,129,.35)">معتمد</span>',
            needs_improvement: '<span class="badge" style="background:rgba(239,68,68,.2);color:#f87171;border:1px solid rgba(239,68,68,.35)">يحتاج تحسين</span>'
          };
          const scoreText = `التزام ${ev.commitment_score} | سرعة ${ev.speed_score} | تعامل ${ev.communication_score} | جودة ${ev.quality_score}`;
          const notes = [ev.strengths, ev.improvement_areas, ev.supervisor_notes, ev.admin_notes].filter(Boolean).join(' | ');
          const actionButtons = [
            `<button class="btn btn-sm btn-primary" onclick="openEvaluationPdf('${ev.id}')">📄 PDF</button>`
          ];
          if (canReviewSurvey && ev.status === 'submitted') {
            actionButtons.push(`<button class="btn btn-sm" style="background:#10b981" onclick="openEvaluationReview('${ev.id}')">مراجعة</button>`);
          }
          return `<tr>
            <td><strong>${ev.employee_name}</strong></td>
            <td>${ev.supervisor_name}</td>
            <td>${ev.period_start} → ${ev.period_end}</td>
            <td>${scoreText}</td>
            <td>${statusMap[ev.status] || ev.status}</td>
            <td style="max-width:320px">${notes || '—'}</td>
            <td><div style="display:flex;gap:6px;flex-wrap:wrap">${actionButtons.join('')}</div></td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;
}

function openEvaluationPdf(evaluationId) {
  const ev = (STAFF_EVALUATIONS || []).find(x => String(x.id) === String(evaluationId));
  if (!ev) {
    showToast('تعذر العثور على بيانات التقييم', 'error');
    return;
  }

  const statusMap = {
    submitted: 'مرفوع',
    approved: 'معتمد',
    needs_improvement: 'يحتاج تحسين'
  };

  const safe = (v) => String(v || '—')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

  const avgScore = ((Number(ev.commitment_score || 0) + Number(ev.speed_score || 0) + Number(ev.communication_score || 0) + Number(ev.quality_score || 0)) / 4).toFixed(2);
  const title = `تقييم موظف - ${safe(ev.employee_name)}`;

  const html = `
    <!doctype html>
    <html lang="ar" dir="rtl">
    <head>
      <meta charset="utf-8" />
      <title>${title}</title>
      <style>
        body { font-family: Tahoma, Arial, sans-serif; margin: 24px; color: #111; }
        h1 { margin: 0 0 10px; font-size: 22px; }
        .meta { margin-bottom: 18px; color: #333; font-size: 14px; }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { border: 1px solid #d0d7de; padding: 10px; text-align: right; vertical-align: top; }
        th { background: #f3f4f6; }
        .section { margin-top: 14px; }
        .label { font-weight: 700; margin-bottom: 6px; }
        .box { border: 1px solid #d0d7de; padding: 10px; min-height: 42px; }
      </style>
    </head>
    <body>
      <h1>نموذج تقييم موظف</h1>
      <div class="meta">
        الموظف: <strong>${safe(ev.employee_name)}</strong> | المشرف: <strong>${safe(ev.supervisor_name)}</strong><br/>
        الفترة: <strong>${safe(ev.period_start)} → ${safe(ev.period_end)}</strong> | الحالة: <strong>${safe(statusMap[ev.status] || ev.status)}</strong><br/>
        تاريخ الرفع: <strong>${safe(ev.submitted_at)}</strong>
      </div>

      <table>
        <thead>
          <tr>
            <th>الالتزام</th>
            <th>السرعة</th>
            <th>التعامل</th>
            <th>الجودة</th>
            <th>المتوسط</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>${safe(ev.commitment_score)}</td>
            <td>${safe(ev.speed_score)}</td>
            <td>${safe(ev.communication_score)}</td>
            <td>${safe(ev.quality_score)}</td>
            <td>${safe(avgScore)}</td>
          </tr>
        </tbody>
      </table>

      <div class="section">
        <div class="label">نقاط القوة</div>
        <div class="box">${safe(ev.strengths)}</div>
      </div>

      <div class="section">
        <div class="label">فرص التحسين</div>
        <div class="box">${safe(ev.improvement_areas)}</div>
      </div>

      <div class="section">
        <div class="label">ملاحظات المشرف</div>
        <div class="box">${safe(ev.supervisor_notes)}</div>
      </div>

      <div class="section">
        <div class="label">ملاحظات الإدارة</div>
        <div class="box">${safe(ev.admin_notes)}</div>
      </div>
    </body>
    </html>
  `;

  const printWindow = window.open('', '_blank');
  if (!printWindow) {
    showToast('المتصفح منع فتح نافذة PDF', 'error');
    return;
  }

  printWindow.document.open();
  printWindow.document.write(html);
  printWindow.document.close();
  printWindow.focus();
  setTimeout(() => {
    printWindow.print();
  }, 250);
}

function renderStaffLeaderboardRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="13"><div class="empty-state"><div class="emoji">📭</div>لا توجد بيانات أداء في الفترة المحددة</div></td></tr>';
  }

  return rows.map((r, idx) => {
    const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : '•';
    const roleLabel = r.role === 'supervisor' ? 'مشرف' : r.role === 'employee' ? 'موظف' : r.role;
    return `
      <tr>
        <td><strong>${medal} #${r.rank}</strong></td>
        <td>
          <div style="font-weight:700">${r.full_name || '—'}</div>
          <div style="font-size:11px;color:var(--muted)">@${r.username || '—'}</div>
        </td>
        <td>${roleLabel}</td>
        <td>${r.complaints_resolved || 0}</td>
        <td>${r.reservations_approved || 0}</td>
        <td>${r.requests_completed || 0}</td>
        <td>${r.total_actions || 0}</td>
        <td>${Number(r.avg_resolution_hours || 0).toFixed(2)}</td>
        <td>${Number(r.avg_approval_hours || 0).toFixed(2)}</td>
        <td>${Number(r.first_response_sla_rate || 0).toFixed(1)}%</td>
        <td>${Number(r.resolution_sla_rate || 0).toFixed(1)}%</td>
        <td>${renderWeeklyTrend(r.weekly_trend || [])}</td>
        <td>${r.last_activity_at ? fmtDate(r.last_activity_at) : '—'}</td>
        <td><span class="badge" style="background:rgba(124,58,237,.2);color:#c4b5fd;border:1px solid rgba(124,58,237,.35)">${r.score || 0}</span></td>
      </tr>
    `;
  }).join('');
}

function setStaffPerfDays(days) {
  if (staffPerfDays === days) return;
  staffPerfDays = days;
  loadStaffPerformance();
}

function renderWeeklyTrend(points) {
  if (!points.length) return '—';
  return `<div style="display:flex;gap:4px;flex-wrap:wrap">${points.map(p => {
    const level = p.actions >= 5 ? '#10b981' : p.actions >= 2 ? '#f59e0b' : '#6b7280';
    return `<span title="${p.week_start}: ${p.actions}" style="display:inline-block;min-width:20px;padding:2px 6px;border-radius:6px;background:${level};color:#fff;font-size:10px;text-align:center">${p.actions}</span>`;
  }).join('')}</div>`;
}

function exportStaffPerformanceExcel() {
  const token = sessionStorage.getItem('token');
  fetch(`${API}/hotels/${HOTEL_ID}/reports/staff-performance/export?days=${staffPerfDays}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
    .then(res => {
      if (!res.ok) throw new Error('Network response was not ok');
      return res.blob();
    })
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `staff_performance_${staffPerfDays}d.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    })
    .catch(() => showToast('فشل تصدير التقرير', 'error'));
}

async function submitEmployeeEvaluation() {
  const employee_user_id = document.getElementById('eval-employee')?.value;
  const period_start = document.getElementById('eval-period-start')?.value;
  const period_end = document.getElementById('eval-period-end')?.value;
  const commitment_score = Number(document.getElementById('eval-commitment')?.value || 0);
  const speed_score = Number(document.getElementById('eval-speed')?.value || 0);
  const communication_score = Number(document.getElementById('eval-communication')?.value || 0);
  const quality_score = Number(document.getElementById('eval-quality')?.value || 0);
  const strengths = (document.getElementById('eval-strengths')?.value || '').trim();
  const improvement_areas = (document.getElementById('eval-improvements')?.value || '').trim();
  const supervisor_notes = (document.getElementById('eval-notes')?.value || '').trim();

  if (!employee_user_id || !period_start || !period_end) {
    showToast('يرجى تعبئة الموظف والفترة', 'error');
    return;
  }
  const scores = [commitment_score, speed_score, communication_score, quality_score];
  if (scores.some(s => s < 1 || s > 5)) {
    showToast('جميع الدرجات يجب أن تكون من 1 إلى 5', 'error');
    return;
  }

  try {
    await apiFetch(`/hotels/${HOTEL_ID}/employee-evaluations`, {
      method: 'POST',
      body: JSON.stringify({
        employee_user_id,
        period_start,
        period_end,
        commitment_score,
        speed_score,
        communication_score,
        quality_score,
        strengths: strengths || null,
        improvement_areas: improvement_areas || null,
        supervisor_notes: supervisor_notes || null,
      })
    });
    showToast('تم رفع التقييم للإدارة بنجاح');
    await loadStaffPerformance();
  } catch (e) {
    showToast('فشل رفع التقييم', 'error');
  }
}

function openEvaluationReview(evaluationId) {
  const body = `
    <div style="display:grid;grid-template-columns:1fr;gap:12px">
      <div class="form-group" style="margin-bottom:0">
        <label>قرار الإدارة</label>
        <select id="eval-review-status" class="input">
          <option value="approved">اعتماد</option>
          <option value="needs_improvement">يحتاج تحسين</option>
        </select>
      </div>
      <div class="form-group" style="margin-bottom:0">
        <label>ملاحظات الإدارة</label>
        <textarea id="eval-review-notes" class="input" rows="4" style="min-height:120px;resize:vertical" placeholder="اكتب ملاحظات واضحة للإجراء القادم"></textarea>
      </div>
      <div style="font-size:12px;color:var(--muted)">سيتم إشعار المشرف بقرار الإدارة والملاحظات.</div>
    </div>
  `;
  const foot = `
    <button class="btn btn-secondary" onclick="closeModal()">إلغاء</button>
    <button class="btn btn-primary" onclick="reviewEmployeeEvaluation('${evaluationId}')">حفظ المراجعة</button>
  `;
  openModal('مراجعة تقييم موظف', body, foot);
}

async function reviewEmployeeEvaluation(evaluationId) {
  const status = document.getElementById('eval-review-status')?.value;
  const admin_notes = (document.getElementById('eval-review-notes')?.value || '').trim();
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/employee-evaluations/${evaluationId}/review`, {
      method: 'PATCH',
      body: JSON.stringify({ status, admin_notes: admin_notes || null })
    });
    closeModal();
    showToast('تمت مراجعة التقييم');
    await loadStaffPerformance();
  } catch (e) {
    showToast('فشل مراجعة التقييم', 'error');
  }
}
