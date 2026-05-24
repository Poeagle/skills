#!/usr/bin/env python3
"""
iCost 每周报告 — 基于用户的消费价值观：
- 自炊标准 ≤¥15/顿，外食 = 浪费
- 零食饮料 = 浪费
- VPN/API = 刚需
- 水果、衣服偶尔 = 正常
输出格式：该花多少 vs 浪费多少，能省多少。
"""

import os
import sys
import glob
import pandas as pd
from datetime import datetime, timedelta, date

SKILL_DIR = os.path.expanduser("~/.claude/skills/icost-analysis")
DATA_DIR = os.path.expanduser("~/records/finance")
PROCESSED_LOG = os.path.join(DATA_DIR, "processed.log")
HOME_COOK_COST = 15  # 自炊一顿 ¥15

sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
import ingest


def load_csv(year: int) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{year}.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    df["日期_dt"] = pd.to_datetime(df["日期"], errors="coerce")
    df["金额_n"] = pd.to_numeric(df["金额"], errors="coerce").fillna(0)
    df["退款_n"] = pd.to_numeric(df["退款"], errors="coerce").fillna(0)
    df["净支出"] = abs(df["金额_n"] + df["退款_n"])
    return df.dropna(subset=["日期_dt"])


def send_message(msg: str):
    with open("/tmp/icost_report.txt", "w", encoding="utf-8") as f:
        f.write(msg)
    os.system("hermes send -t qqbot:59939641932FACF52F564201079BDE09 -f /tmp/icost_report.txt")


def classify(row) -> str:
    """必要 / 正常 / 可优化"""
    remark = str(row.get("备注", "")).lower()
    subcat = str(row.get("二级分类", ""))
    l1 = str(row.get("一级分类", ""))
    amount = float(row.get("净支出", 0))

    # 必要：不能动的
    if l1 in ("住房", "通讯"):
        return "必要"
    if any(kw in remark for kw in ("房租", "话费", "电费")):
        return "必要"
    if any(kw in remark for kw in ("vpn", "api", "deepseek")):
        return "必要"

    # 正常：合理的日常开支
    if any(kw in remark for kw in ("饮用水", "农夫山泉", "矿泉水")):
        return "正常"
    if subcat in ("水果", "剪发", "穿着", "其他"):
        return "正常"
    if l1 in ("交通", "人情", "旅游"):
        return "正常"
    # 外食 ¥25 以内算正常
    if subcat in ("午餐", "晚餐") and amount <= 25:
        return "正常"

    # 可优化：超出合理范围的
    if subcat in ("午餐", "晚餐") and amount > 25:
        return "可优化"
    if subcat == "零食饮料":
        return "可优化"
    if l1 == "软件" and subcat == "续约制":
        return "可优化"

    return "正常"


def step_scan_and_ingest() -> int:
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
            for y in sorted(years.keys()):
                ingest.append_to_csv(y, years[y])
            with open(PROCESSED_LOG, "a") as f:
                f.write(fname + "\n")
            os.remove(fpath)
        except Exception as e:
            print(f"❌ {fname}: {e}")
    return len(new_files)


def step_missing_check():
    today = datetime.now()
    df = load_csv(today.year)
    if df.empty:
        return
    last_date = df["日期_dt"].max()
    lw_end = today - timedelta(days=today.weekday() + 1)
    lw_start = lw_end - timedelta(days=6)
    if last_date < datetime(lw_start.year, lw_start.month, lw_start.day):
        send_message(f"📌 上周账单还没导？最后记录是 {last_date.strftime('%m/%d')}。")


def generate_report() -> str:
    today = datetime.now()
    year = today.year
    df = load_csv(year)
    if df.empty:
        return "暂无消费数据。"

    me = today.date()
    ms = date(today.year, today.month, 1)
    lw_end = today - timedelta(days=today.weekday() + 1)
    lw_start = lw_end - timedelta(days=6)

    month_df = df[(df["日期_dt"] >= pd.Timestamp(ms)) & (df["日期_dt"] <= pd.Timestamp(me))].copy()
    week_df = df[(df["日期_dt"] >= pd.Timestamp(lw_start)) & (df["日期_dt"] <= pd.Timestamp(lw_end))].copy()

    def split_by_classification(df):
        result = {"必要": [], "正常": [], "可优化": []}
        for _, r in df.iterrows():
            level = classify(r)
            result[level].append(r)
        return {level: {"total": sum(r["净支出"] for r in items), "count": len(items), "rows": items}
                for level, items in result.items()}

    month_c = split_by_classification(month_df)
    week_c = split_by_classification(week_df)
    month_total = month_df["净支出"].sum()
    month_c = split_by_classification(month_df)
    week_c = split_by_classification(week_df)
    month_total = month_df["净支出"].sum()
    week_total = week_df["净支出"].sum()
    days_passed = (me - ms).days + 1

    # ── 外食节省 ──
    dining = month_df[month_df["二级分类"].isin(["午餐", "晚餐"])]
    dine_total = dining["净支出"].sum()
    dine_count = len(dining)
    dine_save = dine_total - dine_count * HOME_COOK_COST

    # ── 可优化明细 ──
    opt = month_c["可优化"]["rows"]
    snack = [r for r in opt if str(r.get("二级分类", "")) == "零食饮料"]
    snack_total = sum(r["净支出"] for r in snack)
    subs = [r for r in opt if str(r.get("一级分类", "")) == "软件" and str(r.get("二级分类", "")) == "续约制"]
    subs_total = sum(r["净支出"] for r in subs)
    total_save = dine_save + snack_total + subs_total
    base = month_c["必要"]["total"] + month_c["正常"]["total"]

    # ── 上周同样算法 ──
    wk_dining = week_df[week_df["二级分类"].isin(["午餐", "晚餐"])]
    wk_dine_save = wk_dining["净支出"].sum() - len(wk_dining) * HOME_COOK_COST
    wk_snack = week_df[week_df["二级分类"] == "零食饮料"]["净支出"].sum()
    wk_subs = week_df[(week_df["一级分类"] == "软件") & (week_df["二级分类"] == "续约制")]["净支出"].sum()
    wk_save = wk_dine_save + wk_snack + wk_subs

    lines = ["📋 消费周报"]
    S = "\n" + "─" * 20

    # ── 预算（含早餐¥5，早餐无iCost记录，但预算是完整的）──
    # 工作日：早¥5+晚¥10 = ¥15；周末：早¥5+午¥10+晚¥10 = ¥25
    def budget_per_day(d):
        return 15 if d.weekday() < 5 else 25  # 含早¥5

    # 上周
    wk_budget = sum(budget_per_day(lw_start + timedelta(days=i)) for i in range(7))
    wk_food = week_df[week_df["一级分类"] == "餐饮"]  # 所有餐饮（午+晚+零食+水果）
    wk_actual = wk_food["净支出"].sum()
    wk_over = wk_actual - wk_budget

    # 本月
    mo_all_days = [(ms + timedelta(days=i)) for i in range(days_passed)]
    mo_budget = sum(budget_per_day(d) for d in mo_all_days)
    mo_food = month_df[month_df["一级分类"] == "餐饮"]
    mo_actual = mo_food["净支出"].sum()
    mo_over = mo_actual - mo_budget

    # 每月按自然周拆分（周一到周日）
    month_calendar = []
    # 找到本月第一天所在周的周一
    week_start = ms - timedelta(days=ms.weekday())
    for w in range(6):
        w_mon = week_start + timedelta(weeks=w)
        w_sun = w_mon + timedelta(days=6)
        # 只取在本月范围内的部分
        w_start = max(w_mon, ms)
        w_end = min(w_sun, me)
        if w_start > me or w_start > w_end:
            break
        w_days = (w_end - w_start).days + 1
        w_bud = sum(budget_per_day(w_start + timedelta(days=i)) for i in range(w_days))
        w_df = month_df[(month_df["日期_dt"] >= pd.Timestamp(w_start)) & (month_df["日期_dt"] <= pd.Timestamp(w_end))]
        w_food = w_df[w_df["一级分类"] == "餐饮"]
        w_act = w_food["净支出"].sum()
        w_ov = w_act - w_bud
        label = f"{w_start.month}/{w_start.day}-{w_end.month}/{w_end.day}"
        month_calendar.append((label, w_act, w_bud, w_ov))

    # 上月累计
    lines.append(f"📆 上周 {lw_start.month}/{lw_start.day}-{lw_end.month}/{lw_end.day}")
    cat_parts = [f"{cat}¥{amt:.0f}" for cat, amt in week_df.groupby("一级分类")["净支出"].sum().sort_values(ascending=False).items()]
    lines.append(f"消费 ¥{week_total:.0f}（{' · '.join(cat_parts)}）")

    if wk_over > 0:
        lines.append(f"伙食 ¥{wk_actual:.0f}，预算 ¥{wk_budget:.0f}，超出 ¥{wk_over:.0f}")
        # 列超标的项（单餐超¥10）
        over_items = wk_food[wk_food["净支出"] > 10]
        if len(over_items) > 0:
            items_str = " · ".join([f"{r['日期_dt'].strftime('%m/%d')}¥{r['净支出']:.0f}{str(r.get('备注',''))[:10]}" for _, r in over_items.iterrows()])
            lines.append(f"超标项：{items_str}")
    else:
        lines.append(f"伙食 ¥{wk_actual:.0f}，预算 ¥{wk_budget:.0f}，省 ¥{abs(wk_over):.0f}")

    # 本月
    lines.append(f"{S}")
    lines.append(f"📆 本月 1-{me.day}（{days_passed} 天）总消费 ¥{month_total:.0f}")

    # 分类明细
    cat_parts = []
    for cat, amt in month_df.groupby("一级分类")["净支出"].sum().sort_values(ascending=False).items():
        cat_parts.append(f"{cat}¥{amt:.0f}")
    lines.append(f"{' · '.join(cat_parts)}")

    # 可节省明细
    lines.append(f"伙食超支 ¥{mo_over:.0f}（餐饮¥{mo_actual:.0f} - 预算¥{mo_budget:.0f}含早）")
    # 其他可砍项（排除 VPN/API 刚需）
    subs_df = month_df[(month_df["一级分类"] == "软件") & (month_df["二级分类"] == "续约制")]
    subs_cuttable = subs_df[~subs_df["备注"].fillna("").str.lower().str.contains("vpn|api|deepseek", na=False)]
    subs_cost = subs_cuttable["净支出"].sum()
    other_save = 0
    if subs_cost > 0:
        lines.append(f"订阅 ¥{subs_cost:.0f}（非必要，可砍）")
        other_save += subs_cost
    lines.append(f"  合计可省 ¥{mo_over + other_save:.0f}/月")

    # 每周明细
    lines.append(f"{S}")
    lines.append(f"📊 每周伙食对比（工作日¥15/天 · 周末¥25/天 · 含早¥5）")
    for w_label, w_act, w_bud, w_ov in month_calendar:
        if w_ov > 0:
            lines.append(f"{w_label}  实际 ¥{w_act:.0f}  预算 ¥{w_bud:.0f}  🔺超 ¥{w_ov:.0f}")
        else:
            lines.append(f"{w_label}  实际 ¥{w_act:.0f}  预算 ¥{w_bud:.0f}  ✅省 ¥{abs(w_ov):.0f}")

    # 总结
    total_extra = mo_over  # 伙食超支部分
    lines.append(f"{S}")
    lines.append(f"✅ 如果伙食控制在预算内：")
    lines.append(f"  每月省 ¥{mo_over:.0f}（餐饮实际 ¥{mo_actual:.0f} → 预算 ¥{mo_budget:.0f}）")
    base = month_c["必要"]["total"] + month_c["正常"]["total"]
    lines.append(f"  每月只需 ¥{base:.0f}（¥{base/days_passed:.0f}/天）")
    lines.append(f"{S}")
    lines.append(f"📌 资产更新了没？")
    return "\n".join(lines)


def main():
    n = step_scan_and_ingest()
    if n == 0:
        step_missing_check()
    report = generate_report()
    print(report)
    send_message(report)


if __name__ == "__main__":
    main()
