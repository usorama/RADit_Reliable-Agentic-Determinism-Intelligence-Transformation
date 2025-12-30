/**
 * Auth components barrel export
 * Re-exports all authentication components for convenient importing
 */

export { SignIn } from './SignIn'
export { SignUp } from './SignUp'
export { UserButton } from './UserButton'

// Re-export Clerk components for convenience
export {
  SignedIn,
  SignedOut,
  SignInButton,
  SignUpButton,
  ClerkLoaded,
  ClerkLoading,
} from '@clerk/nextjs'
