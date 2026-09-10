"""Tripo v2 OpenAPI: explicit submissions, durable jobs and local model collection."""
from __future__ import annotations
import asyncio
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import struct
import tempfile
from threading import Lock
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, SecretStr, model_validator
from .card_asset_models import CardAssetError, CardAssetRecord

API='https://api.tripo3d.ai/v2/openapi'
VERSIONS=['v3.1-20260211','v2.5-20250123','P1-20260311']
class TripoSettings(BaseModel):
    configured: bool
    model_version: str='v3.1-20260211'
    available_models: list[str]=Field(default_factory=lambda:list(VERSIONS))
class TripoSettingsInput(BaseModel):
    api_key: SecretStr | None=None
    clear_key: bool=False
    model_version: str='v3.1-20260211'
class TripoRequest(BaseModel):
    request_id: str=Field(pattern=r'^[a-zA-Z0-9_-]{8,100}$')
    session_id: str=Field(min_length=1,max_length=160)
    prompt: str=Field(default='',max_length=1024)
    reference_id: str | None=None
    @model_validator(mode='after')
    def content(self):
        self.prompt=self.prompt.strip()
        if not self.prompt and not self.reference_id:raise ValueError('请输入描述或选择参考图。')
        return self
class TripoJob(BaseModel):
    id: str
    project_id: str
    card_id: str
    session_id: str
    task_id: str | None=None
    credential_id: str | None=None
    status: str
    progress: int=0
    model_version: str
    error: str | None=None
    local_url: str | None=None
    asset_id: str | None=None
    mode: str='live'

class TripoService:
    def __init__(self,assets,*,transport=None):
        self.assets=assets;self.database=assets.database_path
        self.secrets=Path(self.database).parent/'tripo-secrets.json'
        self.root=assets.data_root/'tripo-models'
        if self.root.is_symlink():raise CardAssetError('TRIPO_STORAGE_UNSAFE','Tripo 输出目录不能是符号链接。')
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.transport=transport;self.secret_lock=Lock();self.locks={};self.async_locks={};self.guard=Lock()
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS tripo_jobs(id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,card_id TEXT NOT NULL,session_id TEXT NOT NULL,
                request_id TEXT NOT NULL,request TEXT NOT NULL,payload TEXT NOT NULL,
                UNIQUE(project_id,card_id,session_id,request_id))''')
    def connect(self):
        db=sqlite3.connect(self.database,timeout=10);db.row_factory=sqlite3.Row;return db
    def lock(self,key):
        with self.guard:return self.locks.setdefault(key,Lock())
    def _secret(self):
        if not self.secrets.exists():return {'model_version':VERSIONS[0],'current_key':None,'keys':{}}
        if self.secrets.is_symlink() or self.secrets.stat().st_mode & 0o077:raise CardAssetError('TRIPO_SECRET_PERMISSIONS','Tripo 密钥文件权限不安全。')
        return json.loads(self.secrets.read_text())
    def settings(self):
        value=self._secret();return TripoSettings(configured=bool(value.get('current_key')),model_version=value['model_version'])
    def configure(self,request):
        if request.model_version not in VERSIONS:raise CardAssetError('TRIPO_MODEL_INVALID','不支持的 Tripo 模型版本。',status_code=422)
        with self.secret_lock:
            value=self._secret()
            if request.clear_key:value['current_key']=None
            elif request.api_key is not None:
                key=request.api_key.get_secret_value().strip()
                if not re.fullmatch(r'[\x21-\x7e]{8,512}',key):raise CardAssetError('TRIPO_KEY_INVALID','API Key 格式无效。',status_code=422)
                reference=uuid4().hex;value['keys'][reference]=key;value['current_key']=reference
            value['model_version']=request.model_version
            fd,name=tempfile.mkstemp(prefix='.tripo-',dir=self.secrets.parent)
            try:
                with os.fdopen(fd,'w') as out:json.dump(value,out);out.flush();os.fsync(out.fileno())
                os.replace(name,self.secrets);os.chmod(self.secrets,0o600)
            finally:Path(name).unlink(missing_ok=True)
        return self.settings()
    async def remote(self,method,path,*,credential_id=None,**kwargs):
        secret=self._secret();key=secret['keys'].get(credential_id or secret['current_key'])
        if not key:raise CardAssetError('TRIPO_NOT_CONFIGURED','请先配置 Tripo API Key。',status_code=422)
        try:
            async with httpx.AsyncClient(transport=self.transport,timeout=60,follow_redirects=False) as client:
                response=await client.request(method,API+path,headers={'Authorization':'Bearer '+key},**kwargs)
            if response.status_code in [401,403]:raise CardAssetError('TRIPO_AUTH','Tripo 密钥无效或没有权限。',status_code=502)
            if response.status_code==429:raise CardAssetError('TRIPO_RATE_LIMIT','Tripo 请求过于频繁，请稍后刷新状态。',status_code=429)
            if response.status_code>=300:raise CardAssetError('TRIPO_REMOTE','Tripo 请求失败，请到控制台检查额度和任务状态。',status_code=502)
            value=response.json()
            if not isinstance(value,dict) or value.get('code')!=0:raise CardAssetError('TRIPO_REJECTED','Tripo 未接受请求，请检查参数、额度或内容要求。',status_code=502)
            data=value.get('data')
            if not isinstance(data,dict):raise CardAssetError('TRIPO_RESPONSE_INVALID','Tripo 响应格式无效。',status_code=502)
            return data
        except (httpx.HTTPError,ValueError,KeyError) as exc:
            raise CardAssetError('TRIPO_NETWORK','无法确认 Tripo 响应，请检查网络或控制台任务记录。',status_code=502) from None
    def save(self,job):
        with self.connect() as db:db.execute('UPDATE tripo_jobs SET payload=? WHERE id=?',(job.model_dump_json(),job.id))
    def get(self,job_id):
        with self.connect() as db:row=db.execute('SELECT payload FROM tripo_jobs WHERE id=?',(job_id,)).fetchone()
        if not row:raise CardAssetError('TRIPO_JOB_NOT_FOUND','Tripo 任务不存在。',status_code=404)
        job=TripoJob.model_validate_json(row['payload']);self.assets._binding(job.project_id,job.card_id);return job
    def list(self,project,card,session):
        self.assets._binding(project,card)
        with self.connect() as db:rows=db.execute('SELECT payload FROM tripo_jobs WHERE project_id=? AND card_id=? AND session_id=? ORDER BY rowid DESC',(project,card,session)).fetchall()
        return [TripoJob.model_validate_json(row['payload']) for row in rows]
    async def submit(self,project,card,request):
        _,root=self.assets._binding(project,card);settings=self.settings()
        if not settings.configured:raise CardAssetError('TRIPO_NOT_CONFIGURED','请先配置 Tripo API Key。',status_code=422)
        images=self.assets._reference_images(project,card,root,request.reference_id)
        canonical=request.model_dump_json()
        job=TripoJob(id='tripo_'+uuid4().hex,project_id=project,card_id=card,session_id=request.session_id,status='submitting',model_version=settings.model_version,credential_id=self._secret()['current_key'])
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT request,payload FROM tripo_jobs WHERE project_id=? AND card_id=? AND session_id=? AND request_id=?',(project,card,request.session_id,request.request_id)).fetchone()
            if row:
                if row['request']!=canonical:raise CardAssetError('TRIPO_REQUEST_CONFLICT','同一请求标识不能用于不同描述。',status_code=409)
                return TripoJob.model_validate_json(row['payload'])
            db.execute('INSERT INTO tripo_jobs VALUES(?,?,?,?,?,?,?)',(job.id,project,card,request.session_id,request.request_id,canonical,job.model_dump_json()))
        task_requested=False
        try:
            payload={'type':'image_to_model' if images else 'text_to_model','model_version':job.model_version}
            if images:
                path=images[0];suffix=path.suffix.lower();kind={'png':'png','jpg':'jpeg','jpeg':'jpeg','webp':'webp'}[suffix[1:]]
                if path.stat().st_size>10*1024*1024:raise CardAssetError('TRIPO_IMAGE_LIMIT','参考图不能超过 10 MiB。',status_code=422)
                with path.open('rb') as stream:data=await self.remote('POST','/upload/sts',credential_id=job.credential_id,files={'file':(path.name,stream,'image/'+kind)})
                payload['file']={'type':kind,'file_token':data['image_token']}
            else:payload['prompt']=request.prompt
            task_requested=True
            data=await self.remote('POST','/task',credential_id=job.credential_id,json=payload)
            task=data.get('task_id','')
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,160}',task):raise CardAssetError('TRIPO_INVALID_TASK','Tripo 返回了无效任务标识。',status_code=502)
            job.task_id=task;job.status='queued'
        except Exception as error:
            uncertain=task_requested and getattr(error,'code','') not in {'TRIPO_AUTH','TRIPO_RATE_LIMIT','TRIPO_REJECTED'}
            job.status='submission_unknown' if uncertain else 'failed'
            job.error='提交未能确认。请在 Tripo 控制台检查任务，避免重复生成扣费。' if uncertain else '提交失败；尚未确认生成任务。请检查配置与参考图。'
            self.save(job);raise
        self.save(job);return job
    async def poll(self,job_id):
        job=self.get(job_id)
        if not job.task_id or job.status in {'collected','imported'}:return job
        previous=job.model_dump_json()
        data=await self.remote('GET','/task/'+job.task_id,credential_id=job.credential_id)
        if data.get('task_id')!=job.task_id:raise CardAssetError('TRIPO_TASK_MISMATCH','Tripo 任务响应不匹配。',status_code=502)
        status=data.get('status')
        if status not in {'queued','running','success','failed','banned','expired','cancelled','unknown'}:raise CardAssetError('TRIPO_STATUS_INVALID','无法识别 Tripo 任务状态。',status_code=502)
        job.status=status;job.progress=max(0,min(100,int(data.get('progress',0))))
        if status in {'failed','banned','expired','cancelled','unknown'}:job.error='Tripo 任务未完成：'+status
        with self.connect() as db:
            updated=db.execute('UPDATE tripo_jobs SET payload=? WHERE id=? AND payload=?',(job.model_dump_json(),job.id,previous)).rowcount
        return job if updated else self.get(job.id)
    @staticmethod
    async def validate_download(url):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):raise CardAssetError('TRIPO_URL_UNSAFE','生成文件地址不安全。',status_code=502)
        try:answers=await asyncio.to_thread(socket.getaddrinfo,parsed.hostname,443,type=socket.SOCK_STREAM)
        except OSError:raise CardAssetError('TRIPO_DOWNLOAD_DNS','无法解析模型下载地址。',status_code=502) from None
        if not answers or any(not ipaddress.ip_address(item[4][0]).is_global for item in answers):raise CardAssetError('TRIPO_URL_UNSAFE','拒绝访问本地或私有网络下载地址。',status_code=502)
        return answers[0][4][0], parsed.hostname
    def file(self,job_id):
        self.get(job_id);target=self.root/(job_id+'.glb')
        if target.is_symlink() or not target.is_file():raise CardAssetError('TRIPO_FILE_MISSING','尚未取得本地模型。',status_code=404)
        return target
    async def collect(self,job_id):
        with self.guard:lock=self.async_locks.setdefault(job_id,asyncio.Lock())
        async with lock:return await self._collect(job_id)
    async def _collect(self,job_id):
        job=self.get(job_id)
        if job.status in {'collected','imported'}:return job
        if not job.task_id:raise CardAssetError('TRIPO_NOT_READY','尚无已确认的远端任务。',status_code=409)
        data=await self.remote('GET','/task/'+job.task_id,credential_id=job.credential_id)
        if data.get('task_id')!=job.task_id:raise CardAssetError('TRIPO_TASK_MISMATCH','Tripo 任务响应不匹配。',status_code=502)
        if data.get('status')!='success':raise CardAssetError('TRIPO_NOT_READY','Tripo 模型尚未生成成功。',status_code=409)
        output=data.get('output',{});url=output.get('pbr_model') or output.get('model') or output.get('base_model')
        if not isinstance(url,str):raise CardAssetError('TRIPO_NO_MODEL','Tripo 没有返回模型文件。',status_code=502)
        address,hostname=await self.validate_download(url)
        download_url=httpx.URL(url).copy_with(host=address)
        fd,name=tempfile.mkstemp(prefix='tripo-',dir=self.root);size=0
        try:
            async with httpx.AsyncClient(transport=self.transport,timeout=120,follow_redirects=False,trust_env=False) as client:
                async with client.stream('GET',download_url,headers={'Host':urlsplit(url).netloc},extensions={'sni_hostname':hostname}) as response:
                    if response.status_code!=200:raise CardAssetError('TRIPO_DOWNLOAD_FAILED','模型下载失败，请重试获取文件。',status_code=502)
                    with os.fdopen(fd,'wb') as stream:
                        fd=-1
                        async for chunk in response.aiter_bytes():
                            size+=len(chunk)
                            if size>100*1024*1024:raise CardAssetError('TRIPO_MODEL_LIMIT','生成模型超过 100 MiB。',status_code=422)
                            stream.write(chunk)
            with open(name,'rb') as stream:header=stream.read(12)
            if len(header)!=12 or struct.unpack('<4sII',header)!=(b'glTF',2,size):raise CardAssetError('TRIPO_NOT_GLB','生成文件不是有效的 GLB。',status_code=502)
            try:
                with open(name,'rb') as stream:
                    stream.seek(12);chunk=stream.read(8)
                    length,kind=struct.unpack('<II',chunk)
                    if kind!=0x4e4f534a or length>size-20:raise ValueError()
                    document=json.loads(stream.read(length))
                if not isinstance(document,dict) or document.get('asset',{}).get('version')!='2.0':raise ValueError()
                for item in document.get('buffers',[])+document.get('images',[]):
                    uri=item.get('uri')
                    if uri is not None and (not isinstance(uri,str) or not uri.startswith('data:')):
                        raise CardAssetError('TRIPO_EXTERNAL_RESOURCE','生成的 GLB 含外部文件引用，已拒绝导入。',status_code=502)
            except (ValueError,TypeError,AttributeError,struct.error):
                raise CardAssetError('TRIPO_NOT_GLB','生成文件的 GLB 结构无效。',status_code=502) from None
            os.replace(name,self.root/(job.id+'.glb'))
        except httpx.HTTPError:raise CardAssetError('TRIPO_DOWNLOAD_FAILED','模型下载中断，请重试获取文件。',status_code=502) from None
        finally:
            if fd>=0:os.close(fd)
            Path(name).unlink(missing_ok=True)
        job.status='collected';job.progress=100;job.local_url=f'/api/card-assets/tripo/jobs/{job.id}/model';self.save(job);return job
    def import_model(self,job_id):
        with self.lock(job_id):
            job=self.get(job_id);source=self.file(job_id)
            if job.asset_id:return self.assets._load('card_asset_records',job.asset_id,CardAssetRecord)
            filename=job.id+'.glb'
            previous=next((a for a in self.assets.list(job.project_id,job.card_id).assets if a.source_filename==filename and a.session_id==job.session_id and a.status=='ready'),None)
            record=previous or self.assets.import_asset(job.project_id,job.card_id,source,filename,job.session_id,generation_provider='tripo')
            job.asset_id=record.id;job.status='imported';self.save(job);return record
