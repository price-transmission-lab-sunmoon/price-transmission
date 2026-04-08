"""
KAMIS 도매가 수집기
==============================================
수집 대상: 쇠고기, 땅콩, 바나나, 오렌지 월별 도매가
API: periodProductList (품목코드 직접 지정)
실행 방법: python src/collectors/collect_kamis.py

주의:
- dailyPriceByCategoryList는 부류 필터가 작동하지 않음 (식량작물만 반환)
- periodProductList로 품목코드를 직접 지정해야 정상 조회됨
- 조회 기간이 최대 1년이므로 연도별로 순회하여 수집
"""

import os
import sys
import json
import time
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

CERT_KEY = os.getenv("KAMIS_CERT_KEY", "")
CERT_ID = os.getenv("KAMIS_CERT_ID", "")

if not CERT_KEY:
    print("❌ .env에 KAMIS_CERT_KEY가 없습니다.")
    sys.exit(1)

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "kamis"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"


# ============================================================
# 매핑 파일에서 KAMIS 수집 대상 읽기
# ============================================================
def load_kamis_targets():
    """commodity_mapping.json에서 KAMIS 도매가 수집 대상 추출"""
    mapping_path = PROJECT_ROOT / "config" / "commodity_mapping.json"

    if not mapping_path.exists():
        print(f"❌ 매핑 파일 없음: {mapping_path}")
        sys.exit(1)

    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    targets = []
    for commodity in mapping.get("commodities", []):
        kamis = commodity.get("sources", {}).get("kamis_wholesale", {})
        if kamis.get("status") == "confirmed" and kamis.get("item_code"):
            targets.append({
                "commodity_id": commodity["commodity_id"],
                "name_kr": commodity["name_kr"],
                "category_code": kamis["category_code"],
                "item_code": kamis["item_code"],
                "item_name": kamis.get("item_name", ""),
            })

    return targets


# ============================================================
# API 호출
# ============================================================
def fetch_period_prices(category_code, item_code, start_day, end_day, cls_code="01"):
    """
    periodProductList API로 기간별 도매가 조회

    Parameters
    ----------
    category_code : str  부류코드 (예: "500")
    item_code : str      품목코드 (예: "511")
    start_day : str      시작일 (예: "2020-01-01")
    end_day : str        종료일 (예: "2020-12-31")
    cls_code : str       "01"=도매, "02"=소매
    """
    params = {
        "action": "periodProductList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_product_cls_code": cls_code,
        "p_country_code": "1101",
        "p_startday": start_day,
        "p_endday": end_day,
        "p_convert_kg_yn": "Y",
        "p_item_category_code": category_code,
        "p_item_code": item_code,
        "p_kind_code": "",
        "p_product_rank_code": "",
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        data = resp.json()
    except Exception as e:
        print(f"      ❌ API 호출 실패: {e}")
        return []

    items = data.get("data", {}).get("item", [])
    return items


def parse_price(price_str):
    """가격 문자열을 숫자로 변환 ("-", "," 등 처리)"""
    if not price_str or price_str == "-" or price_str == "0":
        return None
    try:
        return float(str(price_str).replace(",", "").strip())
    except ValueError:
        return None


# ============================================================
# 수집 함수
# ============================================================
def collect_kamis(start_year=2000, end_year=2026):
    """
    KAMIS 도매가 전체 수집

    periodProductList API는 조회 기간이 제한되어 있으므로
    연도별로 순회하여 수집합니다.
    """
    print("=" * 60)
    print(f"  KAMIS 도매가 수집")
    print(f"  기간: {start_year} ~ {end_year}")
    print("=" * 60)

    targets = load_kamis_targets()
    print(f"  수집 대상: {len(targets)}개 품목")
    for t in targets:
        print(f"    {t['commodity_id']:<12} {t['name_kr']} (부류:{t['category_code']}, 품목:{t['item_code']})")

    all_records = []

    for target in targets:
        cid = target["commodity_id"]
        name_kr = target["name_kr"]
        cat_code = target["category_code"]
        item_code = target["item_code"]

        print(f"\n  [{name_kr}] ({cid}) 수집 중...")

        for year in range(start_year, end_year + 1):
            start_day = f"{year}-01-01"
            end_day = f"{year}-12-31"

            items = fetch_period_prices(cat_code, item_code, start_day, end_day)

            if not items:
                continue

            for it in items:
                yyyy = it.get("yyyy", "")
                regday = it.get("regday", "")  # MM/DD 형식
                price = parse_price(it.get("price", ""))

                if not yyyy or not regday or price is None:
                    continue

                # 날짜 변환
                try:
                    date_str = f"{yyyy}-{regday.replace('/', '-')}"
                    date = pd.to_datetime(date_str, format="%Y-%m-%d")
                except Exception:
                    continue

                all_records.append({
                    "date": date,
                    "commodity_id": cid,
                    "item_name": name_kr,
                    "price": price,
                    "unit": "원/kg",
                })

            time.sleep(0.3)

        year_count = len(set(r["date"].year for r in all_records if r["commodity_id"] == cid))
        item_count = len([r for r in all_records if r["commodity_id"] == cid])
        print(f"    → {item_count}건 ({year_count}개 연도)")

    if not all_records:
        print("\n  ❌ 수집된 데이터가 없습니다.")
        return pd.DataFrame()

    # DataFrame 변환
    df = pd.DataFrame(all_records)
    df = df.sort_values(["commodity_id", "date"]).reset_index(drop=True)

    # 일별 원본 저장
    daily_path = RAW_DIR / "kamis_wholesale_daily.csv"
    df.to_csv(daily_path, index=False, encoding="utf-8-sig")
    print(f"\n  💾 일별 원본 저장: {daily_path} ({len(df)}건)")

    # 월평균 집계
    df["year_month"] = df["date"].dt.to_period("M")
    monthly = df.groupby(["year_month", "commodity_id", "item_name"]).agg(
        price_avg=("price", "mean"),
        price_min=("price", "min"),
        price_max=("price", "max"),
        sample_count=("price", "count"),
    ).reset_index()

    monthly["date"] = monthly["year_month"].dt.to_timestamp()
    monthly = monthly.drop(columns=["year_month"])
    monthly = monthly[["date", "commodity_id", "item_name",
                        "price_avg", "price_min", "price_max", "sample_count"]]
    monthly = monthly.sort_values(["commodity_id", "date"]).reset_index(drop=True)

    # 월평균 저장
    monthly_path = RAW_DIR / "kamis_wholesale_monthly.csv"
    monthly.to_csv(monthly_path, index=False, encoding="utf-8-sig")
    print(f"  💾 월평균 저장: {monthly_path} ({len(monthly)}개월)")

    # 요약
    print(f"\n  📋 수집 요약:")
    for cid in sorted(monthly["commodity_id"].unique()):
        sub = monthly[monthly["commodity_id"] == cid]
        print(
            f"    {cid:<12} {sub['item_name'].iloc[0]:<8} "
            f"{len(sub):>4}개월  "
            f"{sub['date'].min().strftime('%Y-%m')}~{sub['date'].max().strftime('%Y-%m')}  "
            f"{sub['price_avg'].min():,.0f}~{sub['price_avg'].max():,.0f} 원/kg"
        )

    return monthly


if __name__ == "__main__":
    collect_kamis()
