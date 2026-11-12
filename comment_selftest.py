"""comment_engine 自检：覆盖率、措辞红线、确定性。

用法：python comment_selftest.py
"""
import itertools
import sys

from comment_engine import IND_KEYS, IND_NAMES, build_comment, explain

FORBIDDEN = ("买入", "卖出", "抄底", "逃顶", "见底", "见顶", "建仓", "清仓", "满仓",
             "空仓", "加仓", "减仓", "建议", "应该", "一定会", "必然", "必涨", "必跌", "稳赚")
MAX_HEADLINE = 40
MAX_DETAIL = 90


def check_one(scores, fgi, der, where=""):
    c = build_comment(scores, fgi, der)
    h, det = c["headline"], c["detail"]
    problems = []
    if not h or not h.strip():
        problems.append("空主句")
    if not det or not det.strip():
        problems.append("空依据")
    if len(h) > MAX_HEADLINE:
        problems.append(f"主句过长 {len(h)}")
    if len(det) > MAX_DETAIL:
        problems.append(f"依据过长 {len(det)}")
    for w in FORBIDDEN:
        if w in h or w in det:
            problems.append(f"出现红线词 {w}")
    if "None" in h or "None" in det or "{" in h:
        problems.append("模板未填充")
    c2 = build_comment(scores, fgi, der)
    if (c2["headline"], c2["detail"]) != (h, det):
        problems.append("不确定性（同状态两次结果不同）")
    if problems:
        raise AssertionError(f"{where} {scores} fgi={fgi}: {problems} | {h} | {det}")
    return c


def main():
    # 1) 三态全组合 3^5 = 243
    vals = (15.0, 50.0, 85.0)
    tags, heads = {}, set()
    for combo in itertools.product(vals, repeat=5):
        s = dict(zip(IND_KEYS, combo))
        f = sum(combo) / 5
        c = check_one(s, f, 0.0, "三态")
        tags[c["tags"][0]] = tags.get(c["tags"][0], 0) + 1
        heads.add(c["headline"])
    print(f"[1] 三态组合 243 个全部通过；命中情形 {len(tags)} 种：")
    for k, v in sorted(tags.items(), key=lambda kv: -kv[1]):
        print(f"      {k:18s} {v:4d}")
    print(f"      不同主句 {len(heads)} 条")

    # 2) 七档全组合 7^5 = 16807（各档取中值）
    level_vals = (4.0, 15.0, 30.0, 50.0, 70.0, 85.0, 97.0)
    heads7, tags7 = set(), {}
    for combo in itertools.product(level_vals, repeat=5):
        s = dict(zip(IND_KEYS, combo))
        f = sum(combo) / 5
        c = check_one(s, f, 0.0, "七档")
        heads7.add(c["headline"])
        tags7[c["tags"][0]] = tags7.get(c["tags"][0], 0) + 1
    print(f"[2] 七档组合 16807 个全部通过；不同主句 {len(heads7)} 条")
    print(f"      情形分布：{sorted(tags7.items(), key=lambda kv: -kv[1])}")

    # 3) 导数/边界
    for f in (0, 5, 15, 50, 85, 95, 100):
        for d in (-5, -1.5, 0, 1.5, 5):
            check_one({"vol": 50, "volume": 50, "futures": 50,
                       "safe_haven": 50, "strength": 50}, f, d, "边界")
    print("[3] FGI 0~100 × 导数 -5~5 边界组合通过")

    # 4) 缺字段容错
    check_one({"vol": 60}, 55, 0, "缺字段")
    check_one({}, 50, 0, "全缺")
    print("[4] 缺字段容错通过")

    # 5) 抽样展示
    print("\n[5] 抽样（情形 → 主句）：")
    samples = [
        ("极端恐惧", {"vol": 5, "volume": 10, "futures": 10, "safe_haven": 12, "strength": 8}, 9, -2),
        ("极端贪婪", {"vol": 95, "volume": 90, "futures": 88, "safe_haven": 92, "strength": 96}, 92, 1),
        ("全面恐惧", {"vol": 20, "volume": 25, "futures": 20, "safe_haven": 18, "strength": 25}, 22, -1),
        ("全面贪婪", {"vol": 80, "volume": 75, "futures": 78, "safe_haven": 82, "strength": 85}, 80, 0.5),
        ("平静阴跌", {"vol": 87, "volume": 85, "futures": 56, "safe_haven": 32, "strength": 3}, 52.5, 2.7),
        ("放量下跌", {"vol": 30, "volume": 92, "futures": 30, "safe_haven": 25, "strength": 20}, 39, -2),
        ("放量上行", {"vol": 70, "volume": 88, "futures": 75, "safe_haven": 80, "strength": 78}, 78, 1),
        ("波动放大趋势未破", {"vol": 12, "volume": 72, "futures": 55, "safe_haven": 62, "strength": 70}, 54, -1.5),
        ("缩量阴跌", {"vol": 62, "volume": 15, "futures": 40, "safe_haven": 30, "strength": 32}, 36, -0.4),
        ("安静的强势", {"vol": 82, "volume": 58, "futures": 62, "safe_haven": 62, "strength": 82}, 69, 0.3),
        ("资金躲债", {"vol": 48, "volume": 42, "futures": 38, "safe_haven": 10, "strength": 38}, 35, -0.8),
        ("风险偏好回归", {"vol": 60, "volume": 58, "futures": 55, "safe_haven": 88, "strength": 60}, 64, 1.2),
        ("期指贴水", {"vol": 55, "volume": 50, "futures": 8, "safe_haven": 45, "strength": 48}, 41, -0.3),
        ("期指升水", {"vol": 60, "volume": 55, "futures": 95, "safe_haven": 55, "strength": 62}, 65, 0.6),
        ("指标分裂", {"vol": 10, "volume": 92, "futures": 20, "safe_haven": 85, "strength": 50}, 51, 0),
        ("情绪修复", {"vol": 42, "volume": 45, "futures": 45, "safe_haven": 40, "strength": 38}, 41, 2.4),
        ("情绪转冷", {"vol": 40, "volume": 45, "futures": 45, "safe_haven": 40, "strength": 38}, 60, -2.2),
        ("五项齐平", {"vol": 52, "volume": 48, "futures": 50, "safe_haven": 51, "strength": 49}, 50, 0.2),
    ]
    for name, s, f, d in samples:
        print(f"   {name:12s} {explain(s, f, d)}")

    print("\n✅ 全部通过")


if __name__ == "__main__":
    sys.exit(main())
