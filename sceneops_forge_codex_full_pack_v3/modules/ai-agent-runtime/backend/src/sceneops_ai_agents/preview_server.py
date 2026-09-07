"""Application-owned localhost server for one verified game build directory."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading


class BuildHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        root = Path(self.directory).resolve()
        path = Path(self.translate_path(self.path))
        if path.resolve() != path or not path.is_relative_to(root):
            self.send_error(403, 'Outside registered build')
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(403, 'Directory listing disabled')
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    directory = Path(args.directory)
    if not directory.is_absolute() or directory.resolve() != directory or not (directory / 'index.html').is_file():
        raise SystemExit('invalid build directory')
    handler = partial(BuildHandler, directory=str(directory))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    print(json.dumps({'host': '127.0.0.1', 'port': server.server_port}), flush=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sys.stdin.buffer.read()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
