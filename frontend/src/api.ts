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

export interface GitHubStatus {
  linked: boolean
  username: string | null
  selected_repo: GitHubRepo | null
}

export interface GitHubRepo {
  id: number
  name: string
  full_name: string
  html_url: string
  description?: string
  is_selected?: boolean
}

export interface GitHubReposResponse {
  repos: GitHubRepo[]
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

export const getGitHubOAuthURL = async (userId: number): Promise<string> => {
  const response = await apiClient.get<{ url: string }>('/api/github/oauth/url/', {
    params: { user_id: userId },
  })
  return response.data.url
}

export const exchangeGitHubCode = async (code: string, userId: number): Promise<{ username: string }> => {
  const response = await apiClient.post<{ username: string; github_user_id: number }>(
    '/api/github/oauth/callback/',
    { code, user_id: userId }
  )
  return response.data
}

export const getGitHubStatus = async (userId: number): Promise<GitHubStatus> => {
  const response = await apiClient.get<GitHubStatus>('/api/github/status/', {
    params: { user_id: userId },
  })
  return response.data
}

export const getGitHubRepos = async (userId: number): Promise<GitHubRepo[]> => {
  const response = await apiClient.get<GitHubReposResponse>('/api/github/repos/', {
    params: { user_id: userId },
  })
  return response.data.repos
}

export const selectGitHubRepo = async (userId: number, repoId: number): Promise<GitHubRepo> => {
  const response = await apiClient.post<GitHubRepo>('/api/github/repos/select/', {
    user_id: userId,
    repo_id: repoId,
  })
  return response.data
}

export default apiClient
