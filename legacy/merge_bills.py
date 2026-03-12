# merge_bills.py
# -*- coding: utf-8 -*-
"""
Merge WeChat & Alipay statements into a unified CSV (Obsidian-friendly)
with category mapping by BOTH merchant and keyword, priority & regex.

Usage:
1) Put WeChat/Alipay CSV/XLS/XLSX into ./input
2) Prepare ./category_map.csv (columns: priority,merchant,keyword,category,subcategory,regex)
3) Run:  python merge_bills.py
4) Output: ./output/merged.csv
"""

import os
import re
import csv
import glob
import unicodedata
from datetime import datetime

import pandas as pd

# ---------------- Config ----------------
INPUT_DIR = "./input"
OUTPUT_DIR = "./output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "merged.csv")
CATEGORY_MAP_FILE = "./category_map.csv"

# 调试：导出命中品牌与未命中样本，便于排错
DEBUG = True
DEBUG_BRANDS = ["肯德基", "kfc", "麦当劳", "mcdonald", "星巴克", "starbucks", "喜茶", "heytea"]

# ---------------- Helpers ----------------
def _clean_amount(x):
    if pd.isna(x):
        return None
    s = str(x).strip().replace(",", "")
    s = re.sub(r"[￥¥]", "", s)
    s = s.replace("=", "").replace("(", "-").replace(")", "")
    try:
        return float(s)
    except Exception:
        return None


def _to_date(s):
    if pd.isna(s):
        return None
    s = str(s).strip()
    fmts = [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
        "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y.%m.%d"
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            pass
    # fallback
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return None


def _normalize_text(s: str) -> str:
    """中文账单文本规范化：
    - 全角->半角（NFKC）
    - 去不可见空格（U+00A0/U+200B），合并多空格
    - 小写
    - 仍然保留去掉括号中的门店/备注
    """
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u00A0", " ").replace("\u200B", "")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.lower()
    #s = re.sub(r"[（(].*?[)）]", "", s)  # 删除括号内容
    return s


def _try_read(path):
    """Robust reader: Excel/CSV 自动多编码、多 skiprows 尝试，跳过导出说明行。"""
    lower = path.lower()
    if lower.endswith((".xls", ".xlsx")):
        # 需要 openpyxl；若未安装，请: pip install openpyxl
        try:
            df = pd.read_excel(path)
        except Exception as e:
            raise RuntimeError(f"Read Excel failed ({os.path.basename(path)}): {e}")
        # 若首列不像表头，尝试跳过若干行
        if df.shape[1] > 0 and not any(k in str(df.columns[0]) for k in ["交易", "时间"]):
            for k in [1, 2, 3, 4, 5, 10]:
                try:
                    df2 = pd.read_excel(path, skiprows=k)
                    if df2.shape[1] > 0 and any("交易" in str(c) or "时间" in str(c) for c in df2.columns):
                        return df2
                except Exception:
                    pass
        return df

    # CSV：多编码尝试；若首列不像表头，尝试 skiprows
    for enc in ["utf-8-sig", "utf-8", "gbk", "gb18030", "cp936", "latin1"]:
        try:
            df = pd.read_csv(path, encoding=enc)
            if df.shape[1] > 0 and not any("交易" in str(c) or "时间" in str(c) for c in df.columns):
                for k in [1, 2, 3, 4, 5, 10]:
                    try:
                        df2 = pd.read_csv(path, encoding=enc, skiprows=k)
                        if df2.shape[1] > 0 and any("交易" in str(c) or "时间" in str(c) for c in df2.columns):
                            return df2
                    except Exception:
                        pass
            return df
        except Exception:
            continue
    # 最后兜底
    return pd.read_csv(path)


def _load_category_rules():
    """读取 category_map.csv（多编码 & 列名容错），返回按 priority 降序的规则列表。"""
    if not os.path.exists(CATEGORY_MAP_FILE):
        print("No category_map.csv found. Skip categorization.")
        return []

    df = None
    last_err = None
    for enc in ["utf-8-sig", "utf-8", "gbk", "gb18030", "cp936", "latin1"]:
        try:
            df = pd.read_csv(CATEGORY_MAP_FILE, encoding=enc)
            break
        except Exception as e:
            last_err = e
            df = None
    if df is None:
        print(f"Warning: cannot read category_map.csv ({type(last_err).__name__}). Skip categorization.")
        return []

    # 规范列名
    df.columns = [str(c).replace("\ufeff", "").strip().lower() for c in df.columns]
    # 缺列补齐
    for c in ["priority", "merchant", "keyword", "category", "subcategory", "regex"]:
        if c not in df.columns:
            df[c] = ""

    def to_int(x, default=0):
        try:
            return int(float(x))
        except Exception:
            return default

    rules = []
    for _, row in df.iterrows():
        pri = to_int(row.get("priority", 0))
        cat = str(row.get("category", "") if not pd.isna(row.get("category", "")) else "").strip()
        if not cat:
            continue
        rules.append({
            "priority": pri,
            "merchant": "" if pd.isna(row.get("merchant", "")) else str(row.get("merchant", "")).strip(),
            "keyword": "" if pd.isna(row.get("keyword", "")) else str(row.get("keyword", "")).strip(),
            "category": cat,
            "subcategory": "" if pd.isna(row.get("subcategory", "")) else str(row.get("subcategory", "")).strip(),
            "regex": str(row.get("regex", "0")).strip() in ["1", "true", "True"],
        })
    rules.sort(key=lambda r: r["priority"], reverse=True)
    return rules


def _classify(note, merchant, item, rules):
    """更鲁棒的分类匹配。
    - 先规范化 merchant/item/note
    - 若规则只有 merchant，则在 (merchant+item+note) 合并文本中搜索（避免品牌落在商品说明里漏匹配）
    - 非正则时支持 'a|b|c' 多别名
    - 正则时 IGNORECASE
    """
    m_raw = "" if merchant is None else str(merchant)
    i_raw = "" if item is None else str(item)
    n_raw = "" if note is None else str(note)

    mtext = _normalize_text(m_raw)
    itext = _normalize_text(i_raw)
    ntext = _normalize_text(n_raw)

    itext_join = " ".join([itext, ntext]).strip()
    fulltext   = " ".join([mtext, itext, ntext]).strip()

    for r in rules:
        ok = True

        # 商家条件
        if r["merchant"]:
            patt = _normalize_text(r["merchant"])
            # keyword 为空时，商家搜索目标扩大到 fulltext
            target = fulltext if not r.get("keyword") else mtext
            if r["regex"]:
                try:
                    if re.search(patt, target, re.IGNORECASE) is None:
                        ok = False
                except Exception:
                    ok = False
            else:
                variants = [v for v in patt.split("|") if v]
                if not any(v in target for v in variants):
                    ok = False

        # 关键字条件（只在 item/note）
        if ok and r.get("keyword"):
            pattk = _normalize_text(r["keyword"])
            if r["regex"]:
                try:
                    if re.search(pattk, itext_join, re.IGNORECASE) is None:
                        ok = False
                except Exception:
                    ok = False
            else:
                variants = [v for v in pattk.split("|") if v]
                if not any(v in itext_join for v in variants):
                    ok = False

        if ok:
            return r["category"], r["subcategory"]

    return "", ""


# ---------------- Parsers ----------------
def parse_alipay(df_raw):
    cols = {c.strip(): c for c in df_raw.columns}
    c_time = next((cols.get(k) for k in ["交易时间", "时间", "创建时间", "支付时间"] if k in cols), None)
    c_io = next((cols.get(k) for k in ["收/支", "收支", "收支类型"] if k in cols), None)
    c_amount = next((cols.get(k) for k in ["金额（元）", "金额(元)", "金额", "交易金额"] if k in cols), None)
    c_merchant = next((cols.get(k) for k in ["交易对方", "对方", "商家", "商户名称"] if k in cols), None)
    c_item = next((cols.get(k) for k in ["商品说明", "商品", "商品名称", "标题", "事由"] if k in cols), None)
    c_status = next((cols.get(k) for k in ["交易状态", "状态"] if k in cols), None)
    c_method = next((cols.get(k) for k in ["支付方式", "收/付款方式", "资金渠道"] if k in cols), None)
    c_note = next((cols.get(k) for k in ["备注", "用户备注", "附言"] if k in cols), None)
    if not (c_time and c_amount):
        return None

    out = []
    for _, r in df_raw.iterrows():
        dt = _to_date(r.get(c_time))
        amt = _clean_amount(r.get(c_amount))
        if amt is None:
            continue
        io = str(r.get(c_io, "")).strip()
        if io in ["支出", "转出"]:
            typ = "支出"
        elif io in ["收入", "转入"]:
            typ = "收入"
        else:
            typ = "支出"
        out.append({
            "date": dt, "type": typ, "amount": abs(amt),
            "merchant": r.get(c_merchant, ""), "item": r.get(c_item, ""),
            "method": r.get(c_method, ""), "status": r.get(c_status, ""),
            "platform": "Alipay", "note": r.get(c_note, "")
        })
    return pd.DataFrame(out)


def parse_wechat(df_raw):
    cols = {c.strip(): c for c in df_raw.columns}
    c_time = next((cols.get(k) for k in ["交易时间", "时间", "支付时间"] if k in cols), None)
    c_type = next((cols.get(k) for k in ["交易类型", "类型"] if k in cols), None)
    c_amount = next((cols.get(k) for k in ["金额(元)", "金额（元）", "金额", "交易金额(元)"] if k in cols), None)
    c_io = next((cols.get(k) for k in ["收/支", "收支"] if k in cols), None)
    c_merchant = next((cols.get(k) for k in ["交易对方", "商户名称", "收/付款方"] if k in cols), None)
    c_item = next((cols.get(k) for k in ["商品", "商品说明", "商品名称"] if k in cols), None)
    c_status = next((cols.get(k) for k in ["当前状态", "交易状态", "状态"] if k in cols), None)
    c_method = next((cols.get(k) for k in ["支付方式", "收/付款方式", "资金渠道"] if k in cols), None)
    c_note = next((cols.get(k) for k in ["备注", "用户备注", "附言"] if k in cols), None)
    if not (c_time and c_amount):
        return None

    out = []
    for _, r in df_raw.iterrows():
        dt = _to_date(r.get(c_time))
        amt = _clean_amount(r.get(c_amount))
        if amt is None:
            continue
        io = str(r.get(c_io, "")).strip()
        typ_guess = str(r.get(c_type, "")).strip()
        if io == "支出":
            typ = "支出"
        elif io == "收入":
            typ = "收入"
        else:
            if any(k in typ_guess for k in ["退款", "转入", "收入"]):
                typ = "收入"
            else:
                typ = "支出"
        out.append({
            "date": dt, "type": typ, "amount": abs(amt),
            "merchant": r.get(c_merchant, ""), "item": r.get(c_item, ""),
            "method": r.get(c_method, ""), "status": r.get(c_status, ""),
            "platform": "WeChat", "note": r.get(c_note, "")
        })
    return pd.DataFrame(out)


# ---------------- Main ----------------
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = []
    for ext in ("*.csv", "*.xls", "*.xlsx"):
        files.extend(glob.glob(os.path.join(INPUT_DIR, ext)))
    if not files:
        print(f"No files found in {INPUT_DIR}")
        return

    dfs = []
    for fp in files:
        try:
            df0 = _try_read(fp)
            df0 = df0.dropna(how="all")
            df = parse_alipay(df0)
            if df is None:
                df = parse_wechat(df0)
            if df is None:
                print(f"Unrecognized format, skip: {os.path.basename(fp)}")
                continue
            dfs.append(df)
            print(f"Parsed {os.path.basename(fp)}: {len(df)} rows")
        except Exception as e:
            print(f"Error reading {fp}: {e}")

    if not dfs:
        print("No recognizable files parsed.")
        return

    merged = pd.concat(dfs, ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.dropna(subset=["date", "amount"]).sort_values("date").reset_index(drop=True)

    rules = _load_category_rules()
    if rules:
        cats, subs = [], []
        for _, r in merged.iterrows():
            c1, c2 = _classify(r.get("note", ""), r.get("merchant", ""), r.get("item", ""), rules)
            cats.append(c1)
            subs.append(c2)
        merged["category"] = cats
        merged["subcategory"] = subs
    else:
        merged["category"] = ""
        merged["subcategory"] = ""

    # 导出调试信息
    if DEBUG:
        try:
            pd.DataFrame(rules).to_csv(os.path.join(OUTPUT_DIR, "rules_loaded.csv"),
                                       index=False, encoding="utf-8-sig")
        except Exception:
            pass

        mask_brand = merged.apply(
            lambda r: any(
                b.lower() in _normalize_text(
                    " ".join([str(r.get("merchant","")), str(r.get("item","")), str(r.get("note",""))])
                )
                for b in DEBUG_BRANDS
            ),
            axis=1
        )
        brand_hits = merged[mask_brand].copy()
        if not brand_hits.empty:
            brand_hits["merchant_norm"] = brand_hits["merchant"].apply(_normalize_text)
            brand_hits["item_norm"] = brand_hits["item"].apply(_normalize_text)
            brand_hits["note_norm"] = brand_hits["note"].apply(_normalize_text)
            brand_hits.to_csv(os.path.join(OUTPUT_DIR, "debug_brand_hits.csv"),
                              index=False, encoding="utf-8-sig")

        unmatched = merged[merged["category"] == ""].copy()
        if not unmatched.empty:
            unmatched.head(200)[["date","platform","merchant","item","note","amount"]]\
                .to_csv(os.path.join(OUTPUT_DIR, "unmatched_preview.csv"),
                        index=False, encoding="utf-8-sig")

    # 最终列顺序
    col_order = ["date", "type", "category", "subcategory", "amount", "platform",
                 "merchant", "item", "method", "status", "note"]
    for c in col_order:
        if c not in merged.columns:
            merged[c] = ""
    merged = merged[col_order]

    merged.to_csv(OUTPUT_FILE, index=False, quoting=csv.QUOTE_MINIMAL, encoding="utf-8-sig")
    print(f"Done. Output -> {OUTPUT_FILE} ({len(merged)} rows)")


if __name__ == "__main__":
    main()
