'use client'

import { ReactNode } from 'react'
import {
  SignedIn as ClerkSignedIn,
  SignedOut as ClerkSignedOut,
} from '@clerk/nextjs'

/**
 * Development bypass mode check
 */
const DEV_BYPASS_AUTH = process.env.NEXT_PUBLIC_DEV_BYPASS_AUTH === 'true'

interface AuthWrapperProps {
  children: ReactNode
}

/**
 * SignedIn wrapper that respects DEV_BYPASS_AUTH
 * In dev bypass mode, always renders children (simulates signed-in state)
 */
export function SignedIn({ children }: AuthWrapperProps) {
  if (DEV_BYPASS_AUTH) {
    // In dev bypass mode, always show signed-in content
    return <>{children}</>
  }
  return <ClerkSignedIn>{children}</ClerkSignedIn>
}

/**
 * SignedOut wrapper that respects DEV_BYPASS_AUTH
 * In dev bypass mode, never renders children (simulates signed-in state)
 */
export function SignedOut({ children }: AuthWrapperProps) {
  if (DEV_BYPASS_AUTH) {
    // In dev bypass mode, never show signed-out content
    return null
  }
  return <ClerkSignedOut>{children}</ClerkSignedOut>
}
