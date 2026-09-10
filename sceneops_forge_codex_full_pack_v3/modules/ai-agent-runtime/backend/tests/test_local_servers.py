"""Only the dedicated temporary Python listener is stopped; no existing service is changed."""
import asyncio
import copy
import json
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sceneops_ai_agents.local_servers import LocalServerInventory
from sceneops_harness import HarnessError


class LocalServerSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_dedicated_listener_inventory_and_stop(self):
        script = "import socket,time; sockets=[socket.socket(),socket.socket()]; [(s.bind(('127.0.0.1',0)),s.listen()) for s in sockets]; print([s.getsockname()[1] for s in sockets],flush=True); time.sleep(60)"
        process = subprocess.Popen([sys.executable, '-I', '-c', script, 'private-argument-token'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ports = json.loads(await asyncio.to_thread(process.stdout.readline))
            game = SimpleNamespace(previews={'fixture': {
                'process': process, 'run': SimpleNamespace(project_id='fixture-project')}})
            inventory = LocalServerInventory(game)
            listing = await inventory.list()
            selected = next(item for item in listing.servers if item.pid == process.pid)
            self.assertTrue(selected.can_stop)
            self.assertTrue(selected.managed)
            self.assertEqual(selected.project_id, 'fixture-project')
            self.assertEqual({item.port for item in selected.endpoints}, set(ports))
            self.assertNotIn('private-argument-token', listing.model_dump_json())
            protected = await inventory.list(protected_ports={ports[0]})
            self.assertFalse(next(item for item in protected.servers if item.pid == process.pid).can_stop)
            stopped = await inventory.stop(selected.id)
            self.assertEqual(stopped.state, 'stopped')
            self.assertEqual(stopped.remaining_endpoints, [])
            self.assertTrue(game.previews['fixture']['stop_requested'])
            await asyncio.to_thread(process.wait, timeout=3)
        finally:
            if process.poll() is None:
                process.terminate()
                await asyncio.to_thread(process.wait, timeout=3)
            process.stdout.close()
            process.stderr.close()

    async def test_reused_pid_or_changed_listener_never_receives_signal(self):
        item = {'pid': 999991, 'parent': 1, 'uid': os.getuid(), 'name': 'python3',
                'started_at': '2026-09-08T01:00:00+00:00', 'endpoints': [('127.0.0.1', 39891)]}
        for change in ({'started_at': '2026-09-08T02:00:00+00:00'},
                       {'endpoints': [('127.0.0.1', 39892)]}, {'uid': os.getuid() + 1}):
            inventory = LocalServerInventory()
            changed = {**copy.deepcopy(item), **change}
            with patch('sceneops_ai_agents.local_servers.discover_listeners',
                       side_effect=[{item['pid']: item}, {item['pid']: changed}]), \
                    patch('sceneops_ai_agents.local_servers.os.kill') as kill:
                listing = await inventory.list()
                with self.assertRaises(HarnessError) as error:
                    await inventory.stop(listing.servers[0].id)
                self.assertEqual(error.exception.code, 'LOCAL_SERVER_SELECTION_CHANGED')
                kill.assert_not_called()
