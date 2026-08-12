import json
# pyright: ignore [missing-import]
import numpy as np

def make_serializable(obj):
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(v) for v in obj]
    elif hasattr(obj, 'item') and callable(getattr(obj, 'item')):
        return obj.item()
    return obj

try:
    score = np.float32(0.5)
    page_num = np.int32(1)
    citations = [{"id": 1, "source": "test.pdf", "page": page_num, "score": score}]
    clean_citations = make_serializable(citations)
    print("Clean citations:", clean_citations)
    print("JSON:", json.dumps(clean_citations))
except Exception as e:
    import traceback
    traceback.print_exc()
