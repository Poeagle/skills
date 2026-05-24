#!/usr/bin/env python3
"""
iCost xlsx → csv 转换工具
用法:
  首次全量导入: python3 ingest.py --file 全量文件.xlsx
  增量追加:     python3 ingest.py --file 增量文件.xlsx

自动将记录按年份拆分到 /Users/ymchen/records/finance/YYYY.csv
丢弃图片相关列，保留约定的列。
"""

import argparse
import os
import pandas as pd
from datetime import datetime

DATA_DIR = os.path.expanduser("~/records/finance")
KEEP_COLS = [
    "日期", "类型", "金额", "一级分类", "二级分类",
    "账户1", "账户2", "备注", "货币", "标签",
    "账本", "位置", "退款", "优惠", "手续费"
]


def convert(filepath: str) -> dict[int, pd.DataFrame]:
    """Read xlsx, group by year, return {year: df}."""
    df = pd.read_excel(filepath, sheet_name="收支账单")

    # Drop image columns
    drop_cols = [c for c in df.columns if c.startswith(("图片链接", "图片附件"))]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    # Keep only known columns (ignore unexpected ones)
    keep = [c for c in KEEP_COLS if c in df.columns]
    df = df[keep]

    # Only keep expense records (用户只关心消费)
    df = df[df["类型"] == "支出"].copy()

    # Parse dates
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df = df.dropna(subset=["日期"])

    # Group by year
    years = {}
    for year, group in df.groupby(df["日期"].dt.year):
        years[int(year)] = group.reset_index(drop=True)
    return years


def append_to_csv(year: int, new_rows: pd.DataFrame):
    """Append new_rows to YYYY.csv, skipping duplicates by (日期, 金额, 备注)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{year}.csv")

    if os.path.exists(path):
        existing = pd.read_csv(path, dtype=str).fillna("")
        # Normalize literal "nan" strings from CSV
        existing = existing.replace("nan", "").replace("NaN", "").replace("None", "")
        # Use 日期+金额+备注 as dedup key
        new_rows_str = new_rows.astype(str).fillna("")
        new_rows_str = new_rows_str.replace("nan", "").replace("NaN", "").replace("None", "")
        existing_key = existing["日期"] + "|" + existing["金额"] + "|" + existing["备注"]
        new_key = new_rows_str["日期"] + "|" + new_rows_str["金额"] + "|" + new_rows_str["备注"]
        # Filter out existing rows
        new_rows = new_rows[~new_key.isin(existing_key)]
        print(f"  {year}: {len(existing)} existing, {len(new_rows)} new to append")
    else:
        print(f"  {year}: file doesn't exist, creating with {len(new_rows)} rows")

    if len(new_rows) == 0:
        return

    # Write header only if file doesn't exist or is empty
    write_header = not (os.path.exists(path) and os.path.getsize(path) > 0)
    new_rows.to_csv(
        path,
        mode="a",
        header=write_header,
        index=False,
        encoding="utf-8"
    )


PROCESSED_LOG = os.path.join(DATA_DIR, "processed.log")


def mark_processed(filepath: str):
    """Append timestamp + filename to processed.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {os.path.basename(filepath)}\n"
    with open(PROCESSED_LOG, "a", encoding="utf-8") as f:
        f.write(line)


def main():
    parser = argparse.ArgumentParser(description="iCost xlsx → csv 转换")
    parser.add_argument("--file", required=True, help="iCost 导出的 xlsx 文件路径")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"❌ 文件不存在: {args.file}")
        return

    print(f"📄 处理: {args.file}")
    years = convert(args.file)
    for year in sorted(years.keys()):
        append_to_csv(year, years[year])
    total = sum(len(v) for v in years.values())
    print(f"✅ 完成，共 {total} 条记录")
    mark_processed(args.file)
    os.remove(args.file)
    print(f"🗑️ 已删除原始文件: {args.file}")


if __name__ == "__main__":
    main()
