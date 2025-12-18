<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { googleLogout } from 'vue3-google-login'
import {
  checkHealth,
  authenticateWithGoogle,
  getGitHubOAuthURL,
  exchangeGitHubCode,
  getGitHubStatus,
  getGitHubRepos,
  selectGitHubRepo,
  type User,
  type GitHubStatus,
  type GitHubRepo,
} from './api'

const backendStatus = ref<string>('Checking...')
const isConnected = ref<boolean>(false)
const isLoading = ref<boolean>(true)
const user = ref<User | null>(null)
const authError = ref<string>('')
const isAuthenticating = ref<boolean>(false)

const githubStatus = ref<GitHubStatus | null>(null)
const githubRepos = ref<GitHubRepo[]>([])
const githubError = ref<string>('')
const isLinkingGitHub = ref<boolean>(false)
const isLoadingRepos = ref<boolean>(false)
const isSelectingRepo = ref<boolean>(false)

const isGitHubLinked = computed(() => githubStatus.value?.linked ?? false)
const selectedRepo = computed(() => githubStatus.value?.selected_repo ?? null)

const loadUserFromStorage = () => {
  const stored = localStorage.getItem('user')
  if (stored) {
    try {
      user.value = JSON.parse(stored)
    } catch {
      localStorage.removeItem('user')
    }
  }
}

const checkBackendHealth = async () => {
  isLoading.value = true
  try {
    const response = await checkHealth()
    backendStatus.value = response.status
    isConnected.value = response.status === 'ok'
  } catch (error) {
    backendStatus.value = 'Failed to connect'
    isConnected.value = false
    console.error('Health check failed:', error)
  } finally {
    isLoading.value = false
  }
}

const handleGoogleLogin = async (response: { credential: string }) => {
  authError.value = ''
  isAuthenticating.value = true
  
  try {
    const userData = await authenticateWithGoogle(response.credential)
    user.value = userData
    localStorage.setItem('user', JSON.stringify(userData))
  } catch (error: unknown) {
    console.error('Authentication failed:', error)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { error?: string } } }
      authError.value = axiosError.response?.data?.error || 'Authentication failed'
    } else {
      authError.value = 'Authentication failed. Please try again.'
    }
  } finally {
    isAuthenticating.value = false
  }
}

const handleLogout = () => {
  googleLogout()
  user.value = null
  githubStatus.value = null
  githubRepos.value = []
  localStorage.removeItem('user')
}

const fetchGitHubStatus = async () => {
  if (!user.value) return
  
  try {
    githubStatus.value = await getGitHubStatus(user.value.id)
  } catch (error) {
    console.error('Failed to fetch GitHub status:', error)
  }
}

const handleLinkGitHub = async () => {
  if (!user.value) return
  
  githubError.value = ''
  isLinkingGitHub.value = true
  
  try {
    const url = await getGitHubOAuthURL(user.value.id)
    window.location.href = url
  } catch (error: unknown) {
    console.error('Failed to get GitHub OAuth URL:', error)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { error?: string } } }
      githubError.value = axiosError.response?.data?.error || 'Failed to start GitHub OAuth'
    } else {
      githubError.value = 'Failed to start GitHub OAuth'
    }
    isLinkingGitHub.value = false
  }
}

const handleGitHubCallback = async () => {
  const urlParams = new URLSearchParams(window.location.search)
  const code = urlParams.get('code')
  const error = urlParams.get('error')
  
  if (window.location.pathname !== '/auth/github/callback') return
  
  window.history.replaceState({}, document.title, '/')
  
  if (error) {
    githubError.value = error === 'access_denied' 
      ? 'GitHub authorization was cancelled' 
      : `GitHub OAuth error: ${error}`
    return
  }
  
  if (!code || !user.value) return
  
  isLinkingGitHub.value = true
  
  try {
    await exchangeGitHubCode(code, user.value.id)
    await fetchGitHubStatus()
  } catch (error: unknown) {
    console.error('GitHub OAuth callback failed:', error)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { error?: string } } }
      githubError.value = axiosError.response?.data?.error || 'Failed to link GitHub account'
    } else {
      githubError.value = 'Failed to link GitHub account'
    }
  } finally {
    isLinkingGitHub.value = false
  }
}

const fetchGitHubRepos = async () => {
  if (!user.value) return
  
  githubError.value = ''
  isLoadingRepos.value = true
  
  try {
    githubRepos.value = await getGitHubRepos(user.value.id)
  } catch (error: unknown) {
    console.error('Failed to fetch repos:', error)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { error?: string } } }
      githubError.value = axiosError.response?.data?.error || 'Failed to fetch repositories'
    } else {
      githubError.value = 'Failed to fetch repositories'
    }
  } finally {
    isLoadingRepos.value = false
  }
}

const handleSelectRepo = async (repo: GitHubRepo) => {
  if (!user.value || isSelectingRepo.value) return
  
  githubError.value = ''
  isSelectingRepo.value = true
  
  try {
    await selectGitHubRepo(user.value.id, repo.id)
    await fetchGitHubStatus()
    githubRepos.value = githubRepos.value.map((r: GitHubRepo) => ({
      ...r,
      is_selected: r.id === repo.id,
    }))
  } catch (error: unknown) {
    console.error('Failed to select repo:', error)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { error?: string } } }
      githubError.value = axiosError.response?.data?.error || 'Failed to select repository'
    } else {
      githubError.value = 'Failed to select repository'
    }
  } finally {
    isSelectingRepo.value = false
  }
}

watch(isGitHubLinked, (linked: boolean) => {
  if (linked && githubRepos.value.length === 0) {
    fetchGitHubRepos()
  }
})

onMounted(async () => {
  loadUserFromStorage()
  checkBackendHealth()
  
  if (user.value) {
    await fetchGitHubStatus()
    handleGitHubCallback()
  }
})

watch(user, async (newUser: User | null) => {
  if (newUser) {
    await fetchGitHubStatus()
    handleGitHubCallback()
  }
})
</script>

<template>
  <div class="container">
    <header>
      <h1>GitHub Integration App</h1>
      <p class="subtitle">{{ user ? `Welcome, ${user.name}` : 'Sign in to get started' }}</p>
    </header>
    
    <main>
      <div class="auth-card">
        <template v-if="user">
          <div class="user-info">
            <div class="user-avatar">{{ user.name.charAt(0).toUpperCase() }}</div>
            <div class="user-details">
              <span class="user-name">{{ user.name }}</span>
              <span class="user-email">{{ user.email }}</span>
            </div>
          </div>
          <button @click="handleLogout" class="logout-btn">Sign Out</button>
        </template>
        
        <template v-else>
          <h2>Sign In</h2>
          <p class="auth-description">Use your Google account to sign in</p>
          
          <div v-if="authError" class="error-message">{{ authError }}</div>
          
          <GoogleLogin
            :callback="handleGoogleLogin"
            :disabled="isAuthenticating"
          />
          
          <p v-if="isAuthenticating" class="auth-status">Authenticating...</p>
        </template>
      </div>

      <div v-if="user" class="github-card">
        <h2>GitHub Integration</h2>
        
        <div v-if="githubError" class="error-message">{{ githubError }}</div>
        
        <template v-if="!isGitHubLinked">
          <p class="github-description">Link your GitHub account to select a repository</p>
          <button 
            @click="handleLinkGitHub" 
            :disabled="isLinkingGitHub"
            class="github-btn"
          >
            <svg class="github-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            {{ isLinkingGitHub ? 'Redirecting...' : 'Link GitHub Account' }}
          </button>
        </template>
        
        <template v-else>
          <div class="github-linked">
            <div class="github-user">
              <svg class="github-icon-small" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
              </svg>
              <span>@{{ githubStatus?.username }}</span>
              <span class="linked-badge">Linked</span>
            </div>
          </div>
          
          <div v-if="selectedRepo" class="selected-repo">
            <h3>Selected Repository</h3>
            <a :href="selectedRepo.html_url" target="_blank" class="repo-link">
              {{ selectedRepo.full_name }}
            </a>
          </div>
          
          <div class="repos-section">
            <div class="repos-header">
              <h3>Your Public Repositories</h3>
              <button @click="fetchGitHubRepos" :disabled="isLoadingRepos" class="refresh-repos-btn">
                {{ isLoadingRepos ? 'Loading...' : 'Refresh' }}
              </button>
            </div>
            
            <div v-if="isLoadingRepos" class="loading-repos">
              Loading repositories...
            </div>
            
            <ul v-else-if="githubRepos.length > 0" class="repo-list">
              <li 
                v-for="repo in githubRepos" 
                :key="repo.id"
                :class="{ selected: repo.is_selected }"
              >
                <div class="repo-info">
                  <span class="repo-name">{{ repo.name }}</span>
                  <span v-if="repo.description" class="repo-desc">{{ repo.description }}</span>
                </div>
                <button 
                  @click="handleSelectRepo(repo)"
                  :disabled="isSelectingRepo || repo.is_selected"
                  class="select-repo-btn"
                  :class="{ 'is-selected': repo.is_selected }"
                >
                  {{ repo.is_selected ? '✓ Selected' : 'Select' }}
                </button>
              </li>
            </ul>
            
            <p v-else class="no-repos">No public repositories found</p>
          </div>
        </template>
      </div>

      <div class="status-card">
        <h2>Backend Status</h2>
        <div class="status-indicator" :class="{ connected: isConnected, loading: isLoading }">
          <span class="status-dot"></span>
          <span class="status-text">{{ isLoading ? 'Checking...' : backendStatus }}</span>
        </div>
        <button @click="checkBackendHealth" :disabled="isLoading" class="refresh-btn">
          {{ isLoading ? 'Checking...' : 'Refresh Status' }}
        </button>
      </div>
      
      <div class="info-section">
        <h3>Progress</h3>
        <ul>
          <li :class="{ completed: !!user }">Google OAuth Login</li>
          <li :class="{ completed: isGitHubLinked }">GitHub Account Linking</li>
          <li :class="{ completed: !!selectedRepo }">Repository Selection</li>
          <li>Webhook Integration</li>
        </ul>
      </div>
    </main>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  min-height: 100vh;
  color: #e8e8e8;
}

.container {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

header {
  text-align: center;
  margin-bottom: 3rem;
}

h1 {
  font-size: 2.5rem;
  font-weight: 700;
  background: linear-gradient(90deg, #00d9ff, #00ff88);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: #8892b0;
  font-size: 1.1rem;
}

.auth-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 2rem;
  margin-bottom: 2rem;
  backdrop-filter: blur(10px);
  text-align: center;
}

.auth-card h2 {
  font-size: 1.3rem;
  margin-bottom: 0.5rem;
  color: #ccd6f6;
}

.auth-description {
  color: #8892b0;
  margin-bottom: 1.5rem;
}

.error-message {
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.auth-status {
  color: #8892b0;
  margin-top: 1rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
  justify-content: center;
}

.user-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(90deg, #00d9ff, #00ff88);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  font-weight: 700;
  color: #1a1a2e;
}

.user-details {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.user-name {
  font-size: 1.1rem;
  font-weight: 600;
  color: #ccd6f6;
}

.user-email {
  font-size: 0.9rem;
  color: #8892b0;
}

.logout-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #8892b0;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  border-color: #ff6b6b;
  color: #ff6b6b;
}

.github-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 2rem;
  margin-bottom: 2rem;
  backdrop-filter: blur(10px);
}

.github-card h2 {
  font-size: 1.3rem;
  margin-bottom: 1rem;
  color: #ccd6f6;
}

.github-description {
  color: #8892b0;
  margin-bottom: 1.5rem;
  text-align: center;
}

.github-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  max-width: 280px;
  margin: 0 auto;
  background: #24292e;
  border: 1px solid #444;
  color: #fff;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.github-btn:hover:not(:disabled) {
  background: #2f363d;
  border-color: #666;
}

.github-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.github-icon {
  width: 20px;
  height: 20px;
}

.github-icon-small {
  width: 16px;
  height: 16px;
}

.github-linked {
  margin-bottom: 1.5rem;
}

.github-user {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: center;
  color: #ccd6f6;
}

.linked-badge {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.selected-repo {
  background: rgba(0, 255, 136, 0.1);
  border: 1px solid rgba(0, 255, 136, 0.3);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  text-align: center;
}

.selected-repo h3 {
  font-size: 0.9rem;
  color: #8892b0;
  margin-bottom: 0.5rem;
}

.repo-link {
  color: #00ff88;
  text-decoration: none;
  font-weight: 600;
}

.repo-link:hover {
  text-decoration: underline;
}

.repos-section {
  margin-top: 1.5rem;
}

.repos-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.repos-header h3 {
  font-size: 1rem;
  color: #8892b0;
}

.refresh-repos-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #8892b0;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-repos-btn:hover:not(:disabled) {
  border-color: #00d9ff;
  color: #00d9ff;
}

.refresh-repos-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-repos {
  text-align: center;
  color: #8892b0;
  padding: 2rem;
}

.repo-list {
  list-style: none;
  max-height: 400px;
  overflow-y: auto;
}

.repo-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  margin-bottom: 0.5rem;
  transition: all 0.2s;
}

.repo-list li:hover {
  background: rgba(255, 255, 255, 0.05);
}

.repo-list li.selected {
  border-color: rgba(0, 255, 136, 0.3);
  background: rgba(0, 255, 136, 0.05);
}

.repo-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.repo-name {
  color: #ccd6f6;
  font-weight: 500;
}

.repo-desc {
  color: #64748b;
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.select-repo-btn {
  background: transparent;
  border: 1px solid rgba(0, 217, 255, 0.5);
  color: #00d9ff;
  padding: 0.375rem 0.75rem;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  margin-left: 1rem;
}

.select-repo-btn:hover:not(:disabled) {
  background: rgba(0, 217, 255, 0.1);
}

.select-repo-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.select-repo-btn.is-selected {
  background: rgba(0, 255, 136, 0.2);
  border-color: #00ff88;
  color: #00ff88;
}

.no-repos {
  text-align: center;
  color: #64748b;
  padding: 2rem;
}

.status-card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 2rem;
  margin-bottom: 2rem;
  backdrop-filter: blur(10px);
}

.status-card h2 {
  font-size: 1.3rem;
  margin-bottom: 1.5rem;
  color: #ccd6f6;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 1.5rem;
}

.status-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #ff6b6b;
  box-shadow: 0 0 10px rgba(255, 107, 107, 0.5);
  transition: all 0.3s ease;
}

.status-indicator.connected .status-dot {
  background: #00ff88;
  box-shadow: 0 0 10px rgba(0, 255, 136, 0.5);
}

.status-indicator.loading .status-dot {
  background: #ffd93d;
  box-shadow: 0 0 10px rgba(255, 217, 61, 0.5);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  font-size: 1.2rem;
  font-weight: 500;
  text-transform: capitalize;
}

.refresh-btn {
  background: linear-gradient(90deg, #00d9ff, #00ff88);
  border: none;
  color: #1a1a2e;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 217, 255, 0.3);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.info-section {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 2rem;
}

.info-section h3 {
  font-size: 1.1rem;
  color: #8892b0;
  margin-bottom: 1rem;
}

.info-section ul {
  list-style: none;
}

.info-section li {
  padding: 0.5rem 0;
  color: #64748b;
  position: relative;
  padding-left: 1.5rem;
}

.info-section li::before {
  content: '○';
  position: absolute;
  left: 0;
  color: #64748b;
}

.info-section li.completed {
  color: #00ff88;
}

.info-section li.completed::before {
  content: '●';
  color: #00ff88;
}
</style>
