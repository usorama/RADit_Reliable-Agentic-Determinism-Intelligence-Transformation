import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import { NextRequest, NextResponse } from 'next/server'

/**
 * Development bypass mode - allows testing without Clerk credentials
 * Set NEXT_PUBLIC_DEV_BYPASS_AUTH=true in .env.local to enable
 */
const DEV_BYPASS_AUTH = process.env.NEXT_PUBLIC_DEV_BYPASS_AUTH === 'true'

/**
 * Public routes that don't require authentication
 * Users can access these routes without signing in
 */
const isPublicRoute = createRouteMatcher([
  '/',                    // Landing page
  '/sign-in(.*)',         // Sign-in page and sub-routes
  '/sign-up(.*)',         // Sign-up page and sub-routes
  '/api/public(.*)',      // Public API endpoints
  '/api/health',          // Health check endpoint
  '/about',               // About page
  '/privacy',             // Privacy policy
  '/terms',               // Terms of service
])

/**
 * Admin routes that require admin role
 */
const isAdminRoute = createRouteMatcher(['/admin(.*)'])

/**
 * API routes that require authentication
 */
const isProtectedApiRoute = createRouteMatcher([
  '/api/chat(.*)',
  '/api/workflow(.*)',
  '/api/user(.*)',
])

/**
 * Clerk middleware configuration for Next.js
 *
 * This middleware:
 * 1. Allows public routes without authentication
 * 2. Protects all other routes, redirecting unauthenticated users to sign-in
 * 3. Enforces admin role for admin routes
 * 4. Validates API authentication
 */
/**
 * Type for session claims metadata
 */
interface SessionClaimsMetadata {
  role?: string
}

/**
 * Development bypass middleware - skips Clerk auth entirely
 */
function devBypassMiddleware(request: NextRequest): NextResponse {
  // In dev bypass mode, allow all routes
  return NextResponse.next()
}

/**
 * Production middleware with full Clerk authentication
 */
const productionMiddleware = clerkMiddleware(async (auth, request) => {
  const { userId, sessionClaims } = await auth()

  // Handle admin routes - require admin role
  if (isAdminRoute(request)) {
    if (!userId) {
      const signInUrl = new URL('/sign-in', request.url)
      signInUrl.searchParams.set('redirect_url', request.url)
      return NextResponse.redirect(signInUrl)
    }

    // Check for admin role in session claims metadata
    const metadata = sessionClaims?.metadata as SessionClaimsMetadata | undefined
    if (metadata?.role !== 'admin') {
      return NextResponse.redirect(new URL('/unauthorized', request.url))
    }
  }

  // Handle protected API routes
  if (isProtectedApiRoute(request) && !userId) {
    return NextResponse.json(
      { error: 'Unauthorized', message: 'Authentication required' },
      { status: 401 }
    )
  }

  // Protect all non-public routes
  if (!isPublicRoute(request)) {
    if (!userId) {
      const signInUrl = new URL('/sign-in', request.url)
      signInUrl.searchParams.set('redirect_url', request.url)
      return NextResponse.redirect(signInUrl)
    }
  }

  return NextResponse.next()
})

/**
 * Export the appropriate middleware based on environment
 */
export default DEV_BYPASS_AUTH ? devBypassMiddleware : productionMiddleware

/**
 * Middleware configuration
 * Defines which routes the middleware should run on
 */
export const config = {
  matcher: [
    // Skip Next.js internals and static files
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
}
