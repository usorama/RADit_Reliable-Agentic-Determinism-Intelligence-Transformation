'use client'

import { SignUp as ClerkSignUp } from '@clerk/nextjs'

/**
 * SignUp component integrates Clerk's sign-up functionality.
 * Uses Clerk's pre-built SignUp component with custom routing configuration.
 *
 * Features:
 * - OAuth providers (Google, GitHub, etc.)
 * - Email/password registration
 * - Terms and conditions acceptance (configurable in Clerk dashboard)
 * - Email verification flow
 */

interface SignUpProps {
  /**
   * URL to redirect to after successful sign-up
   * @default "/"
   */
  redirectUrl?: string
  /**
   * Custom path to sign-in page
   * @default "/sign-in"
   */
  signInUrl?: string
}

export function SignUp({ redirectUrl = '/', signInUrl = '/sign-in' }: SignUpProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            DAW
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Deterministic Agentic Workbench
          </p>
          <p className="mt-1 text-xs text-gray-500">
            Create your account to get started
          </p>
        </div>
        <ClerkSignUp
          path="/sign-up"
          routing="path"
          signInUrl={signInUrl}
          forceRedirectUrl={redirectUrl}
          appearance={{
            elements: {
              rootBox: 'mx-auto',
              card: 'shadow-xl border-0 rounded-lg',
              headerTitle: 'text-xl font-semibold text-gray-900',
              headerSubtitle: 'text-gray-500',
              socialButtonsBlockButton:
                'border border-gray-300 hover:bg-gray-50 transition-colors',
              socialButtonsBlockButtonText: 'font-medium',
              dividerLine: 'bg-gray-200',
              dividerText: 'text-gray-500 text-sm',
              formFieldLabel: 'text-sm font-medium text-gray-700',
              formFieldInput:
                'border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500',
              formButtonPrimary:
                'bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md transition-colors w-full',
              footerActionLink: 'text-blue-600 hover:text-blue-700 font-medium',
              identityPreview: 'border border-gray-200 rounded-md',
              formFieldErrorText: 'text-red-600 text-sm',
              alert: 'bg-red-50 border border-red-200 text-red-800 rounded-md',
              alertText: 'text-sm',
              // Terms and conditions styling
              checkbox: 'text-blue-600 focus:ring-blue-500',
              checkboxLabel: 'text-sm text-gray-600',
            },
          }}
        />
      </div>
    </div>
  )
}

export default SignUp
