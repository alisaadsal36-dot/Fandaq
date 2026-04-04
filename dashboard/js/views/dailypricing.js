// ══════════════════════════════════════════════
//  DAILY PRICING
// ══════════════════════════════════════════════


async function loadDailyPricing() {
  const content = document.getElementById('content');
  if (!HOTEL_ID) {
    content.innerHTML = '<div style="padding:20px">الرجاء اختيار فندق أولاً.</div>';
    return;
  }

  content.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
      <h3>📊 أسعار السوق (التسعير اليومي)</h3>
      <button class="btn btn-primary" onclick="showAddPricingModal()">+ إضافة تسعيرة</button>
    </div>
    
    <div class="card" style="margin-bottom: 24px;">
      <div class="table-header" style="background:var(--card);border-radius:12px 12px 0 0;border-bottom:1px solid var(--border);padding:15px">
        <h4 style="margin:0;color:var(--primary)">تسعيرات اليوم</h4>
      </div>
      <div class="table-responsive">
        <table class="table" style="width:100%">
          <thead>
            <tr>
              <th>تاريخ التسعيرة</th>
              <th>اسم الفندق المنافس</th>
              <th>سعر منافسنا</th>
              <th>سعر فندقنا</th>
              <th>الفرق</th>
              <th>إجراء</th>
            </tr>
          </thead>
          <tbody id="pricing-body">
            <tr><td colspan="6" style="text-align:center;">جاري التحميل...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Archive Section -->
    <div class="card">
      <div class="table-header" style="background:var(--card);border-radius:12px;padding:15px">
        <h4 style="margin:0;color:var(--text-muted)">🗂️ التقارير والأرشيف السابقة</h4>
      </div>
      <div id="pricing-archive" style="padding: 15px;">
        <p style="text-align:center; color:var(--text-muted)">جاري جلب الأرشيف...</p>
      </div>
    </div>
  `;

  try {
    const data = await apiFetch('/hotels/' + HOTEL_ID + '/daily-pricing');
    const tbody = document.getElementById('pricing-body');
    const archiveContainer = document.getElementById('pricing-archive');
    const items = data.items || [];

    if (items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">لا يوجد تسعيرات مسجلة لليوم.</td></tr>';
      archiveContainer.innerHTML = '<p style="text-align:center; color:var(--text-muted)">لا يوجد أرشيف مسجل مسبقاً.</p>';
      return;
    }

    // Today's date string (YYYY-MM-DD for comparison)
    // Create it using exact local timezone trick to match the API's date strings
    const todayStr = new Date().toLocaleDateString('en-CA'); // 'YYYY-MM-DD' in local timezone natively

    const todayItems = [];
    const archivedItemsByDate = {};

    items.forEach(p => {
      // The API returns date as "YYYY-MM-DD"
      const pDate = p.date;
      if (pDate === todayStr) {
        todayItems.push(p);
      } else {
        if (!archivedItemsByDate[pDate]) archivedItemsByDate[pDate] = [];
        archivedItemsByDate[pDate].push(p);
      }
    });

    // Option: Always show a send report button for TODAY if there are items today
    if (todayItems.length > 0) {
      if (!archivedItemsByDate[todayStr]) archivedItemsByDate[todayStr] = todayItems; // to also appear in reports section for sending/downloading easily
    }

    // 1. Render today's items
    if (todayItems.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">لم يتم إدخال تسعيرات اليوم. الصفحة مصفّرة.</td></tr>';
    } else {
      tbody.innerHTML = todayItems.map(p => {
        const diff = p.my_price - p.competitor_price;
        const diffLabel = diff > 0
          ? `<span class="badge" style="background:#ef4444;color:white">أغلى من المنافس بـ ${diff}</span>`
          : diff < 0
            ? `<span class="badge" style="background:#10b981;color:white">أرخص من المنافس بـ ${Math.abs(diff)}</span>`
            : `<span class="badge" style="background:#6b7280;color:white">نفس السعر</span>`;

        return `
        <tr>
          <td>${p.date}</td>
          <td><strong>${p.competitor_hotel_name}</strong></td>
          <td style="font-weight:bold">${p.competitor_price}</td>
          <td style="font-weight:bold">${p.my_price}</td>
          <td>${diffLabel}</td>
          <td>
            <button class="btn btn-sm btn-danger" onclick="deletePricing('${p.id}')">مسح</button>
          </td>
        </tr>
        `;
      }).join('');
    }

    // 2. Render Archive
    const dates = Object.keys(archivedItemsByDate).sort().reverse();
    if (dates.length === 0) {
      archiveContainer.innerHTML = '<p style="text-align:center; color:var(--text-muted)">لا يوجد أرشيف مسجل مسبقاً.</p>';
    } else {
      archiveContainer.innerHTML = dates.map(dt => {
        const dItems = archivedItemsByDate[dt];
        const isToday = dt === todayStr;
        const titleBadge = isToday ? '<span class="badge" style="background:var(--primary);color:#fff;margin-right:8px">تقرير اليوم</span>' : '';
        return `
          <div style="display:flex; justify-content:space-between; align-items:center; padding:12px; background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:8px; margin-bottom:10px">
            <div>
              <strong style="font-size:1.1em">${dt}</strong> 
              <span style="color:var(--text-muted); font-size:0.9em; margin-right:10px;">(${dItems.length} تسعيرات)</span>
              ${titleBadge}
            </div>
            <div style="display:flex; gap:8px">
              <button class="btn btn-sm" style="background:#10b981; color:white; border:none" onclick="downloadPricingExcel('${dt}')">📥 شيت إكسل</button>
              <button class="btn btn-sm btn-primary" onclick="sendPricingReport('${dt}')">📤 إرسال للمالك</button>
            </div>
          </div>
        `;
      }).join('');
    }

  } catch (e) {
    document.getElementById('pricing-body').innerHTML = '<tr><td colspan="6" style="text-align:center; color:red">حدث خطأ أثناء تحميل البيانات.</td></tr>';
  }
}

function showAddPricingModal() {
  const body = `
    <div class="form-group">
      <label>اسم الفندق المنافس</label>
      <input type="text" id="dp-comp-name" class="input" placeholder="اسم الفندق...">
    </div>
    <div style="display:flex; gap:10px;">
      <div class="form-group" style="flex:1">
        <label>سعر المنافس (لليوم)</label>
        <input type="number" id="dp-comp-price" class="input" placeholder="0">
      </div>
      <div class="form-group" style="flex:1">
        <label>سعر فندقنا (لليوم)</label>
        <input type="number" id="dp-my-price" class="input" placeholder="0">
      </div>
    </div>
  `;
  const foot = `
    <button class="btn" onclick="closeModal()">إلغاء</button>
    <button class="btn btn-primary" onclick="savePricing()">💾 حفظ التسعيرة</button>
  `;
  openModal("➕ تسجيل تسعيرة منافس", body, foot);
}

async function savePricing() {
  const cName = document.getElementById('dp-comp-name').value;
  const cPrice = document.getElementById('dp-comp-price').value;
  const mPrice = document.getElementById('dp-my-price').value;

  if (!cName || !cPrice || !mPrice) {
    showToast('الرجاء إدخال جميع البيانات', 'error');
    return;
  }

  try {
    await apiFetch('/hotels/' + HOTEL_ID + '/daily-pricing', {
      method: 'POST',
      body: JSON.stringify({
        competitor_hotel_name: cName,
        competitor_price: parseFloat(cPrice),
        my_price: parseFloat(mPrice)
      })
    });
    showToast('تمت إضافة التسعيرة بنجاح!');
    closeModal();
    loadDailyPricing();
  } catch (e) {
    showToast('ربما توجد تسعيرة اليوم لنفس الفندق!', 'error');
  }
}

async function deletePricing(id) {
  confirmAction(
    '🗑️ مسح التسعيرة؟', 
    'هل تريد فعلاً مسح هذه التسعيرة؟ لن تتمكن من التراجع عن هذا الإجراء.', 
    'نعم، امسح', 
    async () => {
      try {
        await apiFetch('/hotels/' + HOTEL_ID + '/daily-pricing/' + id, { method: 'DELETE' });
        showToast('تم مسح التسعيرة بنجاح.');
        loadDailyPricing();
      } catch (e) {
        showToast('خطأ أثناء عملية المسح.', 'error');
      }
    }
  );
}

function downloadPricingExcel(dateStr) {
  // Directly trigger a file download using the valid JWT token in query string if needed, 
  // or by fetching a Blob. Fetching a Blob is safer to inject headers.
  const token = localStorage.getItem('access_token');
  fetch(`${API_URL}/hotels/${HOTEL_ID}/daily-pricing/export?date=${dateStr}`, {
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
    // filename from API matches daily_pricing_YYYYMMDD.csv
    a.download = `daily_pricing_${dateStr}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
  })
  .catch(() => showToast('حدث خطأ أثناء تحميل التقرير', 'error'));
}

async function sendPricingReport(dateStr) {
  confirmAction(
    '📤 إرسال التقرير', 
    `هل تود إرسال تقرير أسعار يوم ${dateStr} لمالك الفندق الآن للواتساب/تيليجرام؟`, 
    'إرسال', 
    async () => {
      try {
        await apiFetch(`/hotels/${HOTEL_ID}/daily-pricing/send-report?date=${dateStr}`, { method: 'POST' });
        showToast('تم إرسال التقرير بنجاح للمالك ✨');
      } catch (e) {
        showToast('حدث خطأ أثناء إرسال التقرير.', 'error');
      }
    }
  );
}
