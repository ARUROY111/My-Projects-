# Encapsulates core conversational flow if running strictly via MCP SDK protocol 
# rather than REST, acting as a bridge between the standard FastMCP server and the backend.

import uuid
from pydantic import BaseModel

class MCPChatSession(BaseModel):
    session_id: str
    history: list = []
    
    def generate_id(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
            
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        
session_cache = {}

def get_session(session_id: str) -> MCPChatSession:
    if session_id not in session_cache:
        session_cache[session_id] = MCPChatSession(session_id=session_id)
    return session_cache[session_id]
