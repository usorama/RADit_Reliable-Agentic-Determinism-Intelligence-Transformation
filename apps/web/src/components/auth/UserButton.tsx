'use client'

import { UserButton as ClerkUserButton, SignInButton } from '@clerk/nextjs'
import { SignedIn, SignedOut } from './AuthWrappers'

/**
 * Development bypass mode check
 */
const DEV_BYPASS_AUTH = process.env.NEXT_PUBLIC_DEV_BYPASS_AUTH === 'true'

/**
 * UserButton component displays the authenticated user's avatar and provides
 * a dropdown menu with sign out and profile settings options.
 *
 * When signed out, displays a sign-in button instead.
 */

interface UserButtonProps {
  /**
   * URL to redirect to after signing out
   * @default "/"
   */
  afterSignOutUrl?: string
  /**
   * Show user name next to avatar
   * @default false
   */
  showName?: boolean
  /**
   * Size of the avatar
   * @default "default"
   */
  size?: 'small' | 'default' | 'large'
}

const sizeClasses = {
  small: 'w-6 h-6',
  default: 'w-8 h-8',
  large: 'w-10 h-10',
}

export function UserButton({
  afterSignOutUrl = '/',
  showName = false,
  size = 'default',
}: UserButtonProps) {
  // In dev bypass mode, show a simple dev user avatar
  if (DEV_BYPASS_AUTH) {
    return (
      <div className="flex items-center gap-3">
        <div className={`${sizeClasses[size]} rounded-full bg-gray-300 flex items-center justify-center text-gray-600 text-xs font-medium`}>
          D
        </div>
        {showName && <span className="text-sm text-gray-700">Dev User</span>}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3">
      <SignedIn>
        <ClerkUserButton
          afterSignOutUrl={afterSignOutUrl}
          showName={showName}
          appearance={{
            elements: {
              avatarBox: sizeClasses[size],
              userButtonPopoverCard: 'shadow-lg border border-gray-200 rounded-lg',
              userButtonPopoverActionButton:
                'hover:bg-gray-100 rounded-md transition-colors',
              userButtonPopoverActionButtonText: 'text-gray-700',
              userButtonPopoverActionButtonIcon: 'text-gray-500',
              userButtonPopoverFooter: 'border-t border-gray-200 mt-2 pt-2',
              userPreview: 'px-2 py-2',
              userPreviewMainIdentifier: 'font-medium text-gray-900',
              userPreviewSecondaryIdentifier: 'text-sm text-gray-500',
            },
          }}
          userProfileMode="navigation"
          userProfileUrl="/user-profile"
        >
          {/* Custom menu items can be added here */}
          <ClerkUserButton.MenuItems>
            <ClerkUserButton.Link
              label="Dashboard"
              labelIcon={<DashboardIcon />}
              href="/dashboard"
            />
            <ClerkUserButton.Link
              label="Settings"
              labelIcon={<SettingsIcon />}
              href="/settings"
            />
            <ClerkUserButton.Action label="manageAccount" />
            <ClerkUserButton.Action label="signOut" />
          </ClerkUserButton.MenuItems>
        </ClerkUserButton>
      </SignedIn>

      <SignedOut>
        <SignInButton mode="modal">
          <button
            type="button"
            className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          >
            Sign In
          </button>
        </SignInButton>
      </SignedOut>
    </div>
  )
}

/**
 * Dashboard icon for menu items
 */
function DashboardIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      className="w-4 h-4"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
      />
    </svg>
  )
}

/**
 * Settings icon for menu items
 */
function SettingsIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      className="w-4 h-4"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  )
}

export default UserButton
