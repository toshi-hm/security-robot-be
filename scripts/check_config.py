
import sys
import os

sys.path.append(os.getcwd())

try:
    from app.core.config import settings
    print(f"Attributes: {dir(settings)}")
    try:
        print(f"Dict: {settings.model_dump()}")
    except:
        pass
    try:
        print(f"Dict (v1): {settings.dict()}")
    except:
        pass
except ImportError:
    print("Could not import settings")
except Exception as e:
    print(f"Error: {e}")
