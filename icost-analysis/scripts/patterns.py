#!/usr/bin/env python3
"""
iCost 消费行为模式分析 — 用户问「根据消费能分析出什么模式」时使用。

分析维度：
  1. 按星期拆解（周一到周日的晚餐/午餐/零食分布）
  2. 上旬 vs 下旬对比（1-15 vs 16-月底）
  3. 晚饭-零食同日绑定率（最危险的模式）
  4. 每月均价走势（晚餐均价是否在涨）
  5. 大额支出后反弹效应
  6. 工作日 vs 周末对比

Usage:
    python3 ~/.claude/skills/icost-analysis/scripts/patterns.py [year1 year2 ...]
    默认分析所有年份。
"""
import sys, csv
from collections import defaultdict
from datetime import datetime

DATA_DIR = os.path.expanduser("~/records/finance")

def load(year: int) -> list:
    path = os.path.join(DATA_DIR, f"{year}.csv")
    rows = []
    try:
        with open(path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                net = abs(float(r['金额']) + float(r['退款'] if r['退款'] else '0'))
                try:
                    d = datetime.strptime(r['日期'][:10], '%Y-%m-%d')
                except:
                    d = None
                rows.append({
                    'date': d, 'cat1': r['一级分类'], 'cat2': r['二级分类'],
                    'note': r['备注'], 'net': net, 'type': r['类型'], 'year': year
                })
    except FileNotFoundError:
        return []
    return [r for r in rows if r['type'] == '支出']

def report(all_exp: list):
    days_cn = ['周一','周二','周三','周四','周五','周六','周日']
    food = [r for r in all_exp if r['cat1'] == '餐饮']

    # ── 1. 按星期 ──
    wk_dinner = {i: {'total': 0, 'cnt': 0} for i in range(7)}
    wk_snack = {i: {'total': 0, 'cnt': 0} for i in range(7)}
    wk_lunch = {i: {'total': 0, 'cnt': 0} for i in range(7)}
    for r in food:
        if not r['date']: continue
        w = r['date'].weekday()
        if r['cat2'] == '晚餐':
            wk_dinner[w]['total'] += r['net']; wk_dinner[w]['cnt'] += 1
        if r['cat2'] == '午餐':
            wk_lunch[w]['total'] += r['net']; wk_lunch[w]['cnt'] += 1
        if r['cat2'] == '零食饮料':
            wk_snack[w]['total'] += r['net']; wk_snack[w]['cnt'] += 1

    print('📅 按星期（晚餐+午餐）')
    print(f'  {"":>6}', '   '.join([f'{d}' for d in days_cn]))
    total_line = [wk_dinner[i]['total'] + wk_lunch[i]['total'] for i in range(7)]
    print(f'  总额:', '  '.join([f'¥{total_line[i]:.0f}' for i in range(7)]))
    cnt_line = [wk_dinner[i]['cnt'] + wk_lunch[i]['cnt'] for i in range(7)]
    print(f'  笔数:', '   '.join([f'{cnt_line[i]:2d}' for i in range(7)]))
    # 周末 vs 工作日
    wd_total = sum(total_line[i] for i in range(5))
    we_total = sum(total_line[i] for i in range(5,7))
    wd_days = 5; we_days = 2
    print(f'  工作日(5天): ¥{wd_total:.0f}  |  周末(2天): ¥{we_total:.0f} (x{we_total/wd_total*5/2:.1f})')

    print()
    print('🍿 按星期（零食）')
    sn_total = [wk_snack[i]['total'] for i in range(7)]
    print(f'  总额:', '  '.join([f'¥{sn_total[i]:.0f}' for i in range(7)]))
    sn_cnt = [wk_snack[i]['cnt'] for i in range(7)]
    print(f'  笔数:', '   '.join([f'{sn_cnt[i]:2d}' for i in range(7)]))

    # ── 2. 上旬 vs 下旬 ──
    half = {'上旬(1-15)': {'dinner': 0, 'dinner_cnt': 0, 'snack': 0, 'snack_cnt': 0},
            '下旬(16-月底)': {'dinner': 0, 'dinner_cnt': 0, 'snack': 0, 'snack_cnt': 0}}
    for r in food:
        if not r['date']: continue
        h = '上旬(1-15)' if r['date'].day <= 15 else '下旬(16-月底)'
        if r['cat2'] == '晚餐':
            half[h]['dinner'] += r['net']; half[h]['dinner_cnt'] += 1
        if r['cat2'] == '零食饮料':
            half[h]['snack'] += r['net']; half[h]['snack_cnt'] += 1

    print()
    print('📆 上旬 vs 下旬')
    for h in ['上旬(1-15)', '下旬(16-月底)']:
        d = half[h]
        avg = d['dinner'] / d['dinner_cnt'] if d['dinner_cnt'] else 0
        print(f'  {h}: 晚餐¥{d["dinner"]:.0f}({d["dinner_cnt"]}次 ¥{avg:.0f}/次)'
              f'  零食¥{d["snack"]:.0f}({d["snack_cnt"]}次)')

    # ── 3. 晚饭-零食同日绑定 ──
    daily = defaultdict(lambda: {'dinner': 0, 'snack': 0})
    for r in food:
        if not r['date']: continue
        key = (r['year'], r['date'].month, r['date'].day)
        if r['cat2'] == '晚餐':
            daily[key]['dinner'] += r['net']
        elif r['cat2'] == '零食饮料':
            daily[key]['snack'] += r['net']

    dinner_only = sum(1 for v in daily.values() if v['dinner']>0 and v['snack']==0)
    both = sum(1 for v in daily.values() if v['dinner']>0 and v['snack']>0)
    snack_only = sum(1 for v in daily.values() if v['dinner']==0 and v['snack']>0)

    total_dinner = dinner_only + both
    print()
    print('🔄 晚饭-零食同日绑定率')
    if total_dinner:
        print(f'  有晚饭的天数: {total_dinner}')
        print(f'  其中也买零食: {both}天 ({both/total_dinner*100:.0f}%)')
        print(f'  纯晚饭无零食: {dinner_only}天')
        print(f'  纯零食无晚饭: {snack_only}天')
        print(f'  🔑 如果戒晚饭或隔离零食通道，可消除 {both} 天的零食冲动')

    # ── 4. 均价走势 ──
    years = sorted(set(r['year'] for r in all_exp))
    print()
    print('📈 晚餐均价走势')
    for year in years:
        y_food = [r for r in food if r['year'] == year]
        for m in range(1, 13):
            meals = [r for r in y_food if r['date'] and r['date'].month == m and r['cat2'] == '晚餐']
            if not meals: continue
            t = sum(r['net'] for r in meals)
            c = len(meals)
            print(f'  {year}/{m:02d}: ¥{t/c:.0f}/次 × {c}次 = ¥{t:.0f}')

    # 跨年汇总
    print()
    for year in sorted(years):
        y_food = [r for r in food if r['year'] == year and r['cat2'] == '晚餐']
        if not y_food: continue
        t = sum(r['net'] for r in y_food); c = len(y_food)
        print(f'  {year} 全年: ¥{t/c:.0f}/次 × {c}次 = ¥{t:.0f}')

    # ── 5. 大额反弹效应 ──
    big = sorted([r for r in all_exp if r['net'] >= 500 and r['cat1'] != '餐饮'], key=lambda x: -x['net'])
    if big:
        print()
        print('💰 大额支出前后餐饮变化 (前5天 vs 后5天)')
        for b in big[:8]:
            bd = b['date']
            if not bd: continue
            before = sum(r['net'] for r in food if r['date'] and -5 <= (r['date'] - bd).days <= -1)
            after = sum(r['net'] for r in food if r['date'] and 1 <= (r['date'] - bd).days <= 5)
            arrow = '⬆反弹' if after > before else '⬇收敛'
            d = bd.strftime('%m/%d')
            print(f'  {d} ¥{b["net"]:.0f} {b["cat1"]}>{b["cat2"]} {b["note"][:15]}')
            print(f'    前5天¥{before:.0f} → 后5天¥{after:.0f} {arrow}')

    # ── 6. 晚餐次数 vs 晚餐金额趋势线 ──
    print()
    print('📊 晚餐月度频次')
    for year in sorted(years):
        by_month = defaultdict(int)
        for r in food:
            if r['year'] != year or r['cat2'] != '晚餐' or not r['date']: continue
            by_month[r['date'].month] += 1
        min_m = min(by_month.keys()) if by_month else 1
        max_m = max(by_month.keys()) if by_month else 12
        counts = [by_month.get(m, 0) for m in range(min_m, max_m+1)]
        avg_cnt = sum(counts) / len(counts) if counts else 0
        print(f'  {year}: 月均{avg_cnt:.0f}次, 范围{min(counts)}-{max(counts)}')

if __name__ == '__main__':
    import os
    years = [int(y) for y in sys.argv[1:]] if len(sys.argv) > 1 else [2024, 2025, 2026]
    all_exp = []
    for y in years:
        exp = load(y)
        if exp:
            print(f'--- {y}年 ---')
            report([r for r in exp if r['date']])  # only with dates
        else:
            print(f'{y}年: 无数据或文件不存在')
