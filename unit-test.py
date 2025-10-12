from utils.LMWrapper import LMWrapper
from utils.GPTTools import GPTParsingUtils, PromptBuilder
from dotenv import load_dotenv

from utils.ChatHistory import LocalChatHistory
from utils.ChatHistory import ChatHistoryProvider

import os

# --- Setup ---
load_dotenv()

def test_lm_wrapper_and_tool_parsing():
    """
    This test simulates the core logic of CoordinateServer:
    1. Initializes LMWrapper and other utils.
    2. Builds a system prompt with tool definitions.
    3. Simulates a user message that should trigger a tool call.
    4. Fetches the LLM response.
    5. Parses the response to check for a valid tool call.
    """
    print("--- Running Test: LMWrapper and Tool Parsing ---")

    # 1. Initialize Components
    try:
        # LMWrapper will load config from `config/configure.json` upon initialization
        lm_wrapper = LMWrapper()
        
        # Define the system prompt template (same as in CoordinateServer)
        system_prompt_template = """
You are a task-oriented assistant for a smart solar panel maintenance system.
Your goal is to understand user commands and use the available tools to operate drones and rovers,
or to query the status of the system.

You have access to the following tools:
{tool_definitions}

When a user gives a command, you should first determine which tool(s) to use.
Then, respond with the appropriate tool call in the specified format.
"""
        prompt_builder = PromptBuilder(base_prompt_template=system_prompt_template)
        parsing_utils = GPTParsingUtils()

    except Exception as e:
        print(f"\n[FAIL] Initialization failed: {e}")
        return

    # 2. Build and Set the System Prompt
    system_prompt = prompt_builder.build_system_prompt()
    lm_wrapper.set_system_prompt(system_prompt)
    print("\nSystem prompt has been built and set.")
    # For debugging, you can uncomment the next line to see the full prompt
    # print("--- PROMPT --- \n", system_prompt, "\n--- END PROMPT ---")

    # 3. Simulate User Input and Conversation History
    # We'll test the `find_panels` tool.
    user_message_content = "find all panels in cluster 3 that are dirty"
    
    # We simulate a simple conversation history with one user message
    messages = [
        {"role": "user", "content": user_message_content}
    ]
    print(f"\nSimulating user message: '{user_message_content}'")
    
    # 4. Get Response from LLM
    print("\nGetting completion from LLM... (This may take a moment)")
    try:
        llm_response = lm_wrapper.get_completion(messages)
        print(f"\nRaw LLM Response:\n---\n{llm_response}\n---")
    except Exception as e:
        print(f"\n[FAIL] LLM call failed: {e}")
        return

    # 5. Parse for Tool Call
    if not llm_response or llm_response.startswith("Error:"):
         print(f"\n[FAIL] Received an error from LMWrapper: {llm_response}")
         return

    tool_call = parsing_utils.tool_usage_parsing(llm_response)

    # 6. Print Results and Assert
    if tool_call:
        print("\n[SUCCESS] Successfully parsed a tool call.")
        print(f"  - Tool Name: {tool_call.get('tool_name')}")
        print(f"  - Parameters: {tool_call.get('parameters')}")
        
        # Basic assertion to check if the parsing was correct
        assert tool_call.get('tool_name') == 'find_panels'
        assert tool_call.get('parameters').get('cluster_id') == 3
        assert tool_call.get('parameters').get('status') == 'dirty'
        print("\nAssertions passed!")

    else:
        print("\n[FAIL] Did not find a valid tool call in the LLM response.")
        print("Please check:")
        print("  - If your local LLM server is running and configured correctly.")
        print("  - If the model you are using supports tool calling/function calling.")
        print("  - The raw LLM response above for clues.")


def test_chat_history():
    """
    Test ChatHistory functionality including:
    1. Creating conversations
    2. Adding messages
    3. Retrieving conversations
    4. Listing all conversations
    5. Data persistence (reload test)
    """
    print("--- Running Test: ChatHistory ---")
    
    import uuid
    from pathlib import Path
    from utils.ChatHistory import ChatHistoryProvider, LocalChatHistory
    
    # Use a test file to avoid affecting real data
    test_file = "history/test_conversations.json"
    
    try:
        # Clean up test file if exists
        test_path = Path(test_file)
        if test_path.exists():
            test_path.unlink()
        
        # 1. Initialize
        print("\n1. Testing initialization...")
        backend = LocalChatHistory(storage_file=test_file)
        provider = ChatHistoryProvider(backend=backend)
        print("   ✓ ChatHistoryProvider initialized")
        
        # 2. Create conversation
        print("\n2. Testing create conversation...")
        conv_id = str(uuid.uuid4())
        provider.create_conversation(conv_id)
        assert provider.conversation_exists(conv_id)
        print(f"   ✓ Conversation created: {conv_id[:8]}...")
        
        # 3. Add messages
        print("\n3. Testing add messages...")
        provider.add_message(conv_id, {"role": "user", "content": "Hello"})
        provider.add_message(conv_id, {"role": "assistant", "content": "Hi there!"})
        print("   ✓ Messages added")
        
        # 4. Get conversation
        print("\n4. Testing get conversation...")
        conv = provider.get_conversation(conv_id)
        assert conv is not None
        assert len(conv["messages"]) == 2
        print(f"   ✓ Retrieved conversation with {len(conv['messages'])} messages")
        
        # 5. List conversations
        print("\n5. Testing list conversations...")
        conv_list = provider.list_conversations()
        assert len(conv_list) == 1
        assert conv_list[0]["id"] == conv_id
        print(f"   ✓ Listed {len(conv_list)} conversation(s)")
        
        # 6. Persistence test
        print("\n6. Testing data persistence...")
        # Reload from file
        backend2 = LocalChatHistory(storage_file=test_file)
        provider2 = ChatHistoryProvider(backend=backend2)
        
        # Verify data persisted
        assert provider2.conversation_exists(conv_id)
        conv_reloaded = provider2.get_conversation(conv_id)
        assert len(conv_reloaded["messages"]) == 2
        assert conv_reloaded["messages"][0]["content"] == "Hello"
        print("   ✓ Data successfully persisted and reloaded")
        
        # 7. Error handling test
        print("\n7. Testing error handling...")
        try:
            provider.create_conversation(conv_id)  # Duplicate
            print("   ✗ Should have raised ValueError")
        except ValueError:
            print("   ✓ Correctly raised ValueError for duplicate conversation")
        
        print("\n[SUCCESS] All ChatHistory tests passed! ✅")
        
        # Clean up
        if test_path.exists():
            test_path.unlink()
        print("   ✓ Test file cleaned up")
        
    except Exception as e:
        print(f"\n[FAIL] ChatHistory test failed: {e}")
        import traceback
        traceback.print_exc()
if __name__ == "__main__":
    test_chat_history()
    test_lm_wrapper_and_tool_parsing()