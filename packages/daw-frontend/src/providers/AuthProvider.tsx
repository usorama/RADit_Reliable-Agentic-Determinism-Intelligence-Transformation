'use client'

import { ClerkProvider } from '@clerk/nextjs'
import type { ReactNode } from 'react'

/**
 * AuthProvider wraps the application with Clerk authentication context.
 * This provider must wrap all components that need access to authentication state.
 *
 * Environment variables required:
 * - NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: Clerk publishable key
 * - CLERK_SECRET_KEY: Clerk secret key (server-side only)
 * - NEXT_PUBLIC_CLERK_SIGN_IN_URL: Sign-in page URL (default: /sign-in)
 * - NEXT_PUBLIC_CLERK_SIGN_UP_URL: Sign-up page URL (default: /sign-up)
 */

interface AuthProviderProps {
  children: ReactNode
}

/**
 * Clerk appearance customization for brand consistency
 */
const clerkAppearance = {
  // Required for Tailwind CSS 4 compatibility
  cssLayerName: 'clerk',
  variables: {
    colorPrimary: '#3b82f6', // blue-500
    colorBackground: '#ffffff',
    colorText: '#1f2937', // gray-800
    colorTextOnPrimaryBackground: '#ffffff',
    colorTextSecondary: '#6b7280', // gray-500
    colorInputBackground: '#f9fafb', // gray-50
    colorInputText: '#1f2937', // gray-800
    borderRadius: '0.5rem',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  elements: {
    rootBox: 'w-full',
    card: 'shadow-lg border border-gray-200',
    headerTitle: 'text-xl font-semibold',
    headerSubtitle: 'text-gray-500',
    formButtonPrimary:
      'bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors',
    formFieldInput:
      'border-gray-300 focus:border-blue-500 focus:ring-blue-500 rounded-md',
    footerActionLink: 'text-blue-600 hover:text-blue-700',
    identityPreviewEditButton: 'text-blue-600 hover:text-blue-700',
    formResendCodeLink: 'text-blue-600 hover:text-blue-700',
    userButtonAvatarBox: 'w-8 h-8',
    userButtonPopoverCard: 'shadow-lg border border-gray-200',
    userButtonPopoverActionButton: 'hover:bg-gray-100',
    userButtonPopoverFooter: 'border-t border-gray-200',
  },
}

export function AuthProvider({ children }: AuthProviderProps) {
  return (
    <ClerkProvider
      appearance={clerkAppearance}
      signInUrl={process.env.NEXT_PUBLIC_CLERK_SIGN_IN_URL || '/sign-in'}
      signUpUrl={process.env.NEXT_PUBLIC_CLERK_SIGN_UP_URL || '/sign-up'}
      afterSignInUrl={process.env.NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL || '/'}
      afterSignUpUrl={process.env.NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL || '/'}
    >
      {children}
    </ClerkProvider>
  )
}

export default AuthProvider
