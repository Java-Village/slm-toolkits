
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
    This class is used to parse the response from the GPT model.
    For example, if the response is a JSON object, it will be parsed into a Python dictionary.
    """

    def tool_usage_parsing(self, response) -> dict:
        """
        Parse the tool usage response from the GPT model.
        Returns a dictionary with 'tool_name' and 'parameters' if a tool call is found,
        None if no tool call pattern is matched.
        """

        # Try the newer format first: to=tool_name
        match = re.search(r"to=(\w+).*<\|message\|>(.*)", response, re.DOTALL)

        # If that doesn't work, try the older format: to=functions.tool_name
        if not match:
            match = re.search(
                r"to=functions\.(\w+).*<\|message\|>(.*)", response, re.DOTALL)
        if match:
            try:
                tool_name = match.group(1).strip()
                json_string = match.group(2).strip()
                parameters = json.loads(json_string)

                return {
                    "tool_name": tool_name,
                    "parameters": parameters
                }
            except Exception as e:
                raise Exception(f"Error parsing tool usage response: {e}")

        else:  # If no tool call pattern is matched, return None
            return None
