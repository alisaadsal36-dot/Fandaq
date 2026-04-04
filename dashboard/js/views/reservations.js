// ══════════════════════════════════════════════
//  PAGE: RESERVATIONS
// ══════════════════════════════════════════════
let resFilter = 'all';
async function loadReservations() {
  if (!HOTEL_ID) return;
  const url = resFilter === 'all' ? `/hotels/${HOTEL_ID}/reservations?limit=100`
    : `/hotels/${HOTEL_ID}/reservations?status=${resFilter}&limit=100`;
  const data = await apiFetch(url).catch(() => ({ reservations: [] }));

  const pending = GLOBAL_DATA.pending_res || [];
  const all = data.reservations || [];
  GLOBAL_DATA.all_res = all;
  const statusFilters = ['all', 'pending', 'confirmed', 'checked_in', 'checked_out', 'cancelled', 'rejected'];

  document.getElementById('content').innerHTML = `
    ${pending.length > 0 && resFilter !== 'confirmed' ? `
    <div class="pending-section">
      <div class="section-title">⏳ حجوزات تنتظر موافقتك (${pending.length})</div>
      <div class="pending-cards">${pending.map((r, i) => `
        <div class="pending-card" id="pcard-${r.id}">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px">
            <div class="pending-card-id">📋 #${String(r.id).slice(0, 6).toUpperCase()}</div>
            <button class="btn btn-sm" style="padding:2px 8px; font-size:12px; background:rgba(255,165,0,0.1); color:orange; border:1px solid rgba(255,165,0,0.2)" onclick="showGuestInfoFromPending(${i})">ℹ️ بيانات الضيف</button>
          </div>
          <div class="pending-card-info"><span>نوع الغرفة: </span>${roomTypeLabel(r.room_type_id || '')}</div>
          <div class="pending-card-info"><span>الدخول: </span>${fmtDate(r.check_in)}</div>
          <div class="pending-card-info"><span>الخروج: </span>${fmtDate(r.check_out)}</div>
          <div class="pending-card-info"><span>الإجمالي: </span>${fmtMoney(r.total_price)}</div>
          <div class="pending-card-actions">
            <button class="btn btn-success" onclick="confirmRes('${r.id}')">✅ موافقة</button>
            <button class="btn btn-danger" onclick="rejectRes('${r.id}')">❌ رفض</button>
          </div>
        </div>`).join('')}</div></div>` : ''}
    <div class="filter-bar">
      ${statusFilters.map(s => `<button class="filter-btn ${resFilter === s ? 'active' : ''}" onclick="setResFilter('${s}')">
        ${s === 'all' ? 'الكل' : statusLabel(s)}</button>`).join('')}
    </div>
    <div class="table-card">
      <div class="table-header">
        <div><h3>جميع الحجوزات</h3><span style="color:var(--muted);font-size:13px" id="res-count">${all.length} حجز</span></div>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;justify-content:flex-end">
          <input type="date" id="res-date-start" class="search-input" style="width:130px;padding:8px;background-position:calc(100% - 10px)" onchange="filterReservations(document.getElementById('res-search')?.value)">
          <span style="color:var(--muted);font-size:12px">إلى</span>
          <input type="date" id="res-date-end" class="search-input" style="width:130px;padding:8px;background-position:calc(100% - 10px)" onchange="filterReservations(document.getElementById('res-search')?.value)">
          <input type="text" id="res-search" class="search-input" style="width:200px" placeholder="🔍 بحث..." oninput="filterReservations(this.value)">
          <button class="btn btn-primary btn-sm" onclick="showAddReservationModal()">➕ إضافة حجز يدوي</button>
        </div>
      </div>
      <table><thead><tr><th>رقم الحجز</th><th>تاريخ الإنشاء</th><th>الضيف</th><th>الغرفة</th><th>الدخول</th><th>الخروج</th><th>السعر</th><th>الحالة</th><th>إجراء</th></tr></thead>
      <tbody id="res-tbody">${renderResMarkup(all)}</tbody></table></div>`;
}

function filterReservations(q) {
  const query = (q || '').toLowerCase();
  const dStart = document.getElementById('res-date-start')?.value;
  const dEnd = document.getElementById('res-date-end')?.value;
  const filtered = GLOBAL_DATA.all_res.filter(r => {
    const textMatch = String(r.id).toLowerCase().includes(query) ||
      (r.guest_name || '').toLowerCase().includes(query) ||
      (r.guest_phone || '').includes(query) ||
      (r.room_number || '').includes(query);
      
    let dateMatch = true;
    const rDate = r.check_in.split('T')[0];
    if (dStart && rDate < dStart) dateMatch = false;
    if (dEnd && rDate > dEnd) dateMatch = false;
    return textMatch && dateMatch;
  });
  document.getElementById('res-tbody').innerHTML = renderResMarkup(filtered);
  document.getElementById('res-count').textContent = filtered.length + ' حجز';
}

function renderResMarkup(all) {
  if (!all.length) return '<tr><td colspan="9"><div class="empty-state"><div class="emoji">📭</div>لا توجد حجوزات مطابقة</div></td></tr>';
  return all.map(r => `
    <tr><td style="font-family:monospace;color:var(--accent)">#${String(r.id).slice(0, 6).toUpperCase()}</td>
    <td>${fmtDate(r.created_at)}</td>
    <td style="font-weight:bold;">
      <div style="display:flex; align-items:center; gap:8px">
        ${r.guest_name || 'غير محدد'}
        <button class="btn-icon-sh" title="بيانات الضيف" onclick="showGuestInfo('${r.id}')">ℹ️</button>
      </div>
    </td>
    <td><span class="badge" style="background:var(--tertiary);color:var(--text)">غرفة ${r.room_number || 'غير محدد'}</span></td><td>${fmtDate(r.check_in)}</td><td>${fmtDate(r.check_out)}</td>
    <td>${fmtMoney(r.total_price)}</td><td>${badgeHtml(r.status)}</td>
    <td>${r.status === 'pending' ? `<button class="btn btn-success btn-sm" onclick="confirmRes('${r.id}')">✅</button>
      <button class="btn btn-danger btn-sm" onclick="rejectRes('${r.id}')">❌</button>` :
      r.status === 'confirmed' ? `<button class="btn btn-primary btn-sm" onclick="checkInRes('${r.id}')">تسجيل دخول</button>
      <button class="btn btn-danger btn-sm" onclick="cancelRes('${r.id}')">إلغاء</button>` :
        r.status === 'checked_in' ? `<button class="btn btn-success btn-sm" onclick="checkOutRes('${r.id}')">تسجيل خروج</button>` : '—'}</td></tr>`).join('');
}

function showGuestInfo(resId) {
  const r = GLOBAL_DATA.all_res.find(x => x.id === resId);
  if (!r) return;
  _displayGuestModal(r);
}

function showGuestInfoFromPending(idx) {
  const r = GLOBAL_DATA.pending_res[idx];
  if (!r) return;
  _displayGuestModal(r);
}

function _displayGuestModal(r) {
  const body = `
    <div class="guest-info-modal">
      <div class="info-row"><span>🧑 الاسم:</span> <b>${r.guest_name || 'غير محدد'}</b></div>
      <div class="info-row"><span>📱 الجوال:</span> <b>${r.guest_phone || 'غير متوفر'}</b></div>
      <div class="info-row"><span>🇸🇦 الجنسية:</span> <b>${r.guest_nationality || 'غير محدد'}</b></div>
      <div class="info-row"><span>🪪 رقم الهوية:</span> <b>${r.guest_id_number || 'غير مسجل'}</b></div>
      <hr style="border:0; border-top:1px solid var(--border); margin:15px 0">
      <div class="info-row"><span>🏨 تفاصيل الحجز:</span> #${String(r.id).slice(0, 8).toUpperCase()}</div>
      <div class="info-row"><span>📅 الموعد:</span> ${fmtDate(r.check_in)} إلى ${fmtDate(r.check_out)}</div>
    </div>
    <style>
      .guest-info-modal { padding: 10px 0; }
      .info-row { display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 15px; color: var(--text); }
      .info-row span { color: var(--muted); }
      .btn-icon-sh { background:none; border:none; cursor:pointer; font-size:14px; opacity:0.6; padding:0; }
      .btn-icon-sh:hover { opacity:1; }
    </style>
  `;
  const foot = `<button class="btn btn-primary" onclick="closeModal()">تم</button>`;
  openModal('📋 تفاصيل الضيف', body, foot);
}

function setResFilter(f) { resFilter = f; loadReservations(); }
async function confirmRes(id) {
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/reservations/${id}/confirm`, { method: 'POST' });
    showToast('تم تأكيد الحجز بنجاح'); loadReservations(); loadBadges();
  } catch (e) { showToast('فشل تأكيد الحجز', 'error'); }
}
function checkInRes(id) {
  const body = `
    <div style="text-align:center; padding: 20px 0;">
      <div style="font-size: 50px; margin-bottom: 10px;">🏨</div>
      <h3 style="color:var(--text); margin-bottom: 10px;">مرحباً بضيوفك!</h3>
      <p style="color:var(--muted); line-height: 1.6;">هل العميل متواجد في الفندق بالفعل؟<br>بتأكيدك لهذا الإجراء، هتتغير حالة الغرفة لـ <b style="color:var(--danger)">مشغولة 🔴</b></p>
    </div>
  `;
  const btns = `
    <button class="btn btn-secondary" onclick="closeModal()">تراجع</button>
    <button class="btn btn-primary" onclick="executeCheckIn('${id}')">✅ تأكيد دخول العميل</button>
  `;
  openModal("تسجيل الدخول / Check-In", body, btns);
}

async function executeCheckIn(id) {
  closeModal();
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/reservations/${id}/checkin`, { method: 'POST' });
    showToast('تم تسجيل الدخول بنجاح! نورتونا 🎉'); loadReservations(); loadBadges();
  } catch (e) { showToast('فشل عملية تسجيل الدخول', 'error'); }
}

function checkOutRes(id) {
  const body = `
    <div style="text-align:center; padding: 20px 0;">
      <div style="font-size: 50px; margin-bottom: 10px;">🧳</div>
      <h3 style="color:var(--text); margin-bottom: 10px;">إتمام المغادرة</h3>
      <p style="color:var(--muted); line-height: 1.6;">هل قام العميل بتسليم مفتاح الغرفة؟<br>ستعود الغرفة لتصبح <b style="color:var(--success)">متاحة 🟢</b> للحجوزات الجديدة.</p>
    </div>
  `;
  const btns = `
    <button class="btn btn-secondary" onclick="closeModal()">تراجع</button>
    <button class="btn btn-success" onclick="executeCheckOut('${id}')">✅ تأكيد المغادرة</button>
  `;
  openModal("تسجيل الخروج / Check-Out", body, btns);
}

async function executeCheckOut(id) {
  closeModal();
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/reservations/${id}/checkout`, { method: 'POST' });
    showToast('تم تسجيل الخروج بنجاح! شرفتونا 👋'); loadReservations(); loadBadges();
  } catch (e) { showToast('فشل عملية تسجيل الخروج', 'error'); }
}
async function rejectRes(id) {
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/reservations/${id}/reject`, { method: 'POST' });
    showToast('تم رفض الحجز'); loadReservations(); loadBadges();
  } catch (e) { showToast('فشل رفض الحجز', 'error'); }
}
async function cancelRes(id) {
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/reservations/${id}/cancel`, { method: 'POST' });
    showToast('تم إلغاء الحجز'); loadReservations();
  } catch (e) { showToast('فشل إلغاء الحجز', 'error'); }
}

async function showAddReservationModal() {
  const rts = await apiFetch(`/hotels/${HOTEL_ID}/room-types`).catch(() => []);
  if (!rts.length) { showToast('يجب إضافة أنواع غرف أولاً', 'error'); return; }

  const opts = rts.map(rt => `<option value="${rt.name}">${nameToAr(rt.name)} - ${fmtMoney(rt.daily_rate)}/يوم</option>`).join('');
  const today = new Date().toISOString().split('T')[0];
  const tmrw = new Date(Date.now() + 86400000).toISOString().split('T')[0];

  const body = `
    <div class="form-group"><label>اسم الضيف (ورقم الهاتف للتواصل)</label><input type="text" id="m-res-gst" placeholder="مثال: أحمد 0500000000"></div>
    <div class="form-group"><label>نوع الغرفة</label><select id="m-res-type" style="width:100%;padding:10px">${opts}</select></div>
    <div style="display:flex;gap:10px">
      <div class="form-group" style="flex:1"><label>تاريخ الدخول</label><input type="date" id="m-res-in" value="${today}"></div>
      <div class="form-group" style="flex:1"><label>تاريخ الخروج</label><input type="date" id="m-res-out" value="${tmrw}"></div>
    </div>
    <div class="form-group"><label>المبلغ الإجمالي المطلق (اختياري، يترك فارغ للحساب الآلي)</label><input type="number" id="m-res-price" placeholder="مثال: 1500"></div>
  `;
  const foot = `
    <button class="btn" onclick="closeModal()">إلغاء</button>
    <button class="btn btn-primary" onclick="submitReservation()">حفظ الحجز المقبول</button>`;
  openModal('➕ إنشاء حجز يدوي مباشر', body, foot);
}

function submitReservation() {
  const gst = document.getElementById('m-res-gst').value;
  const typ = document.getElementById('m-res-type').value;
  const dIn = document.getElementById('m-res-in').value;
  const dOut = document.getElementById('m-res-out').value;
  const prc = document.getElementById('m-res-price').value;

  if (!gst || !dIn || !dOut) return showToast('تأكد من إدخال البيانات الاساسية', 'error');
  
  // Extract phone (last part if digits) and name
  const parts = gst.trim().split(' ');
  const possiblePhone = parts[parts.length - 1];
  let phone = '';
  let guest_name = gst;
  
  if (possiblePhone.replace(/\\D/g, '').length >= 9) {
      phone = parts.pop();
      guest_name = parts.join(' ') || "عميل يدوي";
  } else {
      phone = "0000000000"; // fallback if no phone provided
  }

  closeModal();
  addReservation({
    room_type: typ,
    check_in: dIn,
    check_out: dOut,
    guest_name: guest_name,
    phone: phone,
    total_price: prc ? parseFloat(prc) : null,
    status: 'confirmed'
  });
}

async function addReservation(data) {
  try {
    await apiFetch(`/hotels/${HOTEL_ID}/reservations`, { method: 'POST', body: JSON.stringify(data) });
    showToast('تم إنشاء الحجز اليدوي بنجاح');
    loadReservations(); loadBadges();
  } catch (e) { showToast('فشل إنشاء الحجز', 'error'); }
}

