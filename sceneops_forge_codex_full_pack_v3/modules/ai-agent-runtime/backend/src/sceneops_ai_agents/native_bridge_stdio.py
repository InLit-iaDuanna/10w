"""MCP JSON-lines client. Launched by native CLIs, uses only the standard library."""
import json
import os
import sys
from urllib.request import Request, build_opener, ProxyHandler


def main():
    url, token = os.environ['SCENEOPS_BRIDGE_URL'], os.environ['SCENEOPS_BRIDGE_TOKEN']
    # The endpoint belongs to this process, independent of user HTTP proxy settings.
    client = build_opener(ProxyHandler({}))
    for line in sys.stdin:
        message = json.loads(line)
        if 'id' not in message:
            continue
        try:
            request = Request(url, data=line.encode(), headers={
                'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, method='POST')
            with client.open(request, timeout=600) as response:
                result = json.load(response)
        except Exception:
            result = {'jsonrpc': '2.0', 'id': message['id'], 'error': {
                'code': -32603, 'message': 'SceneOps task bridge unavailable; inspect the task status before retrying.'}}
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
