import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface HealthResponse {
  status: string
}

export interface User {
  id: number
  email: string
  name: string
}

export interface GoogleAuthPayload {
  id_token: string
}

export const checkHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>('/api/health/')
  return response.data
}

export const authenticateWithGoogle = async (idToken: string): Promise<User> => {
  const response = await apiClient.post<User>('/api/auth/google/', {
    id_token: idToken,
  })
  return response.data
}

export default apiClient
