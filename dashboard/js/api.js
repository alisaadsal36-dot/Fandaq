// ══════════════════════════════════════════════
//  CONFIG
// ══════════════════════════════════════════════
const API = '/api/v1';
let HOTEL_ID = null;
let currentPage = 'overview';
let charts = {};
let ROOM_TYPES = {}; // id -> name map
let PAGE_CACHE_RENDERED = {};
let GLOBAL_DATA = { pending_res: [], open_comps: [], all_rooms: [], all_res: [], all_comps: [], all_reqs: [], all_hotels: [], all_types: [] };
let CURRENT_USER = null;

const API_CACHE = new Map();

async function apiFetch(path, opts={}) {
  const token = sessionStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const isGet = !opts.method || opts.method === 'GET';
  const cacheKey = path;
  if (isGet && opts.useCache && API_CACHE.has(cacheKey)) {
      return API_CACHE.get(cacheKey);
  }

    let requestPath = path;
    if (isGet && opts.useCache === false) {
            const sep = path.includes('?') ? '&' : '?';
            requestPath = `${path}${sep}_=${Date.now()}`;
    }

    const fetchOpts = { headers, ...opts, cache: 'no-store' };
    delete fetchOpts.useCache;

    const res = await fetch(API + requestPath, fetchOpts);
  if (res.status === 401 || res.status === 403) {
      if (path !== '/auth/login') {
          sessionStorage.removeItem('token');
          sessionStorage.removeItem('user');
          location.reload();
      }
  }
  if (!res.ok) throw new Error(await res.text());
  if (res.status === 204) return null;
  
  const data = await res.json();
  if (isGet && opts.useCache) {
      API_CACHE.set(cacheKey, data);
      // clear cache after 1 minute automatically for freshness
      setTimeout(() => API_CACHE.delete(cacheKey), 60000); 
  }
  return data;
}

function clearApiCache() {
    API_CACHE.clear();
}
