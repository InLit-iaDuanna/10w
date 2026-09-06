"""Authorized empty, visible Editor startup/readback only; no games, builds or test runner."""
import json
import argparse
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine_unity import UnityAgentSession


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, help='Reconnect an existing dedicated smoke workspace with its original grant.')
    arguments = parser.parse_args()
    project_id = 'prj_unity_connection_' + uuid.uuid4().hex[:12]
    application = Path.home() / 'Library/Application Support/SceneOps'
    root = application / 'agent-workspaces' / project_id
    if arguments.workspace:
        root = arguments.workspace.resolve()
        project_id = root.name
    session = UnityAgentSession(root, application / 'agent-tool-state' / project_id / 'unity')
    grant = dict(task_id='task_' + project_id, grant_id='grant_' + project_id,
        project_id=project_id, workspace_root=str(root),
        allowed_capabilities=['unity.asset.import', 'unity.scene.inspect'],
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat())
    if arguments.workspace:
        grant = json.loads((root / 'unity/.sceneops-agent/session.json').read_text())['grant']
    session.bind_authorization(grant)
    try:
        print(json.dumps(session.start(), ensure_ascii=False), flush=True)
        print(json.dumps(session.inspect(), ensure_ascii=False), flush=True)
    finally:
        session.stop()


if __name__ == '__main__':
    main()
