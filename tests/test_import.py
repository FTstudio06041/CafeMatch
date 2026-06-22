import sys
sys.path.insert(0, '.')
try:
    from services import ai_service
    print('ai_service import OK')
except Exception as e:
    print(f'Import error: {e}')

try:
    from app import app
    print('app import OK')
except Exception as e:
    print(f'App import error: {e}')
