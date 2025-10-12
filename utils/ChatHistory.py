import json
import datetime
from typing import Protocol, Optional, List, Dict, Any


# --- Protocol Definition ---

class IChatHistoryBackend(Protocol):
    """
    Defines the interface that all chat history storage backends must implement.
    """
    def conversation_exists(self, conversation_id: str) -> bool:
        pass
        
    def create_conversation(self, conversation_id: str) -> None:
        pass

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        pass

    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> None:
        pass

    def list_conversations(self) -> List[Dict[str, Any]]:
        pass



class ChatHistoryProvider(Protocol):
    def __init__(self):
        self.backend: Optional[ChatHistoryBackend] = None
       

class LocalChatHistory:
    def __init__(self):
        pass

class MongoDBChatHistory:
    def __init__(self):
        pass 

    # TODO: in the future, we will implement the MongoDBChatHistory class