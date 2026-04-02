const BASE = '/api/v1';

function getToken() {
  return localStorage.getItem('testops_token');
}

function saveToken(token) {
  localStorage.setItem('testops_token', token);
}

function clearToken() {
  localStorage.removeItem('testops_token');
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 204) return null;

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const message = data?.detail ?? `Request failed: ${res.status}`;
    throw Object.assign(new Error(message), { status: res.status, data });
  }

  return data;
}

// Auth
export const auth = {
  register: (name, email, password) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password }) }),

  login: async (email, password) => {
    const data = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    saveToken(data.token.access_token);
    return data;
  },

  logout: () => clearToken(),
};

// Users
export const users = {
  list: (skip = 0, limit = 50) => request(`/users/?skip=${skip}&limit=${limit}`),
  get: (id) => request(`/users/${id}`),
  create: (payload) => request('/users/', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id, payload) => request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  remove: (id) => request(`/users/${id}`, { method: 'DELETE' }),
};

// Tasks
export const tasks = {
  list: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, v])
    ).toString();
    return request(`/tasks/${qs ? `?${qs}` : ''}`);
  },
  get: (id) => request(`/tasks/${id}`),
  create: (payload) => request('/tasks/', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id, payload) => request(`/tasks/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  remove: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),
};

// Runs
export const runsApi = {
  create: (payload) => request('/runs/', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id, patch) => request(`/runs/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  list: (skip = 0, limit = 100) => request(`/runs/?skip=${skip}&limit=${limit}`),
  get: (id) => request(`/runs/${id}`),
};

export { getToken, saveToken, clearToken };
