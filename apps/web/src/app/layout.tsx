import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/providers/AuthProvider'
import { UserButton, SignedIn, SignedOut } from '@/components/auth'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'DAW - Deterministic Agentic Workbench',
  description: 'Reliable Agentic Intelligence Transformation',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <AuthProvider>
      <html lang="en">
        <body className={inter.className}>
          <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-gray-900">DAW</h1>
              <span className="hidden text-sm text-gray-500 sm:inline">
                Deterministic Agentic Workbench
              </span>
            </div>
            <nav className="flex items-center gap-4">
              <SignedIn>
                <UserButton afterSignOutUrl="/" />
              </SignedIn>
              <SignedOut>
                <a
                  href="/sign-in"
                  className="text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  Sign In
                </a>
                <a
                  href="/sign-up"
                  className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  Sign Up
                </a>
              </SignedOut>
            </nav>
          </header>
          <main>{children}</main>
        </body>
      </html>
    </AuthProvider>
  )
}
