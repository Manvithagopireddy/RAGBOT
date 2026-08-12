import sys
from pathlib import Path

# Add project root to path
sys.path.append("c:\\RAGBOT")

from storage import ChatStore
# pyright: ignore [missing-import]
import numpy as np

store = ChatStore(Path("c:\\RAGBOT\\chat_store.db"))
session_id = store.create_session("Test")
print("Session created:", session_id)

try:
    msg_id = store.add_message(
        session_id=session_id,
        role="assistant",
        content="Testing",
        citations=[{"id": 1, "score": np.float32(0.5)}],
        confidence_score=np.float32(0.8),
        confidence_desc="High"
    )
    print("Message added successfully:", msg_id)
except Exception as e:
    import traceback
    traceback.print_exc()
