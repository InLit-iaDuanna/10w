"""Local-only onboarding routes for the allowlisted CLI setup adapter."""
import ipaddress
import os
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sceneops_ai_provider import CLISetup, SetupFailure

Provider = Literal['codexcli', 'codebuddycli']


class InstallRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    providers: list[Provider] = Field(min_length=1, max_length=2)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Provider


class CLIToolStatus(BaseModel):
    provider: Provider
    label: str
    installed: bool
    compatible: bool
    version: str | None
    install_package: str
    login_command: str
    docs_url: str


class SetupOperation(BaseModel):
    state: Literal['idle', 'installing', 'succeeded', 'failed']
    message: str
    provider: Provider | None


class CLISetupStatus(BaseModel):
    platform: str
    install_supported: bool
    terminal_supported: bool
    npm_available: bool
    tools: list[CLIToolStatus]
    operation: SetupOperation


class LoginResponse(BaseModel):
    message: str


def require_local_request(request: Request) -> None:
    try:
        loopback = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        loopback = False
    ports = {os.environ.get('SCENEOPS_WEB_PORT', '4300'), os.environ.get('SCENEOPS_API_PORT', '8300')}
    origins = {f'http://{host}:{port}' for host in ('localhost', '127.0.0.1') for port in ports}
    if not loopback or request.headers.get('origin') not in origins:
        raise HTTPException(403, '环境配置只接受当前本地工作台的请求。')


def create_setup_router(setup: CLISetup | None = None) -> APIRouter:
    service = setup or CLISetup()
    router = APIRouter(prefix='/setup', tags=['ai-setup'])

    @router.get('', response_model=CLISetupStatus)
    async def status():
        return await service.status()

    @router.post('/install', response_model=CLISetupStatus)
    async def install(body: InstallRequest, request: Request):
        require_local_request(request)
        try:
            return await service.start_install(body.providers)
        except SetupFailure as error:
            raise HTTPException(409, str(error)) from error

    @router.post('/login', response_model=LoginResponse)
    async def login(body: LoginRequest, request: Request):
        require_local_request(request)
        try:
            return await service.login(body.provider)
        except SetupFailure as error:
            raise HTTPException(409, str(error)) from error

    return router
