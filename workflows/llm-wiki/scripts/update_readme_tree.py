#!/usr/bin/env python3
"""更新 llm-wiki README 的目录树章节。"""
import re, os, sys

readme_path = sys.argv[1]
vault_raw_dir = sys.argv[2]

with open(readme_path, 'r') as f:
    content = f.read()

# 获取 vault 实际 raw/ 子目录
raw_dirs = []
if os.path.isdir(vault_raw_dir):
    for d in sorted(os.listdir(vault_raw_dir)):
        if os.path.isdir(os.path.join(vault_raw_dir, d)):
            raw_dirs.append(d)

# 生成 raw/ 子树
raw_lines = ''
count = len(raw_dirs)
descs = {
    '01-articles': '# 网页剪藏文章', '02-papers': '# 论文 PDF',
    '03-transcripts': '# 视频/播客转录', '04-weread': '# 微信读书划线笔记（自动同步）',
    '05-coderepo': '# 代码仓库工作区', '09-archive': '# 已处理文件归档（仅追加，不读取）'
}
for i, d in enumerate(raw_dirs):
    prefix = '└──' if i == count - 1 else '├──'
    padded = (d + '/').ljust(15)
    desc = descs.get(d, '')
    raw_lines += '│   {} {} {}\n'.format(prefix, padded, desc)

# 生成 wiki/ 子树
wiki_dirs = ['code-design', 'concepts', 'entities', 'sources', 'syntheses']
wiki_descs = {
    'code-design': '# 软件设计文档', 'sources': '# 来源摘要',
    'entities': '# 实体', 'concepts': '# 概念', 'syntheses': '# 综合研究'
}
wiki_lines = ''
for d in wiki_dirs:
    padded = (d + '/').ljust(15)
    wiki_lines += '│   ├── {} {}\n'.format(padded, wiki_descs.get(d, ''))

# 组装完整目录树
new_tree = u'''## 目录结构

```
llm-wiki/
├── CLAUDE.md              # 项目指令（从 vault 同步）
├── raw/                   # 原始资料收件箱
{}
├── wiki/                  # 知识编译输出层
{}
│   ├── index.md           # 全局内容字典
│   └── log.md             # 操作日志
└── assets/                # 媒体资产
```
'''.format(raw_lines, wiki_lines)

pattern = r'## 目录结构[\s\S]*?(?=\n## |\n*$)'
result = re.sub(pattern, new_tree.rstrip('\n'), content)

with open(readme_path, 'w') as f:
    f.write(result)

print("README tree updated")
