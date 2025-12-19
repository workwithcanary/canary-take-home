<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { googleLogout } from 'vue3-google-login'
import {
  checkHealth,
  authenticateWithGoogle,
  getGitHubOAuthURL,
  getGitHubOAuthURLForReauth,
  exchangeGitHubCode,
  getGitHubStatus,
  unlinkGitHub,
  getGitHubRepos,
  selectGitHubRepo,
  setupWebhook,
  getWebhookEvents,
  type User,
  type GitHubStatus,
  type GitHubRepo,
  type WebhookEvent,
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

const webhookEvents = ref<WebhookEvent[]>([])
const isLoadingEvents = ref<boolean>(false)
const isSettingUpWebhook = ref<boolean>(false)
const webhookError = ref<string>('')
const expandedEventId = ref<number | null>(null)

const isGitHubLinked = computed(() => githubStatus.value?.linked ?? false)
const hasWebhookScope = computed(() => githubStatus.value?.has_webhook_scope ?? false)
const selectedRepo = computed(() => githubStatus.value?.selected_repo ?? null)
const isWebhookActive = computed(() => githubStatus.value?.selected_repo?.webhook_active ?? false)

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

const handleReauthorizeGitHub = async () => {
  if (!user.value) return
  
  githubError.value = ''
  isLinkingGitHub.value = true
  
  try {
    const url = await getGitHubOAuthURLForReauth(user.value.id)
    window.location.href = url
  } catch (error: unknown) {
    console.error('Failed to get GitHub re-auth URL:', error)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { error?: string } } }
      githubError.value = axiosError.response?.data?.error || 'Failed to start GitHub re-authorization'
    } else {
      githubError.value = 'Failed to start GitHub re-authorization'
    }
    isLinkingGitHub.value = false
  }
}

const isUnlinkingGitHub = ref<boolean>(false)

const handleUnlinkGitHub = async () => {
  if (!user.value) return
  
  if (!confirm('Are you sure you want to unlink your GitHub account? This will remove all GitHub data including repositories and webhooks.')) {
    return
  }
  
  githubError.value = ''
  isUnlinkingGitHub.value = true
  
  try {
    await unlinkGitHub(user.value.id)
    githubStatus.value = null
    githubRepos.value = []
    webhookEvents.value = []
    await fetchGitHubStatus()
  } catch (error: unknown) {
    console.error('Failed to unlink GitHub:', error)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { error?: string } } }
      githubError.value = axiosError.response?.data?.error || 'Failed to unlink GitHub account'
    } else {
      githubError.value = 'Failed to unlink GitHub account'
    }
  } finally {
    isUnlinkingGitHub.value = false
  }
}

const handleSetupWebhook = async () => {
  if (!user.value) return
  
  webhookError.value = ''
  isSettingUpWebhook.value = true
  
  try {
    await setupWebhook(user.value.id)
    await fetchGitHubStatus()
    await fetchWebhookEvents()
  } catch (error: unknown) {
    console.error('Failed to setup webhook:', error)
    if (error && typeof error === 'object' && 'response' in error) {
      const axiosError = error as { response?: { data?: { error?: string; requires_reauth?: boolean } } }
      if (axiosError.response?.data?.requires_reauth) {
        webhookError.value = 'Missing webhook permissions. Please re-authorize GitHub.'
      } else {
        webhookError.value = axiosError.response?.data?.error || 'Failed to setup webhook'
      }
    } else {
      webhookError.value = 'Failed to setup webhook'
    }
  } finally {
    isSettingUpWebhook.value = false
  }
}

const fetchWebhookEvents = async () => {
  if (!user.value) return
  
  isLoadingEvents.value = true
  
  try {
    webhookEvents.value = await getWebhookEvents(user.value.id)
  } catch (error) {
    console.error('Failed to fetch webhook events:', error)
  } finally {
    isLoadingEvents.value = false
  }
}

const toggleEventExpand = (eventId: number) => {
  expandedEventId.value = expandedEventId.value === eventId ? null : eventId
}

const formatEventTime = (isoString: string): string => {
  return new Date(isoString).toLocaleString()
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

watch(isWebhookActive, (active: boolean) => {
  if (active) {
    fetchWebhookEvents()
  }
})

onMounted(async () => {
  loadUserFromStorage()
  checkBackendHealth()
  
  if (user.value) {
    await fetchGitHubStatus()
    handleGitHubCallback()
    if (isWebhookActive.value) {
      fetchWebhookEvents()
    }
  }
})

watch(user, async (newUser: User | null) => {
  if (newUser) {
    await fetchGitHubStatus()
    handleGitHubCallback()
    if (isWebhookActive.value) {
      fetchWebhookEvents()
    }
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
            <button 
              @click="handleUnlinkGitHub"
              :disabled="isUnlinkingGitHub"
              class="unlink-github-btn"
            >
              {{ isUnlinkingGitHub ? 'Unlinking...' : 'Sign Out' }}
            </button>
          </div>
          
          <div v-if="!hasWebhookScope" class="scope-warning">
            <p>⚠️ Missing webhook permissions. Re-authorize to enable webhook creation.</p>
            <button 
              @click="handleReauthorizeGitHub"
              :disabled="isLinkingGitHub"
              class="reauth-btn"
            >
              {{ isLinkingGitHub ? 'Redirecting...' : 'Re-authorize GitHub' }}
            </button>
          </div>
          
          <div v-if="selectedRepo" class="selected-repo">
            <div class="selected-repo-header">
              <h3>Selected Repository</h3>
              <span v-if="isWebhookActive" class="webhook-badge active">Webhook Active</span>
              <span v-else class="webhook-badge inactive">No Webhook</span>
            </div>
            <a :href="selectedRepo.html_url" target="_blank" class="repo-link">
              {{ selectedRepo.full_name }}
            </a>
            
            <div v-if="webhookError" class="error-message webhook-error">{{ webhookError }}</div>
            
            <div v-if="!isWebhookActive && hasWebhookScope" class="webhook-setup">
              <button 
                @click="handleSetupWebhook"
                :disabled="isSettingUpWebhook"
                class="setup-webhook-btn"
              >
                {{ isSettingUpWebhook ? 'Setting up...' : 'Setup Webhook' }}
              </button>
            </div>
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
          
          <div v-if="isWebhookActive" class="events-section">
            <div class="events-header">
              <h3>Webhook Events</h3>
              <button @click="fetchWebhookEvents" :disabled="isLoadingEvents" class="refresh-events-btn">
                {{ isLoadingEvents ? 'Loading...' : 'Refresh' }}
              </button>
            </div>
            
            <div v-if="isLoadingEvents" class="loading-events">
              Loading events...
            </div>
            
            <ul v-else-if="webhookEvents.length > 0" class="event-list">
              <li 
                v-for="event in webhookEvents" 
                :key="event.id"
                class="event-item"
              >
                <div class="event-summary" @click="toggleEventExpand(event.id)">
                  <span class="event-type" :class="event.event_type">{{ event.event_type }}</span>
                  <span class="event-repo">{{ event.repo_full_name }}</span>
                  <span class="event-time">{{ formatEventTime(event.received_at) }}</span>
                  <span class="expand-icon">{{ expandedEventId === event.id ? '▼' : '▶' }}</span>
                </div>
                <div v-if="expandedEventId === event.id" class="event-payload">
                  <pre>{{ JSON.stringify(event.payload, null, 2) }}</pre>
                </div>
              </li>
            </ul>
            
            <p v-else class="no-events">No webhook events received yet</p>
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
          <li :class="{ completed: isWebhookActive }">Webhook Integration</li>
          <li :class="{ completed: webhookEvents.length > 0 }">Events Received</li>
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  gap: 1rem;
}

.github-user {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
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

.unlink-github-btn {
  background: rgba(255, 107, 107, 0.2);
  border: 1px solid rgba(255, 107, 107, 0.4);
  color: #ff6b6b;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.unlink-github-btn:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.3);
  border-color: rgba(255, 107, 107, 0.6);
  transform: translateY(-1px);
}

.unlink-github-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

.scope-warning {
  background: rgba(255, 193, 7, 0.1);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  text-align: center;
}

.scope-warning p {
  color: #ffc107;
  margin-bottom: 1rem;
}

.reauth-btn {
  background: linear-gradient(90deg, #ffc107, #ff9800);
  border: none;
  color: #1a1a2e;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.reauth-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(255, 193, 7, 0.3);
}

.reauth-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.selected-repo-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
  justify-content: center;
}

.webhook-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
}

.webhook-badge.active {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.webhook-badge.inactive {
  background: rgba(255, 255, 255, 0.1);
  color: #8892b0;
}

.webhook-setup {
  margin-top: 1rem;
}

.setup-webhook-btn {
  background: linear-gradient(90deg, #00d9ff, #00ff88);
  border: none;
  color: #1a1a2e;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.setup-webhook-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(0, 217, 255, 0.3);
}

.setup-webhook-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.webhook-error {
  margin-top: 0.75rem;
}

.events-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.events-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.events-header h3 {
  font-size: 1rem;
  color: #8892b0;
}

.refresh-events-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #8892b0;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-events-btn:hover:not(:disabled) {
  border-color: #00d9ff;
  color: #00d9ff;
}

.refresh-events-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-events {
  text-align: center;
  color: #8892b0;
  padding: 2rem;
}

.event-list {
  list-style: none;
  max-height: 400px;
  overflow-y: auto;
}

.event-item {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  margin-bottom: 0.5rem;
  overflow: hidden;
}

.event-summary {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
  transition: background 0.2s;
}

.event-summary:hover {
  background: rgba(255, 255, 255, 0.05);
}

.event-type {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  background: rgba(0, 217, 255, 0.2);
  color: #00d9ff;
}

.event-type.push {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.event-type.pull_request {
  background: rgba(156, 39, 176, 0.2);
  color: #ce93d8;
}

.event-repo {
  color: #ccd6f6;
  flex: 1;
  font-size: 0.9rem;
}

.event-time {
  color: #64748b;
  font-size: 0.8rem;
}

.expand-icon {
  color: #64748b;
  font-size: 0.7rem;
}

.event-payload {
  background: rgba(0, 0, 0, 0.3);
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 1rem;
  max-height: 300px;
  overflow: auto;
}

.event-payload pre {
  margin: 0;
  font-family: 'Fira Code', 'Monaco', monospace;
  font-size: 0.75rem;
  color: #8892b0;
  white-space: pre-wrap;
  word-break: break-all;
}

.no-events {
  text-align: center;
  color: #64748b;
  padding: 2rem;
}
</style>
