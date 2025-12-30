'use client'

import { SignIn as ClerkSignIn } from '@clerk/nextjs'

/**
 * SignIn component integrates Clerk's sign-in functionality.
 * Uses Clerk's pre-built SignIn component with custom routing configuration.
 *
 * Routes:
 * - redirectUrl: Where to redirect after successful sign-in (default: /)
 * - signUpUrl: Link to sign-up page for new users
 */

interface SignInProps {
  /**
   * URL to redirect to after successful sign-in
   * @default "/"
   */
  redirectUrl?: string
  /**
   * Custom path to sign-up page
   * @default "/sign-up"
   */
  signUpUrl?: string
}

export function SignIn({ redirectUrl = '/', signUpUrl = '/sign-up' }: SignInProps) {
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
        </div>
        <ClerkSignIn
          path="/sign-in"
          routing="path"
          signUpUrl={signUpUrl}
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
            },
          }}
        />
      </div>
    </div>
  )
}

export default SignIn
