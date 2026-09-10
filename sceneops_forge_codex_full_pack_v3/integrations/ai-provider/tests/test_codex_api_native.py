"""Local Responses fixture: real CLI/config, no external model or user credentials."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from sceneops_ai_provider import ProviderService, codex_cli
from sceneops_ai_provider.codex_api import LOCAL_KEY_ENV


class CodexAPINativeSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_isolated_native_route(self):
        requests = []
        key = 'fixture-upstream-key-never-in-child'
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                request = json.loads(body)
                requests.append((self.path, self.headers.get('Authorization'), request))
                message = {'id':'msg_fixture', 'type':'message', 'role':'assistant',
                    'content':[{'type':'output_text','text':'isolated native fixture complete','annotations':[]}]}
                if len(requests) == 1:
                    message = {'id':'fc_fixture', 'type':'function_call', 'call_id':'call_fixture',
                        'name':'exec_command',
                        'arguments':json.dumps({'cmd':"printf native-fixture > native-fixture.txt; printf '%s' \"${SCENEOPS_CODEX_RELAY_TOKEN-unset}\"", 'max_output_tokens':100})}
                response = {'id':'resp_fixture','object':'response','status':'completed',
                    'output':[message], 'usage':{'input_tokens':10,'output_tokens':5,'total_tokens':15}}
                events = [
                    {'type':'response.created','response':{**response,'status':'in_progress','output':[]}},
                    {'type':'response.output_item.added','output_index':0,'item':{**message,'content':[]}},
                    {'type':'response.output_text.delta','output_index':0,'content_index':0,
                     'item_id':message['id'],'delta':'isolated native fixture complete'},
                    {'type':'response.output_item.done','output_index':0,'item':message},
                    {'type':'response.completed','response':response},
                ]
                data = ''.join('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n' for event in events).encode()
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval':.1},daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                provider = ProviderService(root / 'state.sqlite3')
                url = f'http://127.0.0.1:{server.server_port}/v1'
                provider.update_settings(provider='openai-compatible',model='gpt-6-astra',
                    base_url=url,api_key=key,reasoning_effort='max')
                home_paths = []
                original_run = codex_cli._run
                async def run(*args, **kwargs):
                    environment = kwargs['environment']
                    self.assertNotIn(key, json.dumps([args, environment], default=str))
                    self.assertIn(LOCAL_KEY_ENV, environment)
                    home_paths.append(Path(environment['CODEX_HOME']))
                    self.assertTrue(home_paths[-1].is_dir())
                    return await original_run(*args, **kwargs)
                events = []
                async def observe(event):
                    events.append(event)
                with patch.object(codex_cli, '_run', side_effect=run):
                    result = await provider.execute_task('Return the local fixture response.',workspace_root=root,
                        model='gpt-6-astra',authorized_scope='Only this temporary smoke directory.',timeout=20,
                        expected_provider='openai-compatible',expected_base_url=url,on_event=observe,
                        native_production=True)
                    resumed = await provider.execute_task('Continue the same fixture conversation.',workspace_root=root,
                        model='gpt-6-astra',authorized_scope='Only this temporary smoke directory.',timeout=20,
                        expected_provider='openai-compatible',expected_base_url=url,on_event=observe,
                        native_production=True,session_id=result['session_id'])
                self.assertEqual(result['result'],'isolated native fixture complete')
                self.assertTrue(any(event.get('type')=='assistant_message' for event in events))
                self.assertTrue(home_paths)
                self.assertTrue(all(path == root / '.sceneops/codex-compatible-harness'
                                    for path in home_paths))
                self.assertEqual(len(requests),3)
                self.assertTrue((root / 'native-fixture.txt').exists(), json.dumps(requests[1][2].get('input')))
                self.assertTrue((root / '.sceneops/codex-compatible-harness').is_dir())
                self.assertIsInstance(result.get('session_id'), str)
                self.assertEqual(resumed.get('session_id'), result.get('session_id'))
                self.assertEqual((root / 'native-fixture.txt').read_text(),'native-fixture')
                self.assertTrue(any(event.get('type')=='command_execution' for event in events))
                self.assertIn('unset',json.dumps(requests[1][2]))
                self.assertEqual(requests[0][0],'/v1/responses')
                self.assertEqual(requests[0][1],'Bearer '+key)
                self.assertEqual(requests[0][2]['model'],'gpt-6-astra')
                self.assertNotIn(key, json.dumps(result))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
