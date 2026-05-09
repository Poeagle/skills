#!/bin/bash
# Batch Job 文件操作脚本
# 包含 batch job 目录浏览和文件搜索功能



# @description 列出 batch job 目录最近修改的文件（path 自动使用节点 batchJobDir）
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, limit:int:optional:default=20:max=100
# @permission readonly
listBatchJobFiles() {
    [ -d {path} ] && find {path} -maxdepth 2 -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS|%s|%p\n' 2>/dev/null | sort -r | head -{limit} || echo 'batch job directory not found: {path}'
}

# @description 查看指定 batch job 文件末尾内容；未传具体文件时默认选择目录中的最近文件
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, lines:int:optional:default=100:max=1000
# @permission readonly
tailBatchJobFile() {
    TARGET={path}; if [ -f "$TARGET" ]; then tail -{lines} "$TARGET"; elif [ -d "$TARGET" ]; then FILE=$(find "$TARGET" -maxdepth 2 -type f -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -1 | cut -d'|' -f2-); [ -n "$FILE" ] && tail -{lines} "$FILE" || echo 'no batch job file found in directory: {path}'; else echo 'batch job file not found: {path}'; fi
}

# @description 按关键词搜索指定 batch job 文件；未传具体文件时默认选择目录中的最近文件
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, pattern:str:required:allow_chars=|, lines:int:optional:default=50:max=500
# @permission readonly
getBatchJobFile() {
    TARGET={path}; if [ -f "$TARGET" ]; then echo '__PATH__:'"$TARGET"; grep -iE '{pattern}' "$TARGET" | tail -{lines}; elif [ -d "$TARGET" ]; then FILE=$(find "$TARGET" -maxdepth 2 -type f -printf '%T@|%p\n' 2>/dev/null | sort -nr | head -1 | cut -d'|' -f2-); [ -n "$FILE" ] && { echo '__PATH__:'"$FILE"; grep -iE '{pattern}' "$FILE" | tail -{lines}; } || echo 'no batch job file found in directory: {path}'; else echo 'batch job file not found: {path}'; fi
}

# @description 在 batch job 目录内跨文件搜索关键词（path 自动使用节点 batchJobDir）
# @params path:str:required:pattern=^[a-zA-Z0-9_./@:~ /-][a-zA-Z0-9_./@:~ /-]*$, pattern:str:required:allow_chars=|, lines:int:optional:default=20:max=200
# @permission readonly
searchBatchJobFiles() {
    if [ -d {path} ]; then grep -Rin -E '{pattern}' {path} 2>/dev/null | head -{lines}; else echo 'batch job directory not found: {path}'; fi
}
