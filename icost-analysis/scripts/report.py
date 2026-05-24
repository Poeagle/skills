#!/usr/bin/env python3
"""
iCost 每周一 07:00 自动报告
功能:
  1. 扫描未处理的 xlsx → ingest
  2. 漏传检测
  3. 分析上周/本月/本年消费
  4. 生成微信报告
  5. 资产提醒
"""

import os
import sys
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

SKILL_DIR = os.path.expanduser("~/.claude/skills/icost-analysis")
DATA_DIR = os.path.expanduser("~/records/finance")
PROCESSED_LOG = os.path.join(DATA_DIR, "processed.log")
WECHAT_TARGET = "weixin:o9cq80x2hrS1kO_XsyEc63iSf5gg@im.wechat"
MONTHLY_TARGET = 4000  # 动态预算目标，可调整
FIRE_TARGET = 1500000

sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
import ingest


# ── helpers ──────────────────────────────────────────────────────────

def load_csv(year: int) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{year}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    df["日期_dt"] = pd.to_datetime(df["日期"], errors="coerce")
    df["金额_n"] = pd.to_numeric(df["金额"], errors="coerce").fillna(0)
    df["退款_n"] = pd.to_numeric(df["退款"], errors="coerce").fillna(0)
    df["净支出"] = df["金额_n"] + df["退款_n"]
    return df.dropna(subset=["日期_dt"])


def week_range(d: datetime) -> tuple:
    """Return (monday_start, sunday_end) for the week containing d."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday.replace(hour=0, minute=0, second=0), sunday.replace(hour=23, minute=59, second=59)


def last_week_range() -> tuple:
    """Return (monday, sunday) for last week."""
    today = datetime.now()
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday = this_monday - timedelta(days=1)
    return last_monday.replace(hour=0, minute=0, second=0), last_sunday.replace(hour=23, minute=59, second=59)


def month_range(y: int, m: int) -> tuple:
    import calendar
    last_day = calendar.monthrange(y, m)[1]
    return (datetime(y, m, 1), datetime(y, m, last_day, 23, 59, 59))


def send_wechat(msg: str):
    """Send message via Hermes send."""
    # Write message to temp file to avoid shell escaping issues
    tmpfile = "/tmp/icost_weekly_report.txt"
    with open(tmpfile, "w", encoding="utf-8") as f:
        f.write(msg)
    cmd = f"hermes send -t weixin:o9cq80x2hrS1kO_XsyEc63iSf5gg@im.wechat -f {tmpfile}"
    ret = os.system(cmd)
    if ret != 0:
        print(f"⚠️ 微信发送失败 (exit={ret})")
        print("=" * 40)
        print(msg)
        print("=" * 40)


# ── step 1: scan & ingest ────────────────────────────────────────────

def step_scan_and_ingest() -> int:
    """Returns number of files processed."""
    os.makedirs(DATA_DIR, exist_ok=True)
    processed = set()
    if os.path.exists(PROCESSED_LOG):
        with open(PROCESSED_LOG) as f:
            processed = set(line.strip() for line in f if line.strip())

    xlsx_files = glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
    new_files = [f for f in xlsx_files if os.path.basename(f) not in processed]

    if not new_files:
        return 0

    for fpath in new_files:
        fname = os.path.basename(fpath)
        try:
            years = ingest.convert(fpath)
            for year in sorted(years.keys()):
                ingest.append_to_csv(year, years[year])
            with open(PROCESSED_LOG, "a") as f:
                f.write(fname + "\n")
            os.remove(fpath)
            print(f"✅ {fname} → csv, 已删除原始文件")
        except Exception as e:
            print(f"❌ {fname} 处理失败: {e}")

    return len(new_files)


# ── step 2: missing file check ───────────────────────────────────────

def step_missing_check():
    """Check if last record is from last week. If not, remind."""
    today = datetime.now()
    year = today.year
    df = load_csv(year)
    if df.empty:
        send_wechat("📌 上周未上传消费记录，且年度 csv 为空，请检查 iCost 导出。")
        return

    last_date = df["日期_dt"].max()
    lw_start, lw_end = last_week_range()
    if last_date < lw_start:
        lw_str = f"{lw_start.strftime('%m/%d')}-{lw_end.strftime('%m/%d')}"
        send_wechat(
            f"📌 消费数据提醒：年度 csv 最后一条记录是 {last_date.strftime('%m/%d')}，"
            f"早于上周 ({lw_str})，可能忘记上传 iCost 导出。"
        )


# ── step 3: analysis ─────────────────────────────────────────────────

def analyze_period(df: pd.DataFrame, label: str, start: datetime, end: datetime, prev_start: datetime = None, prev_end: datetime = None) -> str:
    """Analyze spending in [start, end], compare with [prev_start, prev_end] if given."""
    mask = (df["日期_dt"] >= start) & (df["日期_dt"] <= end) & (df["类型"] == "支出")
    period = df[mask]

    if period.empty:
        return f"\n## 📆 {label}\n无支出记录。\n"

    total = abs(period["净支出"].sum())
    lines = [f"\n## 📆 {label}\n"]
    lines.append(f"总支出：¥{total:.0f} ({len(period)} 笔)")

    # Category breakdown
    cat_sum = period.groupby("一级分类")["净支出"].apply(lambda x: abs(x.sum())).sort_values(ascending=False)
    lines.append("\n分类明细：")
    for cat, amt in cat_sum.items():
        pct = amt / total * 100
        lines.append(f"  • {cat}：¥{amt:.0f} ({pct:.0f}%) - {len(period[period['一级分类']==cat])} 笔")

    # Prev period comparison
    if prev_start and prev_end:
        prev_mask = (df["日期_dt"] >= prev_start) & (df["日期_dt"] <= prev_end) & (df["类型"] == "支出")
        prev_total = abs(df[prev_mask]["净支出"].sum())
        if prev_total > 0:
            change = (total - prev_total) / prev_total * 100
            sign = "+" if change > 0 else ""
            lines.append(f"\n环比：¥{prev_total:.0f} → ¥{total:.0f} ({sign}{change:.0f}%)")

    # Anomaly detection (single item > 2σ of its category)
    anomalies = []
    for cat in cat_sum.index:
        cat_data = period[period["一级分类"] == cat]
        vals = abs(cat_data["净支出"])
        if len(vals) >= 3:
            mean_v = vals.mean()
            std_v = vals.std()
            outliers = cat_data[abs(cat_data["净支出"]) > (mean_v + 2 * std_v)]
            for _, row in outliers.iterrows():
                anomalies.append(f"  🔺 {row['日期_dt'].strftime('%m/%d')} {cat} ¥{abs(row['净支出']):.0f} 「{row['备注']}」")

    if anomalies:
        lines.append("\n异常大额：")
        lines.extend(anomalies)

    return "\n".join(lines)


def step_analyze() -> str:
    """Generate full analysis report."""
    today = datetime.now()
    year = today.year
    df = load_csv(year)

    # Also load previous year for year-over-year
    df_prev = load_csv(year - 1) if year > 2024 else pd.DataFrame()
    df_all = pd.concat([df_prev, df], ignore_index=True) if not df_prev.empty else df

    lines = ["📊 消费周报\n" + "=" * 30]

    # Last week
    lw_s, lw_e = last_week_range()
    prev_lw_s = lw_s - timedelta(days=7)
    prev_lw_e = lw_s - timedelta(days=1)
    lines.append(analyze_period(df_all, "上周", lw_s, lw_e, prev_lw_s, prev_lw_e))

    # This month
    ms, me = month_range(today.year, today.month)
    prev_ms, prev_me = month_range(today.year, today.month - 1) if today.month > 1 else month_range(today.year - 1, 12)
    lines.append(analyze_period(df_all, "本月累计", ms, min(me, today), prev_ms, prev_me))

    # This year
    ys = datetime(today.year, 1, 1)
    ye = datetime(today.year, today.month, today.day, 23, 59, 59)
    lines.append(analyze_period(df_all, "本年累计", ys, ye))

    # FIRE progress
    year_df = load_csv(year)
    year_mask = (year_df["日期_dt"] >= ys) & (year_df["日期_dt"] <= ye) & (year_df["类型"] == "支出")
    year_total = abs(year_df[year_mask]["净支出"].sum())
    days_passed = (today - ys).days + 1
    daily_avg = year_total / days_passed
    projected_year = daily_avg * 365
    monthly_avg = year_total / (today.month)

    lines.append(f"\n## 🎯 FIRE 进度")
    lines.append(f"本年已支出：¥{year_total:.0f}（{days_passed} 天）")
    lines.append(f"日均支出：¥{daily_avg:.0f}")
    lines.append(f"年化推算：¥{projected_year:.0f}")
    lines.append(f"月均支出：¥{monthly_avg:.0f}（目标 ¥{MONTHLY_TARGET:.0f}）")

    if monthly_avg > MONTHLY_TARGET:
        overspend = monthly_avg - MONTHLY_TARGET
        lines.append(f"⚠️ 超出月目标 ¥{overspend:.0f}，需关注")
    else:
        underspend = MONTHLY_TARGET - monthly_avg
        lines.append(f"✅ 低于月目标 ¥{underspend:.0f}，继续保持")

    # Simple suggestions
    lines.append(f"\n## 💡 建议")
    # Find top increasing categories vs prev month
    # (Simplified: just flag the top 3 categories)
    this_month_mask = (df_all["日期_dt"] >= ms) & (df_all["日期_dt"] <= min(me, today)) & (df_all["类型"] == "支出")
    this_month_df = df_all[this_month_mask]
    if not this_month_df.empty and not df_prev.empty:
        prev_month_mask = (df_prev["日期_dt"] >= prev_ms) & (df_prev["日期_dt"] <= prev_me) & (df_prev["类型"] == "支出")
        prev_month_df = df_prev[prev_month_mask]
        if not prev_month_df.empty:
            this_cats = this_month_df.groupby("一级分类")["净支出"].apply(lambda x: abs(x.sum()))
            prev_cats = prev_month_df.groupby("一级分类")["净支出"].apply(lambda x: abs(x.sum()))
            for cat in this_cats.index:
                if cat in prev_cats.index:
                    chg = (this_cats[cat] - prev_cats[cat]) / prev_cats[cat] * 100
                    if chg > 30 and this_cats[cat] > 200:
                        lines.append(f"  🔺 {cat} 环比上涨 {chg:.0f}%，建议留意")

    # Asset reminder
    lines.append(f"\n📌 记得更新你的资产情况：指数基金、比特币、现金等各部分当前估值。")

    return "\n".join(lines)


# ── main ─────────────────────────────────────────────────────────────

def main():
    print(f"🕐 iCost 周报 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 40)

    # Step 1: Scan & ingest new xlsx
    n = step_scan_and_ingest()
    print(f"📥 处理 {n} 个新文件")

    # Step 2: Missing check
    if n == 0:
        step_missing_check()

    # Step 3-4: Analyze & report
    report = step_analyze()
    print("\n" + report)

    # Step 5: Send to WeChat
    send_wechat(report)
    print("\n✅ 报告已推送微信")


if __name__ == "__main__":
    main()
