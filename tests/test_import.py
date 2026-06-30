import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app import app
    print("All imports successful!")
except Exception as e:
    import traceback
    print("Error importing app:")
    traceback.print_exc()
