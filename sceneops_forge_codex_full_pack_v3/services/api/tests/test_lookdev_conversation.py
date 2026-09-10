import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from vfx_shader.lookdev_service import LookdevService
from vfx_shader.lookdev_models import LookdevTarget

class TurnHistoryTests(unittest.TestCase):
    def test_finish_records_existing_main_conversation_once(self):
        from conversation_home import AIRepository
        from vfx_shader.lookdev_models import LookdevTurn, FinishLookdevTurnRequest
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'data.sqlite3'
            conversation = AIRepository(database)
            service = LookdevService(database, SimpleNamespace(exists=lambda _: True), None, None, None,
                record_exchange=conversation.append_exchange)
            turn = LookdevTurn(id='turn1', prompt='外壳改红', target=LookdevTarget(asset_id='a', asset_version=1),
                status='proposed', summary='外壳已改红。', model='test', provider='codexcli')
            with service.connect() as db:
                db.execute('INSERT INTO lookdev_turns VALUES(?,?,?)', ('p', turn.id, turn.model_dump_json()))
            self.assertEqual(conversation.conversation('p').messages, [])
            service.finish_turn('p', turn.id, FinishLookdevTurnRequest(status='applied'))
            service.finish_turn('p', turn.id, FinishLookdevTurnRequest(status='applied'))
            self.assertEqual(len(conversation.conversation('p').messages), 2)
            self.assertEqual(service.history('p')[0].status, 'applied')
            self.assertEqual(conversation.conversation('p').messages[0].text, '外壳改红')
