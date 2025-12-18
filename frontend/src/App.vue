<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { checkHealth } from './api'

const backendStatus = ref<string>('Checking...')
const isConnected = ref<boolean>(false)
const isLoading = ref<boolean>(true)

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

onMounted(() => {
  checkBackendHealth()
})
</script>

<template>
  <div class="container">
    <header>
      <h1>GitHub Integration App</h1>
      <p class="subtitle">Phase 0 - Infrastructure Setup</p>
    </header>
    
    <main>
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
        <h3>Next Steps (Coming Soon)</h3>
        <ul>
          <li>Google OAuth Login</li>
          <li>GitHub Account Linking</li>
          <li>Repository Selection</li>
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
</style>

