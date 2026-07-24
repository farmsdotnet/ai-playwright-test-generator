# AI-Driven QA Test Framework

## 🎯 Project Objective
The main objective of this project is to build a **zero-cost, lightweight, AI-driven QA Automation Framework** that automates the lifecycle of writing test scripts. 

By utilizing a local, open-source large language model (LLM), the framework dynamically extracts Acceptance Criteria (A.C.) from a live project management board (Linear), reviews the existing automation code structure (Page Object Model), and generates robust, parameter-free browser validation scripts. To ensure absolute control, a mandatory human-in-the-loop terminal sequence allows an engineer to approve, decline, or request modifications before any generated script is allowed into the live testing suite.

---

## 🧠 Workspace Context Strategy
The framework relies on a hierarchical context model to maximize local AI reasoning efficiency without exceeding token windows or introducing hallucinations:
*   **Main Skill (`global_domain_rules.md`)**: Acts as the global source of truth. It stores persistent business logic, target application rules (SauceDemo), strict code guidelines, and architectural constraints.
*   **Child Skills (`{TKT_ID}_ac.md`)**: Granular target context definitions generated dynamically on-demand. They isolate *only* the specific acceptance criteria for the ticket currently being processed.

---

## 🛠️ Functional Overview of Core Scripts

### 1. `linear_fetch.py` (The Synchronization Layer)
*   **Purpose**: Pulls raw requirements directly from the project board.
*   **How it Works**: Connects to the Linear GraphQL API using an account Personal API Key. It searches for the requested ticket ID, parses the description field to find everything below the `A.C:` marker, and saves it cleanly into `context_store/child_contexts/` as a text markdown file named `{TKT_ID}_ac.md`. It utilizes a raw file-stream read operation to bypass Windows terminal character truncation.

### 2. `generate_test.py` (The Structure Enforcer)
*   **Purpose**: Compiles structural system inputs and interrogates the local AI engine.
*   **How it Works**: Scans your live `src/pages/` folder to build a structural reference map of your existing Page Object Model (POM) classes and actions. It pairs this map with your **Main Skill** and **Child Skill**, then queries a local instance of **Ollama (Qwen 2.5:7b)**. 
*   **Safety Guards**: Rather than trusting the model to write clean execution code, it strips out hallucinated function arguments (`page: Page`), duplicate imports, or invalid browser methods (`.navigate()`), wrapping the pure functional test actions safely inside a rigid, parameter-free python template driven by standard Playwright contexts.

### 3. `pipeline.py` (The Orchestration & Feedback Gateway)
*   **Purpose**: Manages the end-to-end user terminal interface and the Human-in-the-Loop approval step.
*   **How it Works**: Glues the pipeline execution steps together in order:
    1. Triggers `linear_fetch.py` to sync requirements.
    2. Triggers `generate_test.py` to create the initial draft script inside `tests/pending_review/`.
    3. Renders the generated code live on screen and prompts the reviewer for a selection: **`[A]pprove`** (moves the file safely to the active staging suite), **`[D]ecline`** (deletes the draft), or **`[S]uggest Changes`** (takes typed feedback, re-injects it into the prompt layer, and loops back with a regenerated code draft for re-review).

### 4. `run_staging.py` (The Suite Execution Master)
*   **Purpose**: Executes your verified test automation scripts cleanly.
*   **How it Works**: Bypasses any IDE visual test configuration popups or Windows path index bugs by programmatically invoking **Pytest** and **Playwright** directly on the `tests/staging/` repository folder using your explicit local virtual environment binaries.

---

## 🏃‍♂️ End-to-End Execution Workflow Order

To process a new testing requirement, execute the workspace components in this exact order:

```text
  Run pipeline.py (Input Ticket ID)
           │
           ▼
  Sync A.C. from Linear ──► Stored as Child Context File
           │
           ▼
  Parse POM Classes ──► Query Local Ollama ──► Sanitize & Wrap Code
           │
           ▼
  Human Terminal Review Screen 
       ├──► [Decline] ──► Erase Script 
       ├──► [Suggest] ──► Re-generate code with human feedback
       └──► [Approve] ──► Move script cleanly to tests/staging/
           │
           ▼
  Run run_staging.py ──► Execute Pytest ──► Launch Headed Browser
```

### 1. Clean Workspace Caches
Wipes out temporary data compilation blocks and legacy directory parametrization overrides:
```powershell
Remove-Item -Recurse -Force .pytest_cache
```

### 2. Launch the Framework Core Loop
Starts the generation suite, syncs with the Linear Kanban board, and prompts for human code review:
```powershell
.\.venv\Scripts\python.exe pipeline.py
```

### 3. Execute Approved Test Suite
Runs your live browser validations cleanly inside your terminal session, opening the active headed testing interface:
```powershell
.\.venv\Scripts\python.exe run_staging.py
```
