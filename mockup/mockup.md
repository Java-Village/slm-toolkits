## 🧪 Proof of Concept: Smart Drone-Based Solar Panel Maintenance System

### Overview

This is a **proof-of-concept (PoC)** Flask-based backend system that demonstrates the integration of a **LLM (Language Model)** for interpreting task commands related to solar panel maintenance via drones.

The system:

- Accepts natural language commands
- Converts them into structured JSON tasks using a local LLM (e.g., `gemma-3-12b-it-qat`)
- Simulates decision-making using mock drone and panel data
- Supports recursive tool-use if needed (e.g., querying database before assigning a task)

---

### Key Features

- Strict JSON-only output enforced by a detailed system prompt
- Handles task assignment, inspection checks, and error validation
- Simulates a drone fleet and a panel cluster with mock telemetry and history
- Supports LLM multi-turn logic (initial reasoning + tool response + follow-up)
- Designed to be expandable for real-time backend drone control logic

---

### API Endpoint

**POST** `/api/command`

**Input:**

```json
{
  "command": "Clean panel P-002 immediately."
}
```

**Output:**

```json
{
  "status": "success",
  "data": {
    "llm_response": {...},
    "drone_data": [...]
  },
  "timestamp": "2025-06-02T08:00:00Z",
  "message": "Command processed with success status"
}
```

---

### System Prompt Behavior

The backend sends the LLM a **strict task-oriented system prompt** to ensure only valid JSON outputs are returned. It defines:

- Output format requirements
- Task vs No-Action vs Error vs Tool Usage response types
- Predefined error codes and task assignment rules
- Tool invocation structures for follow-up querying (e.g., drone status, panel history)

---

### Code Modules

- `extract_json_from_llm()`: Extracts JSON block from LLM output
- `call_llm_api()`: Calls the local LLM server with user + system prompt
- `call_tool()`: Mocks tool behaviors like database queries
- `handle_command()`: Main API endpoint that executes the command lifecycle

---

### Mermaid Flowchart

```mermaid
graph TD
    A[Client Sends Command] --> B[Flask /api/command Endpoint]
    B --> C[Send to LLM with System Prompt]
    C --> D[LLM Responds with JSON]
    D --> E{Tool Needed?}
    E -- Yes --> F[Call Tool (e.g., db)]
    F --> G[Attach Tool Result]
    G --> H[Resend to LLM for Final Decision]
    E -- No --> H
    H --> I[Randomly Simulate Task Success or Failure]
    I --> J[Return Final Response as JSON]
```

---

### For Frontend Partner

You will interact with the API via the `/api/command` endpoint.

**Expected Responsibilities:**

1. **Command Interface**

   - Build a user interface where users can input natural language commands (e.g., "Inspect panel P-003")
   - Implement command history and suggestions
   - Add command validation and formatting

2. **Response Display**

   - Display the structured JSON response from the backend, including:
     - Drone assignments
     - Task reasoning
     - Any tool queries or error feedback
   - Handle response status (success / error)
   - Display appropriate feedback messages

3. **Visualization (Optional)**

   - Visualize drone positions and destinations (from MOCK_DB)
   - Show panel statuses and cluster layout
   - Display task execution progress
   - Implement real-time updates

4. **Error Handling**
   - Handle API connection errors
   - Display user-friendly error messages
   - Implement retry mechanisms
   - Log errors for debugging

---

### For Backend Partner (Coordination Server)

This backend currently contains a proof-of-concept mockup simulating:

- LLM-driven task reasoning
- Tool-based query logic
- Mock database

**Core Backend Tasks:**

1. **Database Implementation**

   - Replace MOCK_DB with actual queryable database (e.g., PostgreSQL, MongoDB)
   - Structure database schema to align with LLM expectations:
     - ID patterns
     - History records
     - Position format
     - Status enums

2. **Search Capabilities**

   - Implement real search functionality:
     - Query panel by ID
     - Query drone by status, ID, position
     - Search maintenance history
     - Filter by date ranges

3. **Status Monitoring**

   - Implement real-time monitoring:
     - Battery levels
     - Last-known positions
     - Current task state
     - System health metrics

4. **Data Management**

   - Implement data update logic:
     - Panel status after task
     - Drone task assignment status
     - Maintenance history updates
     - Performance metrics

5. **Tool Implementation**

   - Support tool commands defined in the LLM system prompt:
     - `db` query implementation
     - `tasklist` fetch logic
     - `assign` execution logic
   - Add new tools as needed
   - Implement tool response validation
