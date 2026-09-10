"""Executable discovery shared by both supported local CLI adapters."""
import os
import shutil
from pathlib import Path


def cli_install_prefix() -> Path:
    return Path.home() / '.local' / 'share' / 'sceneops' / 'cli'


def resolve_cli_executable(name: str) -> str | None:
    if name not in {'codex', 'codebuddy'}:
        raise ValueError('Unsupported CLI')
    candidate = cli_install_prefix() / 'bin' / name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return shutil.which(name)
