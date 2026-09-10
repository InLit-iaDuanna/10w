"""Local service controls inherit the composition root's origin and token checks."""
import os
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request

from .local_servers import LocalServerInventory, LocalServerList, LocalServerStopResult


def create_local_server_router(service):
    router = APIRouter(prefix='/api/agent/local-servers', tags=['local-servers'])
    inventory = LocalServerInventory(service.game if service is not None else None)

    def protected_ports(request):
        ports = {int(os.environ.get('SCENEOPS_WEB_PORT', '4300')),
                 int(os.environ.get('SCENEOPS_API_PORT', '8300'))}
        for url in (str(request.url), request.headers.get('origin', '')):
            port = urlparse(url).port
            if port:
                ports.add(port)
        return ports

    def require_service():
        if service is None:
            raise HTTPException(503, '本地服务管理未启用。')

    @router.get('', response_model=LocalServerList, operation_id='listLocalServers')
    async def list_servers(request: Request):
        require_service()
        return await inventory.list(protected_ports(request))

    @router.post('/{server_id}/stop', response_model=LocalServerStopResult, operation_id='stopLocalServer')
    async def stop_server(server_id: str, request: Request):
        require_service()
        return await inventory.stop(server_id, protected_ports(request))

    return router
