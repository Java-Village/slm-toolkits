import json
import datetime
from typing import Protocol, Optional, List, Dict, Any
from pathlib import Path


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



class ChatHistoryProvider:
    def __init__(self, backend: IChatHistoryBackend):
        self.backend = backend

    def conversation_exists(self, conversation_id: str) -> bool:
        return self.backend.conversation_exists(conversation_id)
    
    def create_conversation(self, conversation_id: str) -> None:
        return self.backend.create_conversation(conversation_id)
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        return self.backend.get_conversation(conversation_id)
    
    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> None:
        return self.backend.add_message(conversation_id, message)
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        return self.backend.list_conversations()
 

class LocalChatHistory:
    """Simple chat history backend that stores conversations in a local JSON file."""
    # This is a simple chat history backend that stores the chat history in a local file
    def __init__(self, storage_file: str = "history/conversations.json"):
        self.storage_file = Path(storage_file)
        self.conversations: Dict[str, Dict] = {}
        self._load_conversations()

    def _load_conversations(self):
        """Load conversations from the JSON file."""
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)

            # If the file does not exist, create it
            if self.storage_file.exists() and self.storage_file.stat().st_size > 0:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.conversations = json.load(f)
                print(f"Loaded {len(self.conversations)} conversations from {self.storage_file}")
            else:
                self.conversations = {}
                self._save_to_file()
                print(f"Created empty conversation file at {self.storage_file}")
        except Exception as e:
            print(f"Error loading conversations from {self.storage_file}: {e}")
            self.conversations = {}

    def _save_to_file(self):
        """Save conversations to the JSON file."""
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.conversations, f, indent=2, ensure_ascii=False)
        except Exception as e:
                print(f"Error saving conversations to {self.storage_file}: {e}")
    def conversation_exists(self, conversation_id: str) -> bool:
        return conversation_id in self.conversations
    
    def create_conversation(self, conversation_id: str) -> None:
        """Create a new conversation."""
        if not self.conversation_exists(conversation_id):
            self.conversations[conversation_id] = {
                "start_time": datetime.datetime.utcnow().isoformat(),
                "messages": []
            }
            self._save_to_file()
            print(f"Created new conversation: {conversation_id}")
        else:
            raise ValueError(f"Conversation {conversation_id} already exists")
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        return self.conversations.get(conversation_id)
    
    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> None:
        """Add a message to a conversation."""
        if self.conversation_exists(conversation_id):
            self.conversations[conversation_id]["messages"].append(message)
            self._save_to_file()
        else:
            raise ValueError(f"Conversation {conversation_id} does not exist")
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        result = [] 
        for conv_id, conv_data in self.conversations.items():
            result.append({
                "id": conv_id,
                "start_time": conv_data["start_time"],
                "message_count": len(conv_data.get("messages", [])),
                "title" : conv_data["messages"][0]["content"] if conv_data["messages"] else "Empty Conversation"
            })
        return result



class MongoDBChatHistory:
    def __init__(self):
        pass 

    # TODO: in the future, we will implement the MongoDBChatHistory class