from typing import List, Dict, Any
from src.logger import get_logger

logger = get_logger(__name__)

class ChatMemory:
    """Manages chat message history for conversation flows and prompt formatting."""
    
    def __init__(self):
        self.messages: List[Dict[str, str]] = []
        
    def add_user_message(self, content: str):
        """Adds a user message to the memory."""
        self.messages.append({"role": "user", "content": content})
        
    def add_assistant_message(self, content: str):
        """Adds an assistant response to the memory."""
        self.messages.append({"role": "assistant", "content": content})
        
    def clear(self):
        """Clears the chat history."""
        self.messages = []
        logger.info("Chat memory cleared.")
        
    def get_messages(self) -> List[Dict[str, str]]:
        """Returns the raw list of message dicts."""
        return self.messages
        
    def format_chat_history(self, limit: int = 5) -> str:
        """Formats the last N interactions of chat history as a text block for prompt injection."""
        formatted_history = []
        # Get last N messages (each interaction is 2 messages: user + assistant)
        history_slice = self.messages[-(limit * 2):] if limit > 0 else self.messages
        
        for msg in history_slice:
            role = "User" if msg["role"] == "user" else "Assistant"
            formatted_history.append(f"{role}: {msg['content']}")
            
        return "\n".join(formatted_history)
