import uuid
import datetime
from flask import Flask, request, jsonify
from flask.wrappers import Response

from utils.LMWrapper import LMWrapper
from utils.ToolExecutor import ToolExecutor
from utils.GPTTools import PromptBuilder, GPTParsingUtils
from utils.ChatHistory import LocalChatHistory, ChatHistoryProvider

from flask_cors import CORS
import json

import os
from dotenv import load_dotenv
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)
GO_SERVER_URL = os.getenv("GO_SERVER_URL")
CORS(app)  # TODO: Configure for production and safer access for orginal endpoints from frontend

# --- Rover Task Tracking ---
rover_tasks = {}  # {task_id: {status, conversation_id, panel_id, ...}}
active_rover_task = None  # Track if there's an active rover task (only one at a time)

# --- Dashboard Status (for Demo) ---
dashboard_status = {
    "total_power_output": 4.3,  # kW (normal baseline)
    "system_efficiency": 85,  # percentage (normal baseline)
    "active_panels": "4/4",
    "daily_revenue": 31.00,  # USD (normal baseline)
    "normal_power_output": 4.3,  # kW (normal baseline)
    "normal_efficiency": 85,  # percentage (normal baseline)
    "normal_revenue": 31.00,  # USD (normal baseline)
    "dirty_panel_count": 0
}

# --- Panel Status Storage (for Demo) ---
# Panel positions based on ROS planner coordinates:
# Panel 1: (-0.5, 0.2) → top-left
# Panel 2: (0.5, 0.2) → top-right
# Panel 3: (-0.5, -1.1) → bottom-left
# Panel 4: (0.5, -1.1) → bottom-right
panel_status_store = {
    "P-001": {
        "panel_id": "P-001",
        "status": "clean",
        "cluster_id": "CL-001",
        "route_number": 1,
        "position": {"x": -0.5, "z": 0.2},
        "grid_position": "top-left",
        "offset": {"x": -2, "y": 2},
        "latest_status_time": "2025-05-15T09:00:00Z",
        "most_recent_repair": "2025-04-30T13:45:00Z",
        "history": [
            {"type": "repair", "date": "2025-04-30", "action": "replaced connector"},
            {"type": "inspection", "date": "2025-05-10", "result": "normal"}
        ]
    },
    "P-002": {
        "panel_id": "P-002",
        "status": "clean",
        "cluster_id": "CL-001",
        "route_number": 2,
        "position": {"x": 0.5, "z": 0.2},
        "grid_position": "top-right",
        "offset": {"x": 2, "y": 2},
        "latest_status_time": "2025-05-15T09:00:00Z",
        "most_recent_repair": "2025-04-10T10:00:00Z",
        "history": [
            {"type": "inspection", "date": "2025-05-15", "result": "normal"}
        ]
    },
    "P-003": {
        "panel_id": "P-003",
        "status": "clean",
        "cluster_id": "CL-001",
        "route_number": 3,
        "position": {"x": -0.5, "z": -1.1},
        "grid_position": "bottom-left",
        "offset": {"x": -2, "y": -2},
        "latest_status_time": "2025-05-15T09:00:00Z",
        "most_recent_repair": "2025-03-25T08:00:00Z",
        "history": [
            {"type": "repair", "date": "2025-03-25", "action": "replaced inverter"},
            {"type": "inspection", "date": "2025-05-15", "result": "normal"}
        ]
    },
    "P-004": {
        "panel_id": "P-004",
        "status": "clean",
        "cluster_id": "CL-001",
        "route_number": 4,
        "position": {"x": 0.5, "z": -1.1},
        "grid_position": "bottom-right",
        "offset": {"x": 2, "y": -2},
        "latest_status_time": "2025-05-15T09:00:00Z",
        "most_recent_repair": "2025-01-10T12:00:00Z",
        "history": [
            {"type": "inspection", "date": "2025-05-15", "result": "normal"}
        ]
    }
}


# --- Server Configuration & Initialization ---
# These should ideally be loaded from a configuration file or environment variables
# The address of the Go coordination-server
SYSTEM_PROMPT_TEMPLATE = """
You are a task-oriented assistant for a smart solar panel maintenance system.
Your goal is to understand user commands and use the available tools to operate drones and rovers,
or to query the status of the system.

You have access to the following tools:
{tool_definitions}

IMPORTANT OPERATIONAL RULES:

1. **Single Rover Constraint**: The system has only ONE rover available. You can only dispatch ONE rover task at a time. If a rover is already on a mission, you must wait for it to complete before dispatching to another panel. Always inform the user about this limitation when they request multiple dispatches.

2. **Automatic Dirty Panel Detection**: When you detect dirty panels (via find_panels tool), you MUST IMMEDIATELY call the dispatch_rover_to_panel tool to dispatch the rover. DO NOT just say you will dispatch - you must actually call the tool. Start with the first dirty panel, wait for confirmation that the rover has completed the task, then proceed to the next dirty panel. If you find dirty panels, call dispatch_rover_to_panel tool immediately without asking for user confirmation.

3. **Dashboard Monitoring**: Use get_dashboard_status to check system health. When dirty panels are present, the dashboard will show reduced power output and efficiency. After cleaning panels, check the dashboard again to confirm improvements.

4. **Drone Availability**: Drones are currently disabled for demo purposes. If users request drone dispatch, politely explain that drones are not available in the current demo environment.

5. **Workflow for Dirty Panels**:
   - First, check panel status using find_panels tool
   - If dirty panels are found, IMMEDIATELY call dispatch_rover_to_panel tool for the FIRST dirty panel (DO NOT just say you will dispatch - you MUST call the tool)
   - Optionally check dashboard status to see impact (using get_dashboard_status tool)
   - Inform user about the situation AFTER calling the dispatch tool
   - Wait for rover to complete (arrived → cleaning_done → returned)
   - After rover returns, check if more dirty panels exist using find_panels
   - If yes, IMMEDIATELY call dispatch_rover_to_panel tool for the next dirty panel
   - Repeat until all dirty panels are cleaned
   - Verify final status with dashboard and panel checks

CRITICAL: When you detect dirty panels, you MUST call dispatch_rover_to_panel tool immediately. Do not just describe your intention - actually execute the tool call.

When a user gives a command, you should first determine which tool(s) to use.
Then, respond with the appropriate tool call in the specified format. If no tool is needed, respond in natural language.
"""

# --- Chat History Management ---
# Using ChatHistoryProvider with LocalChatHistory backend for persistent storage
# Can be easily switched to MongoDBChatHistory in the future
chat_history_backend = LocalChatHistory(storage_file="history/conversations.json")
chat_history_provider = ChatHistoryProvider(backend=chat_history_backend)
print("--- Chat History Provider Initialized ---")


# Initialize the core components
# NOTE: The following lines assume that LMWrapper() can be initialized without arguments
# and will be refactored later to load its configuration from files.
tool_executor = ToolExecutor(go_server_base_url=GO_SERVER_URL)
prompt_builder = PromptBuilder(base_prompt_template=SYSTEM_PROMPT_TEMPLATE)
lm_wrapper = LMWrapper()
parsing_utils = GPTParsingUtils()


# Set the system prompt for the LMWrapper instance
# NOTE: This assumes we will add a `set_system_prompt` method to LMWrapper
system_prompt = prompt_builder.build_system_prompt()
lm_wrapper.set_system_prompt(system_prompt)
print("--- System Prompt Initialized ---")


# --- Helper Functions ---

def _handle_tool_call_loop(conversation_id: str, initial_llm_response: str) -> dict:
    """
    Handles the logic for executing a tool call, sending the result back to the LLM,
    and getting a final natural language response.
    Returns the final assistant message dictionary.
    """
    tool_call = parsing_utils.tool_usage_parsing(initial_llm_response)

    if not tool_call:
        # Not a tool call, just return the original response
        cleaned_response = _clean_llm_response(initial_llm_response)
        return {"role": "assistant", "content": cleaned_response}
        

    # --- It is a tool call, so execute the full loop ---
    
    # 1. Execute the tool
    tool_name = tool_call['tool_name']
    parameters = tool_call['parameters']
    print(f"Executing tool: {tool_name} with params: {parameters}")
    tool_result = tool_executor.execute_tool(tool_name, parameters)

    # 2. Append the tool interaction to history
    # First, the assistant's decision to call the tool
    cleaned_initial = _clean_llm_response(initial_llm_response)
    chat_history_provider.add_message(conversation_id, {
        "role": "assistant",
        "content": cleaned_initial
    })
    chat_history_provider.add_message(conversation_id, {
        "role": "tool", # TODO: Check if this is correct
        "name": tool_name,
        "content": json.dumps(tool_result, ensure_ascii=False)
    })

    # 3. Call LLM again to get a natural language summary
    print("Tool executed. Getting summary from LLM...")
    conversation = chat_history_provider.get_conversation(conversation_id)
    final_llm_response_text = lm_wrapper.get_completion(
        messages=conversation["messages"]
    )

    # 4. Return the final, summarized response
    cleaned_final = _clean_llm_response(final_llm_response_text)
    return {"role": "assistant", "content": cleaned_final}



def _clean_llm_response(response: str) -> str:
    """
    Clean LLM response by removing special tags like <|channel|>, <|message|>, etc.
    This is needed for models that output internal reasoning tags.
    
    Extracts only the final message content between the last <|message|> and text end,
    or returns the original if no special tags are found.
    """
    import re
    
    # Pattern to match the final message after <|channel|>final<|message|>
    final_pattern = r'<\|channel\|>final<\|message\|>(.*?)(?:<\|end\|>|$)'
    match = re.search(final_pattern, response, re.DOTALL)
    
    if match:
        # Extract the final message
        cleaned = match.group(1).strip()
        return cleaned
    
    # If no special tags found, check for any <|message|> tags
    if '<|message|>' in response:
        # Extract content after the last <|message|>
        parts = response.split('<|message|>')
        if len(parts) > 1:
            # Get the last part and remove any trailing tags
            cleaned = parts[-1].split('<|end|>')[0].strip()
            return cleaned
    
    # No special tags, return original
    return response


def _generate_tool_call_id(tool_name: str, conversation_id: str) -> str:
    """
    Generate a tool_call_id that meets OpenAI's requirement (max 40 characters).
    
    Format: call_{short_tool_name}_{short_conv_id}_{timestamp}
    """
    import time
    
    # Use last 6 digits of timestamp for uniqueness
    timestamp = str(int(time.time() * 1000))[-6:]
    
    # Calculate available space: "call_" (5) + "_" (1) + "_" (1) + timestamp (6) = 13
    # Remaining: 40 - 13 = 27 chars for tool_name and conversation_id
    available_space = 27
    
    # Shorten conversation ID to max 6 chars
    short_conv_id = conversation_id[:6] if len(conversation_id) > 6 else conversation_id
    conv_id_len = len(short_conv_id)
    
    # Calculate max tool name length
    max_tool_len = available_space - conv_id_len - 1  # -1 for underscore between tool and conv
    max_tool_len = max(1, max_tool_len)  # At least 1 char
    
    # Shorten tool name
    short_tool_name = tool_name[:max_tool_len] if len(tool_name) > max_tool_len else tool_name
    
    # Build ID: call_{tool}_{conv}_{time}
    tool_call_id = f"call_{short_tool_name}_{short_conv_id}_{timestamp}"
    
    # Final safety check - truncate if still too long
    if len(tool_call_id) > 40:
        tool_call_id = tool_call_id[:40]
    
    return tool_call_id


def _track_tool_result(tool_name: str, tool_result: dict, conversation_id: str):
    """
    Track tool execution results that require state management.
    This centralizes post-execution tracking logic for better maintainability.
    
    Args:
        tool_name: Name of the executed tool
        tool_result: Result returned by the tool
        conversation_id: Current conversation ID
    """
    global active_rover_task
    
    # Rover task tracking
    if tool_name == "dispatch_rover_to_panel" and "task_id" in tool_result:
        task_id = tool_result["task_id"]
        rover_tasks[task_id] = {
            "status": "dispatched",
            "conversation_id": conversation_id,
            "panel_id": tool_result.get("panel_id"),
            "cluster_id": tool_result.get("cluster_id"),
            "route_number": tool_result.get("route_number"),
            "created_at": datetime.datetime.now(),
            "last_update": datetime.datetime.now()
        }
        active_rover_task = task_id  # Mark as active task
        _update_dashboard_for_panels()  # Update dashboard
        print(f"[Task] Created rover task: {task_id} (active)")
    
    # Future: Add other tool tracking here
    # elif tool_name == "dispatch_drone_to_cluster" and "task_id" in tool_result:
    #     drone_tasks[tool_result["task_id"]] = {...}


def _update_dashboard_for_panels():
    """
    Update dashboard status based on current panel states.
    Dirty panels reduce power output and efficiency.
    Each dirty panel reduces output by ~15%.
    """
    global dashboard_status, active_rover_task
    
    # Count dirty panels
    dirty_count = sum(1 for panel in panel_status_store.values() if panel["status"] == "dirty")
    total_panels = len(panel_status_store)
    
    # Check if there's an active rover task
    has_active_task = active_rover_task is not None
    
    # Calculate reduction factor (each dirty panel reduces by ~15%)
    reduction_factor = 1.0 - (dirty_count * 0.15)
    reduction_factor = max(0.3, reduction_factor)  # Minimum 30% output
    
    # Update dashboard values
    dashboard_status["total_power_output"] = round(
        dashboard_status["normal_power_output"] * reduction_factor, 1
    )
    dashboard_status["system_efficiency"] = int(
        dashboard_status["normal_efficiency"] * reduction_factor
    )
    dashboard_status["daily_revenue"] = round(
        dashboard_status["normal_revenue"] * reduction_factor, 2
    )
    dashboard_status["active_panels"] = f"{total_panels - dirty_count}/{total_panels}"
    dashboard_status["dirty_panel_count"] = dirty_count
    dashboard_status["has_active_rover_task"] = has_active_task
    
    print(f"[Dashboard] Updated: {dirty_count} dirty panels, power: {dashboard_status['total_power_output']}kW, active_task: {has_active_task}")


# --- API Endpoints ---

@app.route("/api/chat", methods=['POST'])
def chat_endpoint():
    """
    Handles chat requests, manages conversation history, and orchestrates LLM tool usage.
    """
    data = request.get_json()
    if not data or "messages" not in data:
        return jsonify({"error": "Invalid request body, 'messages' field is required."}), 400

    user_messages = data["messages"]
    conversation_id = data.get("conversation_id")

    # --- Conversation Management ---
    if not conversation_id or not chat_history_provider.conversation_exists(conversation_id):
        conversation_id = str(uuid.uuid4())
        chat_history_provider.create_conversation(conversation_id)

    # Add new user messages to the history
    for msg in user_messages:
        chat_history_provider.add_message(conversation_id, msg)

    # Get the full history
    conversation = chat_history_provider.get_conversation(conversation_id)
    full_history = conversation["messages"]

    # --- LLM and Tool Execution ---
    # NOTE: Assumes LMWrapper's get_completion is updated to handle message lists
    llm_response_text = lm_wrapper.get_completion(messages=full_history)
    assistant_response = _handle_tool_call_loop(conversation_id, llm_response_text)

    # Append the final assistant's response to history
    chat_history_provider.add_message(conversation_id, assistant_response)
    
    return jsonify({
        "conversation_id": conversation_id,
        "response": assistant_response
    })

@app.route("/api/conversations", methods=['GET'])
def get_conversations_list():
    """
    Returns a list of all conversations with basic metadata.
    """
    conv_list = chat_history_provider.list_conversations()
    return jsonify(conv_list)


@app.route("/api/conversations/<string:conversation_id>", methods=['GET'])
def get_conversation_history(conversation_id):
    """
    Returns the full message history for a specific conversation.
    """
    history = chat_history_provider.get_conversation(conversation_id)
    if not history:
        return jsonify({"error": "Conversation not found."}), 404

    return jsonify(history)


@app.route("/api/conversations/<string:conversation_id>/recent", methods=['GET'])
def get_recent_messages(conversation_id):
    """
    Get recent messages for polling (used by frontend to check for rover status updates)
    Query param 'since': ISO timestamp to get messages after this time
    """
    since_param = request.args.get('since')
    
    conversation = chat_history_provider.get_conversation(conversation_id)
    if not conversation:
        return jsonify({"error": "Conversation not found."}), 404
    
    messages = conversation["messages"]
    
    # Filter messages if 'since' timestamp provided
    if since_param:
        try:
            since_time = datetime.datetime.fromisoformat(since_param.replace('Z', '+00:00'))
            # Filter messages with timestamp > since_time
            # Note: This assumes messages have 'timestamp' in metadata
            filtered_messages = []
            for msg in messages:
                if isinstance(msg, dict) and 'metadata' in msg:
                    msg_time_str = msg['metadata'].get('timestamp')
                    if msg_time_str:
                        msg_time = datetime.datetime.fromisoformat(msg_time_str.replace('Z', '+00:00'))
                        if msg_time > since_time:
                            filtered_messages.append(msg)
            messages = filtered_messages
        except Exception as e:
            print(f"[WARN] Failed to parse 'since' parameter: {e}")
    
    return jsonify({
        "conversation_id": conversation_id,
        "messages": messages,
        "timestamp": datetime.datetime.now().isoformat()
    })


@app.route("/api/panels/status", methods=['GET'])
def get_panel_status():
    """
    Get status of all panels or specific panel
    Query params: panel_id (optional)
    """
    panel_id = request.args.get('panel_id')
    
    if panel_id:
        if panel_id in panel_status_store:
            return jsonify(panel_status_store[panel_id]), 200
        else:
            return jsonify({"error": f"Panel {panel_id} not found"}), 404
    
    # Return all panels
    return jsonify({
        "panels": list(panel_status_store.values()),
        "cluster_id": "CL-001"
    }), 200


@app.route("/api/panels/status", methods=['POST', 'PUT'])
def update_panel_status():
    """
    Update panel status for demo purposes
    
    Expected format:
    {
        "panel_id": "P-001",
        "status": "clean" | "dirty" | "unknown"
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    panel_id = data.get("panel_id")
    new_status = data.get("status")
    
    if not panel_id or not new_status:
        return jsonify({"error": "Missing panel_id or status"}), 400
    
    if panel_id not in panel_status_store:
        return jsonify({"error": f"Panel {panel_id} not found"}), 404
    
    if new_status not in ["clean", "dirty", "unknown"]:
        return jsonify({"error": "Status must be 'clean', 'dirty', or 'unknown'"}), 400
    
    # Update status
    old_status = panel_status_store[panel_id]["status"]
    panel_status_store[panel_id]["status"] = new_status
    panel_status_store[panel_id]["latest_status_time"] = datetime.datetime.now().isoformat() + "Z"
    
    # Add to history
    panel_status_store[panel_id]["history"].insert(0, {
        "type": "manual_update",
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "result": f"status changed from {old_status} to {new_status}"
    })
    
    # Update dashboard based on panel states
    _update_dashboard_for_panels()
    
    print(f"[PANEL UPDATE] {panel_id}: {old_status} → {new_status}")
    
    return jsonify({
        "success": True,
        "panel_id": panel_id,
        "old_status": old_status,
        "new_status": new_status,
        "panel": panel_status_store[panel_id],
        "dashboard": dashboard_status
    }), 200


@app.route("/api/dashboard/status", methods=['GET'])
def get_dashboard_status():
    """
    Get current dashboard status (power output, efficiency, etc.)
    """
    _update_dashboard_for_panels()  # Ensure up-to-date
    return jsonify(dashboard_status), 200


@app.route("/api/tasks/active", methods=['GET'])
def get_active_tasks():
    """
    Get currently active tasks (rover, drone, etc.)
    """
    active_tasks = []
    
    # Get active rover task
    if active_rover_task and active_rover_task in rover_tasks:
        task = rover_tasks[active_rover_task].copy()
        task["task_id"] = active_rover_task
        task["type"] = "rover"
        task["created_at"] = task.get("created_at", datetime.datetime.now()).isoformat() if isinstance(task.get("created_at"), datetime.datetime) else task.get("created_at")
        task["last_update"] = task.get("last_update", datetime.datetime.now()).isoformat() if isinstance(task.get("last_update"), datetime.datetime) else task.get("last_update")
        active_tasks.append(task)
    
    return jsonify({
        "active_tasks": active_tasks,
        "total_count": len(active_tasks)
    }), 200


@app.route("/api/webhook/rover", methods=['POST'])
def rover_webhook():
    """
    Receive status updates (ACC) from Rover
    
    Expected format:
    {
        "task_id": "uuid",
        "status": "arrived" | "cleaning_done" | "returned",
        "timestamp": "ISO-8601",
        "panel_id": "P-001",
        "position": {"x": 0.5, "z": 0.2}
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    task_id = data.get("task_id")
    status = data.get("status")
    
    if not task_id:
        return jsonify({"error": "Missing task_id"}), 400
    
    if task_id not in rover_tasks:
        return jsonify({"error": "Unknown task_id"}), 404
    
    global active_rover_task
    
    # Update task status
    rover_tasks[task_id]["status"] = status
    rover_tasks[task_id]["last_update"] = datetime.datetime.now()
    rover_tasks[task_id]["rover_data"] = data
    
    # If task completed (returned), clear active task and update panel status
    if status == "returned":
        if active_rover_task == task_id:
            active_rover_task = None
            print(f"[Task] Rover task {task_id} completed, cleared active task")
            
            # Update panel status to clean after rover returns
            panel_id = data.get("panel_id", rover_tasks[task_id].get("panel_id"))
            if panel_id and panel_id in panel_status_store:
                old_status = panel_status_store[panel_id]["status"]
                panel_status_store[panel_id]["status"] = "clean"
                panel_status_store[panel_id]["latest_status_time"] = datetime.datetime.now().isoformat() + "Z"
                panel_status_store[panel_id]["history"].insert(0, {
                    "type": "rover_cleaning",
                    "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "result": f"cleaned by rover, status changed from {old_status} to clean"
                })
                print(f"[PANEL UPDATE] {panel_id}: {old_status} → clean (via rover)")
                _update_dashboard_for_panels()
    
    _update_dashboard_for_panels()
    
    # Get associated conversation
    conversation_id = rover_tasks[task_id].get("conversation_id")
    panel_id = data.get("panel_id", rover_tasks[task_id].get("panel_id", "unknown"))
    
    # Create status message for conversation history
    status_messages = {
        "arrived": f"🤖 Rover arrived at panel {panel_id}",
        "cleaning_done": f"✨ Cleaning completed on panel {panel_id}",
        "returned": f"🏠 Rover returned to base station"
    }
    
    message = status_messages.get(status, f"Rover status update: {status}")
    
    # Add to conversation history with metadata
    if conversation_id:
        chat_history_provider.add_message(conversation_id, {
            "role": "system",
            "content": message,
            "metadata": {
                "type": "rover_status",
                "task_id": task_id,
                "status": status,
                "panel_id": panel_id,
                "timestamp": datetime.datetime.now().isoformat()
            }
        })
        print(f"✅ [Webhook] Rover status stored in conversation {conversation_id}: {status}")
    else:
        print(f"⚠️ [Webhook] No conversation_id for task {task_id}")
    
    return jsonify({
        "status": "acknowledged",
        "task_id": task_id,
        "message": "Status update received"
    })
    

@app.route("/api/chat/stream", methods=['POST'])
def chat_stream_endpoint():
    """
    SSE streaming endpoint for real-time chat responses
    """
    # Get request data BEFORE entering generator (to avoid request context issues)
    request_data = request.get_json()
    if not request_data or "messages" not in request_data:
        return jsonify({"error": "Invalid request body, 'messages' field is required."}), 400
    
    def generate():
        try:
            user_messages = request_data["messages"]
            conversation_id = request_data.get("conversation_id")
            
            # Setup conversation
            if not conversation_id or not chat_history_provider.conversation_exists(conversation_id):
                conversation_id = str(uuid.uuid4())
                chat_history_provider.create_conversation(conversation_id)
            
            # Send conversation_id first
            yield f"data: {json.dumps({'type': 'conversation_id', 'id': conversation_id})}\n\n"
            
            # Add new user messages to history
            for msg in user_messages:
                chat_history_provider.add_message(conversation_id, msg)
            
            # Get full conversation history
            conversation = chat_history_provider.get_conversation(conversation_id)
            full_history = conversation["messages"]
            
            # Stream LLM response (now returns structured events)
            accumulated_response = ""
            tool_call_detected = None
            
            for event in lm_wrapper.get_completion_stream(messages=full_history):
                event_type = event.get("type")
                
                if event_type == "token":
                    # Text token from LLM
                    token = event["content"]
                    accumulated_response += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                
                elif event_type == "tool_call":
                    # Tool call detected (from OpenAI function calling)
                    tool_call_detected = event
                    tool_name = event["tool_name"]
                    parameters = event["parameters"]
                    
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': tool_name, 'parameters': parameters})}\n\n"
                
                elif event_type == "error":
                    # Error occurred during streaming
                    yield f"data: {json.dumps({'type': 'error', 'message': event['content']})}\n\n"
                    return
            
            # Check if response contains tool call (fallback for local LLM text format)
            tool_call = tool_call_detected
            if not tool_call and accumulated_response:
                tool_call = parsing_utils.tool_usage_parsing(accumulated_response)
            
            if tool_call:
                # Extract tool call info
                tool_name = tool_call['tool_name']
                parameters = tool_call['parameters']
                
                # Only send tool_call signal if not already sent (for local LLM fallback)
                if not tool_call_detected:
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': tool_name, 'parameters': parameters})}\n\n"
                
                # Execute tool
                print(f"[STREAM] Executing tool: {tool_name} with params: {parameters}")
                tool_result = tool_executor.execute_tool(tool_name, parameters)
                
                # Track tool results that need state management
                _track_tool_result(tool_name, tool_result, conversation_id)
                
                yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': tool_name, 'result': tool_result})}\n\n"
                
                # Save tool interaction to history
                # Different format for OpenAI function calling vs local LLM
                if tool_call_detected:
                    # OpenAI function calling: save tool_calls in assistant message
                    tool_call_id = _generate_tool_call_id(tool_name, conversation_id)
                    chat_history_provider.add_message(conversation_id, {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(parameters)
                            }
                        }]
                    })
                    chat_history_provider.add_message(conversation_id, {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                else:
                    # Local LLM: save text format
                    cleaned_response = _clean_llm_response(accumulated_response)
                    chat_history_provider.add_message(conversation_id, {
                        "role": "assistant",
                        "content": cleaned_response
                    })
                    chat_history_provider.add_message(conversation_id, {
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                
                # Get final summary from LLM
                conversation = chat_history_provider.get_conversation(conversation_id)
                accumulated_summary = ""
                summary_tool_call = None
                
                for event in lm_wrapper.get_completion_stream(messages=conversation["messages"]):
                    event_type = event.get("type")
                    
                    if event_type == "token":
                        token = event["content"]
                        accumulated_summary += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    
                    elif event_type == "tool_call":
                        # Allow tool_call in summary phase (for automatic dispatch after finding dirty panels)
                        summary_tool_call = event
                        tool_name = event["tool_name"]
                        parameters = event["parameters"]
                        yield f"data: {json.dumps({'type': 'tool_call', 'tool_name': tool_name, 'parameters': parameters})}\n\n"
                    
                    elif event_type == "error":
                        yield f"data: {json.dumps({'type': 'error', 'message': event['content']})}\n\n"
                        return
                
                # Save summary response
                cleaned_summary = _clean_llm_response(accumulated_summary)
                chat_history_provider.add_message(conversation_id, {
                    "role": "assistant",
                    "content": cleaned_summary
                })
                
                # If LLM called a tool in summary phase (e.g., dispatch_rover_to_panel after finding dirty panels)
                if summary_tool_call:
                    tool_name = summary_tool_call["tool_name"]
                    parameters = summary_tool_call["parameters"]
                    
                    # Execute the tool
                    print(f"[STREAM] Executing tool in summary phase: {tool_name} with params: {parameters}")
                    tool_result = tool_executor.execute_tool(tool_name, parameters)
                    
                    # Track tool results
                    _track_tool_result(tool_name, tool_result, conversation_id)
                    
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_name': tool_name, 'result': tool_result})}\n\n"
                    
                    # Save tool interaction
                    tool_call_id = _generate_tool_call_id(tool_name, conversation_id)
                    chat_history_provider.add_message(conversation_id, {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(parameters)
                            }
                        }]
                    })
                    chat_history_provider.add_message(conversation_id, {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                    
                    # Get final response after tool execution
                    conversation = chat_history_provider.get_conversation(conversation_id)
                    final_summary = ""
                    for event in lm_wrapper.get_completion_stream(messages=conversation["messages"]):
                        if event.get("type") == "token":
                            token = event["content"]
                            final_summary += token
                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                        elif event.get("type") == "error":
                            yield f"data: {json.dumps({'type': 'error', 'message': event['content']})}\n\n"
                            return
                    
                    # Save final response
                    cleaned_final = _clean_llm_response(final_summary)
                    chat_history_provider.add_message(conversation_id, {
                        "role": "assistant",
                        "content": cleaned_final
                    })
            else:
                # No tool call, just save the response
                cleaned_response = _clean_llm_response(accumulated_response)
                chat_history_provider.add_message(conversation_id, {
                    "role": "assistant",
                    "content": cleaned_response
                })
            
            # Signal completion
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            print(f"[ERROR] Stream endpoint error: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


if __name__ == '__main__':
    # For local development
    app.run(host='0.0.0.0', port=8000, debug=False) # DO NOT SET TRUE
