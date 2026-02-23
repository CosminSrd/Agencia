import apiClient from './api'

export const loginUser = async (email, password) => {
  const response = await apiClient.post('/auth/login', { email, password })
  return response.data
}

export const logoutUser = async () => {
  const response = await apiClient.post('/auth/logout')
  return response.data
}

export const getCurrentUser = async () => {
  const response = await apiClient.get('/auth/me')
  return response.data
}

export const registerUser = async (userData) => {
  const response = await apiClient.post('/auth/register', userData)
  return response.data
}

export const resetPassword = async (email) => {
  const response = await apiClient.post('/auth/reset-password', { email })
  return response.data
}
