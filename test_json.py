import json
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        return super().default(obj)

data = [{'score': np.float32(0.5)}]
try:
    print(json.dumps(data, cls=NumpyEncoder))
except Exception as e:
    import traceback
    traceback.print_exc()
