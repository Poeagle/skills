#!/bin/bash
# Core dump 查找与分析脚本



# @description 优先根据 core_pattern 判断 core 存储方式；支持 coredumpctl 和节点相关目录扫描。**默认仅最近 1 天**；要看更老的 core 显式传 days=N
# @params search_path:str:optional:default=/:pattern=^[a-zA-Z0-9_./@:~-]+$, search_paths:str:optional:default=/:pattern=^[a-zA-Z0-9_./@:~-][a-zA-Z0-9_./@:~ /;-]*$:allow_chars=;, process_name:str:optional:default=dolphindb:pattern=^[a-zA-Z0-9_.-]+$, days:int:optional:default=1:max=30, maxdepth:int:optional:default=6:max=12, limit:int:optional:default=20:max=100
# @permission readonly
findCoreDumps() {
    CORE_PATTERN=$(cat /proc/sys/kernel/core_pattern 2>/dev/null || true)
    SEARCH_PATHS='{search_paths}'
    PROCESS_NAME='{process_name}'
    if [ -n "$CORE_PATTERN" ]; then
      case "$CORE_PATTERN" in
        \|*)
          if command -v coredumpctl >/dev/null 2>&1; then
            printf '__SOURCE__:%s\n' 'coredumpctl'
            printf '__CORE_PATTERN__:%s\n' "$CORE_PATTERN"
            coredumpctl --no-pager --no-legend list "COREDUMP_COMM=$PROCESS_NAME" --since="{days} days ago" 2>/dev/null | head -{limit}
            exit 0
          fi
          ;;
        /*)
          PATTERN_DIR=$(dirname "$CORE_PATTERN")
          if [ -d "$PATTERN_DIR" ]; then
            case ";$SEARCH_PATHS;" in
              *";$PATTERN_DIR;"*) ;;
              *) if [ -n "$SEARCH_PATHS" ]; then SEARCH_PATHS="$PATTERN_DIR;$SEARCH_PATHS"; else SEARCH_PATHS="$PATTERN_DIR"; fi ;;
            esac
          fi
          ;;
      esac
    fi
    printf '__SOURCE__:%s\n' 'filesystem'
    printf '__CORE_PATTERN__:%s\n' "$CORE_PATTERN"
    printf '__SEARCH_PATHS__:%s\n' "$SEARCH_PATHS"
    OLDIFS=$IFS
    IFS=';'
    for ROOT in $SEARCH_PATHS; do
      [ -n "$ROOT" ] || continue
      [ -d "$ROOT" ] || continue
      find "$ROOT" -maxdepth {maxdepth} -type f \( -name 'core' -o -name 'core.*' -o -name '*.core' -o -name '*.core.*' \) -mtime -{days} -printf '%TY-%Tm-%Td %TH:%TM:%TS|%s|%p\n' 2>/dev/null
    done | sort -r | head -{limit} | while IFS='|' read -r MTIME SIZE FPATH; do
      # 验证 core 文件是否属于目标进程
      FILE_INFO=$(file "$FPATH" 2>/dev/null | head -1)
      case "$FILE_INFO" in
        *"$PROCESS_NAME"*|*"core file"*)
          printf '%s|%s|%s|%s\n' "$MTIME" "$SIZE" "$FPATH" "$FILE_INFO"
          ;;
      esac
    done
    IFS=$OLDIFS
}


# @description 使用 gdb 分析 core dump 文件，提取崩溃堆栈、信号信息和线程状态。需提供 core 文件路径和 DolphinDB 可执行文件路径
# @params core_path:str:required:pattern=^[a-zA-Z0-9_./@:~-]+$, exec_path:str:optional:default=dolphindb:pattern=^[a-zA-Z0-9_./@:~-]+$, max_threads:int:optional:default=20:max=200
# @permission readonly
analyzeCoreDump() {
    CORE_PATH='{core_path}'
    EXEC_PATH='{exec_path}'
    MAX_THREADS={max_threads}

    if [ ! -f "$CORE_PATH" ]; then
        echo "ERROR: core 文件不存在: $CORE_PATH"
        exit 1
    fi

    # 尝试自动定位 dolphindb 可执行文件
    if [ "$EXEC_PATH" = "dolphindb" ]; then
        # 从 core 文件的 file 信息中提取可执行文件路径
        DETECTED=$(file "$CORE_PATH" 2>/dev/null | grep -oP "execfn: '\K[^']+")
        if [ -n "$DETECTED" ] && [ -f "$DETECTED" ]; then
            EXEC_PATH="$DETECTED"
        else
            # 尝试常见路径
            for CANDIDATE in /usr/bin/dolphindb /opt/dolphindb/server/dolphindb; do
                if [ -f "$CANDIDATE" ]; then
                    EXEC_PATH="$CANDIDATE"
                    break
                fi
            done
        fi
    fi

    echo "=== Core Dump Analysis ==="
    echo "Core file: $CORE_PATH"
    echo "Executable: $EXEC_PATH"
    echo ""

    # 检查 gdb 是否可用
    if ! command -v gdb >/dev/null 2>&1; then
        echo "WARNING: gdb 未安装，尝试使用 file 命令获取基本信息"
        file "$CORE_PATH" 2>/dev/null
        exit 0
    fi

    gdb -q "$EXEC_PATH" "$CORE_PATH" \
        -ex "set debuginfod enabled off" \
        -ex "set pagination off" \
        -ex "echo === Signal Info ===\n" \
        -ex "info signal" \
        -ex "echo \n=== Crash Thread Backtrace ===\n" \
        -ex "bt" \
        -ex "echo \n=== All Threads (max $MAX_THREADS) ===\n" \
        -ex "thread apply all bt" \
        -ex "quit" 2>&1 | \
    grep -v "^\[New LWP" | \
    grep -v "^This GDB supports" | \
    grep -v "^<https://" | \
    grep -v "^Enable debuginfod" | \
    grep -v "^\[answered" | \
    grep -v "^Debuginfod has been" | \
    grep -v "^To make this setting" | \
    grep -v "^\[Thread debugging" | \
    grep -v "^Using host libthread" | \
    grep -v "^Reading symbols from" | \
    grep -v "^warning: Can't open file" | \
    grep -v "^Missing separate debuginfo" | \
    grep -v "^Try: " | \
    head -1000
}
