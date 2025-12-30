# Authentication Setup

## Clerk Configuration

Clerk is used for user authentication and session management across the DAW (Deterministic Agentic Workbench) platform.

### Prerequisites

1. Create an account at https://clerk.com
2. Create a new Clerk application
3. Obtain your API keys from the Clerk dashboard

### Configuration Steps

#### 1. Backend Setup (packages/daw-agents)

1. Navigate to `packages/daw-agents/`
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Update `.env` with your Clerk credentials:
   ```
   CLERK_SECRET_KEY=sk_test_xxxxx
   CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
   CLERK_JWT_ISSUER=https://xxxxx.clerk.accounts.dev
   ```

#### 2. Frontend Setup (packages/daw-frontend)

1. Navigate to `packages/daw-frontend/`
2. Copy `.env.local.example` to `.env.local`:
   ```bash
   cp .env.local.example .env.local
   ```
3. Update `.env.local` with your Clerk credentials:
   ```
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxx
   CLERK_SECRET_KEY=sk_test_xxxxx
   ```

### Required Keys

| Key | Location | Purpose |
|-----|----------|---------|
| `CLERK_SECRET_KEY` | Backend `.env` | Backend authentication and token verification |
| `CLERK_PUBLISHABLE_KEY` | Backend `.env` | For service-to-service communication |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Frontend `.env.local` | Frontend authentication provider |
| `CLERK_JWT_ISSUER` | Backend `.env` | JWT token issuer for validation |

### Clerk Dashboard Configuration

1. Navigate to https://dashboard.clerk.com
2. Go to your application settings
3. Configure **Allowed Origins** (CORS):
   - Development: `http://localhost:3000`
   - Production: Your production domain
4. Enable authentication methods (Email, Google, GitHub, etc.)
5. Copy API keys to environment files

### Verification

To verify the Clerk setup is working:

1. Start the development backend:
   ```bash
   cd packages/daw-agents
   python -m uvicorn main:app --reload
   ```

2. Start the development frontend:
   ```bash
   cd packages/daw-frontend
   npm run dev
   ```

3. Navigate to `http://localhost:3000` and verify the authentication UI loads

### Security Considerations

1. Never commit `.env` or `.env.local` files to version control
2. Use `.env.example` and `.env.local.example` as templates
3. Rotate API keys regularly
4. Use different keys for development and production environments
5. Store production keys securely (e.g., CI/CD secrets, environment management services)

### Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Verify `CLERK_SECRET_KEY` is correct and matches Clerk dashboard |
| CORS Errors | Add domain to **Allowed Origins** in Clerk dashboard |
| Invalid JWT | Ensure `CLERK_JWT_ISSUER` matches your Clerk instance |
| Frontend won't load | Check `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set in frontend `.env.local` |

### Related Documentation

- [Clerk Official Docs](https://clerk.com/docs)
- [Clerk API Reference](https://clerk.com/docs/reference/backend-api)
- Environment Setup: See `.env.example` and `.env.local.example` templates
