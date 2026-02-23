import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expirado o inválido
      localStorage.removeItem('authToken')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Admin API
export const getAdminStats = () =>
  apiClient.get('/admin/stats').then((res) => res.data)

export const getBookings = (params) =>
  apiClient.get('/admin/reservas', { params }).then((res) => res.data)

export const getBooking = (id) =>
  apiClient.get(`/admin/reservas/${id}`).then((res) => res.data)

export const updateBooking = (id, data) =>
  apiClient.put(`/admin/reservas/${id}`, data).then((res) => res.data)

export const cancelBooking = (id) =>
  apiClient.post(`/admin/reservas/${id}/cancel`).then((res) => res.data)

export const getTours = (params) =>
  apiClient.get('/tours/buscar', { params }).then((res) => res.data)

export const getTour = (id) =>
  apiClient.get(`/tours/${id}/completo`).then((res) => res.data)

export const createTour = (data) =>
  apiClient.post('/admin/tours', data).then((res) => res.data)

export const updateTour = (id, data) =>
  apiClient.put(`/admin/tours/${id}`, data).then((res) => res.data)

export const deleteTour = (id) =>
  apiClient.delete(`/admin/tours/${id}`).then((res) => res.data)

export const getAnalytics = (params) =>
  apiClient.get('/admin/analytics', { params }).then((res) => res.data)

export default apiClient
