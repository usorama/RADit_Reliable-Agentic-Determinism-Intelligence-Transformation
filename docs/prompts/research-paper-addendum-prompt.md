# DIRECTIVE: DETERMINISTIC SPECIFICATION AUDIT & EVOLUTION

## 1. CONTEXT & SOURCE OF TRUTH
You are a **Senior Agentic Architect**. Your task is to review and update existing project documentation produced via the **BMAD Method** (PRD, Architecture, Tech Specs). Your objective is to align these documents with the principles of **Deterministic Agentic Engineering** as defined in the provided research report.

## 2. THE MISSION
The system we are building is NOT yet operational. We are in the **Solutioning Phase**. You must ensure the "specifications" provide a deterministic "North Star" for the eventual build.

## 3. DOCUMENT REVIEW & GAP ANALYSIS
Analyze the existing BMAD artifacts against the following research report requirements:
*   **Decoupling:** Do the docs clearly separate the **Reasoning Engine (LLM)** from the **Execution Environment (Tools)** and **Workflow (Logic)**?
*   **MCP Standardization:** Does the architecture specify the **Model Context Protocol (MCP)** for dynamic tool discovery?
*   **Sandboxing:** Is there a requirement for **E2B/ephemeral environments** to contain side effects?
*   **Determinism:** Do the docs enforce a strict **Red-Green-Refactor TDD loop** where no production code is written without a failing test?

## 4. DETERMINISTIC TASK DECOMPOSITION (tasks.json)
The research paper mandates that a PRD must be parsed into a **`tasks.json`** file—a deterministic list of **atomic units of work**.
*   **IF `tasks.json` EXISTS:** Audit it. Each task must be small enough to fit a high-relevance context window to prevent hallucinations.
*   **IF `tasks.json` DOES NOT EXIST:** You are COMMANDED to generate it now. Parse the updated PRD into discrete, verifiable implementation steps (e.g., "Implement MCP server for Git," "Configure E2B sandbox for Python execution").

## 5. OUTPUT REQUIREMENTS
1.  **Gap Report:** Identify exactly where the current BMAD docs fail to meet "Deterministic" standards.
2.  **Updated Specs:** Provide the revised PRD and Architecture documents. Then, delete sharded files, and re-shard both PRD and Architecture documents.
3.  **Atomic Task List:** Provide the finalized `tasks.json` as the immediate next step for the implementation phase.
4.  **Update or recreate any other files as required** as per BMAD Method - in folders: scrum, stories, test_strategy, etc., using PRD, Architecture and tasks.json documents.
5.  **Do Gap Analysis** between the updated BMAD docs and the research report requirements. Provide a detailed gap report.

## 6. CONSTRAINT
Do not assume features exist yet, this is planning phase to build. Treat every component mentioned in the research report as a **Requirement to be Built**, not a tool currently at your disposal.