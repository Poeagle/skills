#!/bin/bash
# Trace 文件操作脚本
# 包含 trace 目录浏览和文件搜索功能



# @description 列出 trace 目录最近修改的文件（path 自动使用节点 traceLogDir）
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, limit:int:optional:default=20:max=100
# @permission readonly
listTraceFiles() {
    [ -d {path} ] && find {path} -maxdepth 1 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS|%s|%p\n' 2>/dev/null | sort -r | head -{limit} || echo 'trace directory not found: {path}'
}

# @description 查看指定 trace 文件末尾内容；未传具体文件时默认选择目录中的最近文件。输出含文件 mtime（让 LLM 判断是否陈旧）
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, lines:int:optional:default=100:max=1000
# @permission readonly
tailTraceFile() {
    TARGET={path}
    if [ -d "$TARGET" ]; then
        FILE=$(find "$TARGET" -maxdepth 1 -type f -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -1 | cut -d'|' -f2-)
        if [ -n "$FILE" ]; then TARGET="$FILE"; else echo 'no trace file found in directory: {path}'; exit 0; fi
    fi
    if [ ! -f "$TARGET" ]; then echo 'trace file not found: {path}'; exit 0; fi
    NOW_TS=$(date +%s); FILE_MTIME=$(stat -c %Y "$TARGET" 2>/dev/null || echo 0)
    AGE_MIN=$(( (NOW_TS - FILE_MTIME) / 60 ))
    AGE_HUMAN="${AGE_MIN} min ago"
    if [ "$AGE_MIN" -ge 1440 ]; then AGE_HUMAN="$((AGE_MIN / 1440)) day ago"
    elif [ "$AGE_MIN" -ge 60 ]; then AGE_HUMAN="$((AGE_MIN / 60)) hour ago"; fi
    echo "__PATH__:$TARGET"
    echo "__FILE_MTIME__: $(date -d "@$FILE_MTIME" '+%Y-%m-%d %H:%M:%S') ($AGE_HUMAN)"
    [ "$AGE_MIN" -ge 60 ] && echo "(WARNING: trace file has not been written for $AGE_HUMAN; tail content is stale)"
    tail -{lines} "$TARGET"
}

# @description 按关键词搜索指定 trace 文件；未传具体文件时默认选择目录中的最近文件。输出含文件 mtime
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, pattern:str:required:allow_chars=|, lines:int:optional:default=50:max=500
# @permission readonly
getTraceFile() {
    TARGET={path}
    if [ -d "$TARGET" ]; then
        FILE=$(find "$TARGET" -maxdepth 1 -type f -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -1 | cut -d'|' -f2-)
        if [ -n "$FILE" ]; then TARGET="$FILE"; else echo 'no trace file found in directory: {path}'; exit 0; fi
    fi
    if [ ! -f "$TARGET" ]; then echo 'trace file not found: {path}'; exit 0; fi
    NOW_TS=$(date +%s); FILE_MTIME=$(stat -c %Y "$TARGET" 2>/dev/null || echo 0)
    AGE_MIN=$(( (NOW_TS - FILE_MTIME) / 60 ))
    AGE_HUMAN="${AGE_MIN} min ago"
    if [ "$AGE_MIN" -ge 1440 ]; then AGE_HUMAN="$((AGE_MIN / 1440)) day ago"
    elif [ "$AGE_MIN" -ge 60 ]; then AGE_HUMAN="$((AGE_MIN / 60)) hour ago"; fi
    echo "__PATH__:$TARGET"
    echo "__FILE_MTIME__: $(date -d "@$FILE_MTIME" '+%Y-%m-%d %H:%M:%S') ($AGE_HUMAN)"
    [ "$AGE_MIN" -ge 60 ] && echo "(WARNING: trace file has not been written for $AGE_HUMAN; matches below are stale)"
    grep -iE '{pattern}' "$TARGET" | tail -{lines}
}

# @description 在 trace 目录内跨文件搜索关键词（path 自动使用节点 traceLogDir）
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, pattern:str:required:allow_chars=|, lines:int:optional:default=20:max=200
# @permission readonly
searchTraceFiles() {
    if [ -d {path} ]; then grep -Rin -E '{pattern}' {path} 2>/dev/null | head -{lines}; else echo 'trace directory not found: {path}'; fi
}
