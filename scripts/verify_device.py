from pathlib import Path
import sys

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import torch  # noqa: E402

from app.core.config import settings  # noqa: E402

print(f"Torch CUDA available: {torch.cuda.is_available()}")
print(f"Settings training_device: {settings.training_device}")
print(f"Resolved training device: {settings.get_training_device()}")
