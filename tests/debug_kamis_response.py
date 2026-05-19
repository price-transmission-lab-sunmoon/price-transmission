"""
KAMIS periodProductList API 응답 구조 디버깅
==============================================
목적: 실제 응답에 어떤 품목/품종/등급이 포함되는지 확인
실행: python tests/debug_kamis_response.py
"""

import os
import sys
import json
import requests
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "tests" else script_dir
load_dotenv(project_root / ".env")

CERT_KEY = os.getenv("KAMIS_CERT_KEY", "")
CERT_ID = os.getenv("KAMIS_CERT_ID", "")
BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"

# 4개 품목
TARGETS = [
    {"name": "쇠고기", "cat": "500", "item": "511"},
    {"name": "땅콩",   "cat": "300", "item": "313"},
    {"name": "바나나", "cat": "400", "item": "416"},
    {"name": "오렌지", "cat": "400", "item": "420"},
]


def fetch_raw(cat_code, item_code, start_day, end_day, cls_code="01"):
    """API 원본 응답 반환"""
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
        "p_item_category_code": cat_code,
        "p_item_code": item_code,
        "p_kind_code": "",
        "p_product_rank_code": "",
    }
    resp = requests.get(BASE_URL, params=params, timeout=30)
    return resp.json()


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS periodProductList 응답 구조 디버깅")
    print("=" * 70)

    # 2024년 1년간 데이터로 테스트
    test_period = ("2024-01-01", "2024-12-31")

    for target in TARGETS:
        name = target["name"]
        cat = target["cat"]
        item = target["item"]

        print(f"\n{'─'*70}")
        print(f"  [{name}] 부류:{cat}, 품목:{item}")
        print(f"  조회 기간: {test_period[0]} ~ {test_period[1]}")
        print(f"{'─'*70}")

        try:
            data = fetch_raw(cat, item, test_period[0], test_period[1])
        except Exception as e:
            print(f"  ❌ 호출 실패: {e}")
            continue

        # 1) 최상위 키 확인
        print(f"\n  [1] 응답 최상위 키: {list(data.keys())}")

        # 2) data 내부 키
        data_section = data.get("data", {})
        if isinstance(data_section, dict):
            print(f"  [2] data 내부 키: {list(data_section.keys())}")
            error_code = data_section.get("error_code", "")
            if error_code:
                print(f"      error_code: {error_code}")

        # 3) item 리스트 확인
        items = data_section.get("item", [])
        if not items or not isinstance(items, list):
            print(f"  [3] item이 비어있거나 리스트가 아님: {type(items)}")
            # 전체 응답 일부 출력
            print(f"      응답 (처음 800자):")
            print(f"      {json.dumps(data, ensure_ascii=False)[:800]}")
            continue

        print(f"  [3] item 개수: {len(items)}")

        # 4) 첫 번째 item의 모든 필드 출력
        print(f"\n  [4] 첫 번째 item의 전체 필드:")
        first = items[0]
        for k, v in first.items():
            print(f"      {k:<25} = {v}")

        # 5) 품목명·품종·등급 분포
        item_names = Counter(it.get("item_name", "") for it in items)
        kind_names = Counter(it.get("kind_name", "") for it in items)
        ranks = Counter(it.get("rank", "") for it in items)
        countynames = Counter(it.get("countyname", "") for it in items)

        print(f"\n  [5] item_name 분포:")
        for name_val, cnt in item_names.most_common(10):
            print(f"      {name_val:<20} {cnt}건")

        print(f"\n  [6] kind_name 분포:")
        for kind, cnt in kind_names.most_common(15):
            print(f"      {kind:<20} {cnt}건")

        print(f"\n  [7] rank(등급) 분포:")
        for rank, cnt in ranks.most_common(10):
            print(f"      {rank:<20} {cnt}건")

        print(f"\n  [8] countyname 분포:")
        for county, cnt in countynames.most_common(10):
            print(f"      {county:<20} {cnt}건")

        # 6) 날짜 범위
        dates = set()
        for it in items:
            yyyy = it.get("yyyy", "")
            regday = it.get("regday", "")
            if yyyy and regday:
                dates.add(f"{yyyy}-{regday}")
        if dates:
            sorted_dates = sorted(dates)
            print(f"\n  [9] 날짜 범위: {sorted_dates[0]} ~ {sorted_dates[-1]} ({len(dates)}개 고유 날짜)")

        # 7) 같은 날짜에 몇 건씩 있는지 (첫 번째 날짜 기준)
        if dates:
            first_date = sorted(dates)[0]
            first_yyyy, first_regday = first_date.split("-", 1)
            same_date = [it for it in items
                         if it.get("yyyy") == first_yyyy
                         and it.get("regday") == first_regday.replace("-", "/")]
            print(f"\n  [10] 첫 날짜({first_date})의 건수: {len(same_date)}")
            print(f"       품종별:")
            for it in same_date[:10]:
                print(f"         kind={it.get('kind_name',''):<15} "
                      f"rank={it.get('rank',''):<10} "
                      f"price={it.get('price','')}")

    print(f"\n{'='*70}")
    print(f"  디버깅 완료")
    print(f"{'='*70}")
