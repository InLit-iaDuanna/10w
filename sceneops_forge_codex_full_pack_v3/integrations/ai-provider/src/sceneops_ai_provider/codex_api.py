"""Per-invocation Codex configuration and credential isolation for compatible APIs.

The real upstream key stays in this process. Codex receives a short-lived local
credential for a fixed endpoint/model, excluded from its tool environments.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import secrets
import socket
import tempfile
import threading

import httpx

LOCAL_KEY_ENV = 'SCENEOPS_CODEX_RELAY_TOKEN'


class _Relay(ThreadingHTTPServer):
    daemon_threads = False

    def __init__(self, base_url, api_key, model):
        super().__init__(('127.0.0.1', 0), _Request)
        self.upstream = base_url
        self.api_key = api_key
        self.model = model
        self.token = secrets.token_urlsafe(32)
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.connections = set()
        self.stopping = False

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(20)
        with self.clients_lock:
            if self.stopping:
                connection.close()
                raise OSError('Relay is stopping')
            self.connections.add(connection)
        return connection, address

    def shutdown_request(self, connection):
        with self.clients_lock:
            self.connections.discard(connection)
        super().shutdown_request(connection)

    def close_connections(self):
        with self.clients_lock:
            self.stopping = True
            clients, connections = list(self.clients), list(self.connections)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        for client in clients:
            client.close()


class _Request(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        # HTTP logs must not retain prompts, URLs or credentials.
        pass

    def reject(self, status):
        self.send_response(status)
        self.send_header('Content-Length', '0')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def do_POST(self):
        relay = self.server
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + relay.token):
            self.reject(401)
            return
        if self.path not in ('/v1/responses', '/v1/responses/compact'):
            self.reject(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 32 * 1024 * 1024 or self.headers.get('Transfer-Encoding'):
                raise ValueError('Invalid body size')
            body = self.rfile.read(length)
            data = json.loads(body)
            if not isinstance(data, dict) or data.get('model') != relay.model:
                raise ValueError('Wrong model')
        except (ValueError, UnicodeError):
            self.reject(400)
            return
        client = httpx.Client(timeout=httpx.Timeout(300, connect=20), follow_redirects=False, trust_env=False)
        with relay.clients_lock:
            if relay.stopping:
                client.close()
                return
            relay.clients.add(client)
        try:
            # Never forward caller-supplied destinations, auth, cookies or headers.
            with client.stream('POST', relay.upstream + self.path.removeprefix('/v1'),
                    headers={'Authorization': 'Bearer ' + relay.api_key,
                             'Content-Type': 'application/json', 'Accept': 'text/event-stream'},
                    content=body) as response:
                if response.is_redirect:
                    self.reject(502)
                    return
                if response.is_error:
                    # Provider diagnostics can echo credentials; expose only status.
                    self.reject(response.status_code)
                    return
                self.send_response(response.status_code)
                self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                self.send_header('Transfer-Encoding', 'chunked')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                for chunk in response.iter_bytes():
                    if chunk:
                        self.wfile.write(f'{len(chunk):x}\r\n'.encode() + chunk + b'\r\n')
                        self.wfile.flush()
                self.wfile.write(b'0\r\n\r\n')
                self.wfile.flush()
        except (httpx.HTTPError, OSError):
            self.close_connection = True
        finally:
            client.close()
            with relay.clients_lock:
                relay.clients.discard(client)


@contextmanager
def isolated_api(base_url: str, api_key: str, model: str, environment: dict[str, str],
                 *, state_directory: Path | None = None):
    """No global environment, login, config or credential file is modified.

    Native production may keep only Codex conversation state in a registered
    project directory. Relay credentials remain process-local and short-lived.
    """
    with tempfile.TemporaryDirectory(prefix='sceneops-codex-api-') as directory:
        root = Path(directory)
        state = root / 'codex' if state_directory is None else Path(state_directory)
        if not state.is_absolute() or state.is_symlink() or state.parent.is_symlink():
            raise ValueError('Codex 会话状态目录必须是已登记的绝对路径。')
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        state.chmod(0o700)
        state = state.resolve(strict=True)
        relay = _Relay(base_url, api_key, model)
        thread = threading.Thread(target=relay.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
        thread.start()
        try:
            child = {key: value for key, value in environment.items()
                     if key in ('PATH', 'LANG', 'LC_ALL', 'SSL_CERT_FILE', 'SSL_CERT_DIR')}
            child.update(HOME=directory, CODEX_HOME=str(state), TMPDIR=directory,
                         XDG_CONFIG_HOME=str(root / 'config'))
            child[LOCAL_KEY_ENV] = relay.token
            overrides = {
                'model_provider': 'sceneops_relay',
                'model_providers.sceneops_relay.name': 'SceneOps compatible API',
                'model_providers.sceneops_relay.base_url': f'http://127.0.0.1:{relay.server_port}/v1',
                'model_providers.sceneops_relay.env_key': LOCAL_KEY_ENV,
                'model_providers.sceneops_relay.wire_api': 'responses',
                'model_providers.sceneops_relay.requires_openai_auth': False,
                'model_providers.sceneops_relay.request_max_retries': 0,
                'model_providers.sceneops_relay.stream_max_retries': 0,
                'cli_auth_credentials_store': 'file',
                'shell_environment_policy.inherit': 'none',
                'shell_environment_policy.experimental_use_profile': False,
                'shell_environment_policy.ignore_default_excludes': False,
            }
            for key, value in child.items():
                if key != LOCAL_KEY_ENV:
                    overrides['shell_environment_policy.set.' + key] = value
            arguments = [argument for key, value in overrides.items()
                         for argument in ('-c', key + '=' + json.dumps(value, ensure_ascii=False))]
            yield arguments, child
        finally:
            relay.close_connections()
            relay.shutdown()
            relay.server_close()
            thread.join()
            relay.api_key = ''
            relay.token = ''
