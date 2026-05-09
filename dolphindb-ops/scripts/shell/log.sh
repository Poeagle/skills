#!/bin/bash
# 日志查看与搜索脚本
# 通过 log_type 一站式访问 7 类日志：runtime / audit / query / acl_audit / job / raw_script / redo



# @description 按 log_type 搜索日志，默认仅近 since_minutes 分钟内的匹配（避免老错误被当现场证据）
# @params log_type:str:required:pattern=^(runtime|audit|query|acl_audit|job|raw_script|redo)$, path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, pattern:str:required:allow_chars=|, lines:int:optional:default=50:max=500, since_minutes:int:optional:default=60:max=10080
# @collect async-replication, crash, disk-full, metadata-repair, node-down, oom, startup-failure, system-hang
# @collect_args oom pattern=OOM|MemoryException|bad_alloc|out.of.memory|Cannot.allocate
# @collect_args crash pattern=segfault|SIGSEGV|core.dump|signal.11|Aborted|Fatal.error
# @collect_args node-down pattern=heartbeat|connection.refused|node.*offline|Cannot.reach
# @collect_args startup-failure pattern=Failed.to.start|Cannot.bind|permission.denied|Cannot.find.license|Cannot.open
# @collect_args system-hang pattern=deadlock|hang|frozen|no.response|timeout|thread.blocked
# @collect_args metadata-repair pattern=chunk|metadata|corrupt|inconsist|recover.*fail
# @collect_args disk-full pattern=No.space|disk.full|write.failed|ENOSPC|Disk.quota
# @collect_args async-replication pattern=replication|raft|sync.*fail|recover|async.*replica
# @permission readonly
getLogs() {
    TARGET={path}
    LOG_TYPE={log_type}

    # raw_script / redo 类型的 path 可能是目录，需自动探测最新匹配文件
    if [ "$LOG_TYPE" = "raw_script" ] && [ -d "$TARGET" ]; then
        FILE=$(find "$TARGET" -maxdepth 2 -type f \( -name '*raw*script*.log' -o -name '*rawScript*.log' -o -name '*raw_script*.log' \) -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -1 | cut -d'|' -f2-)
        if [ -n "$FILE" ]; then
            TARGET="$FILE"
        else
            echo "raw script log not found in directory: {path}"
            exit 0
        fi
    elif [ "$LOG_TYPE" = "redo" ] && [ -d "$TARGET" ]; then
        FILE=$(find "$TARGET" -maxdepth 4 -type f \( -name '*redo*.log' -o -name 'redo*' -o -name '*.redo*' \) -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -1 | cut -d'|' -f2-)
        if [ -n "$FILE" ]; then
            TARGET="$FILE"
        else
            echo "redo log not found in directory: {path}"
            exit 0
        fi
    fi

    if [ ! -f "$TARGET" ]; then
        echo "log file not found: $TARGET"
        exit 0
    fi

    echo "__PATH__:$TARGET"
    SINCE_TS=$(date -d "{since_minutes} minutes ago" +%s 2>/dev/null)
    NOW_TS=$(date +%s)
    FILE_MTIME=$(stat -c %Y "$TARGET" 2>/dev/null || echo 0)
    AGE_SEC=$((NOW_TS - FILE_MTIME))
    AGE_MIN=$((AGE_SEC / 60))
    echo "__WINDOW__: last {since_minutes} min (since $(date -d "@$SINCE_TS" '+%Y-%m-%d %H:%M:%S') -> now)"
    echo "__FILE_MTIME__: $(date -d "@$FILE_MTIME" '+%Y-%m-%d %H:%M:%S') (last write ${AGE_MIN} min ago)"

    # awk 按 DolphinDB 时间戳过滤（YYYY-MM-DD[ T]HH:MM:SS），无时间戳的续行跟随上一条状态
    awk -v since="$SINCE_TS" '
        match($0, /^([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})/, m) {
            ts = mktime(m[1] " " m[2] " " m[3] " " m[4] " " m[5] " " m[6])
            in_win = (ts >= since) ? 1 : 0
            if (in_win) print
            next
        }
        { if (in_win) print }
    ' "$TARGET" | grep -iE '{pattern}' | tail -{lines}

    # 提示：若窗内无匹配，给个明显的标记
    MATCH_COUNT=$(awk -v since="$SINCE_TS" '
        match($0, /^([0-9]{4})-([0-9]{2})-([0-9]{2})[T ]([0-9]{2}):([0-9]{2}):([0-9]{2})/, m) {
            ts = mktime(m[1] " " m[2] " " m[3] " " m[4] " " m[5] " " m[6])
            in_win = (ts >= since) ? 1 : 0
            if (in_win) print
            next
        }
        { if (in_win) print }
    ' "$TARGET" | grep -ciE '{pattern}')
    echo "__MATCH_COUNT__: $MATCH_COUNT in window"
    if [ "$MATCH_COUNT" -eq 0 ]; then
        echo "(no matching entries in last {since_minutes} min; pass since_minutes=N to widen window if you need to inspect older entries)"
    fi
}

# @description 按 log_type 查看日志末尾内容（path 由 MCP 自动按节点配置解析）
# @params log_type:str:required:pattern=^(runtime|audit|query|acl_audit|job|raw_script|redo)$, path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, lines:int:optional:default=100:max=1000
# @collect startup-failure
# @permission readonly
tailLogs() {
    TARGET={path}
    LOG_TYPE={log_type}

    if [ "$LOG_TYPE" = "raw_script" ] && [ -d "$TARGET" ]; then
        FILE=$(find "$TARGET" -maxdepth 2 -type f \( -name '*raw*script*.log' -o -name '*rawScript*.log' -o -name '*raw_script*.log' \) -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -1 | cut -d'|' -f2-)
        if [ -n "$FILE" ]; then
            TARGET="$FILE"
        else
            echo "raw script log not found in directory: {path}"
            exit 0
        fi
    elif [ "$LOG_TYPE" = "redo" ] && [ -d "$TARGET" ]; then
        FILE=$(find "$TARGET" -maxdepth 4 -type f \( -name '*redo*.log' -o -name 'redo*' -o -name '*.redo*' \) -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -1 | cut -d'|' -f2-)
        if [ -n "$FILE" ]; then
            TARGET="$FILE"
        else
            echo "redo log not found in directory: {path}"
            exit 0
        fi
    fi

    if [ ! -f "$TARGET" ]; then
        echo "log file not found: $TARGET"
        exit 0
    fi

    NOW_TS=$(date +%s)
    FILE_MTIME=$(stat -c %Y "$TARGET" 2>/dev/null || echo 0)
    AGE_SEC=$((NOW_TS - FILE_MTIME))
    AGE_MIN=$((AGE_SEC / 60))
    AGE_HUMAN="${AGE_MIN} min ago"
    if [ "$AGE_MIN" -ge 1440 ]; then
        AGE_HUMAN="$((AGE_MIN / 1440)) day ago"
    elif [ "$AGE_MIN" -ge 60 ]; then
        AGE_HUMAN="$((AGE_MIN / 60)) hour ago"
    fi

    echo "__PATH__:$TARGET"
    echo "__FILE_MTIME__: $(date -d "@$FILE_MTIME" '+%Y-%m-%d %H:%M:%S') ($AGE_HUMAN)"
    if [ "$AGE_MIN" -ge 60 ]; then
        echo "(WARNING: log file has not been written for $AGE_HUMAN; the tail below is stale, not current activity)"
    fi
    tail -{lines} "$TARGET"
}
