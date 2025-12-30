# 04. User Stories & Epics

## Epic 1: Project Initialization & Planning
-   **Story 1.1**: As a User, I want to describe my app idea in natural language so that the system can help me structure it.
-   **Story 1.2**: As a Builder, I want the system to critique my idea for scalability risks before I start coding.
-   **Story 1.3**: As a User, I want a generated PRD that I can manually edit and approve.

## Epic 2: The Deterministic Build Loop
-   **Story 2.1**: As an Agent, I cannot write implementation code until I have proven the existence of a failing test (The "Red" Check).
-   **Story 2.2**: As a User, I verified that the agent uses the project's specific existing patterns (via `project-context.md`) instead of generic internet patterns.

## Epic 3: Safety & Verification
-   **Story 3.1**: As a Security Engineer, I want to ensure no API keys from my `.env` are ever visible in the LLM's prompt window (via `.mcpignore`).
-   **Story 3.2**: As a Release Manager, I want UAT (User Acceptance Testing) agents to simulate a user logging in and clicking buttons before I approve a deploy.
