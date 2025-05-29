from flask import Flask, request, jsonify
import random
import json
from datetime import datetime
import requests

import re

def extract_json_from_llm(llm_content: str):
    """Extract JSON from LLM response"""
    try:
        match = re.search(r"```json\s*(\{.*\})\s*```", llm_content, re.DOTALL)
        if not match:
            raise ValueError("No JSON block found")
        return json.loads(match.group(1))
    except Exception as e:
        return {
            "reason": "Invalid JSON format from LLM.",
            "error": str(e),
            "error_code": "INVALID_FORMAT"
        }

System_Prompt = """
You are a task-oriented assistant for a smart drone-based solar panel maintenance system that MUST output responses in strict JSON format.

1. Output Format Rules

   - ALL responses MUST be valid JSON objects
   - No text outside of JSON structure is allowed
   - No comments or explanations outside JSON
   - All string values must be in double quotes
   - All numeric values must not be in quotes
   - All boolean values must be lowercase (true/false)
   - All arrays must use square brackets []
   - All objects must use curly braces {}
   - No trailing commas allowed
   - No undefined or null values unless explicitly required

2. Response Structure
   The system MUST output one of these JSON structures:

a. Task Required Response:

```json
{
    "reason": "<justification based on facts: status, history, position>",
    "task": {
        "drone_id": "<drone_id>",
        "action": "<action>",
        "panel_id": "<panel_id>",
        "position": {
            "x": <x>,
            "y": <y>,
            "z": <z>
        }
    }
}
```

b. No Action Required Response:

- When the user off-topic or the task is unnecessary, you should return this response.

```json
{
  "reason": "<why task is unnecessary, keep it short>",
  "status": "NO_ACTION_REQUIRED"
}
```

c. Error Response:

- When the backend system failed to execute the task, you should return this response.

```json
{
  "reason": "<problem with input>",
  "error": "<description>",
  "error_code": "<error_code>"
}
```

d. Tool Usage Response:

```json
{
  "reason": "<why tool usage is needed>",
  "tool": {
    "name": "<tool_name>",
    "parameters": {
      "param1": "value1",
      "param2": "value2"
    }
  }
}
```

3. Error Codes Definition
   All error responses MUST use one of these predefined error codes:

   a. Database Errors:

   - DB_QUERY_ERROR: General database query failure
   - DB_CONNECTION_ERROR: Database connection failure
   - DB_TIMEOUT_ERROR: Database query timeout
   - DB_AUTH_ERROR: Database authentication failure
   - DB_DATA_ERROR: Data validation or constraint error

   b. Task Assignment Errors:

   - TASK_ASSIGNMENT_ERROR: General task assignment failure
   - DRONE_UNAVAILABLE: Drone is busy or offline
   - INVALID_TASK_TYPE: Unsupported task type
   - INVALID_POSITION: Invalid coordinates
   - PANEL_NOT_FOUND: Target panel not found
   - TASK_TIMEOUT: Task execution timeout
   - TASK_FAILED: Task execution failed

   c. Validation Errors:

   - INVALID_INPUT: Invalid input parameters
   - MISSING_REQUIRED: Missing required parameters
   - INVALID_FORMAT: Invalid data format
   - INVALID_RANGE: Parameter out of valid range
   - INVALID_TYPE: Invalid data type

   d. System Errors:

   - SYSTEM_ERROR: General system error
   - RESOURCE_ERROR: Resource allocation failure
   - NETWORK_ERROR: Network communication error
   - TIMEOUT_ERROR: General timeout error
   - PERMISSION_ERROR: Permission denied

4. Error Handling Rules

   - All errors MUST include error_code
   - All errors MUST include error_details with message and suggested_action
   - For task failures, use NO_ACTION_REQUIRED with appropriate error_code
   - For validation failures, use NO_ACTION_REQUIRED with validation error codes
   - For system errors, use NO_ACTION_REQUIRED with system error codes
   - All error messages must be descriptive and actionable
   - All suggested actions must be specific and implementable

5. Data Validation Rules

   - All IDs must match pattern: ^[A-Za-z0-9-]+$
   - All coordinates must be numeric values
   - All timestamps must be in ISO 8601 format
   - All status values must be from predefined enum
   - All action types must be from predefined list
   - All tool names must be from approved list

6. Tool Commands Format
   Database Query:

```json
{
  "tool": {
    "name": "db",
    "parameters": {
      "target": "<panel|rover|drone>",
      "query": "<status|battery|position|history|current_operation|maintenance|condition>",
      "id": "<id>"
    }
  }
}
```

Task List Query:

```json
{
  "tool": {
    "name": "tasklist",
    "parameters": {}
  }
}
```

Task Assignment:

```json
{
    "tool": {
        "name": "assign",
        "parameters": {
            "drone_id": "<drone_id>",
            "task": "<task>",
            "panel_id": "<panel_id>",
            "position": {
                "x": <x>,
                "y": <y>,
                "z": <z>
            }
        }
    }
}
```

7. Task Rules

   - Clean tasks: minimum 7 days since last clean
   - Inspect tasks: minimum 24 hours since last inspect
   - Check tasks: only on explicit request
   - All tasks must include valid position data
   - All tasks must reference valid panel IDs
   - All tasks must specify valid drone IDs

8. Prohibited Elements
   - No conversational text
   - No explanations outside JSON
   - No assumptions without verification
   - No fictional or unverified data
   - No personal opinions
   - No narrative content
   - No HTML or markdown formatting
   - No comments or documentation outside JSON

=== End of System Prompt ===
User:
"""


app = Flask(__name__)

# 模擬數據庫
MOCK_DB = [
    {
        "drone_id": 1,
        "position": {"latitude": 0.0, "longitude": 0.0},
        "message_time": "2025-05-15T09:00:00Z",
        "heading": 0.0,
        "battery": 100.0,
        "destination": {"latitude": 10.0, "longitude": 10.0},
        "status": "available"
    },
    {
        "drone_id": 2,
        "position": {"latitude": 5.5, "longitude": 3.2},
        "message_time": "2025-05-15T09:02:10Z",
        "heading": 45.0,
        "battery": 87.5,
        "destination": {"latitude": 12.3, "longitude": 8.1},
        "status": "available"
    },
    {
        "drone_id": 3,
        "position": {"latitude": 6.1, "longitude": 2.0},
        "message_time": "2025-05-15T08:59:40Z",
        "heading": 270.0,
        "battery": 65.0,
        "destination": {"latitude": 9.1, "longitude": 5.4},
        "status": "available"
    },
    {
        "drone_id": 4,
        "position": {"latitude": 18.3, "longitude": 10.0},
        "message_time": "2025-05-15T09:03:30Z",
        "heading": 135.0,
        "battery": 43.2,
        "destination": {"latitude": 6.2, "longitude": 3.0},
        "status": "available"
    },
    {
        "cluster_id": "CL-001",
        "location": { "x": 3, "y": 3 },
        "panels": [
            {
                "panel_id": "P-001",
                "status": "clean",
                "latest_status_time": "2025-05-15T09:00:00Z",
                "most_recent_repair": "2025-04-30T13:45:00Z",
                "offset": { "x": -2, "y": 2 },
                "history": [
                    { "type": "repair", "date": "2025-04-30", "action": "replaced connector" },
                    { "type": "inspection", "date": "2025-05-10", "result": "normal" }
                ]
            },
            {
                "panel_id": "P-002",
                "status": "dirty",
                "latest_status_time": "2025-05-14T15:30:00Z",
                "most_recent_repair": "2025-04-10T10:00:00Z",
                "offset": { "x": 2, "y": 2 },
                "history": [
                    { "type": "inspection", "date": "2025-05-14", "result": "dust buildup" }
                ]
            },
            {
                "panel_id": "P-003",
                "status": "unknown",
                "latest_status_time": "2025-05-13T17:20:00Z",
                "most_recent_repair": "2025-03-25T08:00:00Z",
                "offset": { "x": -2, "y": -2 },
                "history": [
                    { "type": "repair", "date": "2025-03-25", "action": "replaced inverter" },
                    { "type": "inspection", "date": "2025-05-13", "result": "power loss" }
                ]
            },
            {
                "panel_id": "P-004",
                "status": "dirty",
                "latest_status_time": "2025-05-15T07:00:00Z",
                "most_recent_repair": "2025-01-10T12:00:00Z",
                "offset": { "x": 2, "y": -2 },
                "history": [
                    { "type": "inspection", "date": "2025-05-14", "result": "normal" }
                ]
            }
        ]
    }
]

def call_llm_api(command):
    """模擬調用 LLM API"""
    try:
        response = requests.post(
            "http://127.0.0.1:1234/v1/chat/completions",
            json={
                
                "messages": [
                    {"role": "system", "content": System_Prompt},
                    {"role": "user", "content": command}
                ],
                "temperature": 0.61,
                "model": "gemma-3-12b-it-qat"
            }
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def call_tool(tool):
    """tool simulation"""
    if tool['name'] == 'db':
        return MOCK_DB
    elif tool['name'] == 'tasklist':
        return "No Drone is available currently. Approximately 10 minutes to complete the task."
    else:
        return None


@app.route('/api/command', methods=['POST'])
def handle_command():
    data = request.json
    command = data.get('command', '')
    
    # Call LLM API
    llm_raw = call_llm_api(command)
    llm_content = llm_raw['choices'][0]['message']['content']
    llm_response = extract_json_from_llm(llm_content)

    # Check if there is ['tool'] in the response
    if 'tool' in llm_content:
        # LLM response in json format
        print("LLM response in json format: ", llm_response)
        # Check if the tools is needed
        if llm_response['tool'] is not None:
            # Call the tool
            tool_response = call_tool(llm_response['tool'])
        else:
            tool_response = None
    

        # Turn the tool response into a string
        # Tool response will be a list of json objects
        final_str = ""
        for tool_response in tool_response:
            final_str += json.dumps(tool_response)
    
        # Add the tool response to the llm chat history
        
        print("Tool response: ", final_str)
        # Concate final_str with previous history
        command = command + "\n" + final_str
        # call the llm again with the tool response
        llm_raw = call_llm_api(command)
  
    # 隨機生成成功/失敗狀態
    status = "success" if random.random() > 0.3 else "error"
    
    response = {
        "status": status,
        "data": {
            "llm_response": llm_raw,
            "drone_data": MOCK_DB
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "message": f"Command processed with {status} status"
    }
    
    return jsonify(response)

if __name__ == '__main__':
    app.run(port=5000, debug=False) 