import axios from 'axios'

function resolveApiBase() {
  const envBase = import.meta.env.VITE_API_BASE as string | undefined
  if (envBase && envBase.trim().length > 0) return envBase
  // Auto-detect: if running Vite dev server, default to backend on 8000
  if (typeof window !== 'undefined' && window.location.port === '5173') {
    // Use Vite proxy to avoid CORS entirely
    return '/api/v1'
  }
  // Default when served by nginx (same-origin proxy)
  return '/api/v1'
}

const API_BASE = resolveApiBase()

export const api = axios.create({
  baseURL: API_BASE
})

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
  } else {
    delete api.defaults.headers.common['Authorization']
  }
}

// Attach token from localStorage on every request
api.interceptors.request.use((config) => {
  try {
    const saved = localStorage.getItem('auth_token')
    if (saved) {
      config.headers = config.headers || {}
      config.headers['Authorization'] = `Bearer ${saved}`
    }
  } catch {}
  return config
})

// Handle 401 by clearing token and redirecting to login
api.interceptors.response.use(
  (res) => res,
  (error) => {
    // For testing, do not auto-redirect on 401. Surface the error to the UI.
    // You can re-enable redirect by restoring the previous logic.
    return Promise.reject(error)
  }
)

