bash <<'EOF'
TARGET_PORT=8406                      # 需要根据自己的 Port 修改
TARGET_NAME="datanode2"              # 需要根据自己的 datanode 修改
CHECK_SECONDS=30
LOG_DIR="/hdd/hdd7/chennuodai/dolphindb_ha_cluster/server/clusterDemo/log"   # 需要根据自己的路径修改
CONTROLLER_LOG="${LOG_DIR}/controller.log"

PID=$(lsof -i:${TARGET_PORT} | awk '/LISTEN/ {print $2}' | head -n 1)

if [ -z "${PID}" ]; then
  echo "❌ 未找到端口 ${TARGET_PORT} 的监听进程"
  exit 1
fi

echo "监听进程 PID: ${PID}"

STAT=$(ps -o stat= -p "${PID}" | awk '{print $1}')
echo "当前进程状态: ${STAT}"

# 1. 如果仍然包含 T，说明进程还被 SIGSTOP 挂着
if [[ "${STAT}" == *T* ]]; then
  echo "❌ ${TARGET_NAME} 进程仍处于暂停状态，问题未消失"
  exit 1
fi

# 2. 记录当前 S01009 数量
BEFORE_COUNT=$(grep "${TARGET_NAME}" "${CONTROLLER_LOG}" 2>/dev/null | grep "S01009" | wc -l || true)
echo "当前 S01009 条数: ${BEFORE_COUNT}"

# 3. 等待一段时间，观察是否继续新增 S01009
echo "等待 ${CHECK_SECONDS} 秒，确认不再产生新的 S01009 ..."
sleep "${CHECK_SECONDS}"

AFTER_COUNT=$(grep "${TARGET_NAME}" "${CONTROLLER_LOG}" 2>/dev/null | grep "S01009" | wc -l || true)
echo "等待后 S01009 条数: ${AFTER_COUNT}"

if [ "${AFTER_COUNT}" -gt "${BEFORE_COUNT}" ]; then
  echo "❌ 最近 ${CHECK_SECONDS} 秒内仍有新的 S01009，问题未消失"
  exit 1
fi

# 4. 检查最近日志中是否出现恢复 online
RECENT_LOG=$(tail -n 200 "${CONTROLLER_LOG}")

echo "${RECENT_LOG}" | grep "${TARGET_NAME}" | grep "is now online" >/dev/null || {
  echo "❌ 最近日志中未检测到 ${TARGET_NAME} 恢复 online"
  exit 1
}

echo "✅ ${TARGET_NAME} 当前运行正常，且最近未新增 S01009，问题已消失"
EOF