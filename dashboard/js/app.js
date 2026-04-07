// ══════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════
async function initApp() {
  updateClock();
  setInterval(updateClock, 1000);

  // 1. Fetch ALL hotels
  try {
    const data = await apiFetch('/hotels');
    const hotels = data.hotels || [];
    GLOBAL_DATA.all_hotels_list = hotels;

    const sel = document.getElementById('hotel-selector');
    if (hotels.length > 0) {
      sel.innerHTML = hotels.map((h, i) =>
        `<option value="${h.id}" ${i === 0 ? 'selected' : ''}>${h.name}</option>`
      ).join('');
      HOTEL_ID = hotels[0].id;
    } else {
      sel.innerHTML = '<option value="">لا توجد فنادق</option>';
    }
  } catch(e) { showToast('تعذر الاتصال بالخادم', 'error'); }

  // 2. Initial Route
  if (!HOTEL_ID) {
    document.getElementById('content').innerHTML =
      '<div class="empty-state" style="margin-top:40px">لا يوجد فندق مرتبط بهذا الحساب حالياً.</div>';
    return;
  }

  if (CURRENT_USER && CURRENT_USER.role === 'employee') {
    nav('reservations');
  } else {
    nav('overview');
  }

  // 3. Load room types + badges in background
  if (HOTEL_ID) {
    fetch(`${API}/hotels/${HOTEL_ID}/room-types`).then(r => r.json()).then(rtData => {
      if (Array.isArray(rtData)) rtData.forEach(rt => { ROOM_TYPES[rt.id] = rt.name; });
      if (currentPage === 'overview') loadOverview();
    }).catch(() => {});
    loadBadges();
  }

  // Auto-refresh badges every 15 seconds for faster notifications
  setInterval(() => {
    loadBadges();
  }, 15000);

  // Auto-refresh page every 2 minutes
  setInterval(() => {
    if(!document.getElementById('modal-overlay').classList.contains('show')) {
      if(currentPage) refreshPage();
    }
  }, 120000);
}

function switchHotel(newId) {
  if (!newId || newId === HOTEL_ID) return;
  HOTEL_ID = newId;
  // Clear all caches
  ROOM_TYPES = {};
  PAGE_CACHE_RENDERED = {};
  GLOBAL_DATA.pending_res = [];
  GLOBAL_DATA.open_comps = [];
  GLOBAL_DATA.all_rooms = [];
  GLOBAL_DATA.all_res = [];
  GLOBAL_DATA.all_comps = [];
  GLOBAL_DATA.all_reqs = [];
  GLOBAL_DATA.all_types = [];

  // Reload room types for new hotel
  fetch(`${API}/hotels/${HOTEL_ID}/room-types`).then(r => r.json()).then(rtData => {
    if (Array.isArray(rtData)) rtData.forEach(rt => { ROOM_TYPES[rt.id] = rt.name; });
  }).catch(() => {});

  loadBadges();
  nav(currentPage);
  showToast('تم التبديل إلى: ' + document.getElementById('hotel-selector').selectedOptions[0]?.text);
}


function updateClock() {
  const now = new Date();
  document.getElementById('topbar-time').textContent =
    now.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }) + ' — ' +
    now.toLocaleDateString('ar-SA', { weekday: 'long', day: 'numeric', month: 'long' });
}

// ── Notification Sound System ───────────────────
let _prevPendingCount = -1;
let _prevComplaintsCount = -1;

function playNotificationSound() {
  const prefs = JSON.parse(localStorage.getItem('dashboard_prefs') || '{}');
  if (!prefs.sound) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    // Play two quick ascending tones for a pleasant "ding-ding"
    [0, 0.15].forEach((delay, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.value = i === 0 ? 587.33 : 783.99; // D5 then G5
      gain.gain.setValueAtTime(0.25, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.4);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.4);
    });
    // Close context after notes finish
    setTimeout(() => ctx.close(), 800);
  } catch (e) { /* AudioContext not supported */ }
}

function sendBrowserNotification(title, body) {
  const prefs = JSON.parse(localStorage.getItem('dashboard_prefs') || '{}');
  if (!prefs.notifications) return;
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification(title, { body, icon: '🏨' });
  }
}

async function loadBadges() {
  if (!HOTEL_ID) return;
  try {
    const [pd, cd] = await Promise.all([
      apiFetch(`/hotels/${HOTEL_ID}/reservations?status=pending&limit=100`).catch(() => ({ reservations: [], total: 0 })),
      apiFetch(`/hotels/${HOTEL_ID}/complaints?status=open&limit=100`).catch(() => ({ complaints: [], total: 0 }))
    ]);

    GLOBAL_DATA.pending_res = pd.reservations || [];
    GLOBAL_DATA.open_comps = cd.complaints || [];

    const pCount = pd.total || 0; const cCount = cd.total || 0;
    const pb = document.getElementById('pending-badge');
    const cb = document.getElementById('complaints-badge');
    pb.textContent = pCount; pb.style.display = pCount > 0 ? 'block' : 'none';
    cb.textContent = cCount; cb.style.display = cCount > 0 ? 'block' : 'none';

    // Play sound + notification when NEW items appear
    if (_prevPendingCount >= 0 || _prevComplaintsCount >= 0) {
      if (pCount > _prevPendingCount) {
        playNotificationSound();
        sendBrowserNotification('حجز جديد 📋', `يوجد ${pCount} حجز معلق بانتظار المراجعة`);
      } else if (cCount > _prevComplaintsCount) {
        playNotificationSound();
        sendBrowserNotification('شكوى جديدة ⚠️', `يوجد ${cCount} شكوى مفتوحة`);
      }
    }
    _prevPendingCount = pCount;
    _prevComplaintsCount = cCount;
  } catch (e) { }
}

// ══════════════════════════════════════════════
//  NAVIGATION
// ══════════════════════════════════════════════
const pageTitles = {
  overview: 'الرئيسية', reservations: 'الحجوزات',
  rooms: 'الغرف', reports: 'التقارير المالية', complaints: 'الشكاوى والطلبات',
  hotels: 'الفنادق', roomsetup: 'إعداد الغرف',
  guests: 'الضيوف', reviews: 'التقييمات', dailypricing: 'التسعير اليومي',
  users: 'الإدارة والموظفين', staffperformance: 'تقييم الموظفين', settings: 'الإعدادات'
};
function nav(page) {
  // Check if role has access
  if (CURRENT_USER) {
      const btn = document.getElementById('nav-' + page);
      if (btn) {
          const roles = btn.getAttribute('data-roles');
          if (roles && !roles.includes(CURRENT_USER.role)) {
              Swal.fire({
                  icon: 'error',
                  title: 'ممنوع',
                  text: 'عذراً، لا تملك الصلاحية للوصول إلى هذه الصفحة.',
                  background: 'var(--surface)', color: 'var(--text)',
                  confirmButtonColor: 'var(--primary)'
              });
              return;
          }
      }
  }

  currentPage = page;
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.getElementById('nav-' + page)?.classList.add('active');
  document.getElementById('page-title').textContent = pageTitles[page];
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  if(sidebar) sidebar.classList.remove('open');
  if(overlay) overlay.classList.remove('show');

  if (!PAGE_CACHE_RENDERED[page]) {
    destroyCharts();
    document.getElementById('content').innerHTML = '<div class="loading"><div class="spinner"></div> جاري التحميل...</div>';
  } else {
    document.getElementById('topbar-time').innerHTML = '<span class="spinner" style="display:inline-block;width:12px;height:12px;border-width:2px;border-top-color:var(--text);vertical-align:middle;margin-left:4px"></span> جاري التحديث...';
  }

  const fns = {
    overview: loadOverview, reservations: loadReservations,
    rooms: loadRooms, reports: loadReports, complaints: loadComplaints,
    hotels: loadHotels, roomsetup: loadRoomSetup,
    guests: loadGuests, reviews: loadReviews, dailypricing: loadDailyPricing,
    users: loadUsers, staffperformance: loadStaffPerformance, settings: loadSettings
  };

  fns[page]?.().then(() => {
    PAGE_CACHE_RENDERED[page] = true;
    updateClock(); // restores time over the update spinner
  });
}
function refreshPage() { nav(currentPage); }
function destroyCharts() {
  Object.values(charts).forEach(c => { try { c.destroy(); } catch (e) { } });
  charts = {};
}
