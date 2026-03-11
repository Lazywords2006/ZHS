const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.message || data.detail || '接口请求失败')
  }
  return data
}

export function fetchAccounts() {
  return request('/api/accounts')
}

export function createAccount(name) {
  return request('/api/accounts', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function deleteAccount(accountId) {
  return request(`/api/accounts/${accountId}`, {
    method: 'DELETE',
  })
}

export function fetchCourses(accountId) {
  const params = new URLSearchParams({ accountId })
  return request(`/api/courses?${params.toString()}`)
}

export function saveAccountConfig(accountId, payload) {
  return request(`/api/accounts/${accountId}/config`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchQrCode(accountId) {
  return request(`/api/accounts/${accountId}/login/qr`, {
    method: 'POST',
  })
}

export function refreshQrCode(accountId) {
  return request(`/api/accounts/${accountId}/login/qr/refresh`, {
    method: 'POST',
  })
}

export function fetchQrStatus(accountId, token) {
  const params = new URLSearchParams({ token })
  return request(`/api/accounts/${accountId}/login/qr/status?${params.toString()}`)
}

export function startRun(accountId) {
  return request(`/api/accounts/${accountId}/run/start`, {
    method: 'POST',
  })
}

export function stopRun(accountId) {
  return request(`/api/accounts/${accountId}/run/stop`, {
    method: 'POST',
  })
}
