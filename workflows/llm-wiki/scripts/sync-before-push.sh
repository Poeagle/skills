#!/bin/bash
# ============================================================
# sync-llm-wiki.sh
# 在 push 前将 llm-wiki 的软链接替换为实体文件，
# 同步目录骨架（仅第一级子目录），更新 README 的目录树。
# ============================================================
set -e

LLM_WIKI_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_DIR="/Users/ymchen/obsidian/zenWiki"

echo "[sync-llm-wiki] 开始同步..."

# ----------------------------------------------------------
# 1. CLAUDE.md：如果是软链接，替换为实体内容
# ----------------------------------------------------------
if [ -L "$LLM_WIKI_DIR/CLAUDE.md" ]; then
    echo "[sync-llm-wiki]   -> CLAUDE.md 转为实体文件"
    cp "$LLM_WIKI_DIR/CLAUDE.md" "$LLM_WIKI_DIR/CLAUDE.md.real"
    mv "$LLM_WIKI_DIR/CLAUDE.md.real" "$LLM_WIKI_DIR/CLAUDE.md"
    git -C "$LLM_WIKI_DIR" add "CLAUDE.md"
fi

# ----------------------------------------------------------
# 2. 目录骨架：同步 raw/ wiki/ assets/ 的第一级子目录
# ----------------------------------------------------------
echo "[sync-llm-wiki]   -> 同步目录骨架"

sync_top_dirs() {
    local base_dir="$1"
    local vault_path="$VAULT_DIR/$base_dir"
    local target_base="$LLM_WIKI_DIR/$base_dir"

    if [ ! -d "$vault_path" ]; then return; fi

    mkdir -p "$target_base"
    touch "$target_base/.gitkeep"

    for subdir in "$vault_path"/*/; do
        [ -d "$subdir" ] || continue
        subname=$(basename "$subdir")
        target="$target_base/$subname"
        if [ ! -d "$target" ]; then
            mkdir -p "$target"
            echo "     + 创建 $base_dir/$subname/"
        fi
        touch "$target/.gitkeep"
    done

    for existing in "$target_base"/*/; do
        [ -d "$existing" ] || continue
        existing_name=$(basename "$existing")
        [ "$existing_name" = ".gitkeep" ] && continue
        if [ ! -d "$vault_path/$existing_name" ]; then
            rm -rf "$existing"
            echo "     - 移除 $base_dir/$existing_name/"
        fi
    done
}

sync_top_dirs "raw"
sync_top_dirs "wiki"
sync_top_dirs "assets"

git -C "$LLM_WIKI_DIR" add "raw/" "wiki/" "assets/" 2>/dev/null || true

# ----------------------------------------------------------
# 3. 更新 README.md 的目录树章节
# ----------------------------------------------------------
echo "[sync-llm-wiki]   -> 更新 README 目录树"

python3 "$LLM_WIKI_DIR/scripts/update_readme_tree.py" "$LLM_WIKI_DIR/README.md" "$VAULT_DIR/raw"

git -C "$LLM_WIKI_DIR" add "README.md"

echo "[sync-llm-wiki]  同步完成"
