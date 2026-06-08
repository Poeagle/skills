#!/usr/bin/env python3
"""
iCost 年度分析 — 全年消费总览、分类拆解、月度趋势、节省潜力计算。

Usage:
    python3 ~/.claude/skills/icost-analysis/scripts/yearly.py [year]

默认当前年份。结果打印到终端。
"""
import sys, csv, os
from collections import defaultdict
from datetime import datetime

DATA_DIR = os.path.expanduser("~/records/finance")

def load(year: int) -> list:
    path = os.path.join(DATA_DIR, f"{year}.csv")
    rows = []
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
                'note': r['备注'], 'net': net, 'type': r['类型']
            })
    return [r for r in rows if r['type'] == '支出']

def report(exp: list, year: int):
    total = sum(r['net'] for r in exp)
    print(f"全年总支出: ¥{total:.0f}  ({len(exp)}笔)")
    # 分类
    cats = defaultdict(float)
    for r in exp: cats[r['cat1']] += r['net']
    print()
    print('📊 一级分类')
    for c in sorted(cats, key=lambda k: -cats[k]):
        print(f'  {c}: ¥{cats[c]:.0f}  ({cats[c]/total*100:.0f}%)')
    # 月度
    monthly = defaultdict(float)
    for r in exp:
        if r['date']: monthly[r['date'].month] += r['net']
    print()
    print('📆 每月支出')
    for m in sorted(monthly):
        bar = '█' * max(1, int(monthly[m] / max(monthly.values()) * 30))
        print(f'  {m:2d}月: ¥{monthly[m]:.0f}  {bar}')
    # 外食
    dining = [r for r in exp if r['cat2'] in ('午餐','晚餐')]
    dt = sum(r['net'] for r in dining); dc = len(dining)
    print(f'\n🍚 外食（午+晚）: ¥{dt:.0f} / {dc}笔')
    print(f'    自炊(¥15/顿)=¥{15*dc:.0f}，可省 ¥{dt-15*dc:.0f}')
    # 零食
    snacks = [r for r in exp if r['cat2'] == '零食饮料']
    st = sum(r['net'] for r in snacks)
    print(f'🍿 零食饮料: ¥{st:.0f} / {len(snacks)}笔')
    # 订阅
    subs = [r for r in exp if r['cat1'] == '软件' and r['cat2'] == '续约制']
    print(f'💻 订阅续费: ¥{sum(r["net"] for r in subs):.0f} / {len(subs)}笔')
    # 大额
    big = sorted([r for r in exp if r['net'] >= 300], key=lambda x: -x['net'])
    if big:
        print(f'\n💰 大额支出 (>=¥300)')
        for r in big[:15]:
            d = r['date'].strftime('%m/%d') if r['date'] else '??'
            print(f'  {d}  ¥{r["net"]:.0f}  {r["cat1"]}>{r["cat2"]}  {r["note"][:30]}')

def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().year
    exp = load(year)
    if not exp:
        print(f'{year}年无数据')
        return
    report(exp, year)

if __name__ == '__main__':
    import os
    main()
