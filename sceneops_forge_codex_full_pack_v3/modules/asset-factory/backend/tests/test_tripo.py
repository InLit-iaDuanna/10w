import asyncio
import json
from pathlib import Path
import socket
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from asset_factory.card_asset_models import CardAssetError
from asset_factory.card_asset_router import create_card_asset_router
from asset_factory.tripo_service import TripoService, TripoSettingsInput, TripoRequest

class Assets:
    def __init__(self,root):
        self.database_path=root/'state.sqlite3';self.data_root=root/'data';self.records=[];self.import_calls=0;self.reference=None
    def _binding(self,project,card):
        if (project,card)!=('p','c'):raise CardAssetError('SCOPE','无效卡片',status_code=404)
        return {},self.data_root
    def _reference_images(self,project,card,root,reference):
        if reference and reference!='ref-owned':raise CardAssetError('REFERENCE_SCOPE_MISMATCH','错误参考图',status_code=422)
        return [self.reference] if reference else []
    def list(self,*args):return SimpleNamespace(assets=self.records)
    def import_asset(self,project,card,source,filename,session,**kwargs):
        assert kwargs=={'generation_provider':'tripo'}
        self.import_calls+=1;record=SimpleNamespace(id='asset-1',source_filename=filename,session_id=session,status='ready')
        self.records.append(record);return record
    def _load(self,table,id,model):return next(r for r in self.records if r.id==id)

def glb():
    body=json.dumps({'asset':{'version':'2.0'},'scene':0,'scenes':[{}]}).encode();body+=b' '*((-len(body))%4)
    return struct.pack('<4sII',b'glTF',2,20+len(body))+struct.pack('<II',len(body),0x4e4f534a)+body

class TripoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.assets=Assets(self.root);self.requests=[];self.remote_status='running';self.output='https://files.tripo.test/result.glb?token=fixture'
        def handler(request):
            self.requests.append(request)
            if request.url.host=='93.184.216.34':return httpx.Response(200,content=glb())
            if request.url.path.endswith('/upload/sts'):return httpx.Response(200,json={'code':0,'data':{'image_token':'image-token'}})
            if request.method=='POST':return httpx.Response(200,json={'code':0,'data':{'task_id':'task-1'}})
            return httpx.Response(200,json={'code':0,'data':{'task_id':'task-1','status':self.remote_status,'progress':65,'output':{'pbr_model':self.output}}})
        self.service=TripoService(self.assets,transport=httpx.MockTransport(handler));self.assets.tripo=self.service
        self.service.configure(TripoSettingsInput(api_key='test-old-private-key'))
        self.body=TripoRequest(request_id='request-0001',session_id='s',prompt='a wooden chair')
    async def test_submission_persisted_and_duplicate_does_not_charge_again(self):
        first,second=await asyncio.gather(self.service.submit('p','c',self.body),self.service.submit('p','c',self.body))
        self.assertEqual(first.id,second.id);self.assertEqual(len(self.requests),1)
        body=json.loads(self.requests[0].content);self.assertEqual(body['type'],'text_to_model');self.assertEqual(body['prompt'],'a wooden chair')
        restarted=TripoService(self.assets,transport=self.service.transport)
        repeated=await restarted.submit('p','c',self.body);self.assertEqual(repeated.task_id,'task-1');self.assertEqual(len(self.requests),1)
        with self.assertRaises(CardAssetError):await self.service.submit('p','c',self.body.model_copy(update={'prompt':'different'}))
        self.assertNotIn('test-old-private-key',self.assets.database_path.read_bytes().decode(errors='ignore'))
    async def test_image_uses_official_upload_token_and_scope_check(self):
        image=self.root/'reference.png';image.write_bytes(b'fixture image');self.assets.reference=image
        await self.service.submit('p','c',TripoRequest(request_id='image-0001',session_id='s',reference_id='ref-owned'))
        self.assertIn(b'fixture image',self.requests[0].content)
        self.assertEqual(json.loads(self.requests[1].content)['file'],{'type':'png','file_token':'image-token'})
        with self.assertRaises(CardAssetError):await self.service.submit('p','c',TripoRequest(request_id='image-0002',session_id='s',reference_id='other-card'))
        self.assertEqual(len(self.requests),2)
    async def test_rotating_key_keeps_original_task_credential(self):
        job=await self.service.submit('p','c',self.body)
        self.service.configure(TripoSettingsInput(api_key='test-new-private-key'))
        await self.service.poll(job.id)
        self.assertEqual(self.requests[-1].headers['Authorization'],'Bearer test-old-private-key')
        self.assertEqual(self.service.secrets.stat().st_mode & 0o777,0o600)
    async def test_timeout_is_not_automatically_resubmitted(self):
        def timeout(request):self.requests.append(request);raise httpx.ReadTimeout('timeout')
        self.service.transport=httpx.MockTransport(timeout)
        with self.assertRaises(CardAssetError):await self.service.submit('p','c',self.body)
        result=await self.service.submit('p','c',self.body)
        self.assertEqual(result.status,'submission_unknown');self.assertEqual(len(self.requests),1)
    async def test_collect_pins_public_ip_and_never_sends_key_to_download(self):
        job=await self.service.submit('p','c',self.body);self.remote_status='success'
        with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]):
            result=await self.service.collect(job.id)
        request=self.requests[-1];self.assertEqual(request.url.host,'93.184.216.34')
        self.assertEqual(request.headers['Host'],'files.tripo.test');self.assertEqual(request.extensions['sni_hostname'],'files.tripo.test')
        self.assertNotIn('authorization',request.headers);self.assertEqual(self.service.file(job.id).read_bytes(),glb());self.assertEqual(result.status,'collected')
        self.service.import_model(job.id);self.service.import_model(job.id);self.assertEqual(self.assets.import_calls,1)
    async def test_reject_private_download_and_redirects(self):
        with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]):
            with self.assertRaises(CardAssetError):await self.service.validate_download('https://evil.test/model.glb')
        job=await self.service.submit('p','c',self.body);self.remote_status='success';self.output='http://127.0.0.1/internal'
        with self.assertRaises(CardAssetError):await self.service.collect(job.id)
    async def test_settings_response_does_not_expose_keys(self):
        app=FastAPI();app.include_router(create_card_asset_router(self.assets))
        @app.exception_handler(CardAssetError)
        async def handler(request,error):return JSONResponse({'message':str(error)},status_code=error.status_code)
        with TestClient(app) as client:
            response=client.get('/api/card-assets/tripo/settings')
            self.assertEqual(response.status_code,200);self.assertTrue(response.json()['configured'])
            self.assertNotIn('private-key',response.text);self.assertNotIn('api_key',response.text)
            self.assertEqual(client.get('/api/card-assets/tripo/jobs/missing').status_code,404)

if __name__=='__main__':unittest.main()
