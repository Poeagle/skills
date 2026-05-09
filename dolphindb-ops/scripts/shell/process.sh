#!/bin/bash
# 进程级诊断脚本
# 包含进程状态、线程、文件描述符、网络连接等检查



# @description 进程多维度全景：基本信息 + 线程数 + 文件描述符数 + /proc/status + 资源限制 + 端口监听 + 网络连接
# @params filter:str:optional:default=, port:int:required
# @collect crash, disk-full, node-down, startup-failure, system-hang
# @permission readonly
checkProcessAll() {
    resolve_pid() {
        local port="$1"
        local filter="$2"
        local pid=""

        if [ -n "$port" ] && [ "$port" != "0" ]; then
            pid=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP "pid=\K[0-9]+" | head -1)
        fi

        if [ -z "$pid" ] && [ -n "$filter" ]; then
            pid=$(ps aux | grep -F "$filter" | grep -v grep | awk '{print $2}' | head -1)
        fi

        printf '%s' "$pid"
    }

    PID=$(resolve_pid "{port}" "{filter}")

    echo "=== Process Info ==="
    if [ -n "$PID" ]; then
        echo "PID: $PID"
        ps -fp "$PID"
    else
        echo "PID: not found via port {port}, fallback to filter '{filter}'"
        ps aux | grep -F "{filter}" | grep -v grep
    fi
    echo ""

    if [ -n "$PID" ]; then
        echo "=== Threads ==="
        ls /proc/$PID/task 2>/dev/null | wc -l || echo 'N/A'
        echo ""

        echo "=== File Descriptors ==="
        ls /proc/$PID/fd 2>/dev/null | wc -l || echo 'N/A'
        echo ""

        echo "=== Process Status ==="
        cat /proc/$PID/status 2>/dev/null | grep -E 'Name|State|VmPeak|VmRSS|VmSize|Threads|FDSize' || echo 'N/A'
        echo ""

        echo "=== Process Limits ==="
        cat /proc/$PID/limits 2>/dev/null || echo 'N/A'
        echo ""
    fi

    echo "=== Port Listening ({port}) ==="
    ss -lnp 2>/dev/null | grep :{port} || netstat -lnp 2>/dev/null | grep :{port} || echo 'not listening'
    echo ""

    echo "=== Active Connections ({port}, top 50) ==="
    ss -tnp 2>/dev/null | grep :{port} | head -50 || netstat -tnp 2>/dev/null | grep :{port} | head -50 || echo 'no active connections'
}

# @description 恢复目标节点当前处于暂停态的进程（仅当 State 为 T/t 时发送 SIGCONT，并校验恢复结果）
# @params filter:str:optional:default=, port:int:required, verify_retries:int:optional:default=5:max=10, verify_interval:int:optional:default=1:max=5
# @permission irreversible
resumeStoppedProcess() {
    resolve_pid() {
        local port="$1"
        local filter="$2"
        local pid=""

        if [ -n "$port" ] && [ "$port" != "0" ]; then
            pid=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP "pid=\K[0-9]+" | head -1)
        fi

        if [ -z "$pid" ] && [ -n "$filter" ]; then
            pid=$(ps aux | grep -F "$filter" | grep -v grep | awk '{print $2}' | head -1)
        fi

        printf '%s' "$pid"
    }

    read_state() {
        local pid="$1"
        awk '/^State:/ {print $2}' "/proc/$pid/status" 2>/dev/null
    }

    find_listener() {
        local port="$1"
        ss -lnp 2>/dev/null | grep ":$port " || netstat -lnp 2>/dev/null | grep ":$port "
    }

    PID=$(resolve_pid "{port}" "{filter}")
    if [ -z "$PID" ]; then
        echo 'process not found on port {port}'
        exit 1
    fi

    BEFORE_STATE=$(read_state "$PID")
    echo "pid: $PID"
    echo "before_state: ${BEFORE_STATE:-unknown}"

    if [ -z "$BEFORE_STATE" ]; then
        echo 'cannot read process state'
        exit 1
    fi

    if [[ "$BEFORE_STATE" != "T" && "$BEFORE_STATE" != "t" ]]; then
        echo 'process is not stopped; skip SIGCONT'
        echo '---port_listener---'
        find_listener "{port}" || true
        exit 0
    fi

    if ! kill -CONT "$PID" 2>/dev/null; then
        echo 'failed to send SIGCONT'
        exit 1
    fi

    echo 'sent_signal: SIGCONT'
    RETRIES={verify_retries}
    INTERVAL={verify_interval}
    AFTER_STATE="$BEFORE_STATE"
    PORT_INFO=''

    while [ "$RETRIES" -gt 0 ]; do
        AFTER_STATE=$(read_state "$PID")
        PORT_INFO=$(find_listener "{port}" || true)
        if [ -n "$AFTER_STATE" ] && [[ "$AFTER_STATE" != "T" && "$AFTER_STATE" != "t" ]] && [ -n "$PORT_INFO" ]; then
            break
        fi
        RETRIES=$((RETRIES - 1))
        if [ "$RETRIES" -gt 0 ]; then
            sleep "$INTERVAL"
        fi
    done

    echo "after_state: ${AFTER_STATE:-unknown}"
    echo '---port_listener---'
    printf '%s\n' "$PORT_INFO"

    if [ -z "$AFTER_STATE" ]; then
        echo 'process state unavailable after SIGCONT'
        exit 1
    fi

    if [[ "$AFTER_STATE" == "T" || "$AFTER_STATE" == "t" ]]; then
        echo 'process still stopped after SIGCONT'
        exit 1
    fi

    if [ -z "$PORT_INFO" ]; then
        echo 'port is not listening after SIGCONT'
        exit 1
    fi
}

# @description 获取进程的完整线程信息（完整堆栈 + 统计摘要：基础信息、高负载线程、状态分布）
# @params filter:str:optional:default=, port:int:required, top_threads:int:optional:default=20:max=100, stack_method:str:optional:default=pstack:pattern=^(pstack|gdb)$
# @collect system-hang, slow-query, job-issues
# @permission readonly
checkThreadInfo() {
    resolve_pid() {
        local port="$1"
        local filter="$2"
        local pid=""

        if [ -n "$port" ] && [ "$port" != "0" ]; then
            pid=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP "pid=\K[0-9]+" | head -1)
        fi

        if [ -z "$pid" ] && [ -n "$filter" ]; then
            pid=$(ps aux | grep -F "$filter" | grep -v grep | awk '{print $2}' | head -1)
        fi

        printf '%s' "$pid"
    }

    PID=$(resolve_pid "{port}" "{filter}")
    if [ -z "$PID" ]; then
        echo 'process not found on port {port}'
        exit 1
    fi

    if [ ! -d "/proc/$PID/task" ]; then
        echo "cannot access thread info for PID $PID"
        exit 1
    fi

    # ========== 第一部分：完整线程堆栈 ==========
    echo "=== Thread Stack Trace (Full) ==="
    echo "PID: $PID"
    echo "Method: {stack_method}"
    echo ""

    if [ "{stack_method}" = "pstack" ]; then
        if command -v pstack >/dev/null 2>&1; then
            pstack "$PID" 2>/dev/null || echo 'pstack failed, try stack_method=gdb'
        else
            echo 'pstack not available, try stack_method=gdb'
        fi
    elif [ "{stack_method}" = "gdb" ]; then
        if command -v gdb >/dev/null 2>&1; then
            gdb --batch \
                -ex "set debuginfod enabled off" \
                -ex "set pagination off" \
                -ex "thread apply all bt" \
                --pid "$PID" 2>&1 | \
            grep -v "^\[New LWP" | \
            grep -v "^This GDB supports" | \
            grep -v "^<https://" | \
            grep -v "^Enable debuginfod" | \
            grep -v "^\[answered" | \
            grep -v "^Debuginfod has been" | \
            grep -v "^To make this setting" | \
            grep -v "^\[Thread debugging" | \
            grep -v "^Using host libthread"
        else
            echo 'gdb not available'
        fi
    fi

    echo ""
    echo "========================================"
    echo ""

    # ========== 第二部分：统计摘要 ==========

    # 1. 基础信息
    TOTAL_THREADS=$(ls /proc/$PID/task 2>/dev/null | wc -l)
    echo "=== Summary ==="
    echo "PID: $PID"
    echo "Total Threads: $TOTAL_THREADS"
    echo ""

    # 2. 高负载线程（按 CPU 时间降序，只显示 CPU > 0 的）
    echo "=== Top CPU Threads (Top {top_threads}) ==="
    printf "%-10s %-10s %-12s\n" "TID" "STATE" "CPU_TIME"

    for TID_DIR in /proc/$PID/task/*; do
        TID=$(basename "$TID_DIR")
        STATE=$(awk '/^State:/ {print $2}' "$TID_DIR/status" 2>/dev/null || echo "?")

        if [ -f "$TID_DIR/stat" ]; then
            CPU=$(awk '{print ($14+$15)}' "$TID_DIR/stat" 2>/dev/null || echo "0")
        else
            CPU="0"
        fi

        # 只输出 CPU > 0 的线程
        if [ "$CPU" != "0" ]; then
            printf "%-10s %-10s %-12s\n" "$TID" "$STATE" "$CPU"
        fi
    done | sort -k3 -rn | head -{top_threads}
    echo ""

    # 3. 状态分布（重点关注异常状态）
    echo "=== Thread State Distribution ==="

    declare -A STATE_MAP
    STATE_MAP["R"]="Running"
    STATE_MAP["S"]="Sleeping"
    STATE_MAP["D"]="Disk Sleep"
    STATE_MAP["Z"]="Zombie"
    STATE_MAP["T"]="Stopped"
    STATE_MAP["t"]="Tracing Stop"
    STATE_MAP["X"]="Dead"
    STATE_MAP["I"]="Idle"

    declare -A STATE_COUNT
    for TID_DIR in /proc/$PID/task/*; do
        STATE=$(awk '/^State:/ {print $2}' "$TID_DIR/status" 2>/dev/null)
        if [ -n "$STATE" ]; then
            STATE_COUNT[$STATE]=$((${STATE_COUNT[$STATE]:-0} + 1))
        fi
    done

    # 检查是否有异常状态
    HAS_ABNORMAL=false
    for CODE in D Z T t X; do
        if [ "${STATE_COUNT[$CODE]:-0}" -gt 0 ]; then
            HAS_ABNORMAL=true
            break
        fi
    done

    if [ "$HAS_ABNORMAL" = "true" ]; then
        # 有异常状态，详细展示
        printf "%-20s %-10s %s\n" "STATE" "CODE" "COUNT"
        for CODE in R S D Z T t X I; do
            COUNT="${STATE_COUNT[$CODE]:-0}"
            if [ "$COUNT" -gt 0 ]; then
                STATE_NAME="${STATE_MAP[$CODE]:-Unknown}"
                printf "%-20s %-10s %s\n" "$STATE_NAME" "$CODE" "$COUNT"
            fi
        done | sort -k3 -rn
    else
        # 无异常状态，简化显示
        echo "All threads in normal state (R/S/I): $TOTAL_THREADS"
    fi
}
