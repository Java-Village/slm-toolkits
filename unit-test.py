from utils.LMWrapper import LMWrapper, OpenAIWrapper, GeminiWrapper
from utils.GPTTools import GPTParsingUtils, PromptBuilder
from dotenv import load_dotenv
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict
import os

load_dotenv()


BASE_SYSTEM_MESSAGE_TEMPLATE = """
You are a helpful assistant in a solar panel maintenance system.
Your goal is to assist the user by calling available tools to answer their questions or perform tasks.

You have access to the following tools:

{tool_definitions}

When a user asks for something, first determine if you can use a tool.
If you decide to use a tool, you must respond with a single JSON object that strictly follows this format:
{{"tool_name": "name_of_the_tool", "parameters": {{"param_name": "param_value"}}}}

Do not provide any other text or explanation before or after the JSON object.
If you cannot use a tool to answer the user, respond normally as a helpful assistant.
"""


lm_wrapper = LMWrapper(OpenAIWrapper(api_key=os.getenv("LM_API_KEY"),
                                     base_url=os.getenv("LM_API_URL"), model=os.getenv("LM_MODEL_NAME")))

prompt_builder = PromptBuilder(BASE_SYSTEM_MESSAGE_TEMPLATE)
system_message = prompt_builder.build_system_prompt()


ask = input("Enter your question: ")
# test the lm wrapper
messages = [
    {"role": "system", "content": system_message},
    {"role": "user", "content": f"user:{ask}"}
]
response = lm_wrapper.chat(messages)
gpt_parsing_utils = GPTParsingUtils()
tool_usage = gpt_parsing_utils.tool_usage_parsing(
    response.choices[0].message.content)
print(tool_usage)
