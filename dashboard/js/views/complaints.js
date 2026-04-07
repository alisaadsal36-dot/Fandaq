// ══════════════════════════════════════════════
//  PAGE: COMPLAINTS & REQUESTS
// ══════════════════════════════════════════════
let compTab = 'complaints';
let ASSIGNABLE_STAFF = [];
const SLA_FIRST_RESPONSE_MINUTES = 15;
const SLA_RESOLUTION_HOURS = 4;
async function loadComplaints() {
  if (!HOTEL_ID) return;
  
  // Show temporary loading if it's the first render
  if(!document.getElementById('comp-content')) {
      document.getElementById('content').innerHTML = '<div class="loading-text" style="text-align:center;padding:40px">جاري جلب البيانات...</div>';
  }

  const [comps, reqs, staffRes] = await Promise.all([
    apiFetch(`/hotels/${HOTEL_ID}/complaints?limit=100`, { useCache: false }).catch(() => ({ complaints: [] })),
    apiFetch(`/hotels/${HOTEL_ID}/guest-requests?limit=100`, { useCache: false }).catch(() => ({ requests: [] })),
    apiFetch(`/hotels/${HOTEL_ID}/assignable-staff`, { useCache: false }).catch(() => ({ users: [] })),
  ]);
  const complaints = comps.complaints || []; const requests = reqs.requests || [];
  ASSIGNABLE_STAFF = staffRes.users || [];
  GLOBAL_DATA.all_comps = complaints; GLOBAL_DATA.all_reqs = requests;
  
  renderCompReqUI();
}

function renderCompReqUI() {
  const openC = GLOBAL_DATA.all_comps.filter(c => c.status === 'open').length;
  const openR = GLOBAL_DATA.all_reqs.filter(r => r.status === 'open').length;
  const complaintBreaches = GLOBAL_DATA.all_comps.filter(isComplaintSlaBreached).length;
  const requestBreaches = GLOBAL_DATA.all_reqs.filter(isRequestSlaBreached).length;

  document.getElementById('content').innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:12px">
      <div class="stat-card" style="padding:10px 12px;border:1px solid rgba(239,68,68,.25)">
        <div style="font-size:12px;color:var(--text-muted)">تجاوزات SLA للشكاوى</div>
        <div style="font-size:22px;font-weight:700;color:var(--danger)">${complaintBreaches}</div>
      </div>
      <div class="stat-card" style="padding:10px 12px;border:1px solid rgba(245,158,11,.25)">
        <div style="font-size:12px;color:var(--text-muted)">تجاوزات SLA للطلبات</div>
        <div style="font-size:22px;font-weight:700;color:#f59e0b">${requestBreaches}</div>
      </div>
      <div class="stat-card" style="padding:10px 12px;border:1px solid rgba(16,185,129,.2)">
        <div style="font-size:12px;color:var(--text-muted)">هدف الاستجابة الأولى</div>
        <div style="font-size:18px;font-weight:700;color:#10b981">${SLA_FIRST_RESPONSE_MINUTES} دقيقة</div>
      </div>
      <div class="stat-card" style="padding:10px 12px;border:1px solid rgba(59,130,246,.2)">
        <div style="font-size:12px;color:var(--text-muted)">هدف الإغلاق</div>
        <div style="font-size:18px;font-weight:700;color:#3b82f6">${SLA_RESOLUTION_HOURS} ساعات</div>
      </div>
    </div>

    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <div class="comp-tabs" style="margin-bottom:0">
        <button class="comp-tab ${compTab === 'complaints' ? 'active' : ''}" onclick="setCompTab('complaints')">
          ⚠️ الشكاوى ${openC > 0 ? `<span class="nav-badge" style="display:inline-block">${openC}</span>` : ''}</button>
        <button class="comp-tab ${compTab === 'requests' ? 'active' : ''}" onclick="setCompTab('requests')">
          🔔 طلبات الخدمة ${openR > 0 ? `<span class="nav-badge" style="display:inline-block">${openR}</span>` : ''}</button>
      </div>
      <input type="text" class="search-input" id="comp-search" placeholder="🔍 بحث..." oninput="filterCompReq(this.value)">
    </div>
    <div id="comp-content">${compTab === 'complaints' ? renderComplaints(GLOBAL_DATA.all_comps) : renderRequests(GLOBAL_DATA.all_reqs)}</div>`;
    
  // Re-apply search filter if any
  const q = document.getElementById('comp-search')?.value;
  if(q) filterCompReq(q);
}

function filterCompReq(q) {
  const query = q.toLowerCase();
  if (compTab === 'complaints') {
    const filtered = GLOBAL_DATA.all_comps.filter(c => (c.text || '').toLowerCase().includes(query) || statusLabel(c.status).includes(query));
    document.getElementById('comp-content').innerHTML = renderComplaints(filtered);
  } else {
    const filtered = GLOBAL_DATA.all_reqs.filter(r => (r.request_type || '').toLowerCase().includes(query) || (r.details || '').toLowerCase().includes(query) || statusLabel(r.status).includes(query));
    document.getElementById('comp-content').innerHTML = renderRequests(filtered);
  }
}

function renderComplaints(list) {
  const canSeeActor = CURRENT_USER && ['admin', 'supervisor'].includes(CURRENT_USER.role);
  const canAssign = canSeeActor;
  if (!list.length) return '<div class="empty-state"><div class="emoji">🎉</div>لا توجد شكاوى</div>';
  return `<div class="table-card"><table><thead><tr><th>الغرفة والضيف</th><th>النص</th><th>التاريخ</th><th>الحالة</th><th>SLA</th>${canAssign ? '<th>المسؤول</th>' : ''}${canSeeActor ? '<th>تم الحل بواسطة</th>' : ''}<th>تحديث</th></tr></thead>
    <tbody>${list.map(c => {
      let guestInfo = '<span style="color:var(--text-muted);font-size:12px">غير محدد</span>';
      if (c.guest_name) {
          guestInfo = `<strong>${c.guest_name}</strong>`;
          if (c.room_number) guestInfo += `<br><span style="background:var(--danger);color:#fff;padding:2px 6px;border-radius:4px;font-size:11px">غرفة ${c.room_number}</span>`;
          else guestInfo += `<br><span style="color:var(--text-muted);font-size:11px">بدون غرفة حالياً</span>`;
      }
      const sla = complaintSlaBadge(c);
      return `<tr>
      <td>${guestInfo}</td>
      <td style="max-width:300px">${c.text}</td><td>${fmtDate(c.created_at)}</td>
      <td>${badgeHtml(c.status)}</td>
      <td>${sla}</td>
      ${canAssign ? `<td>${renderAssignControl(c.id, c.assigned_to_user_id, 'complaint')}</td>` : ''}
      ${canSeeActor ? `<td>${c.resolved_by_name || '—'}</td>` : ''}
      <td><select onchange="updateComplaint('${c.id}', this.value)" style="font-size:11px">
        <option value="open" ${c.status === 'open' ? 'selected' : ''}>مفتوح</option>
        <option value="in_progress" ${c.status === 'in_progress' ? 'selected' : ''}>جاري</option>
        <option value="resolved" ${c.status === 'resolved' ? 'selected' : ''}>تم الحل</option>
      </select></td></tr>`
    }).join('')}</tbody></table></div>`;
}

function renderRequests(list) {
  const canAssign = CURRENT_USER && ['admin', 'supervisor'].includes(CURRENT_USER.role);
  if (!list.length) return '<div class="empty-state"><div class="emoji">✅</div>لا توجد طلبات</div>';
  return `<div class="table-card"><table><thead><tr><th>نوع الطلب</th><th>التفاصيل</th><th>التاريخ</th><th>الحالة</th><th>SLA</th>${canAssign ? '<th>المسؤول</th>' : ''}<th>التسليم</th><th>تحديث</th></tr></thead>
    <tbody>${list.map(r => `<tr>
      <td><strong>${r.request_type}</strong></td><td>${r.details || '—'}</td>
      <td>${fmtDate(r.created_at)}</td><td>${badgeHtml(r.status)}</td><td>${requestSlaBadge(r)}</td>
      ${canAssign ? `<td>${renderAssignControl(r.id, r.assigned_to_user_id, 'request')}</td>` : ''}
      <td>${renderFulfillmentSummary(r)}</td>
      <td>
        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
          <select onchange="updateRequest('${r.id}', this.value)" style="font-size:11px">
            <option value="open" ${r.status === 'open' ? 'selected' : ''}>مفتوح</option>
            <option value="in_progress" ${r.status === 'in_progress' ? 'selected' : ''}>جاري</option>
            <option value="completed" ${r.status === 'completed' ? 'selected' : ''}>مكتمل</option>
          </select>
          <button class="btn btn-sm btn-success" onclick="markDelivered('${r.id}', '${(r.request_type || '').replace(/'/g, "\\'")}')">✅ تم التسليم</button>
          <button class="btn btn-sm" onclick="showFulfillmentModal('${r.id}')">➕ إجراء</button>
        </div>
      </td></tr>`).join('')}</tbody></table></div>`;
}

function renderAssignControl(itemId, selectedUserId, target) {
  if (!ASSIGNABLE_STAFF.length) return '<span style="color:var(--text-muted)">لا يوجد موظفون</span>';
  const options = ASSIGNABLE_STAFF.map(u => {
    const roleLabel = u.role === 'supervisor' ? 'مشرف' : 'موظف';
    const selected = String(selectedUserId || '') === String(u.id) ? 'selected' : '';
    return `<option value="${u.id}" ${selected}>${u.full_name} (${roleLabel})</option>`;
  }).join('');
  const handler = target === 'complaint' ? `assignComplaint('${itemId}', this.value)` : `assignRequest('${itemId}', this.value)`;
  return `<select onchange="${handler}" style="font-size:11px;max-width:180px"><option value="">-- اختر --</option>${options}</select>`;
}

function renderFulfillmentSummary(requestItem) {
  const details = requestItem.fulfillment_details || [];
  if (!details.length) return '<span style="color:var(--text-muted)">لا يوجد تسجيل</span>';
  const last = details[details.length - 1] || {};
  const statusMap = { delivered: 'تم التسليم', pending: 'معلق', failed: 'فشل' };
  const statusLabel = statusMap[last.status] || (requestItem.fulfillment_status || 'partial');
  return `<div style="font-size:12px"><strong>${statusLabel}</strong><br><span style="color:var(--text-muted)">${last.item || '—'}</span></div>`;
}

function hoursBetween(start, end) {
  if (!start || !end) return null;
  const diff = (new Date(end).getTime() - new Date(start).getTime()) / 3600000;
  return Number.isFinite(diff) ? diff : null;
}

function complaintSlaBadge(c) {
  const firstResponseHours = hoursBetween(c.created_at, c.acknowledged_at);
  const resolutionHours = hoursBetween(c.created_at, c.resolved_at);
  const firstResponseOk = firstResponseHours !== null && firstResponseHours <= (SLA_FIRST_RESPONSE_MINUTES / 60);
  const resolutionOk = resolutionHours !== null && resolutionHours <= SLA_RESOLUTION_HOURS;

  if (c.status === 'open') {
    const ageHours = hoursBetween(c.created_at, new Date().toISOString()) || 0;
    if (ageHours > (SLA_FIRST_RESPONSE_MINUTES / 60)) {
      return '<span class="badge" style="background:rgba(239,68,68,.2);color:#f87171;border:1px solid rgba(239,68,68,.35)">متأخر استجابة</span>';
    }
    return '<span class="badge" style="background:rgba(245,158,11,.2);color:#f59e0b;border:1px solid rgba(245,158,11,.35)">قيد المتابعة</span>';
  }

  if (c.status === 'in_progress') {
    return firstResponseOk
      ? '<span class="badge" style="background:rgba(16,185,129,.2);color:#34d399;border:1px solid rgba(16,185,129,.35)">استجابة ضمن SLA</span>'
      : '<span class="badge" style="background:rgba(239,68,68,.2);color:#f87171;border:1px solid rgba(239,68,68,.35)">استجابة متأخرة</span>';
  }

  if (c.status === 'resolved') {
    if (firstResponseOk && resolutionOk) {
      return '<span class="badge" style="background:rgba(16,185,129,.2);color:#34d399;border:1px solid rgba(16,185,129,.35)">ملتزم SLA</span>';
    }
    return '<span class="badge" style="background:rgba(239,68,68,.2);color:#f87171;border:1px solid rgba(239,68,68,.35)">تجاوز SLA</span>';
  }

  return '<span class="badge">—</span>';
}

function requestSlaBadge(r) {
  const firstResponseHours = hoursBetween(r.created_at, r.acknowledged_at);
  const completionHours = hoursBetween(r.created_at, r.completed_at);
  const firstResponseOk = firstResponseHours !== null && firstResponseHours <= (SLA_FIRST_RESPONSE_MINUTES / 60);
  const completionOk = completionHours !== null && completionHours <= SLA_RESOLUTION_HOURS;

  if (r.status === 'open') {
    const ageHours = hoursBetween(r.created_at, new Date().toISOString()) || 0;
    if (ageHours > (SLA_FIRST_RESPONSE_MINUTES / 60)) {
      return '<span class="badge" style="background:rgba(239,68,68,.2);color:#f87171;border:1px solid rgba(239,68,68,.35)">متأخر استجابة</span>';
    }
    return '<span class="badge" style="background:rgba(245,158,11,.2);color:#f59e0b;border:1px solid rgba(245,158,11,.35)">بانتظار الاستجابة</span>';
  }

  if (r.status === 'in_progress') {
    return firstResponseOk
      ? '<span class="badge" style="background:rgba(16,185,129,.2);color:#34d399;border:1px solid rgba(16,185,129,.35)">استجابة ضمن SLA</span>'
      : '<span class="badge" style="background:rgba(239,68,68,.2);color:#f87171;border:1px solid rgba(239,68,68,.35)">استجابة متأخرة</span>';
  }

  if (r.status === 'completed') {
    if (firstResponseOk && completionOk) {
      return '<span class="badge" style="background:rgba(16,185,129,.2);color:#34d399;border:1px solid rgba(16,185,129,.35)">ملتزم SLA</span>';
    }
    return '<span class="badge" style="background:rgba(239,68,68,.2);color:#f87171;border:1px solid rgba(239,68,68,.35)">تجاوز SLA</span>';
  }

  return '<span class="badge">—</span>';
}

function isComplaintSlaBreached(c) {
  const firstResponseHours = hoursBetween(c.created_at, c.acknowledged_at);
  const resolutionHours = hoursBetween(c.created_at, c.resolved_at);

  if (c.status === 'open') {
    const ageHours = hoursBetween(c.created_at, new Date().toISOString()) || 0;
    return ageHours > (SLA_FIRST_RESPONSE_MINUTES / 60);
  }

  if (firstResponseHours !== null && firstResponseHours > (SLA_FIRST_RESPONSE_MINUTES / 60)) {
    return true;
  }

  if (c.status === 'resolved' && resolutionHours !== null && resolutionHours > SLA_RESOLUTION_HOURS) {
    return true;
  }

  return false;
}

function isRequestSlaBreached(r) {
  const firstResponseHours = hoursBetween(r.created_at, r.acknowledged_at);
  const completionHours = hoursBetween(r.created_at, r.completed_at);

  if (r.status === 'open') {
    const ageHours = hoursBetween(r.created_at, new Date().toISOString()) || 0;
    return ageHours > (SLA_FIRST_RESPONSE_MINUTES / 60);
  }

  if (firstResponseHours !== null && firstResponseHours > (SLA_FIRST_RESPONSE_MINUTES / 60)) {
    return true;
  }

  if (r.status === 'completed' && completionHours !== null && completionHours > SLA_RESOLUTION_HOURS) {
    return true;
  }

  return false;
}

function setCompTab(t) { 
    compTab = t; 
    renderCompReqUI(); 
}
async function updateComplaint(id, status) {
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/complaints/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
    showToast('تم تحديث حالة الشكوى'); 

    // Refresh from backend so actor/status metadata stays accurate.
    if(typeof clearApiCache === 'function') clearApiCache();
    await loadComplaints();
    loadBadges();
  } catch (e) { showToast('فشل التحديث', 'error'); }
}

async function assignComplaint(id, assignedToUserId) {
  if (!assignedToUserId) return;
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/complaints/${id}/assign`, {
      method: 'PATCH',
      body: JSON.stringify({ assigned_to_user_id: assignedToUserId })
    });
    showToast('تم تعيين مسؤول حل الشكوى');
    if(typeof clearApiCache === 'function') clearApiCache();
    await loadComplaints();
  } catch (e) {
    showToast('فشل تعيين المسؤول', 'error');
  }
}

async function updateRequest(id, status) {
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/guest-requests/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
    showToast('تم تحديث حالة الطلب');
    if(typeof clearApiCache === 'function') clearApiCache();
    await loadComplaints();
    loadBadges();
  } catch (e) {
    showToast('فشل تحديث الطلب', 'error');
  }
}

async function assignRequest(id, assignedToUserId) {
  if (!assignedToUserId) return;
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/guest-requests/${id}/assign`, {
      method: 'PATCH',
      body: JSON.stringify({ assigned_to_user_id: assignedToUserId })
    });
    showToast('تم تعيين مسؤول تنفيذ الطلب');
    if(typeof clearApiCache === 'function') clearApiCache();
    await loadComplaints();
  } catch (e) {
    showToast('فشل تعيين المسؤول', 'error');
  }
}

async function markDelivered(id, requestType) {
  const item = (requestType || '').trim() || 'عنصر خدمة';
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/guest-requests/${id}/fulfillment`, {
      method: 'POST',
      body: JSON.stringify({ item, status: 'delivered', notes: 'تم التسليم' })
    });
    showToast(`تم تسجيل التسليم: ${item}`);
    if(typeof clearApiCache === 'function') clearApiCache();
    await loadComplaints();
  } catch (e) {
    showToast('فشل تسجيل التسليم', 'error');
  }
}

function showFulfillmentModal(id) {
  const body = `
    <div class="form-group"><label>العنصر</label><input id="ful-item" type="text" placeholder="مثال: منشفة"></div>
    <div class="form-group"><label>الحالة</label>
      <select id="ful-status">
        <option value="delivered">تم التسليم</option>
        <option value="pending">معلق</option>
        <option value="failed">فشل</option>
      </select>
    </div>
    <div class="form-group"><label>ملاحظات</label><input id="ful-notes" type="text" placeholder="اختياري"></div>
  `;
  const foot = `
    <button class="btn" onclick="closeModal()">إلغاء</button>
    <button class="btn btn-primary" onclick="submitFulfillment('${id}')">حفظ</button>
  `;
  openModal('تسجيل إجراء خدمة', body, foot);
}

async function submitFulfillment(id) {
  const item = (document.getElementById('ful-item')?.value || '').trim();
  const status = document.getElementById('ful-status')?.value;
  const notes = (document.getElementById('ful-notes')?.value || '').trim();
  if (!item || !status) {
    showToast('أكمل بيانات الإجراء', 'error');
    return;
  }
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/guest-requests/${id}/fulfillment`, {
      method: 'POST',
      body: JSON.stringify({ item, status, notes: notes || null })
    });
    closeModal();
    showToast('تم تسجيل الإجراء بنجاح');
    if(typeof clearApiCache === 'function') clearApiCache();
    await loadComplaints();
  } catch (e) {
    showToast('فشل تسجيل الإجراء', 'error');
  }
}

