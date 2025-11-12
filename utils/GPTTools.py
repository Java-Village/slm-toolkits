
import re
import json
from pathlib import Path
from typing import List, Dict, Any


class PromptBuilder:
    """
    This class is used to build the system prompt for the GPT model.
    It will load the tools in the json file.
    """

    def __init__(self, base_prompt_template: str):
        self.base_prompt_template = base_prompt_template
        self.tools_config_path = Path(
            __file__).parent.parent / "config" / "tools.json"

    def _load_tools(self) -> List[Dict[str, Any]]:
        """
        Loads tool definitions from the config/tools.json file.
        """
        if not self.tools_config_path.exists():
            print(
                f"Warning: tools.json not found at {self.tools_config_path}. Returning empty tools list.")
            return []

        with open(self.tools_config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def build_system_prompt(self) -> str:
        """
        Builds the complete system prompt by injecting tool definitions.
        """
        tools = self._load_tools()

        # Format the tools into a pretty-printed JSON string for the prompt
        tool_definitions_json_str = json.dumps(tools, indent=2)

        # Inject the formatted tool definitions into the base prompt template
        return self.base_prompt_template.format(tool_definitions=tool_definitions_json_str)


class GPTParsingUtils:
    """
    Utility class for parsing LLM responses, particularly for tool calling.
    Supports multiple formats: OpenAI function calling and text-based tool calls.
    """

    def tool_usage_parsing(self, response, response_object=None) -> dict:
        """
        Parse tool usage from LLM response. Supports dual formats:
        
        Format 1: OpenAI function calling (from response_object)
            response_object.tool_calls = [{"function": {"name": "...", "arguments": "..."}}]
        
        Format 2: Text-based tool calling (from response string)
            "to=find_panels<|message|>{\"status\": \"dirty\"}"
            "to=functions.find_panels<|message|>{\"status\": \"dirty\"}"
        
        Args:
            response: Text response from LLM
            response_object: Optional response object with tool_calls attribute
        
        Returns:
            Dict with 'tool_name' and 'parameters' if tool call found, None otherwise
        """
        
        # Format 1: OpenAI function calling (preferred for OpenAI API)
        if response_object and hasattr(response_object, 'tool_calls') and response_object.tool_calls:
            tool_call = response_object.tool_calls[0]
            return {
                "tool_name": tool_call.function.name,
                "parameters": json.loads(tool_call.function.arguments)
            }
        
        # Format 2: Text-based tool calling (for local LLMs)
        # Regex pattern matches both:
        # - to=functions.tool_name<|message|>{...}
        # - to=tool_name<|message|>{...}
        # The (?:functions\.)? is a non-capturing optional group
        match = re.search(r"to=(?:functions\.)?(\w+).*<\|message\|>(.*)", response, re.DOTALL)
        if match:
            tool_name = match.group(1).strip()
            json_string = match.group(2).strip()
            parameters = json.loads(json_string)
            return {
                "tool_name": tool_name,
                "parameters": parameters
            }
        
        # No tool call detected
        return None