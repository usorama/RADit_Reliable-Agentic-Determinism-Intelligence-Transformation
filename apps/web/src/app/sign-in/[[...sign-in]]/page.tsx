import { SignIn } from '@/components/auth/SignIn'

/**
 * Sign-in page using Next.js App Router catch-all route
 * This handles /sign-in and all sub-routes like /sign-in/factor-one
 */
export default function SignInPage() {
  return <SignIn />
}
