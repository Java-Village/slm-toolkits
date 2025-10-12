import uuid
import datetime
from flask import Flask, request, jsonify
from flask.wrappers import Response

from utils.LMWrapper import LMWrapper
from utils.ToolExecutor import ToolExecutor
from utils.GPTTools import PromptBuilder, GPTParsingUtils
from utils.ChatHistory import LocalChatHistory, ChatHistoryProvider


import json

import os
from dotenv import load_dotenv
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)
GO_SERVER_URL = os.getenv("GO_SERVER_URL")

# --- Server Configuration & Initialization ---
# These should ideally be loaded from a configuration file or environment variables
# The address of the Go coordination-server
SYSTEM_PROMPT_TEMPLATE = """
You are a task-oriented assistant for a smart solar panel maintenance system.
Your goal is to understand user commands and use the available tools to operate drones and rovers,
or to query the status of the system.

You have access to the following tools:
{tool_definitions}

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
        "content": initial_llm_response
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
    return {"role": "assistant", "content": final_llm_response_text}



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


if __name__ == '__main__':
    # For local development
    app.run(host='0.0.0.0', port=8000, debug=True)
