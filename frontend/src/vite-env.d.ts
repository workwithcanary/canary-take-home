/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_GOOGLE_CLIENT_ID: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module 'vue3-google-login' {
  import { Plugin } from 'vue'
  const plugin: Plugin
  export default plugin
  export function googleLogout(): void
  export function googleTokenLogin(): Promise<{ credential: string }>
  export function googleOneTap(): Promise<{ credential: string }>
}
