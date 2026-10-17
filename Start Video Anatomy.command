#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
bash scripts/start-local.sh "$@"
local_status=$?
if [ "$local_status" -ne 0 ]; then
  read -r -p '启动未完成，请保留上面的错误信息。按回车关闭。' _
fi
exit "$local_status"
