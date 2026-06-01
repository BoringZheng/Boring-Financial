from __future__ import annotations

import math
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Category, Transaction

# ---------------------------------------------------------------------------
# configurable thresholds
# ---------------------------------------------------------------------------
SMALL_TXN_THRESHOLD = Decimal("100")        # 小额交易阈值（元）
HIGH_UNIT_PRICE_MULTIPLIER = Decimal("1.5")  # 高单价倍数
EMERGENCY_MONTHS = 6                         # 应急能力基准月数
DIVERSITY_CATEGORY_COUNT = 15                # 消费多样性基准分类数
NEW_MERCHANT_DAYS = 30                       # 新商户回顾天数

# category-name keywords for conspicuous-consumption detection
CONSPICUOUS_KEYWORDS = [
    "餐饮", "美食", "外卖", "餐厅", "饭店", "食堂", "咖啡", "奶茶", "甜品", "小吃", "火锅", "烧烤",
    "服饰", "服装", "衣服", "鞋", "包", "手表", "饰品", "珠宝", "美妆", "护肤", "化妆品", "美容",
    "数码", "电子", "手机", "电脑", "平板", "耳机", "相机", "游戏", "主机",
    "娱乐", "KTV", "电影", "演出", "演唱会", "旅游", "酒店", "机票",
]

# ---------------------------------------------------------------------------
# personality type definitions (16 types, 3-letter codes)
# ---------------------------------------------------------------------------
PERSONALITY_TYPES: dict[str, dict] = {
    "P-S-U": {
        "name": "貔貅型",
        "tagline": "只进不出，省钱界的传奇生物",
        "quote": "我的钱不是花掉了，只是暂时变成了用得上的东西。",
        "academic_basis": "高延迟满足 + 稳定习惯 + 实用主义",
    },
    "P-S-V": {
        "name": "扫地僧",
        "tagline": "看起来朴素，偶尔出手就是大件",
        "quote": "大隐隐于市，大额藏于日常。",
        "academic_basis": "耐心储蓄但品质导向",
    },
    "P-E-U": {
        "name": "旅行青蛙",
        "tagline": "钱花在看不见的地方——体验和探索",
        "quote": "花钱买体验，我的生活不需要仓库。",
        "academic_basis": "储蓄健康 + 愿意为新鲜感付费",
    },
    "P-E-V": {
        "name": "老钱风",
        "tagline": "不跟风不冲动，每件东西都是好货",
        "quote": "买得少，买得好，从不后悔。",
        "academic_basis": "长期主义 + 品质导向",
    },
    "I-S-U": {
        "name": "剁手战士",
        "tagline": "天天喊剁手，每天收快递，都是小东西",
        "quote": "9 块 9 也是爱，100 个 9 块 9 是灾难。",
        "academic_basis": "冲动 + 小额高频",
    },
    "I-S-V": {
        "name": "人间富贵花",
        "tagline": "我买故我在，Logo 越大越好",
        "quote": "Logo 是给别人看的，账单是给自己哭的。",
        "academic_basis": "冲动 + 炫耀性消费",
    },
    "I-E-U": {
        "name": "特种兵消费者",
        "tagline": "什么都试、哪里都去，\"来都来了\"",
        "quote": "来都来了、买都买了、吃都吃了。",
        "academic_basis": "高冲动 + 高探索",
    },
    "I-E-V": {
        "name": "消费主义代言人",
        "tagline": "新款必冲、限量必抢、朋友圈先看",
        "quote": "新款发布的速度就是我赚钱的动力。",
        "academic_basis": "冲动 + 探索 + 炫耀",
    },
    "F-S-U": {
        "name": "佛系散财童子",
        "tagline": "钱花就花了，不记账不纠结，随缘",
        "quote": "记账？那是对生活的不信任。",
        "academic_basis": "心理账户灵活 + 实用消费",
    },
    "F-S-V": {
        "name": "隐形富豪",
        "tagline": "不算账、不省钱，品质生活自然而然",
        "quote": "花了多少？不知道。反正够花。",
        "academic_basis": "灵活 + 品质消费",
    },
    "F-E-U": {
        "name": "快乐小狗",
        "tagline": "哪里好玩去哪里，开心最重要",
        "quote": "省钱的尽头是不快乐。",
        "academic_basis": "灵活 + 兴趣广泛",
    },
    "F-E-V": {
        "name": "氪金玩家",
        "tagline": "人生如游戏，每个爱好都值得满配",
        "quote": "每个爱好都值得满配，直到下个爱好出现。",
        "academic_basis": "随性 + 多样 + 品质",
    },
    "R-S-U": {
        "name": "苦行僧",
        "tagline": "每一笔支出都在 Excel 里有位置",
        "quote": "Excel 里的绿灯是我最大的消费快感。",
        "academic_basis": "严格心理账户 + 习惯固化",
    },
    "R-S-V": {
        "name": "仪式感大师",
        "tagline": "吃饭预算门禁卡，米其林预算在另一张卡",
        "quote": "生活的本质是分类。",
        "academic_basis": "严格分区 + 品质预算",
    },
    "R-E-U": {
        "name": "实验室仓鼠",
        "tagline": "每个品类精打细算，但品类内花式尝试",
        "quote": "预算内最大化多样性。",
        "academic_basis": "严格预算 + 品类内探索",
    },
    "R-E-V": {
        "name": "CFO 人格",
        "tagline": "你管自己叫个人财务，别人管你叫家庭 CFO",
        "quote": "你不理财，财不理你；你理太细，财也怕你。",
        "academic_basis": "全面严格 + 高品质",
    },
}

# ---------------------------------------------------------------------------
# quiz questions (10 questions)
# ---------------------------------------------------------------------------
QUIZ_QUESTIONS: list[dict] = [
    {
        "id": 1,
        "dimension": "time_preference",
        "text": "看到「限时优惠」你会？",
        "options": [
            {"value": 1, "text": "完全无视，我只买需要的"},
            {"value": 2, "text": "会看一眼，但很少被影响"},
            {"value": 3, "text": "经常会因为限时而下单"},
            {"value": 4, "text": "立刻下单，万一错过了呢"},
        ],
    },
    {
        "id": 2,
        "dimension": "mental_accounting",
        "text": "你收到工资后通常会？",
        "options": [
            {"value": 1, "text": "先存一部分，剩下的按预算分配到各类目"},
            {"value": 2, "text": "大概心里有数，主要支出有规划"},
            {"value": 3, "text": "随性花，月底看剩多少"},
            {"value": 4, "text": "从不规划，花完再说"},
        ],
    },
    {
        "id": 3,
        "dimension": "conspicuous_consumption",
        "text": "朋友买了一个新包/新数码产品，你看到后？",
        "options": [
            {"value": 1, "text": "毫无感觉，别人买什么与我无关"},
            {"value": 2, "text": "欣赏一下，但不会因此想买"},
            {"value": 3, "text": "有点心动，会去了解同款或类似产品"},
            {"value": 4, "text": "立刻也想拥有，马上开始搜索下单"},
        ],
    },
    {
        "id": 4,
        "dimension": "openness",
        "text": "你会尝试一家新开的、评价未知的餐厅吗？",
        "options": [
            {"value": 1, "text": "不会，我只去熟悉的店"},
            {"value": 2, "text": "偶尔会，但需要朋友推荐或看到好评"},
            {"value": 3, "text": "经常会，新店开业我总想去试试"},
            {"value": 4, "text": "必须的！我就是朋友圈的新店活地图"},
        ],
    },
    {
        "id": 5,
        "dimension": "mental_accounting",
        "text": "看到账单时，你最惊讶的是什么？",
        "options": [
            {"value": 1, "text": "从不惊讶，每一笔都在我预算之内"},
            {"value": 2, "text": "偶尔有几项超预算，但总体可控"},
            {"value": 3, "text": "经常发现某些类目花超了很多"},
            {"value": 4, "text": "每次都惊讶——我根本没意识到花了这么多"},
        ],
    },
    {
        "id": 6,
        "dimension": "conspicuous_consumption",
        "text": "你更愿意把钱花在？",
        "options": [
            {"value": 1, "text": "实用的东西，性价比第一"},
            {"value": 2, "text": "大部分实用，偶尔犒劳自己买点好的"},
            {"value": 3, "text": "品质和品牌很重要，愿意为此多付钱"},
            {"value": 4, "text": "能让人羡慕的东西最值得花钱"},
        ],
    },
    {
        "id": 7,
        "dimension": "time_preference",
        "text": "打折时你买一个目前不需要但未来可能用的东西？",
        "options": [
            {"value": 1, "text": "从不，只买当下确定需要的"},
            {"value": 2, "text": "很少，除非折扣力度极大"},
            {"value": 3, "text": "偶尔会，\"万一以后用到呢\""},
            {"value": 4, "text": "经常，囤货使我快乐"},
        ],
    },
    {
        "id": 8,
        "dimension": "openness",
        "text": "你的外卖/餐厅消费模式是？",
        "options": [
            {"value": 1, "text": "几乎总点那几家，从不变换"},
            {"value": 2, "text": "有几家常去的，偶尔尝新"},
            {"value": 3, "text": "经常换着吃，每周要试一两家新店"},
            {"value": 4, "text": "每次都要点没吃过的，绝不重复"},
        ],
    },
    {
        "id": 9,
        "dimension": "time_preference",
        "text": "你对大额消费（>5000 元）的态度是？",
        "options": [
            {"value": 1, "text": "精打细算，反复比较后才下手"},
            {"value": 2, "text": "会做功课，但决定后不犹豫"},
            {"value": 3, "text": "差不多就行，早买早享受"},
            {"value": 4, "text": "喜欢就买，不考虑那么多"},
        ],
    },
    {
        "id": 10,
        "dimension": "meta",
        "text": "你觉得自己是哪种类型的消费者？",
        "options": [
            {"value": 1, "text": "理性克制型，每一笔消费都有规划"},
            {"value": 2, "text": "大体理性，偶尔放纵"},
            {"value": 3, "text": "随性而为，开心最重要"},
            {"value": 4, "text": "享受当下，消费是生活乐趣的重要来源"},
        ],
    },
]

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_category_id(transaction: Transaction) -> int | None:
    return transaction.final_category_id or transaction.auto_category_id


def _shannon_index(counts: list[int]) -> float:
    """Shannon diversity index, returns 0..ln(N)."""
    total = sum(counts)
    if total == 0:
        return 0.0
    entropy = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            entropy -= p * math.log(p)
    return entropy


def _scale_to_100(value: float, min_val: float, max_val: float) -> float:
    """Linear scale value from [min_val, max_val] to [0, 100], clamped."""
    if max_val <= min_val:
        return 50.0
    scaled = (value - min_val) / (max_val - min_val) * 100.0
    return max(0.0, min(100.0, scaled))


def _is_conspicuous_category(category_name: str | None) -> bool:
    if not category_name:
        return False
    name = category_name.strip()
    return any(kw in name for kw in CONSPICUOUS_KEYWORDS)


def _dimension_side(dimension: str, value: float) -> str:
    """Return the side label for a dimension value."""
    thresholds = {
        "time_preference": ("Patient", "Impulsive"),
        "mental_accounting": ("Flexible", "Rigid"),
        "conspicuous_consumption": ("Utilitarian", "Veblen"),
        "openness": ("Stable", "Exploratory"),
    }
    low_label, high_label = thresholds.get(dimension, ("Low", "High"))
    return high_label if value >= 50 else low_label


def _dimension_label(dimension: str, value: float) -> str:
    """Return the Chinese label for a dimension value."""
    labels = {
        "time_preference": ("延迟满足型", "即时满足型"),
        "mental_accounting": ("灵活调配", "严格分区"),
        "conspicuous_consumption": ("实用主义", "地位驱动"),
        "openness": ("习惯稳定", "探索尝新"),
    }
    low_label, high_label = labels.get(dimension, ("低", "高"))
    return high_label if value >= 50 else low_label


def _dimension_theory_ref(dimension: str) -> str:
    refs = {
        "time_preference": "Laibson 双曲贴现模型",
        "mental_accounting": "Thaler 心理账户理论",
        "conspicuous_consumption": "Veblen 炫耀性消费理论",
        "openness": "大五人格 Openness 维度",
    }
    return refs.get(dimension, "")


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    norm1 = math.sqrt(sum(x * x for x in v1))
    norm2 = math.sqrt(sum(x * x for x in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    return dot / (norm1 * norm2)


# ---------------------------------------------------------------------------
# core personality computation
# ---------------------------------------------------------------------------

def compute_personality_profile(db: Session, user_id: int) -> dict:
    """Compute the 4-dimension personality profile from all user transactions."""
    transactions = db.scalars(
        select(Transaction).where(Transaction.user_id == user_id)
    ).all()

    if not transactions:
        return _default_profile()

    # --- pre-compute common aggregates ---
    total_income = Decimal("0")
    total_expense = Decimal("0")
    expense_transactions: list[Transaction] = []
    income_transactions: list[Transaction] = []

    for txn in transactions:
        if txn.type == "收入":
            total_income += txn.amount
            income_transactions.append(txn)
        else:
            total_expense += txn.amount
            expense_transactions.append(txn)

    # --- time_preference (现时偏好) ---
    time_pref = _compute_time_preference(total_income, total_expense, expense_transactions)

    # --- mental_accounting (心理账户刚性) ---
    mental_acc = _compute_mental_accounting(db, expense_transactions)

    # --- conspicuous_consumption (炫耀性消费) ---
    conspicuous = _compute_conspicuous_consumption(db, expense_transactions, total_expense)

    # --- openness (消费开放性) ---
    openness = _compute_openness(expense_transactions)

    dimensions = {
        "time_preference": round(time_pref, 1),
        "mental_accounting": round(mental_acc, 1),
        "conspicuous_consumption": round(conspicuous, 1),
        "openness": round(openness, 1),
    }

    classification = _classify_personality(dimensions)

    return {
        "code": classification["code"],
        "name": classification["name"],
        "tagline": classification["tagline"],
        "quote": classification["quote"],
        "match_percent": classification["match_percent"],
        "secondary_code": classification["secondary_code"],
        "secondary_name": classification["secondary_name"],
        "dimensions": [
            _build_dimension_dict("time_preference", time_pref),
            _build_dimension_dict("mental_accounting", mental_acc),
            _build_dimension_dict("conspicuous_consumption", conspicuous),
            _build_dimension_dict("openness", openness),
        ],
    }


def _default_profile() -> dict:
    dims = {
        "time_preference": 50.0,
        "mental_accounting": 50.0,
        "conspicuous_consumption": 50.0,
        "openness": 50.0,
    }
    classification = _classify_personality(dims)
    return {
        "code": classification["code"],
        "name": classification["name"],
        "tagline": classification["tagline"],
        "quote": classification["quote"],
        "match_percent": 0.0,
        "secondary_code": classification["secondary_code"],
        "secondary_name": classification["secondary_name"],
        "dimensions": [
            _build_dimension_dict("time_preference", 50.0),
            _build_dimension_dict("mental_accounting", 50.0),
            _build_dimension_dict("conspicuous_consumption", 50.0),
            _build_dimension_dict("openness", 50.0),
        ],
    }


def _compute_time_preference(
    total_income: Decimal,
    total_expense: Decimal,
    expense_transactions: list[Transaction],
) -> float:
    # savings rate
    if total_income > 0:
        savings_rate = float((total_income - total_expense) / total_income)
        savings_rate = max(0.0, min(1.0, savings_rate))
    else:
        savings_rate = 0.0

    # small transaction ratio
    if expense_transactions:
        small_count = sum(1 for txn in expense_transactions if txn.amount < SMALL_TXN_THRESHOLD)
        small_ratio = small_count / len(expense_transactions)
    else:
        small_ratio = 0.0

    return (1.0 - savings_rate) * 50.0 + small_ratio * 50.0


def _compute_mental_accounting(
    db: Session,
    expense_transactions: list[Transaction],
) -> float:
    """Compute mental accounting rigidity from category spending variance."""
    if not expense_transactions:
        return 50.0

    # group spending by category
    cat_spending: dict[int, Decimal] = defaultdict(Decimal)
    uncategorized = Decimal("0")
    for txn in expense_transactions:
        cat_id = _resolve_category_id(txn)
        if cat_id is not None:
            cat_spending[cat_id] += txn.amount
        else:
            uncategorized += txn.amount

    # include uncategorized as one bucket
    all_values = list(cat_spending.values())
    if uncategorized > 0:
        all_values.append(uncategorized)

    if len(all_values) <= 1:
        return 50.0

    total = sum(all_values)
    if total == 0:
        return 50.0

    proportions = [float(v / total) for v in all_values]
    mean_p = sum(proportions) / len(proportions)
    variance = sum((p - mean_p) ** 2 for p in proportions) / len(proportions)
    std_dev = math.sqrt(variance)

    # scale: typical max std for uniform distribution over 5 categories is ~0.15
    # map std_dev roughly 0..0.25 to 0..100
    return min(std_dev / 0.25 * 100.0, 100.0)


def _compute_conspicuous_consumption(
    db: Session,
    expense_transactions: list[Transaction],
    total_expense: Decimal,
) -> float:
    """Compute conspicuous consumption tendency."""
    if not expense_transactions or total_expense == 0:
        return 50.0

    # identify conspicuous-category transactions
    category_ids = {_resolve_category_id(txn) for txn in expense_transactions if _resolve_category_id(txn) is not None}
    category_lookup: dict[int, str] = {}
    if category_ids:
        categories = db.scalars(select(Category).where(Category.id.in_(category_ids))).all()
        category_lookup = {c.id: c.name for c in categories}

    conspicuous_total = Decimal("0")
    for txn in expense_transactions:
        cat_id = _resolve_category_id(txn)
        cat_name = category_lookup.get(cat_id) if cat_id else None
        if _is_conspicuous_category(cat_name):
            conspicuous_total += txn.amount

    ratio = float(conspicuous_total / total_expense)
    # scale: typical conspicuous ratio roughly 0..0.6 → 0..100
    return min(ratio / 0.6 * 100.0, 100.0)


def _compute_openness(expense_transactions: list[Transaction]) -> float:
    """Compute consumption openness via merchant diversity + new merchant ratio."""
    if not expense_transactions:
        return 50.0

    # merchant Shannon index
    merchant_counts: dict[str, int] = defaultdict(int)
    for txn in expense_transactions:
        merchant = (txn.merchant_norm or txn.merchant or "未知商户").strip()
        merchant_counts[merchant] += 1

    n_merchants = len(merchant_counts)
    shannon = _shannon_index(list(merchant_counts.values()))
    max_shannon = math.log(n_merchants) if n_merchants > 1 else 1.0
    diversity_score = (shannon / max_shannon * 100.0) if max_shannon > 0 else 50.0

    # new merchant ratio (past NEW_MERCHANT_DAYS) relative to the imported
    # ledger, not wall-clock time. Users often analyze historical statements.
    latest_occurred_at = max(txn.occurred_at for txn in expense_transactions)
    cutoff = latest_occurred_at - timedelta(days=NEW_MERCHANT_DAYS)

    old_merchants: set[str] = set()
    recent_merchants: set[str] = set()
    for txn in expense_transactions:
        merchant = (txn.merchant_norm or txn.merchant or "未知商户").strip()
        if txn.occurred_at < cutoff:
            old_merchants.add(merchant)
        else:
            recent_merchants.add(merchant)

    new_merchants = recent_merchants - old_merchants
    novelty_ratio = len(new_merchants) / len(recent_merchants) if recent_merchants else 0.0
    novelty_score = novelty_ratio * 100.0

    return (diversity_score + novelty_score) / 2.0


# ---------------------------------------------------------------------------
# personality classification
# ---------------------------------------------------------------------------

def _classify_personality(dimensions: dict) -> dict:
    """Map 4 dimension scores to a 3-letter personality code."""
    tp = dimensions.get("time_preference", 50.0)
    mc = dimensions.get("mental_accounting", 50.0)
    cc = dimensions.get("conspicuous_consumption", 50.0)
    oa = dimensions.get("openness", 50.0)

    # first letter: whichever of TP or MC deviates more from 50
    tp_dev = abs(tp - 50.0)
    mc_dev = abs(mc - 50.0)

    if tp_dev >= mc_dev:
        first = "P" if tp < 50 else "I"
    else:
        first = "F" if mc < 50 else "R"

    second = "S" if oa < 50 else "E"
    third = "U" if cc < 50 else "V"

    code = f"{first}-{second}-{third}"
    personality = PERSONALITY_TYPES.get(code, PERSONALITY_TYPES["P-S-U"])

    # match_percent: average distance from 50, scaled to 0-100
    avg_distance = (tp_dev + mc_dev + abs(cc - 50.0) + abs(oa - 50.0)) / 4.0
    match_percent = round(avg_distance / 50.0 * 100.0, 1)

    # secondary code: flip dimension closest to 50
    dim_deviations = {
        "tp": tp_dev,
        "mc": mc_dev,
        "cc": abs(cc - 50.0),
        "oa": abs(oa - 50.0),
    }
    closest_dim = min(dim_deviations, key=dim_deviations.get)

    if closest_dim == "tp":
        first2 = "I" if first == "P" else ("P" if first == "I" else first)
    elif closest_dim == "mc":
        first2 = "R" if first == "F" else ("F" if first == "R" else first)
    else:
        first2 = first

    if closest_dim == "oa":
        second2 = "E" if second == "S" else "S"
    else:
        second2 = second

    if closest_dim == "cc":
        third2 = "V" if third == "U" else "U"
    else:
        third2 = third

    secondary_code = f"{first2}-{second2}-{third2}"
    secondary = PERSONALITY_TYPES.get(secondary_code, PERSONALITY_TYPES["P-S-U"])

    return {
        "code": code,
        "name": personality["name"],
        "tagline": personality["tagline"],
        "quote": personality["quote"],
        "match_percent": match_percent,
        "secondary_code": secondary_code,
        "secondary_name": secondary["name"],
    }


# ---------------------------------------------------------------------------
# interpretation builder
# ---------------------------------------------------------------------------

def _build_dimension_dict(dimension: str, value: float) -> dict:
    interpretations = {
        "time_preference": {
            "Patient": "你倾向于延迟满足，注重长期财务规划。你的消费决策受即时诱惑的影响较小，更关注未来的财务安全。",
            "Impulsive": "你倾向于即时满足，享受当下的消费体验。你对限时优惠和促销活动较为敏感，储蓄意愿相对较低。",
        },
        "mental_accounting": {
            "Flexible": "你的心理账户较为灵活，不同类目的支出可以自由调配。你不会死板地按预算分区花钱，消费决策更随性。",
            "Rigid": "你的心理账户结构较为严格，各类目支出界限清晰。你可能在心理上为不同消费类别设立了独立的\"账户\"，切换不灵活。",
        },
        "conspicuous_consumption": {
            "Utilitarian": "你是实用主义消费者，消费以功能和性价比为导向。品牌溢价和社交展示对你的消费决策影响较小。",
            "Veblen": "你有一定的炫耀性消费倾向，注重品牌、品质和社交展示价值。花钱不仅是满足需求，也是身份和品位的表达。",
        },
        "openness": {
            "Stable": "你的消费习惯较为稳定，倾向于在熟悉的商家和品类中消费。你对新体验的尝试意愿较低，消费模式可预测。",
            "Exploratory": "你乐于探索新的消费体验，商户选择多样，愿意尝试新品牌、新品类和新消费场景。",
        },
    }

    side = _dimension_side(dimension, value)
    label = _dimension_label(dimension, value)
    theory_ref = _dimension_theory_ref(dimension)
    side_interpretations = interpretations.get(dimension, {})
    interpretation = side_interpretations.get(side, "")

    return {
        "name": dimension,
        "value": round(value, 1),
        "side": side,
        "label": label,
        "theory_ref": theory_ref,
        "interpretation": interpretation,
    }


# ---------------------------------------------------------------------------
# financial health
# ---------------------------------------------------------------------------

def compute_financial_health(db: Session, user_id: int) -> dict:
    """Compute 5-dimension financial health score."""
    transactions = db.scalars(
        select(Transaction).where(Transaction.user_id == user_id)
    ).all()

    if not transactions:
        return _default_health()

    # separate income / expense
    total_income = Decimal("0")
    total_expense = Decimal("0")
    monthly_income: dict[str, Decimal] = defaultdict(Decimal)
    monthly_expense: dict[str, Decimal] = defaultdict(Decimal)

    category_ids: set[int] = set()
    for txn in transactions:
        month_key = txn.occurred_at.strftime("%Y-%m")
        if txn.type == "收入":
            total_income += txn.amount
            monthly_income[month_key] += txn.amount
        else:
            total_expense += txn.amount
            monthly_expense[month_key] += txn.amount
            cat_id = _resolve_category_id(txn)
            if cat_id is not None:
                category_ids.add(cat_id)

    # 1. savings_rate
    if total_income > 0:
        savings_rate = float((total_income - total_expense) / total_income)
        savings_rate = max(0.0, min(1.0, savings_rate))
    else:
        savings_rate = 0.0
    savings_score = round(savings_rate * 100.0, 1)

    # 2. income_stability
    income_values = [float(v) for v in monthly_income.values()]
    income_stability = _stability_score(income_values)

    # 3. spending_diversity
    diversity_score = round(min(len(category_ids) / DIVERSITY_CATEGORY_COUNT * 100.0, 100.0), 1)

    # 4. expense_volatility
    expense_values = [float(v) for v in monthly_expense.values()]
    expense_volatility = _stability_score(expense_values)

    # 5. emergency_capacity
    savings_total = total_income - total_expense
    months_with_expense = len(monthly_expense)
    if months_with_expense > 0 and total_expense > 0:
        avg_monthly_expense = float(total_expense / months_with_expense)
        if avg_monthly_expense > 0:
            emergency_months = max(0.0, float(savings_total) / avg_monthly_expense)
            emergency_score = round(min(emergency_months / EMERGENCY_MONTHS * 100.0, 100.0), 1)
        else:
            emergency_score = 100.0
    else:
        emergency_score = 0.0

    dimensions = {
        "savings_rate": savings_score,
        "income_stability": income_stability,
        "spending_diversity": diversity_score,
        "expense_volatility": expense_volatility,
        "emergency_capacity": emergency_score,
    }

    total_score = round(sum(dimensions.values()) / 5.0, 1)
    grade = _health_grade(total_score)
    suggestions = _health_suggestions(dimensions)

    return {
        "total_score": total_score,
        "grade": grade,
        "dimensions": [
            {"name": "savings_rate", "value": savings_score, "label": "储蓄率"},
            {"name": "income_stability", "value": income_stability, "label": "收入稳定性"},
            {"name": "spending_diversity", "value": diversity_score, "label": "消费多样性"},
            {"name": "expense_volatility", "value": expense_volatility, "label": "支出波动"},
            {"name": "emergency_capacity", "value": emergency_score, "label": "应急能力"},
        ],
        "suggestions": suggestions,
    }


def _default_health() -> dict:
    return {
        "total_score": 50.0,
        "grade": "C",
        "dimensions": [
            {"name": "savings_rate", "value": 50.0, "label": "储蓄率"},
            {"name": "income_stability", "value": 50.0, "label": "收入稳定性"},
            {"name": "spending_diversity", "value": 50.0, "label": "消费多样性"},
            {"name": "expense_volatility", "value": 50.0, "label": "支出波动"},
            {"name": "emergency_capacity", "value": 50.0, "label": "应急能力"},
        ],
        "suggestions": ["暂无足够数据，请先导入账单后再查看财务健康评分。"],
    }


def _stability_score(monthly_values: list[float]) -> float:
    """Convert monthly values to a stability score (lower CV = higher score)."""
    n = len(monthly_values)
    if n <= 1:
        return 50.0
    mean_val = sum(monthly_values) / n
    if mean_val == 0:
        return 50.0
    variance = sum((v - mean_val) ** 2 for v in monthly_values) / n
    cv = math.sqrt(variance) / mean_val
    # CV of 0 → 100, CV of 1.0+ → 0
    return round(max(0.0, 100.0 - cv * 100.0), 1)


def _health_grade(total_score: float) -> str:
    if total_score >= 90:
        return "S"
    elif total_score >= 75:
        return "A"
    elif total_score >= 55:
        return "B"
    elif total_score >= 35:
        return "C"
    else:
        return "D"


def _health_suggestions(dimensions: dict) -> list[str]:
    templates = {
        "savings_rate": "你的储蓄率偏低，建议将月收入的至少 20% 用于储蓄或投资，建立财务安全垫。",
        "income_stability": "你的收入波动较大，建议建立 3-6 个月的应急基金以应对收入不稳定的风险。",
        "spending_diversity": "你的消费多样性较低，生活支出较为单一，可以适当增加自我投资和体验类消费。",
        "expense_volatility": "你的月度支出波动较大，建议设定月度预算上限，减少非必要的冲动消费。",
        "emergency_capacity": "你的应急能力不足，建议逐步积累至少 3-6 个月生活支出的应急储备金。",
    }
    suggestions: list[str] = []
    for dim_name, score in dimensions.items():
        if score < 60 and dim_name in templates:
            suggestions.append(templates[dim_name])

    if not suggestions:
        suggestions.append("各项指标良好，继续保持当前的财务习惯！")

    return suggestions


# ---------------------------------------------------------------------------
# quiz scoring
# ---------------------------------------------------------------------------

def compute_quiz_result(answers: list[int], data_dimensions: list[dict]) -> dict:
    """Score quiz answers and compare with data-driven profile."""
    # collect dimension → answers mapping from quiz questions
    dim_answers: dict[str, list[int]] = defaultdict(list)
    for question, answer_value in zip(QUIZ_QUESTIONS, answers):
        dim = question["dimension"]
        if dim == "meta":
            # meta question contributes to all 4 dimensions
            for d in ["time_preference", "mental_accounting", "conspicuous_consumption", "openness"]:
                dim_answers[d].append(answer_value)
        else:
            dim_answers[dim].append(answer_value)

    # compute self-assessed dimension scores (1-4 scale → 0-100)
    self_dimensions: dict[str, float] = {}
    for dim in ["time_preference", "mental_accounting", "conspicuous_consumption", "openness"]:
        values = dim_answers.get(dim, [2])
        avg = sum(values) / len(values)
        score = round((avg - 1.0) / 3.0 * 100.0, 1)
        self_dimensions[dim] = score

    # data dimensions as simple dict
    data_dims = {d["name"]: d["value"] for d in data_dimensions}

    # cosine similarity
    dim_order = ["time_preference", "mental_accounting", "conspicuous_consumption", "openness"]
    data_vec = [data_dims.get(d, 50.0) for d in dim_order]
    self_vec = [self_dimensions[d] for d in dim_order]
    similarity = round(_cosine_similarity(data_vec, self_vec), 4)

    # biggest gap
    gaps = {d: abs(self_dimensions[d] - data_dims.get(d, 50.0)) for d in dim_order}
    biggest_gap_dim = max(gaps, key=gaps.get)
    gap_value = round(gaps[biggest_gap_dim], 1)

    # bias analysis text
    bias_analysis = _build_bias_analysis(dim_order, data_dims, self_dimensions, biggest_gap_dim, gap_value)

    return {
        "self_assessment": {
            "dimensions": {
                d: self_dimensions[d] for d in dim_order
            }
        },
        "comparison": {
            "cosine_similarity": similarity,
            "biggest_gap": {
                "dimension": biggest_gap_dim,
                "self_score": self_dimensions[biggest_gap_dim],
                "data_score": data_dims.get(biggest_gap_dim, 50.0),
                "gap": gap_value,
                "analysis": _gap_analysis(biggest_gap_dim, self_dimensions[biggest_gap_dim], data_dims.get(biggest_gap_dim, 50.0)),
                "theory_ref": _dimension_theory_ref(biggest_gap_dim),
            },
            "bias_analysis": bias_analysis,
        },
    }


def _build_bias_analysis(
    dim_order: list[str],
    data_dims: dict,
    self_dims: dict,
    biggest_gap_dim: str,
    gap_value: float,
) -> str:
    dim_names = {
        "time_preference": "现时偏好",
        "mental_accounting": "心理账户",
        "conspicuous_consumption": "炫耀性消费",
        "openness": "消费开放性",
    }

    similarity = _cosine_similarity(
        [data_dims.get(d, 50.0) for d in dim_order],
        [self_dims[d] for d in dim_order],
    )
    if similarity > 0.7:
        consistency = "高度一致"
        note = "说明你对自身消费习惯有较准确的认知。"
    elif similarity > 0.4:
        consistency = "基本一致"
        note = "你在部分维度上对自我的认知与数据存在一定偏差。"
    else:
        consistency = "存在较大差异"
        note = "你可能对自己的消费习惯存在较明显的认知偏差，建议结合数据重新审视。"

    biggest_name = dim_names.get(biggest_gap_dim, biggest_gap_dim)
    if gap_value > 20:
        gap_desc = "明显"
    elif gap_value > 10:
        gap_desc = "一定"
    else:
        gap_desc = "轻微"

    return (
        f"你的自评人格与数据人格{consistency}。{note}"
        f"最大的认知偏差出现在「{biggest_name}」维度（差距 {gap_value:.1f} 分），"
        f"你对该维度的自我认知与实际消费数据存在{gap_desc}差异。"
    )


def _gap_analysis(dimension: str, self_score: float, data_score: float) -> str:
    dim_names = {
        "time_preference": "现时偏好",
        "mental_accounting": "心理账户刚性",
        "conspicuous_consumption": "炫耀性消费倾向",
        "openness": "消费开放性",
    }
    name = dim_names.get(dimension, dimension)
    diff = self_score - data_score

    if abs(diff) <= 10:
        return f"你在「{name}」维度上的自评与数据基本一致，说明你对该消费特质有清晰的自我认知。"
    elif diff > 0:
        return (
            f"你自认为在「{name}」维度上得分较高（{self_score:.0f}），但实际消费数据得分较低（{data_score:.0f}）。"
            f"这可能意味着你高估了自己在这一维度的消费倾向。"
        )
    else:
        return (
            f"你的消费数据显示「{name}」得分较高（{data_score:.0f}），但你自评得分较低（{self_score:.0f}）。"
            f"这可能是一种\"自利偏差\"——你倾向于用更积极的词汇描述自己的消费行为。"
        )
