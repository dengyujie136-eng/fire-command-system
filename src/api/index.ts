import axios from 'axios'

const api = axios.create({
  // Use the current frontend origin by default, then Vite proxies API calls to the local backend.
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.response.use(
  (response: any) => response.data,
  (error: any) => {
    const method = error.config?.method?.toUpperCase?.() || 'REQUEST'
    const url = error.config?.url || ''
    const status = error.response?.status || 'network'
    console.warn(`[API fallback] ${method} ${url} failed (${status})`, error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export default api
