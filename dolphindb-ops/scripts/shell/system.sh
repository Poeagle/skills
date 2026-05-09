#!/bin/bash
# 系统资源诊断脚本
# 包含磁盘、内存、CPU、IO、网络、时间同步等系统级检查



# @description 系统运行态：系统/进程内存 + 系统/进程 CPU + 磁盘/进程 IO + 与节点相关的 dmesg(默认仅近30分钟) + 端口监听
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, port:int:required, dmesg_lines:int:optional:default=50:max=200, dmesg_minutes:int:optional:default=30:max=1440, include_historical_dmesg:str:optional:default=false:pattern=^(true|false)$
# @collect crash, node-down, oom, system-hang, stream-delay, startup-failure
# @permission readonly
checkSystemRuntime() {
    PID=$(ss -tlnp 2>/dev/null | grep ":{port} " | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)
    COMM=''
    if [ -n "$PID" ] && [ -r /proc/$PID/comm ]; then
        COMM=$(cat /proc/$PID/comm 2>/dev/null)
    fi

    echo "=== Memory (system) ==="
    free -h
    echo ""

    echo "=== Memory (process pid=$PID) ==="
    if [ -n "$PID" ]; then
        grep -E '^(VmSize|VmRSS|VmPeak|VmHWM|VmSwap|Threads):' /proc/$PID/status 2>/dev/null
    else
        echo "process not found on port {port}"
    fi
    echo ""

    echo "=== CPU (system) ==="
    top -bn1 | head -5
    echo ""

    echo "=== CPU (process pid=$PID) ==="
    if [ -n "$PID" ]; then
        top -bn1 -p $PID | tail -2
    else
        echo "process not found on port {port}"
    fi
    echo ""

    echo "=== Disk IO (path={path}) ==="
    DEVICE=$(df {path} 2>/dev/null | tail -1 | awk '{print $1}' | xargs basename 2>/dev/null)
    echo "device: $DEVICE"
    iostat -xm $DEVICE 1 1 2>/dev/null || {
        RAW=$(grep " $DEVICE " /proc/diskstats 2>/dev/null)
        if [ -n "$RAW" ]; then
            set -- $RAW
            echo "reads_completed: $4"
            echo "reads_merged: $5"
            echo "sectors_read: $6"
            echo "read_time_ms: $7"
            echo "writes_completed: $8"
            echo "writes_merged: $9"
            echo "sectors_written: ${10}"
            echo "write_time_ms: ${11}"
            echo "io_in_progress: ${12}"
            echo "io_time_ms: ${13}"
        else
            echo "no disk stats available"
        fi
    }
    echo ""

    echo "=== Process IO (pid=$PID) ==="
    if [ -n "$PID" ]; then
        cat /proc/$PID/io 2>/dev/null || echo 'no process io stats (need root?)'
    else
        echo "process not found on port {port}"
    fi
    echo ""

    # ── dmesg：默认只看最近 dmesg_minutes 分钟（避免把陈年崩溃当现场证据） ──
    DMESG_FILTER='oom|killed process|segfault|Out of memory|trap'
    if [ -n "$PID" ]; then
        DMESG_NARROW="(^|[[:space:]])$COMM\[[0-9]+\]|Killed process [0-9]+ \($COMM\)|traps: $COMM\[[0-9]+\]|\[$PID\]|pid[ =]$PID|process[ =]$PID"
    else
        DMESG_NARROW='dolphindb|oom|killed process|segfault|Out of memory|trap'
    fi

    echo "=== dmesg (recent {dmesg_minutes} min, filtered) ==="
    NOW_TS=$(date +%s)
    SINCE_TS=$((NOW_TS - {dmesg_minutes} * 60))
    RECENT_OUT=$(dmesg -T 2>/dev/null | awk -v since="$SINCE_TS" '
        match($0, /^\[([^]]+)\]/, m) {
            cmd = "date -d \"" m[1] "\" +%s"
            cmd | getline ts
            close(cmd)
            if (ts >= since) print
        }
    ' | grep -iE "$DMESG_FILTER" | grep -iE "$DMESG_NARROW" | tail -{dmesg_lines})
    if [ -z "$RECENT_OUT" ]; then
        echo "(no matching dmesg entries in the last {dmesg_minutes} min)"
    else
        [ -n "$PID" ] && echo "PID=$PID  COMM=$COMM"
        echo "$RECENT_OUT"
    fi
    echo ""

    if [ "{include_historical_dmesg}" = "true" ]; then
        echo "=== dmesg (HISTORICAL, older than {dmesg_minutes} min) ==="
        echo "(NOTE: these are stale entries — do not treat as ongoing failures unless cross-confirmed with current logs/process state)"
        HIST_OUT=$(dmesg -T 2>/dev/null | awk -v since="$SINCE_TS" '
            match($0, /^\[([^]]+)\]/, m) {
                cmd = "date -d \"" m[1] "\" +%s"
                cmd | getline ts
                close(cmd)
                if (ts < since) print
            }
        ' | grep -iE "$DMESG_FILTER" | grep -iE "$DMESG_NARROW" | tail -{dmesg_lines})
        if [ -z "$HIST_OUT" ]; then
            echo "(no matching historical entries)"
        else
            echo "$HIST_OUT"
        fi
    else
        echo "(historical dmesg suppressed; pass include_historical_dmesg=true to inspect entries older than {dmesg_minutes} min)"
    fi
    echo ""

    echo "=== Port listening (:{port}) ==="
    ss -tlnp 2>/dev/null | grep -E 'State|:{port}' || netstat -tlnp 2>/dev/null | grep -E 'Proto|:{port}' || echo 'not listening'
}

# @description 系统配置/限制：时间同步 + core dump 配置 + noexec 挂载 + 内核 overcommit + 进程 ulimit/limits
# @params port:int:required
# @collect crash, oom, startup-failure, system-hang
# @permission readonly
checkSystemConfig() {
    PID=$(ss -tlnp 2>/dev/null | grep ":{port} " | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)

    echo "=== Time Sync ==="
    timedatectl status 2>/dev/null || chronyc tracking 2>/dev/null || ntpq -p 2>/dev/null || echo 'no time sync tool found'
    echo ""

    echo "=== Core Dump Settings ==="
    echo "ulimit -c: $(ulimit -c)"
    echo "core_pattern: $(cat /proc/sys/kernel/core_pattern 2>/dev/null || echo 'cannot read')"
    echo ""

    echo "=== noexec Mounts ==="
    mount | grep noexec || echo 'no noexec mounts found'
    echo ""

    echo "=== Kernel Overcommit ==="
    echo "vm.overcommit_memory: $(cat /proc/sys/vm/overcommit_memory 2>/dev/null)"
    echo ""

    echo "=== Shell ulimit -a ==="
    ulimit -a
    echo ""

    echo "=== Process limits (pid=$PID) ==="
    if [ -n "$PID" ]; then
        cat /proc/$PID/limits 2>/dev/null || echo 'cannot read process limits'
    else
        echo "process not found on port {port}"
    fi
}

# @description 磁盘维度全景：df -h + du -sh + df -i（多路径）
# @params paths:str:required:pattern=^[a-zA-Z0-9_./@:~-][a-zA-Z0-9_./@:~ /;-]*$
# @collect crash, disk-full, metadata-repair, node-down, startup-failure
# @permission readonly
checkDiskUsage() {
    echo "=== Filesystem Usage (df -h) ==="
    df -h {paths} 2>/dev/null | awk 'NR==1 || !seen[$0]++ {print}'
    echo ""

    echo "=== Directory Size (du -sh) ==="
    du -sh {paths} 2>/dev/null
    echo ""

    echo "=== Inode Usage (df -i) ==="
    df -i {paths} 2>/dev/null | awk 'NR==1 || !seen[$0]++ {print}'
}

# @description 查看目标节点的配置文件内容（config_path 自动使用节点配置文件路径）
# @params config_path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$
# @permission readonly
checkConfigFile() {
    cat {config_path} 2>/dev/null || echo 'config file not found'
}

# @description 搜索所有DolphinDB License文件路径
# @params install_dir:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$
# @collect license
# @permission readonly
findLicenseFiles() {
    find {install_dir} -maxdepth 3 -name '*.lic' -type f 2>/dev/null | head -20 || echo 'no license files found'
}

# @description 检查指定插件的动态库依赖是否完整
# @params plugin_path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$
# @permission readonly
checkPluginDeps() {
    for so in {plugin_path}/lib*.so {plugin_path}/*.so; do if [ -f "$so" ]; then echo "=== $so ==="; ldd "$so" 2>/dev/null | grep -E 'not found|error' || echo 'all dependencies OK'; fi; done
}

# @description 列出目录下文件和子目录的空间占用（按大小降序排列），用于定位磁盘空间瓶颈。路径必须在节点已知目录范围内
# @params target_dir:str:required:pattern=^[a-zA-Z0-9_./@:~-][a-zA-Z0-9_./@:~ /-]*$
# @permission readonly
listDirUsage() {
    echo "=== TOTAL ==="; du -sh "{target_dir}" 2>/dev/null; echo "=== TOP ITEMS (by size) ==="; du -ah "{target_dir}" --max-depth=1 2>/dev/null | sort -rh | head -30
}

# @description 清理单个文件。mode=delete 删除（跳过被写入的），mode=truncate 截断为0字节（适合活跃日志）。默认 dry_run=true 仅预览。路径必须在节点已知目录范围内
# @params target_path:str:required:pattern=^[a-zA-Z0-9_./@:~-][a-zA-Z0-9_./@:~ /-]*$
# @params mode:str:optional:default=delete:pattern=^(delete|truncate)$
# @params dry_run:str:optional:default=true:pattern=^(true|false)$
# @permission irreversible
cleanFile() {
    T="{target_path}"; [ ! -f "$T" ] && echo "ERROR: $T not found or not a file" && return 1; S=$(du -sh "$T" | cut -f1); if [ "{dry_run}" = "false" ]; then if [ "{mode}" = "truncate" ]; then truncate -s 0 "$T" && echo "TRUNCATED: $T (was $S)"; else W=$(fuser -w "$T" 2>/dev/null); if [ -n "$W" ]; then echo "SKIPPED: $T held by PID $W (use mode=truncate for active files)"; else rm -f "$T" && echo "DELETED: $T ($S freed)"; fi; fi; else echo "DRY_RUN: would {mode} $T ($S)"; fi
}
