"""Fixed Blender worker boundary for card assets; model output never supplies code."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from sceneops_blender.agent_session import sandbox_profile

from .card_asset_models import CardAssetError


class CardAssetBlender:
    def __init__(self, state_root: Path, executable: Path | None = None, timeout: float = 120):
        self.state_root = Path(state_root).resolve()
        self.executable = Path(executable or "/Applications/Blender.app/Contents/MacOS/Blender").resolve()
        self.timeout = timeout
        self.script = (Path(__file__).resolve().parents[3] / "scripts" / "card_asset_blender.py").resolve()

    def run(self, request_id: str, asset_root: Path, payload: dict) -> tuple[dict, Path]:
        asset_root = asset_root.resolve()
        if not self.executable.is_file() or not os.access(self.executable, os.X_OK):
            raise CardAssetError("BLENDER_UNAVAILABLE", "未找到可执行的 Blender；请在诊断中检查本机安装。", status_code=503)
        if not Path("/usr/bin/sandbox-exec").is_file():
            raise CardAssetError("BLENDER_SANDBOX_UNAVAILABLE", "本机缺少 Blender 文件隔离能力，未执行资产写入。", status_code=503)
        if not self.script.is_file():
            raise CardAssetError("BLENDER_WORKER_MISSING", "固定 Blender 工作器缺失，未执行资产写入。", status_code=500)

        run_root = self.state_root / request_id
        run_root.mkdir(parents=True, exist_ok=False, mode=0o700)
        for name in ("home", "tmp", "config", "cache"):
            (run_root / name).mkdir(mode=0o700)
        request_path = run_root / "request.json"
        result_path = run_root / "result.json"
        log_path = run_root / "blender.log"
        profile_path = run_root / "sandbox.sb"
        request_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        profile_path.write_text(sandbox_profile(asset_root, run_root, self.executable, self.script.parent), encoding="utf-8")
        environment = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "__CF_USER_TEXT_ENCODING") if key in os.environ}
        environment.update({
            "HOME": str(run_root / "home"),
            "TMPDIR": str(run_root / "tmp"),
            "BLENDER_USER_CONFIG": str(run_root / "config"),
            "XDG_CACHE_HOME": str(run_root / "cache"),
        })
        command = [
            "/usr/bin/sandbox-exec", "-f", str(profile_path), str(self.executable),
            "--background", "--factory-startup", "--disable-autoexec",
            "--python", str(self.script), "--", str(request_path), str(result_path),
        ]
        try:
            with log_path.open("wb") as log:
                completed = subprocess.run(command, cwd=asset_root, env=environment, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT, timeout=self.timeout, check=False)
        except subprocess.TimeoutExpired as error:
            raise CardAssetError("BLENDER_TIMEOUT", f"Blender 在 {int(self.timeout)} 秒内没有完成；日志已保留。", status_code=504) from error
        except OSError as error:
            raise CardAssetError("BLENDER_START_FAILED", "Blender 无法启动；日志已保留。", status_code=503) from error
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CardAssetError("BLENDER_RESULT_MISSING",
                                 f"Blender 未返回可读结果（退出码 {completed.returncode}）；日志已保留。") from error
        if completed.returncode or not result.get("ok"):
            message = result.get("error") if isinstance(result, dict) else None
            raise CardAssetError("BLENDER_OPERATION_FAILED", str(message or f"Blender 执行失败（退出码 {completed.returncode}）。"))
        return result, log_path
