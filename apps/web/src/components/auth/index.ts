/**
 * Auth components barrel export
 * Re-exports all authentication components for convenient importing
 */

export { SignIn } from './SignIn'
export { SignUp } from './SignUp'
export { UserButton } from './UserButton'

// Export wrapped auth components that respect DEV_BYPASS_AUTH
export { SignedIn, SignedOut } from './AuthWrappers'

// Re-export remaining Clerk components for convenience
export {
  SignInButton,
  SignUpButton,
  ClerkLoaded,
  ClerkLoading,
} from '@clerk/nextjs'
