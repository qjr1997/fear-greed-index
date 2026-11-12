"""恐贪指数「一句话解读」引擎。

输入：五个子指标的 0~100 分（50 = 过去一年中位）、当前 FGI、日变化。
输出：headline（主句，≤34 字）+ detail（依据句）+ tags（命中情形，便于统计）。

方向约定（由 .github/workflows/update-data.yml 的 calc_zscore 决定，勿改）：
    波动率     reverse=True → 高分 = 波动率低 = 平静
    成交量     正向         → 高分 = 放量
    期指升贴水 正向         → 高分 = 升水 / 贴水收窄 = 乐观
    股债强弱   正向         → 高分 = 股票跑赢债券 = 风险偏好高
    股价强度   正向         → 高分 = 价格高于 50 日线
因此统一为：**高分 = 贪婪侧，低分 = 恐惧侧**。

设计原则（2026-11-12 讨论确定）：
1. 只描述当下状态与结构，不预测、不给买卖建议、不出现"该买/该卖/见底"这类词；
2. 同一状态永远同一句话（按状态键做确定性散列选句），便于日后归因统计；
3. 主句按情形优先级从上往下取，detail 永远给出「最强/最弱」两个依据；
4. 组合覆盖 3^5=243 种三态组合、7^5 种七档组合，靠"素材组合"而非堆句子。
"""

from __future__ import annotations

import zlib
from typing import Dict, List

IND_KEYS = ("vol", "volume", "futures", "safe_haven", "strength")
IND_NAMES = {
    "vol": "波动率",
    "volume": "成交量",
    "futures": "期指升贴水",
    "safe_haven": "股债强弱",
    "strength": "股价强度",
}

# 0~100 分切成 7 档：极低 / 很低 / 偏低 / 中性 / 偏高 / 很高 / 极高
LEVEL_EDGES = (8, 22, 38, 62, 78, 92)

PHRASES: Dict[str, tuple] = {
    # 波动率：高分 = 波动率低（平静），低分 = 波动率高（恐慌）
    "vol": (
        ("恐慌指数顶到一年最高", "波动率冲上一年顶点", "市场在剧烈颠簸"),
        ("波动率明显抬升", "恐慌指数偏高", "盘面神经绷得紧"),
        ("波动率比常态略热", "颠簸多了一点", "波动小幅放大"),
        ("波动率在常态区间", "波动不大不小", "波动正常"),
        ("波动率压得偏低", "盘面比平时安静", "波动收敛"),
        ("波动率降到一年低位", "安静得有点反常", "波动被压住"),
        ("波动率贴着一年地板", "没人愿意为波动付钱", "波动率几乎归零"),
    ),
    # 成交量：高分 = 放量
    "volume": (
        ("成交萎缩到极致", "缩量缩到没人气", "量能几乎枯掉"),
        ("明显缩量", "成交比近月均量少一大截", "量能明显退潮"),
        ("略微缩量", "成交偏清淡", "量能小幅收敛"),
        ("成交温和", "量能不出彩", "成交平平"),
        ("略微放量", "成交比常态略多", "量能小幅回升"),
        ("明显放量", "成交比近月均量多出一截", "量能明显放大"),
        ("放量放到天量", "成交极度活跃", "量能爆表"),
    ),
    # 期指升贴水：高分 = 升水 / 乐观
    "futures": (
        ("期指深度贴水", "期货把折扣打到极端", "期指贴水很深"),
        ("期指维持贴水", "期货端在打折", "期指明显贴水"),
        ("期指小幅贴水", "期指略打折", "期货小幅折价"),
        ("期指平水附近", "期货和现货差不多", "期指基差平稳"),
        ("期指小幅升水", "期货略给溢价", "期指小幅溢价"),
        ("期指明显升水", "期货给出溢价", "期指升水"),
        ("期指升水拉到极端", "期货抢跑", "期指大幅升水"),
    ),
    # 股债强弱：高分 = 股票跑赢债券
    "safe_haven": (
        ("股票被债券按在地上", "资金一边倒躲进债市", "股债跷跷板砸向债市"),
        ("股债跷跷板倒向债券", "股票明显跑输债券", "钱在往债市躲"),
        ("股票略跑输债券", "股票小幅落后债券", "股不如债"),
        ("股债打平", "两边差不多", "股债五五开"),
        ("股票略跑赢债券", "股票小幅领先债券", "股略好于债"),
        ("股票明显跑赢债券", "风险偏好在回来", "钱从债市回流"),
        ("股票把债券甩开很远", "股票大幅跑赢债券", "风险偏好明显抬升"),
    ),
    # 股价强度：高分 = 价格高于 50 日线
    "strength": (
        ("指数远在50日线下方", "价格跌破50日线一大截", "均线高高压着价格"),
        ("价格明显弱于50日线", "均线压着价格", "价格在均线下方较远处"),
        ("价格略低于50日线", "小幅跌破均线", "价格略在均线下方"),
        ("价格贴着50日线", "在均线附近磨", "正好卡在均线"),
        ("价格略高于50日线", "小幅站上均线", "价格略在均线上方"),
        ("价格明显站上50日线", "均线在托着价格", "价格稳在均线上方"),
        ("指数远在50日线上方", "强势拉开均线", "价格远离均线"),
    ),
}




def level_of(score: float) -> int:
    """0~100 分 → 0..6 档。"""
    s = 0.0 if score is None else float(score)
    for i, edge in enumerate(LEVEL_EDGES):
        if s <= edge:
            return i
    return 6


def phrase_of(key: str, score: float, variant: int) -> str:
    table = PHRASES[key][level_of(score)]
    return table[variant % len(table)]


# ---------------------------------------------------------------------------
# 主句规则（自上而下，第一个命中生效；每条 5~6 个变体）
# 排序原则：先"极端/共振"这种强判断，再"具体结构"，最后"通用兜底"。
# ---------------------------------------------------------------------------
RULES = [
    {
        "tag": "extreme_fear",
        "test": lambda s, f, d: f <= 15,
        "lines": [
            "情绪掉进极端恐惧，能扛住的人不多",
            "极度恐惧区间：该慌的基本都慌了",
            "极端恐惧位，情绪压过了基本面",
            "指数砸进极度恐惧，情绪跑在基本面前面",
            "极端恐惧，是最容易走极端的位置",
            "冷到极端，价格已开始反映悲观",
            "极端恐惧带，情绪已经跌到地板附近",
            "极度恐惧位，恐慌本身就构成了信息",
        ],
    },
    {
        "tag": "extreme_greed",
        "test": lambda s, f, d: f >= 85,
        "lines": [
            "情绪冲进极端贪婪，乐观已被充分定价",
            "极度贪婪位，好消息很难再超预期",
            "极端贪婪，容错率已经变薄",
            "指数顶到极度贪婪，情绪跑在基本面前面",
            "极度贪婪位，波动风险在累积",
            "极度贪婪位，乐观已经用足",
            "极度贪婪位，好消息的边际作用在减弱",
            "极端贪婪带，拥挤度是隐形的成本",
        ],
    },
    {
        "tag": "panic_all",
        "test": lambda s, f, d: sum(v <= 40 for v in s.values()) >= 4 and f <= 32,
        "lines": [
            "五个指标一起掉进恐惧区，这种共振不常见",
            "所有维度同时转冷，是全面防守的状态",
            "没有哪个指标还在硬撑，全面恐惧",
            "五项同步下沉，情绪被压到一块",
            "整齐划一的恐惧，说明抛压是全市场的",
            "集体转冷，连多头都在缩手",
            "五项一起报警，是全市场一致的悲观",
            "全指标下沉，防守情绪铺满整个盘面",
        ],
    },
    {
        "tag": "greed_all",
        "test": lambda s, f, d: sum(v >= 60 for v in s.values()) >= 4 and f >= 68,
        "lines": [
            "五个指标一起转向贪婪，情绪全面升温",
            "所有维度都亮了绿灯，风险偏好铺开",
            "没有哪个指标拖后腿，全面贪婪",
            "五项同步偏热，是难得的整齐乐观",
            "全体指标一起抬头，钱在往外涌",
            "整齐的贪婪，往往说明分歧还没出现",
            "全指标偏热，情绪顺风但不稳",
            "五项一起抬头，是共识最齐的时候",
        ],
    },
    {
        "tag": "calm_weak",
        "test": lambda s, f, d: s["vol"] >= 70 and s["strength"] <= 30,
        "lines": [
            "指数在走弱，波动率却按在低位——缓跌，不是恐慌",
            "价格贴着均线往下磨，波动却很安静",
            "阴跌：跌得不动声色，钱在慢慢撤",
            "波动不大但价格在退，是温水式走弱",
            "没人恐慌抛售，也没人愿意接，磨人的阴跌",
            "跌得没有声音，是情绪还没宣泄",
            "价格在退、波动不动，是慢性失血",
            "跌得很安静，说明恐慌还没来",
        ],
    },
    {
        "tag": "volume_burst_down",
        "test": lambda s, f, d: s["volume"] >= 78 and s["strength"] <= 35,
        "lines": [
            "放量下跌，有人在夺门而出",
            "量能放大、价格走弱，是出货的样子",
            "成交放大但价格不涨，抛压占上风",
            "放量砸下来，接盘的人不多",
            "有量无价，是分歧最大的状态",
            "放量下挫，卖方掌握主动权",
            "量出来了、价没跟上，是出货节奏",
            "成交放大而承接不足，抛压占上风",
        ],
    },
    {
        "tag": "volume_burst_up",
        "test": lambda s, f, d: s["volume"] >= 78 and s["strength"] >= 65,
        "lines": [
            "放量上行，钱在往里挤",
            "量价齐升，情绪被点燃",
            "成交放大、价格站上均线，是资金推动",
            "量能先说话，价格跟着走",
            "放量突破，至少要有人相信",
            "放量上行，承接力量在增强",
            "量能抬升，价格顺势站上均线",
            "成交放大、价格走高，是资金在表态",
        ],
    },
    {
        "tag": "vol_shock",
        "test": lambda s, f, d: s["vol"] <= 25 and s["strength"] >= 55,
        "lines": [
            "波动突然放大，但价格还站在均线上方",
            "吓一跳但没跌穿：波动放大、趋势未破",
            "急跌式波动，趋势结构还算完整",
            "恐慌指数跳升，价格却还顶着均线",
            "先跌的是情绪，不是趋势",
            "波动先动、价格没跟着崩，结构还稳",
            "情绪受惊，价格守着均线",
            "波动率跳升，但趋势线还没破",
        ],
    },
    {
        "tag": "volume_dry",
        "test": lambda s, f, d: s["volume"] <= 22 and s["strength"] <= 40,
        "lines": [
            "缩量阴跌：卖压不大，但也没人接",
            "量能退潮，价格慢慢往下挪",
            "成交枯着，跌得不痛不痒",
            "没人愿意交易，价格自己往下沉",
            "缩量下行，是最熬人的一段",
            "缩量下移，多空都不愿用力",
            "量能枯竭，价格缺少支撑也缺少抛压",
            "成交稀薄，跌得没有力度",
        ],
    },
    {
        "tag": "strong_quiet",
        "test": lambda s, f, d: s["strength"] >= 72 and s["vol"] >= 62,
        "lines": [
            "价格站上均线、波动又低，最舒服的一段",
            "趋势在、波动小，是安静的强势",
            "均线托着价格，盘面还不吵",
            "强势且平静，通常共识比较强",
            "涨得不急，跌得也不慌",
            "均线上方安静运行，是趋势最舒服的状态",
            "波动低、价格稳，多头握着主动",
            "价格在均线上方慢慢走，盘面很安静",
        ],
    },
    {
        "tag": "bond_flight",
        "test": lambda s, f, d: s["safe_haven"] <= 22,
        "lines": [
            "股债跷跷板倒向债券，钱在避险",
            "股票跑输债券，资金往稳的地方挪",
            "债市更受宠，说明风险偏好在收缩",
            "股不如债，是防守型资金的偏好",
            "钱在躲，比价格先动",
            "股债比价向债券倾斜，防御在升温",
            "股票跑不过债券，资金偏好确定性",
            "跷跷板压向债券这一头",
        ],
    },
    {
        "tag": "risk_on",
        "test": lambda s, f, d: s["safe_haven"] >= 78,
        "lines": [
            "股票明显跑赢债券，风险偏好回来了",
            "钱从债市回流股市，进攻性在回来",
            "股强于债，是不太需要防守的状态",
            "股票把债券甩开，资金选择进攻",
            "跷跷板抬起股票这一头",
            "资金从债市往股市挪，进攻性强了",
            "股债比价向股票倾斜",
            "股票跑赢债券，风险偏好在扩张",
        ],
    },
    {
        "tag": "futures_discount",
        "test": lambda s, f, d: s["futures"] <= 22,
        "lines": [
            "期指还在贴水，机构对冲盘没撤",
            "期货端继续打折，专业资金偏防守",
            "期指贴水没修好，谨慎情绪还在",
            "期货给现货折价，是套保在说话",
            "贴水的期指，说明大钱还没敢转身",
            "期货折价没修好，套保盘还在",
            "期指贴水延续，资金对后市谨慎",
            "现货比期货贵，说明对冲需求强",
        ],
    },
    {
        "tag": "futures_premium",
        "test": lambda s, f, d: s["futures"] >= 78,
        "lines": [
            "期指升水，期货端先乐观了",
            "期货抢跑，比现货更敢下注",
            "期指给出溢价，资金预期偏正面",
            "升水的期指，说明多头愿意付钱",
            "期货先动，是情绪领先的一种",
            "期指给出溢价，多头在期货端表态",
            "期货比现货乐观",
            "升水维持，期货资金偏进攻",
        ],
    },
    {
        "tag": "split",
        "test": lambda s, f, d: max(s.values()) >= 78 and min(s.values()) <= 22,
        "lines": [
            "指标互相打架：一头极热、一头极冷",
            "内部分裂严重，方向感缺失",
            "热的地方很热，冷的地方很冷，结构分化",
            "五个指标分成两派，谁也说服不了谁",
            "极度分歧，是最难解读的一种状态",
            "分项背离，说明只有一部分钱在动",
            "五个指标分成两拨，方向互相抵消",
            "冷热并存，行情只有结构没有整体",
            "指标背离，说明资金分歧在扩大",
        ],
    },
    {
        "tag": "recovering",
        "test": lambda s, f, d: d >= 1.5 and f <= 52,
        "lines": [
            "情绪在修复，但离贪婪还很远",
            "比昨天暖了一点，温度仍偏低",
            "回升中，只是还在偏冷的一侧",
            "情绪在往上勾，幅度还不大",
            "回升中，但温度仍在偏低的一侧",
            "温度在回升，但还在偏冷一侧",
            "比昨天暖，离中位还有距离",
            "情绪修复中，力度有限",
        ],
    },
    {
        "tag": "worsening",
        "test": lambda s, f, d: d <= -1.5 and f >= 48,
        "lines": [
            "情绪在转冷，赚钱效应在退",
            "比昨天更冷，热度在流失",
            "往下拐了，情绪先退一步",
            "温度在降，谨慎在增加",
            "热度掉得比价格快",
            "情绪从偏热往下退",
            "温度在滑落，谨慎情绪回来",
            "分数在往下走，热度在减",
        ],
    },
    {
        "tag": "flat",
        "test": lambda s, f, d: max(s.values()) - min(s.values()) <= 12,
        "lines": [
            "五个指标挤在一起，没什么可挑的",
            "分歧很小，市场在等方向",
            "各项指标挤成一团，典型的中场休息",
            "没有哪一项特别突出，情绪停在原地",
            "分歧收敛，说明分歧本身在消失",
            "各项差不多，市场在横着走",
            "分歧极小，情绪没有方向",
            "五个指标挤在一个窄区里",
        ],
    },
]

BAND_LINES = {
    "band_extreme_fear": [
        "情绪在极度恐惧区，能扛住的人不多",
        "分数落在极端偏低的一侧",
        "整体温度很冷，谨慎情绪占满",
        "极度恐惧带里，价格已经很难看",
        "冷到极端，情绪最不理性",
    ],
    "band_fear": [
        "情绪偏冷，谨慎占上风",
        "分数在恐惧区，防守心态更重",
        "温度不高，大家更愿意等",
        "偏冷的一侧，容错空间相对大些",
        "恐惧区里，情绪压着价格",
    ],
    "band_neutral": [
        "不冷不热，情绪停在中性区",
        "分数居中，多空都没占优",
        "温度正常，属于观望窗口",
        "中性区里，方向要看后续数据",
        "不上不下，是最需要耐心的一段",
    ],
    "band_greed": [
        "情绪偏热，乐观占上风",
        "分数在贪婪区，追价意愿变强",
        "温度偏高，谨慎开始变得不划算",
        "偏热的一侧，容错率在下降",
        "贪婪区里，情绪推着价格走",
    ],
    "band_extreme_greed": [
        "情绪在极度贪婪区，容错率在变薄",
        "分数落在极端偏高的一侧",
        "整体温度很热，乐观被充分表达",
        "极度贪婪带里，坏消息容易被放大",
        "热到极端，情绪最拥挤",
    ],
}

SINGLE_EXTREME = {
    "low": ["{name}被打到 {score:.0f} 分，是今天最极端的一项",
            "最扎眼的是{name}：只有 {score:.0f} 分",
            "{name}已经到极端低的一侧（{score:.0f} 分）"],
    "high": ["{name}冲到 {score:.0f} 分，是今天最极端的一项",
             "最扎眼的是{name}：已经 {score:.0f} 分",
             "{name}到极端高的一侧（{score:.0f} 分）"],
}

BAND_KEYS = [
    (20, "band_extreme_fear"),
    (40, "band_fear"),
    (60, "band_neutral"),
    (80, "band_greed"),
    (101, "band_extreme_greed"),
]

# 当短语本身已含指标名时不再重复前缀
def _fmt_item(name: str, score: float, phrase: str) -> str:
    if name in phrase:
        return f"{phrase}（{score:.0f} 分）"
    return f"{name} {score:.0f}（{phrase}）"


def _state_key(scores, fgi: float) -> str:
    parts = [str(level_of(scores.get(k, 50.0))) for k in IND_KEYS]
    band = next(name for edge, name in BAND_KEYS if fgi < edge)
    return "|".join(parts) + "|" + band


def _pick(key: str, seq, salt: str = "") -> str:
    if not seq:
        return ""
    return seq[zlib.crc32((key + "|" + salt).encode("utf-8")) % len(seq)]


def _band_key(fgi: float) -> str:
    return next(name for edge, name in BAND_KEYS if fgi < edge)


def _detail(scores, key: str) -> str:
    """依据句：永远给出最强 / 最弱两项 + 分歧程度。"""
    items = [(scores.get(k, 50.0), k) for k in IND_KEYS]
    hi_s, hi_k = max(items)
    lo_s, lo_k = min(items)
    if hi_s - lo_s <= 8:
        return (f"五项基本齐平（{lo_s:.0f}~{hi_s:.0f} 分），"
                f"没有明显的最强与最弱；分歧很小")
    hi_p = phrase_of(hi_k, hi_s, zlib.crc32((key + "|hi").encode()) % 3)
    lo_p = phrase_of(lo_k, lo_s, zlib.crc32((key + "|lo").encode()) % 3)
    spread = hi_s - lo_s
    tail = "分歧不大" if spread <= 15 else ("分歧明显" if spread >= 45 else "有一定分歧")
    return (f"最强项 {_fmt_item(IND_NAMES[hi_k], hi_s, hi_p)}；"
            f"最弱项 {_fmt_item(IND_NAMES[lo_k], lo_s, lo_p)}；{tail}")


def build_comment(scores, fgi: float, derivative: float = 0.0) -> dict:
    """生成一句话解读。

    scores: {"vol","volume","futures","safe_haven","strength"} → 0~100
    fgi: 当前恐贪指数 0~100；derivative: 日变化（可缺省）
    """
    s = {k: float(scores.get(k) if scores.get(k) is not None else 50.0) for k in IND_KEYS}
    f = float(fgi)
    d = float(derivative or 0.0)
    key = _state_key(s, f)

    # 1) 结构情形优先（"现在是什么局面"比单看某一项极端更重要）
    for rule in RULES:
        try:
            hit = rule["test"](s, f, d)
        except Exception:
            hit = False
        if hit:
            line = _pick(key, rule["lines"], salt=rule["tag"])
            return {"headline": line, "detail": _detail(s, key),
                    "tags": [rule["tag"]], "state_key": key}

    # 2) 未命中结构情形时，把极端项点出来
    hi_s, hi_k = max((s[k], k) for k in IND_KEYS)
    lo_s, lo_k = min((s[k], k) for k in IND_KEYS)
    if hi_s >= 96 or lo_s <= 4:
        side, (val, ind) = ("high", (hi_s, hi_k)) if hi_s >= 96 else ("low", (lo_s, lo_k))
        line = _pick(key, SINGLE_EXTREME[side], salt="extreme").format(
            name=IND_NAMES[ind], score=val)
        return {"headline": line, "detail": _detail(s, key),
                "tags": ["single_extreme", side], "state_key": key}

    # 3) 兜底：按 FGI 区间
    band = _band_key(f)
    return {"headline": _pick(key, BAND_LINES[band], salt=band),
            "detail": _detail(s, key), "tags": [band], "state_key": key}


def explain(scores, fgi: float, derivative: float = 0.0) -> str:
    c = build_comment(scores, fgi, derivative)
    return f"{c['headline']} —— {c['detail']}"
