import { NextFetchEvent, NextRequest, NextResponse } from 'next/server'

/**
 * Development bypass mode - allows testing without Clerk credentials
 * Set NEXT_PUBLIC_DEV_BYPASS_AUTH=true in .env.local to enable
 */
const DEV_BYPASS_AUTH = process.env.NEXT_PUBLIC_DEV_BYPASS_AUTH === 'true'

/**
 * Development bypass middleware - skips all auth
 */
async function devBypassMiddleware(_request: NextRequest): Promise<NextResponse> {
  return NextResponse.next()
}

/**
 * Production middleware with Clerk authentication
 * Only imported and used when not in dev bypass mode
 */
async function getProductionMiddleware() {
  const { clerkMiddleware, createRouteMatcher } = await import('@clerk/nextjs/server')

  const isPublicRoute = createRouteMatcher([
    '/',
    '/sign-in(.*)',
    '/sign-up(.*)',
    '/api/public(.*)',
    '/api/health',
    '/about',
    '/privacy',
    '/terms',
  ])

  const isAdminRoute = createRouteMatcher(['/admin(.*)'])

  const isProtectedApiRoute = createRouteMatcher([
    '/api/chat(.*)',
    '/api/workflow(.*)',
    '/api/user(.*)',
  ])

  interface SessionClaimsMetadata {
    role?: string
  }

  return clerkMiddleware(async (auth, request) => {
    const { userId, sessionClaims } = await auth()

    if (isAdminRoute(request)) {
      if (!userId) {
        const signInUrl = new URL('/sign-in', request.url)
        signInUrl.searchParams.set('redirect_url', request.url)
        return NextResponse.redirect(signInUrl)
      }
      const metadata = sessionClaims?.metadata as SessionClaimsMetadata | undefined
      if (metadata?.role !== 'admin') {
        return NextResponse.redirect(new URL('/unauthorized', request.url))
      }
    }

    if (isProtectedApiRoute(request) && !userId) {
      return NextResponse.json(
        { error: 'Unauthorized', message: 'Authentication required' },
        { status: 401 }
      )
    }

    if (!isPublicRoute(request)) {
      if (!userId) {
        const signInUrl = new URL('/sign-in', request.url)
        signInUrl.searchParams.set('redirect_url', request.url)
        return NextResponse.redirect(signInUrl)
      }
    }

    return NextResponse.next()
  })
}

// Cached production middleware
type ProductionMiddleware = Awaited<ReturnType<typeof getProductionMiddleware>>
let cachedProductionMiddleware: ProductionMiddleware | null = null

/**
 * Main middleware export
 */
export default async function middleware(request: NextRequest, event: NextFetchEvent) {
  if (DEV_BYPASS_AUTH) {
    return devBypassMiddleware(request)
  }

  // Lazy load production middleware only when needed
  if (!cachedProductionMiddleware) {
    cachedProductionMiddleware = await getProductionMiddleware()
  }

  return cachedProductionMiddleware(request, event)
}

/**
 * Middleware configuration
 */
export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
