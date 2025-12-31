# **The Deterministic Agentic System: Master Design Document**

## **Part 1: Strategic Q\&A & Operational Philosophy**

Before reviewing the technical specifications, it is critical to address the foundational questions regarding agnosticism, determinism, and the operational reality of this system in late 2025\.

### **Q1: How do we achieve true "Model Agnosticism" when tools (Claude Code, Cursor, Gemini) have proprietary ecosystems?**

**Answer:** We achieve agnosticism by treating the LLM as a **stateless reasoning unit**, not the operating system. The system you are building is the Operating System (Agent OS).

* **The Architecture:** We utilize the **Model Context Protocol (MCP)** as the universal abstraction layer. Whether you use claude-code CLI, gemini CLI, or a custom Python script calling gpt-5-turbo, the **tools** (File System, Git, Database, Slack) are exposed via MCP servers.  
* **The "Driver" Layer:** The system will feature a "Model Adapter" pattern. You configure the system: use\_driver: "claude-code-cli" or use\_driver: "openai-api". The system formats the tasks.json into the specific context format required by that driver. The *logic* of what to do next (the workflow) resides in your system's code, not in the model's proprietary memory.1

### **Q2: How does the system handle "Vibe Coding" vs. "Engineering Rigor"?**

**Answer:** The system strictly bifurcates these modes.

* **Ideation Phase (Vibe Mode):** The user chats with a "Product Manager Agent" to brainstorm. This is loose, probabilistic, and creative. The output is a *strict* artifact: a PRD.md.  
* **Execution Phase (Deterministic Mode):** Once the PRD is approved, "Vibe Mode" is disabled. The system enters "Execution Mode." Agents are **forbidden** from deviating from the spec. They cannot "invent" features. They must adhere to the **Request-Validate-Resolve** loop. If a test fails, they must fix it. They cannot say "I think this is better"; they must prove it passes the TDD suite.3

### **Q3: How do we ensure the system is "Self-Aware" of risks and assumptions?**

**Answer:** We implement **compulsory reflection steps** defined in the CLAUDE.md (System Prompt) and enforced by the Orchestrator.

* **Pre-Flight Check:** Before writing code, the agent must output a PLAN block. It must explicitly state: "I am assuming X about the database schema. I will verify this assumption by running \\db\_schema\_dump before proceeding."  
* **Risk Scanning:** A dedicated "Sentinel Agent" runs in parallel. It does not write code; it critiques the Planner's output. If the Planner says "Delete the user table," the Sentinel intercepts the command and pauses execution for human authorization. This is "Human-in-the-Loop" by design for high-risk actions.5

### **Q4: How does the "Fully Automatic Kanban" work?**

**Answer:** The Kanban board is a **visualization of the tasks.json file**, not a separate database.

* **Two-Way Sync:** When the Orchestrator Agent completes a task (passes tests, commits code), it updates the status in tasks.json to done. The UI (Vibe Kanban) watches this file and moves the card to the "Done" column instantly.  
* **User Injection:** If you add a card to the "To Do" column in the UI, the system writes a new entry to tasks.json. The Orchestrator detects this new entry, analyzes dependencies, and queues it for execution.7

## ---

**Part 2: Product Requirements Document (PRD)**

Project Name: The Deterministic Builder (TDB)  
Version: 1.0 (2025-Dec-30)  
Target Users: Senior Architects, Product Managers, "10x" Engineers.

### **2.1 Executive Vision**

To build a "System that Builds Systems." TDB is a deterministic, agentic Secure Software Development Life Cycle (SSDLC) platform. It takes a high-level goal, refines it into a rigorous specification, and orchestrates a fleet of AI agents to implement, test, and deploy the software with minimal human intervention. It prioritizes **correctness over speed** and **transparency over magic**.

### **2.2 Functional Requirements**

#### **2.2.1 Phase 1: Ideation & Specification (The "Brain")**

* **FR-1.1 PRD Generator:** The system must provide an interactive chat interface (Taskmaster-AI based) to interview the user and generate a comprehensive docs/PRD.md. 8  
* **FR-1.2 Complexity Analysis:** The system must analyze the PRD and assign a "Complexity Score" (1-10) to each feature. High-complexity features must be recursively broken down into sub-features. 10  
* **FR-1.3 Task Decomposition:** The system must parse PRD.md into a machine-readable tasks.json. This file must define dependencies (DAG) to ensure agents do not build the roof before the foundation. 12

#### **2.2.2 Phase 2: Orchestration & Execution (The "Hands")**

* **FR-2.1 Kanban Interface:** A web-based Kanban board (Vibe Kanban) must visualize tasks.json. It must support Drag-and-Drop to re-prioritize tasks, which updates the JSON file in real-time. 7  
* **FR-2.2 Orchestrator Agent:** A central agent must loop through tasks.json, identify unblocked tasks, and dispatch them to "Worker Agents." 14  
* **FR-2.3 Worker Isolation:** Each Worker Agent must run in an isolated **E2B Sandbox** or **Docker Container**. They must *never* execute code on the host machine's root environment. 15  
* **FR-2.4 Tool Agnosticism:** The system must support hot-swapping the underlying LLM driver (Claude Code, OpenAI, Gemini) via a simple configuration file config.yaml. 17

#### **2.2.3 Phase 3: Validation & Quality Assurance (The "Conscience")**

* **FR-3.1 TDD Enforcement:** The system must strictly enforce the **Red-Green-Refactor** cycle. The Worker Agent *cannot* write implementation code until a failing test file exists and has been verified (Red state). 3  
* **FR-3.2 Context Retrieval:** Workers must use the **Context7 MCP Server** to fetch up-to-date documentation for libraries (e.g., "Next.js 15 docs") to prevent hallucination of deprecated APIs. 19  
* **FR-3.3 Self-Correction Loop:** If a test fails, the agent must enter a "Repair Loop" (max 3 retries). It must read the error log, attempt a fix, and re-run the test. If it fails 3 times, it marks the task as BLOCKED and alerts the human. 4

### **2.3 Non-Functional Requirements**

* **NFR-1 Determinism:** Given the same tasks.json and PRD.md, the system should produce functionally identical code structures (idempotency).  
* **NFR-2 Security:** No secrets (API keys) shall be passed in plain text. All secrets must be injected via environment variables in the E2B sandbox.  
* **NFR-3 Observability:** Every agent decision, tool call, and terminal output must be logged to a logs/ directory and visible in the UI.

### **2.4 Metrics for Success**

* **Pass Rate:** \>90% of agent-generated Pull Requests must pass CI/CD on the first attempt.  
* **Autonomy Ratio:** The system should complete at least 5 standard tasks (e.g., "Create API endpoint") for every 1 human intervention.  
* **Self-Healing:** 100% of "simple" runtime errors (e.g., syntax error, missing import) must be fixed autonomously by the agent.

## ---

**Part 3: System Architecture Document**

### **3.1 High-Level Topology**

The system follows a **Hub-and-Spoke** architecture centered around the **Agent OS Kernel**.

Code snippet

graph TD  
    User\[User / Architect\] \--\>|Interacts via| UI\[Vibe Kanban UI\]  
    UI \<--\>|Reads/Writes| State  
      
    subgraph "Agent OS Kernel"  
        Orchestrator\[Orchestrator Agent\] \--\>|Reads| State  
        Orchestrator \--\>|Dispatches| WorkerPool  
    end  
      
    subgraph "Execution Plane (Sandboxed)"  
        Worker1 \--\>|Uses| Tools  
        Worker2 \--\>|Uses| Tools  
    end  
      
    subgraph "The Knowledge & Tooling Layer (MCP)"  
        Tools \--\>|Query| Context7  
        Tools \--\>|Execute| Git\[Git MCP\]  
        Tools \--\>|Execute| FS  
        Tools \--\>|Execute| Test  
    end

### **3.2 Component Specifications**

#### **3.2.1 The Orchestrator (The Manager)**

* **Technology:** Python / TypeScript (LangGraph or Custom Loop).  
* **Role:** The "Main Loop." It does not write code. It manages the tasks.json state machine.  
* **Logic:**  
  1. Load tasks.json.  
  2. Find tasks where status \== "pending" AND dependencies are all done.  
  3. Select best model for the task (e.g., o1 for complex logic, haiku for simple CSS).  
  4. Spawn a **Worker Agent** with the specific task context.  
  5. Wait for Worker to return success or failure.  
  6. Update tasks.json.

#### **3.2.2 The Worker Agent (The Builder)**

* **Technology:** Claude Code SDK / OpenCode Interpreter.  
* **Environment:** **E2B Sandbox**.  
* **Workflow (The TDD Loop):**  
  1. **Understand:** Read PRD.md section relevant to the task.  
  2. **Research:** Call context7 to get latest docs for required libraries.  
  3. **Red:** Write tests/feature\_test.py. Run test. Confirm Failure.  
  4. **Green:** Write src/feature.py. Run test. Confirm Success.  
  5. **Refactor:** Lint code. Optimize. Run test again.  
  6. **Commit:** git commit \-m "feat: implemented task X" via Git MCP.

#### **3.2.3 The State Layer (tasks.json)**

This is the database of the system. It must follow a strict schema to ensure determinism.

JSON

{  
  "project\_name": "Deterministic App",  
  "tasks":,  
      "complexity": 3,  
      "assigned\_agent": "db-specialist-01",  
      "artifacts": \["supabase/migrations/20251230\_init.sql"\]  
    }  
  \]  
}

#### **3.2.4 The Interface (Vibe Kanban)**

* **Integration:** Vibe Kanban runs as a local server. It reads the tasks.json file directly from the repo.  
* **Automation:** It does not need a database. It purely reflects the state of the JSON file. When an agent updates the JSON, the board updates via WebSocket.

### **3.3 Security & Guardrails**

#### **3.3.1 The .mcpignore Protocol**

Just as .gitignore prevents tracking of sensitive files, .mcpignore prevents the agents from reading or exfiltrating sensitive data.

* **Default Rules:**  
  * .env  
  * id\_rsa  
  * production\_db\_credentials.json

#### **3.3.2 The "YOLO" Switch (Managed)**

* **Dev Mode:** Agents can execute standard shell commands (ls, cat, grep) without approval. Destructive commands (rm, drop table) require a "Human-in-the-Loop" confirmation via the CLI or Kanban UI.  
* **CI Mode:** Fully autonomous (YOLO), but strictly confined to the ephemeral E2B sandbox. If they destroy the sandbox, no harm is done.

### **3.4 Deployment & Self-Healing (Ops)**

#### **3.4.1 Monitor-Diagnose-Heal Loop**

Once deployed, the system shifts to Ops mode.

1. **Monitor:** An MCP server connects to **Sentry** or **Datadog**.  
2. **Diagnose:** When an alert fires (e.g., 500 Internal Server Error), the Orchestrator creates a new "Bug Fix Task" in tasks.json with high priority.  
3. **Heal:** A Worker Agent picks up the task.  
   * It pulls the stack trace from Sentry.  
   * It creates a reproduction test case (Red).  
   * It fixes the code (Green).  
   * It pushes the fix to a staging branch for human review.

## **4\. Implementation Roadmap (Start Today)**

1. **Day 1: The Skeleton.**  
   * Install claude-code or taskmaster-ai.  
   * Initialize a repo with the tasks.json structure.  
   * Set up **Vibe Kanban** to point to this repo.  
2. **Day 2: The Brain.**  
   * Create the prompts/prd\_generator.md template.  
   * Run the first interview to generate a spec for a simple tool (e.g., "A CLI calculator").  
3. **Day 3: The Hands.**  
   * Configure **E2B** sandbox API keys.  
   * Set up **Context7** MCP server.  
   * Run the first autonomous loop: "Implement Task 1 from tasks.json".  
4. **Day 4: The Loop.**  
   * Implement the TDD enforcement script (a simple Python wrapper around the agent).  
   * Watch the agent fail, retry, and succeed without your input.

This system is not science fiction. It is a specific configuration of tools available *right now* (December 30, 2025). By adhering to this architecture, you move from "playing with AI" to "industrial-grade AI engineering."

#### **Works cited**

1. Unified Tool Integration for LLMs: A Protocol-Agnostic Approach to Function Calling \- arXiv, accessed on December 30, 2025, [https://arxiv.org/html/2508.02979v1](https://arxiv.org/html/2508.02979v1)  
2. The Agent Operating System: A Vision for Canonical AI Agent Development \- Medium, accessed on December 30, 2025, [https://medium.com/@mbonsign/the-agent-operating-system-a-vision-for-canonical-ai-agent-development-79e8c2391f74](https://medium.com/@mbonsign/the-agent-operating-system-a-vision-for-canonical-ai-agent-development-79e8c2391f74)  
3. TDD in the Age of Vibe Coding: Pairing Red-Green-Refactor with AI \- Medium, accessed on December 30, 2025, [https://medium.com/@rupeshit/tdd-in-the-age-of-vibe-coding-pairing-red-green-refactor-with-ai-65af8ed32ae8](https://medium.com/@rupeshit/tdd-in-the-age-of-vibe-coding-pairing-red-green-refactor-with-ai-65af8ed32ae8)  
4. The Codebase Singularity: “My agents run my codebase better than I can” \- YouTube, accessed on December 30, 2025, [https://www.youtube.com/watch?v=fop\_yxV-mPo](https://www.youtube.com/watch?v=fop_yxV-mPo)  
5. How to Secure Model Context Protocol (MCP) | by Tahir | Dec, 2025, accessed on December 30, 2025, [https://medium.com/@tahirbalarabe2/how-to-secure-model-context-protocol-mcp-01339d9e603c](https://medium.com/@tahirbalarabe2/how-to-secure-model-context-protocol-mcp-01339d9e603c)  
6. ACHIEVING A SECURE AI AGENT ECOSYSTEM: | Schmidt Sciences, accessed on December 30, 2025, [https://www.schmidtsciences.org/wp-content/uploads/2025/06/Achieving\_a\_Secure\_AI\_Agent\_Ecosystem-3.pdf](https://www.schmidtsciences.org/wp-content/uploads/2025/06/Achieving_a_Secure_AI_Agent_Ecosystem-3.pdf)  
7. Vibe Kanban MCP Server \- Vibe Kanban, accessed on December 30, 2025, [https://vibekanban.com/docs/integrations/vibe-kanban-mcp-server](https://vibekanban.com/docs/integrations/vibe-kanban-mcp-server)  
8. Examples of PRDs and how you made them : r/vibecoding \- Reddit, accessed on December 30, 2025, [https://www.reddit.com/r/vibecoding/comments/1kblh3d/examples\_of\_prds\_and\_how\_you\_made\_them/](https://www.reddit.com/r/vibecoding/comments/1kblh3d/examples_of_prds_and_how_you_made_them/)  
9. How to Reduce AI Coding Errors with a Claude TaskMaster AI, a task manager MCP, accessed on December 30, 2025, [https://shipixen.com/tutorials/reduce-ai-coding-errors-with-taskmaster-ai](https://shipixen.com/tutorials/reduce-ai-coding-errors-with-taskmaster-ai)  
10. Task Master: How I solved Cursor code slop and escaped the AI loop of hell (Claude/Gemini/Perplexity powered) : r/ClaudeAI \- Reddit, accessed on December 30, 2025, [https://www.reddit.com/r/ClaudeAI/comments/1jlhg7g/task\_master\_how\_i\_solved\_cursor\_code\_slop\_and/](https://www.reddit.com/r/ClaudeAI/comments/1jlhg7g/task_master_how_i_solved_cursor_code_slop_and/)  
11. God Mode Coding with AI Developer Tools: Cursor \+ Task Master \+ MCP \- Ideas2IT, accessed on December 30, 2025, [https://www.ideas2it.com/blogs/ai-developer-tools-workflow](https://www.ideas2it.com/blogs/ai-developer-tools-workflow)  
12. claude-task-master/docs/tutorial.md at main \- GitHub, accessed on December 30, 2025, [https://github.com/eyaltoledano/claude-task-master/blob/main/docs/tutorial.md](https://github.com/eyaltoledano/claude-task-master/blob/main/docs/tutorial.md)  
13. Task Structure \- Task Master, accessed on December 30, 2025, [https://docs.task-master.dev/capabilities/task-structure](https://docs.task-master.dev/capabilities/task-structure)  
14. The One Agent to RULE them ALL \- Advanced Agentic Coding \- YouTube, accessed on December 30, 2025, [https://www.youtube.com/watch?v=p0mrXfwAbCg](https://www.youtube.com/watch?v=p0mrXfwAbCg)  
15. disler/agent-sandbox-skill: An agent skill for managing ... \- GitHub, accessed on December 30, 2025, [https://github.com/disler/agent-sandbox-skill](https://github.com/disler/agent-sandbox-skill)  
16. Examples \- Documentation \- E2B, accessed on December 30, 2025, [https://e2b.dev/docs/mcp/examples](https://e2b.dev/docs/mcp/examples)  
17. automagik-dev/forge: The Vibe Coding++™ platform \- orchestrate multiple AI agents, experiment with isolated attempts, ship code you understand. Multi-agent kanban with MCP integration. \- GitHub, accessed on December 30, 2025, [https://github.com/automagik-dev/forge](https://github.com/automagik-dev/forge)  
18. mosofsky/spec-then-code: LLM prompts for structured ... \- GitHub, accessed on December 30, 2025, [https://github.com/mosofsky/spec-then-code](https://github.com/mosofsky/spec-then-code)  
19. Context7 MCP Server \-- Up-to-date code documentation for LLMs and AI code editors \- GitHub, accessed on December 30, 2025, [https://github.com/upstash/context7](https://github.com/upstash/context7)  
20. I Should Be Selling This Context Engineering System \- YouTube, accessed on December 30, 2025, [https://www.youtube.com/watch?v=zrsAYgHvr8M](https://www.youtube.com/watch?v=zrsAYgHvr8M)