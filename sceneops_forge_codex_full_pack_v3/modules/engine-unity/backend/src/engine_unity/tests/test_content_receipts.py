import json
from engine_unity import content_dispatch_absent, content_receipt


def receipt(tmp_path, *, status='failed', code='UNITY_SCENE_MISMATCH', marked=False):
    root=tmp_path.resolve();mail=root/'unity/.sceneops-agent';mail.mkdir(parents=True)
    request={'command':'unity.content.save','session_id':'session-one',
        'authorization':{'task_id':'task-one','grant_id':'grant-one','action_id':'save-one'}}
    (mail/'request-one.request.json').write_text(json.dumps(request))
    (mail/'request-one.result.json').write_text(json.dumps({'status':status,'error_code':code,'message':'rejected',
        'resultJson':json.dumps({'session_id':'session-one','source_version':'2'})}))
    if marked:(mail/'request-one.content-started.json').write_text('{}')
    return root


def read(root, **overrides):
    return content_receipt(root,**{'request_id':'request-one','task_id':'task-one','grant_id':'grant-one','action_id':'save-one',**overrides})


def test_bound_prewrite_rejection_is_known_without_replaying(tmp_path):
    root=receipt(tmp_path)
    result=read(root)
    assert result['effect_state']=='NONE' and result['outcome']=='rejected'
    assert read(root,grant_id='another-grant') is None


def test_started_write_is_not_reclassified_as_no_effect(tmp_path):
    assert read(receipt(tmp_path,marked=True)) is None


def test_success_receipt_is_cached_and_preserves_its_session(tmp_path):
    result=read(receipt(tmp_path,status='succeeded',code='',marked=True))
    assert result['effect_state']=='COMMITTED' and result['mode']=='cached'
    assert result['readback']['source_version']=='2'


def test_unknown_failure_stays_unknown(tmp_path):
    assert read(receipt(tmp_path,code='UNITY_OUTCOME_UNCERTAIN')) is None


def test_absent_dispatch_requires_all_editor_markers_to_be_missing(tmp_path):
    root=tmp_path.resolve()
    assert content_dispatch_absent(root,request_id='request-never-sent')
    mailbox=root/'unity/.sceneops-agent';mailbox.mkdir(parents=True)
    (mailbox/'request-never-sent.content-started.json').write_text('{}')
    assert not content_dispatch_absent(root,request_id='request-never-sent')
