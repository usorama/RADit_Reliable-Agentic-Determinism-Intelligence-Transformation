'use client'

import { useAuth as useClerkAuth, useUser, useClerk } from '@clerk/nextjs'
import { useCallback, useEffect, useState } from 'react'

/**
 * Extended auth state returned by useAuth hook
 */
export interface AuthState {
  // Loading states
  isLoaded: boolean
  isSignedIn: boolean

  // User information
  userId: string | null | undefined
  sessionId: string | null | undefined
  user: ReturnType<typeof useUser>['user']

  // Actions
  signOut: () => Promise<void>
  openSignIn: () => void
  openSignUp: () => void
  openUserProfile: () => void

  // Token management for API calls
  getToken: (options?: GetTokenOptions) => Promise<string | null>
}

/**
 * Options for getToken
 */
export interface GetTokenOptions {
  /**
   * Template name for custom JWT claims
   */
  template?: string
  /**
   * Skip cache and get fresh token
   */
  skipCache?: boolean
}

/**
 * Custom useAuth hook that wraps Clerk's authentication hooks
 * and provides additional functionality for API calls.
 *
 * Features:
 * - Re-exports Clerk's useUser, useAuth hooks
 * - Provides getToken() for authenticated API calls
 * - Provides isLoaded, isSignedIn states
 * - Provides sign out and profile management actions
 *
 * @example
 * ```tsx
 * const { isSignedIn, user, getToken, signOut } = useAuth()
 *
 * // Make authenticated API call
 * const token = await getToken()
 * const response = await fetch('/api/data', {
 *   headers: { Authorization: `Bearer ${token}` }
 * })
 * ```
 */
export function useAuth(): AuthState {
  const clerkAuth = useClerkAuth()
  const { isLoaded: isUserLoaded, user } = useUser()
  const clerk = useClerk()

  const { isLoaded: isAuthLoaded, isSignedIn, userId, sessionId, getToken: clerkGetToken } = clerkAuth

  // Combined loading state
  const isLoaded = isAuthLoaded && isUserLoaded

  /**
   * Get authentication token for API calls
   * Automatically handles token refresh
   */
  const getToken = useCallback(
    async (options?: GetTokenOptions): Promise<string | null> => {
      if (!isSignedIn) {
        return null
      }

      try {
        const token = await clerkGetToken({
          template: options?.template,
          skipCache: options?.skipCache,
        })
        return token
      } catch (error) {
        console.error('Failed to get auth token:', error)
        return null
      }
    },
    [isSignedIn, clerkGetToken]
  )

  /**
   * Sign out the current user
   */
  const signOut = useCallback(async () => {
    await clerk.signOut()
  }, [clerk])

  /**
   * Open the sign-in modal
   */
  const openSignIn = useCallback(() => {
    clerk.openSignIn()
  }, [clerk])

  /**
   * Open the sign-up modal
   */
  const openSignUp = useCallback(() => {
    clerk.openSignUp()
  }, [clerk])

  /**
   * Open the user profile modal
   */
  const openUserProfile = useCallback(() => {
    clerk.openUserProfile()
  }, [clerk])

  return {
    // Loading states
    isLoaded,
    isSignedIn: isSignedIn ?? false,

    // User information
    userId,
    sessionId,
    user,

    // Actions
    signOut,
    openSignIn,
    openSignUp,
    openUserProfile,

    // Token management
    getToken,
  }
}

/**
 * Hook to get authentication token with automatic refresh
 * Useful for maintaining a fresh token in state
 *
 * @example
 * ```tsx
 * const { token, isLoading, error } = useAuthToken()
 *
 * useEffect(() => {
 *   if (token) {
 *     // Use token for WebSocket or other connections
 *   }
 * }, [token])
 * ```
 */
export function useAuthToken(options?: GetTokenOptions) {
  const { isSignedIn, getToken } = useAuth()
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    async function fetchToken() {
      if (!isSignedIn) {
        setToken(null)
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setError(null)
        const newToken = await getToken(options)
        setToken(newToken)
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to get token'))
        setToken(null)
      } finally {
        setIsLoading(false)
      }
    }

    fetchToken()

    // Refresh token every 50 minutes (before 1 hour expiry)
    const interval = setInterval(fetchToken, 50 * 60 * 1000)
    return () => clearInterval(interval)
  }, [isSignedIn, getToken, options])

  return { token, isLoading, error }
}

/**
 * Hook for making authenticated API calls
 *
 * @example
 * ```tsx
 * const { fetchWithAuth, isLoading } = useAuthenticatedFetch()
 *
 * const handleSubmit = async () => {
 *   const response = await fetchWithAuth('/api/workflow', {
 *     method: 'POST',
 *     body: JSON.stringify({ action: 'create' })
 *   })
 * }
 * ```
 */
export function useAuthenticatedFetch() {
  const { getToken, isSignedIn } = useAuth()
  const [isLoading, setIsLoading] = useState(false)

  const fetchWithAuth = useCallback(
    async (url: string, options: RequestInit = {}): Promise<Response> => {
      if (!isSignedIn) {
        throw new Error('User must be signed in to make authenticated requests')
      }

      setIsLoading(true)
      try {
        const token = await getToken()
        if (!token) {
          throw new Error('Failed to get authentication token')
        }

        const headers = new Headers(options.headers)
        headers.set('Authorization', `Bearer ${token}`)
        headers.set('Content-Type', 'application/json')

        return await fetch(url, {
          ...options,
          headers,
        })
      } finally {
        setIsLoading(false)
      }
    },
    [getToken, isSignedIn]
  )

  return { fetchWithAuth, isLoading }
}

// Re-export Clerk hooks for convenience
export { useUser, useClerk } from '@clerk/nextjs'

export default useAuth
