import axios from 'axios'
import { shouldClearAuthentication, toApiError } from '../apiErrors'

export const API_BASE = import.meta.env.PROD
  ? '/api'
  : (import.meta.env.VITE_API_URL || 'http://localhost:5000/api')
const api = axios.create({ baseURL: API_BASE, timeout: 15000, withCredentials: true })
let csrfToken = null
let csrfRequest = null

api.interceptors.request.use(async config => {
  if (['post', 'put', 'patch', 'delete'].includes((config.method || 'get').toLowerCase())) {
    if (!csrfToken) {
      csrfRequest ||= axios.get(`${API_BASE}/auth/csrf`, { withCredentials: true }).then(res => {
        csrfToken = res.data.data.csrf_token
        return csrfToken
      }).finally(() => { csrfRequest = null })
      await csrfRequest
    }
    config.headers['X-CSRF-Token'] = csrfToken
  }
  return config
})

api.interceptors.response.use(res => {
  if (/\/auth\/(login|register|logout|reset-password)$/.test(res.config.url || '') || /\/settings\/(account|password)$/.test(res.config.url || '')) csrfToken = null
  return res.data
}, error => {
  if (shouldClearAuthentication(error.response?.status, error.config?.url || '')) {
    csrfToken = null
    window.dispatchEvent(new Event('fittrack:unauthorized'))
  }
  return Promise.reject(toApiError(error, error.config?.url || ''))
})

export const authApi = {
  providers: () => api.get('/auth/providers'),
  me: () => api.get('/auth/me'),
  register: data => api.post('/auth/register', data),
  login: data => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  forgot: data => api.post('/auth/forgot-password', data),
  reset: data => api.post('/auth/reset-password', data),
}
export const getProfile = () => api.get('/profile')
export const saveProfile = data => api.put('/profile', data)
export const getGoal = () => api.get('/goals')
export const saveGoal = data => api.put('/goals', data)
export const setGoalStatus = status => api.patch('/goals/status', { status })
export const getWeightHistory = params => api.get('/weight', { params })
export const addWeight = data => api.post('/weight', data)
export const updateWeight = (recordId, data) => api.put(`/weight/${recordId}`, data)
export const deleteWeight = recordId => api.delete(`/weight/${recordId}`)
export const getSummary = () => api.get('/dashboard/summary')
export const getActivity = period => api.get('/dashboard/activity', { params: { period } })
export const getFitness = params => api.get('/fitness/history', { params })
export const createFitness = data => api.post('/fitness', data)
export const updateFitness = (recordId, data) => api.put(`/fitness/${recordId}`, data)
export const deleteFitness = recordId => api.delete(`/fitness/${recordId}`)
export const saveDailyStepGoal = daily_step_goal => api.put('/fitness/step-goal', { daily_step_goal })
export const changePassword = data => api.put('/settings/password', data)
export const deleteAccount = data => api.delete('/settings/account', { data: { ...data, confirmation: 'DELETE' } })
