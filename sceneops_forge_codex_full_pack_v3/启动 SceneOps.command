#!/bin/zsh

set -u
launcher_directory="${0:A:h}"
cd -- "$launcher_directory"

if ! command -v node >/dev/null 2>&1; then
  echo "未找到 Node.js。SceneOps 需要 Node.js 22.12 或更高版本。"
  echo "安装后重新双击“启动 SceneOps.command”。"
  read -k 1 "?按任意键关闭…"
  exit 1
fi

node scripts/one-click.mjs
launch_status=$?
if (( launch_status != 0 )); then
  echo
  read -k 1 "?启动未完成，按任意键关闭…"
fi
exit "$launch_status"
