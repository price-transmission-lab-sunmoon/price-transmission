"""
KAMIS periodProductList 날짜 + 쇠고기 집중 테스트
==============================================
확인 사항:
  1. 날짜 파라미터가 왜 과거 조회가 안 되는지
     → 혹시 periodProductList 자체가 "최근 N일"만 지원하는 API?
     → 과거 조회는 다른 action이 필요?
  2. 쇠고기 응답이 list인 이유

실행: python tests/debug_kamis_date_beef.py
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


def call_api(label, params, show_raw=False):
    """API 호출 후 요약"""
    try:
        resp = requests.get(BASE_URL, params=params, timeout=45)
        data = resp.json()
    except Exception as e:
        print(f"\n  [{label}]")
        print(f"    ❌ {type(e).__name__}: {str(e)[:120]}")
        return None

    print(f"\n  [{label}]")

    if show_raw:
        raw = json.dumps(data, ensure_ascii=False, indent=2)
        print(f"    전체 응답 (2000자):")
        print(raw[:2000])
        return data

    if isinstance(data, list):
        print(f"    응답이 list (len={len(data)})")
        for i, elem in enumerate(data[:3]):
            if isinstance(elem, dict):
                print(f"    [{i}]: {json.dumps(elem, ensure_ascii=False)[:400]}")
        return data

    data_section = data.get("data", {})
    if isinstance(data_section, list):
        print(f"    data가 list (len={len(data_section)})")
        for i, elem in enumerate(data_section[:3]):
            if isinstance(elem, dict):
                print(f"    [{i}]: {json.dumps(elem, ensure_ascii=False)[:400]}")
        return data

    if not isinstance(data_section, dict):
        print(f"    data 타입: {type(data_section)}")
        return data

    error_code = data_section.get("error_code", "")
    items = data_section.get("item", [])

    if not items or not isinstance(items, list):
        print(f"    error_code: {error_code}, item 없음 (type={type(items).__name__})")
        return data

    print(f"    error_code: {error_code}, item: {len(items)}건")

    first = items[0]
    for k in ["itemname", "kindname", "countyname", "yyyy", "regday", "price"]:
        val = first.get(k, "")
        if val or k in ["yyyy", "regday", "price"]:
            print(f"    {k:<15} = {val}")

    dates = sorted(set(f"{it.get('yyyy')}-{it.get('regday')}" for it in items if it.get("yyyy")))
    if dates:
        print(f"    날짜: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")

    return data


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS 날짜 + 쇠고기 집중 테스트")
    print("=" * 70)

    # ================================================================
    # Part 1: 쇠고기 응답 구조 확인 (raw 출력)
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Part 1: 쇠고기 raw 응답 확인")
    print(f"{'─'*70}")

    call_api("쇠고기 (p_itemcategorycode=500, p_itemcode=511)", {
        "action": "periodProductList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_product_cls_code": "01",
        "p_country_code": "1101",
        "p_convert_kg_yn": "Y",
        "p_itemcategorycode": "500",
        "p_itemcode": "511",
        "p_startday": "2024-01-01",
        "p_endday": "2024-06-30",
    }, show_raw=True)

    # 쇠고기 품목코드 변형 테스트
    for code in ["511", "5111", "512"]:
        call_api(f"쇠고기 p_itemcode={code}", {
            "action": "periodProductList",
            "p_cert_key": CERT_KEY,
            "p_cert_id": CERT_ID,
            "p_returntype": "json",
            "p_product_cls_code": "01",
            "p_country_code": "1101",
            "p_convert_kg_yn": "Y",
            "p_itemcategorycode": "500",
            "p_itemcode": code,
            "p_startday": "2024-01-01",
            "p_endday": "2024-06-30",
        })

    # ================================================================
    # Part 2: 날짜 파라미터 집중 테스트 (바나나)
    # 과거 vs 최근, 다양한 기간
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Part 2: 날짜 파라미터 집중 (바나나, 붙여쓰기)")
    print(f"{'─'*70}")

    banana_base = {
        "action": "periodProductList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_product_cls_code": "01",
        "p_country_code": "1101",
        "p_convert_kg_yn": "Y",
        "p_itemcategorycode": "400",
        "p_itemcode": "416",
    }

    # 다양한 기간 테스트
    date_tests = [
        ("2026-01-01 ~ 2026-03-31 (올해)", "2026-01-01", "2026-03-31"),
        ("2025-01-01 ~ 2025-06-30 (작년 상반기)", "2025-01-01", "2025-06-30"),
        ("2024-01-01 ~ 2024-06-30 (2년 전)", "2024-01-01", "2024-06-30"),
        ("2020-01-01 ~ 2020-12-31 (6년 전)", "2020-01-01", "2020-12-31"),
        ("2015-01-01 ~ 2015-12-31 (11년 전)", "2015-01-01", "2015-12-31"),
    ]

    for label, start, end in date_tests:
        p = dict(banana_base)
        p["p_startday"] = start
        p["p_endday"] = end
        call_api(label, p)

    # ================================================================
    # Part 3: 다른 action으로 과거 데이터 조회 테스트
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Part 3: 다른 action 테스트 (바나나 2020년)")
    print(f"{'─'*70}")

    # 3-A: dailyPriceByCategoryList
    call_api("dailyPriceByCategoryList (2020-06-15)", {
        "action": "dailyPriceByCategoryList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_product_cls_code": "01",
        "p_country_code": "1101",
        "p_regday": "2020-06-15",
        "p_convert_kg_yn": "Y",
        "p_category_code": "400",
    })

    # 3-B: monthlySalesList (2020년)
    call_api("monthlySalesList (바나나 2020)", {
        "action": "monthlySalesList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_yyyy": "2020",
        "p_period": "3",
        "p_itemcategorycode": "400",
        "p_itemcode": "416",
        "p_kindcode": "",
        "p_graderank": "",
        "p_countycode": "1101",
        "p_convert_kg_yn": "Y",
    }, show_raw=True)

    print(f"\n{'='*70}")
    print(f"  테스트 완료")
    print(f"{'='*70}")
