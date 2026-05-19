"""
KAMIS periodProductList 파라미터명 테스트 v2
==============================================
v1 결과:
  - p_itemcategorycode (붙여쓰기) + p_item_code (언더스코어) 조합이 유효
  - 날짜 파라미터(p_startday/p_endday)도 무시되는 듯 → 파라미터명 테스트 필요
  - 응답이 list로 올 수 있음 → 에러 핸들링 추가

실행: python tests/debug_kamis_params_v2.py
"""

import os
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


def test_params(label, extra_params):
    """공통 파라미터 + extra_params로 API 호출 후 요약"""
    base = {
        "action": "periodProductList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_product_cls_code": "01",
        "p_country_code": "1101",
        "p_convert_kg_yn": "Y",
    }
    base.update(extra_params)

    try:
        resp = requests.get(BASE_URL, params=base, timeout=45)
        data = resp.json()
    except Exception as e:
        print(f"\n  [{label}]")
        print(f"    ❌ 호출 실패: {e}")
        return

    print(f"\n  [{label}]")

    # 응답이 list일 수 있음
    if isinstance(data, list):
        print(f"    응답이 list (len={len(data)})")
        if data:
            print(f"    첫 요소 키: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")
            # list 안에 item 데이터가 직접 들어있을 수 있음
            first = data[0] if isinstance(data[0], dict) else {}
            print(f"    첫 요소: {json.dumps(first, ensure_ascii=False)[:300]}")
        return

    # dict 응답
    error_code = ""
    items = []

    # data 키 안에 있을 수도, 바로 있을 수도
    data_section = data.get("data", data)
    if isinstance(data_section, dict):
        error_code = data_section.get("error_code", "")
        items_raw = data_section.get("item", [])
    elif isinstance(data_section, list):
        # data 자체가 list
        print(f"    data가 list (len={len(data_section)})")
        if data_section and isinstance(data_section[0], dict):
            print(f"    첫 요소: {json.dumps(data_section[0], ensure_ascii=False)[:300]}")
        return
    else:
        items_raw = []

    # item이 문자열이거나 빈 경우
    if not items_raw or not isinstance(items_raw, list):
        print(f"    error_code: {error_code}")
        print(f"    item 없음 (type={type(items_raw).__name__})")
        raw = json.dumps(data, ensure_ascii=False)
        print(f"    응답 (처음 500자): {raw[:500]}")
        return

    items = items_raw
    print(f"    error_code: {error_code}")
    print(f"    item 개수: {len(items)}")

    first = items[0]
    print(f"    첫 item:")
    for k in ["itemname", "item_name", "kindname", "kind_name",
              "countyname", "yyyy", "regday", "price"]:
        if k in first:
            print(f"      {k:<15} = {first[k]}")

    # 날짜 범위
    dates = set()
    for it in items:
        yyyy = it.get("yyyy", "")
        regday = it.get("regday", "")
        if yyyy and regday:
            dates.add(f"{yyyy}-{regday}")
    if dates:
        sorted_dates = sorted(dates)
        print(f"    날짜 범위: {sorted_dates[0]} ~ {sorted_dates[-1]} ({len(dates)}일)")

    # countyname
    counties = Counter(it.get("countyname", "") for it in items)
    print(f"    countyname: {dict(counties.most_common(5))}")


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS periodProductList 파라미터명 테스트 v2")
    print("=" * 70)

    # ================================================================
    # Part 1: 바나나(416) — 유효했던 혼합 방식으로 날짜 파라미터 테스트
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Part 1: 바나나 — 날짜 파라미터명 테스트")
    print(f"  (품목 파라미터: p_itemcategorycode=400, p_item_code=416 고정)")
    print(f"{'─'*70}")

    # 1-A: 현재 방식 (p_startday / p_endday)
    test_params("날짜: p_startday/p_endday", {
        "p_itemcategorycode": "400",
        "p_item_code": "416",
        "p_startday": "2024-01-01",
        "p_endday": "2024-03-31",
    })

    # 1-B: 붙여쓰기 (p_startdate / p_enddate)
    test_params("날짜: p_startdate/p_enddate", {
        "p_itemcategorycode": "400",
        "p_item_code": "416",
        "p_startdate": "2024-01-01",
        "p_enddate": "2024-03-31",
    })

    # 1-C: p_regday 방식
    test_params("날짜: p_regday=2024-06-15", {
        "p_itemcategorycode": "400",
        "p_item_code": "416",
        "p_regday": "2024-06-15",
    })

    # 1-D: p_yyyy + p_period (monthlySalesList 스타일)
    test_params("날짜: p_yyyy=2024 + p_period=3", {
        "p_itemcategorycode": "400",
        "p_item_code": "416",
        "p_yyyy": "2024",
        "p_period": "3",
    })

    # ================================================================
    # Part 2: 품목별 비교 — 혼합 방식으로 다른 품목이 다른 가격을 주는지
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Part 2: 품목별 비교 (혼합 방식)")
    print(f"{'─'*70}")

    targets = [
        ("바나나", "400", "416"),
        ("오렌지", "400", "420"),
        ("쇠고기", "500", "511"),
        ("땅콩",   "300", "313"),
    ]

    for name, cat, item in targets:
        test_params(f"{name} (cat={cat}, item={item})", {
            "p_itemcategorycode": cat,
            "p_item_code": item,
            "p_startday": "2024-01-01",
            "p_endday": "2024-03-31",
        })

    # ================================================================
    # Part 3: kind_code 테스트 (바나나)
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Part 3: 바나나 kind_code 변형")
    print(f"{'─'*70}")

    for kc in ["", "00", "01", "02"]:
        test_params(f"바나나 kind_code='{kc}'", {
            "p_itemcategorycode": "400",
            "p_item_code": "416",
            "p_kind_code": kc,
            "p_startday": "2024-01-01",
            "p_endday": "2024-03-31",
        })

    # ================================================================
    # Part 4: p_kindcode (붙여쓰기) 테스트
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Part 4: 바나나 p_kindcode (붙여쓰기)")
    print(f"{'─'*70}")

    for kc in ["", "00", "01", "02"]:
        test_params(f"바나나 p_kindcode='{kc}'", {
            "p_itemcategorycode": "400",
            "p_item_code": "416",
            "p_kindcode": kc,
            "p_startday": "2024-01-01",
            "p_endday": "2024-03-31",
        })

    print(f"\n{'='*70}")
    print(f"  테스트 완료")
    print(f"{'='*70}")
