from pathlib import Path
import sys
import json
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'modules/conversation-home/backend/src'))
from api import app
out = root / 'modules/conversation-home/contracts/codebuddy.openapi.json'
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + '\n')
print(out)
