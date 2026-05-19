"""
KAMIS periodProductList 최종 파라미터 확인
==============================================
핵심 발견:
  - KAMIS 공식 샘플 URL에 p_strartday (start의 오타) 사용
  - 품목: p_itemcategorycode + p_itemcode (붙여쓰기)
  - 이 조합으로 과거 날짜 + 품목별 구분이 되는지 최종 확인

실행: python tests/debug_kamis_final.py
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


def call_api(label, params):
    """API 호출 후 요약 출력"""
    try:
        resp = requests.get(BASE_URL, params=params, timeout=45)
        data = resp.json()
    except Exception as e:
        print(f"\n  [{label}]")
        print(f"    ❌ 호출 실패: {type(e).__name__}: {str(e)[:100]}")
        return None

    print(f"\n  [{label}]")

    # 응답 구조 파악
    if isinstance(data, list):
        print(f"    응답이 list (len={len(data)})")
        if data and isinstance(data[0], dict):
            print(f"    첫 요소: {json.dumps(data[0], ensure_ascii=False)[:300]}")
        return None

    # data 키 안의 item 추출
    data_section = data.get("data", {})
    if isinstance(data_section, list):
        print(f"    data가 list (len={len(data_section)})")
        if data_section and isinstance(data_section[0], dict):
            print(f"    첫 요소: {json.dumps(data_section[0], ensure_ascii=False)[:300]}")
        return None

    if not isinstance(data_section, dict):
        print(f"    data가 예상외 타입: {type(data_section)}")
        return None

    error_code = data_section.get("error_code", "")
    items = data_section.get("item", [])

    if not items or not isinstance(items, list):
        print(f"    error_code: {error_code}, item 없음")
        raw = json.dumps(data, ensure_ascii=False)
        print(f"    전체 응답 (500자): {raw[:500]}")
        return None

    print(f"    error_code: {error_code}")
    print(f"    item 개수: {len(items)}")

    # 핵심 정보
    first = items[0]
    for k in ["itemname", "item_name", "kindname", "kind_name",
              "countyname", "marketname", "yyyy", "regday", "price"]:
        val = first.get(k, "")
        if val or k in ["yyyy", "regday", "price"]:
            print(f"    {k:<15} = {val}")

    # 날짜 범위
    dates = set()
    for it in items:
        yyyy = it.get("yyyy", "")
        regday = it.get("regday", "")
        if yyyy and regday:
            dates.add(f"{yyyy}-{regday}")
    if dates:
        sd = sorted(dates)
        print(f"    날짜: {sd[0]} ~ {sd[-1]} ({len(dates)}일)")

    # countyname 분포
    counties = Counter(it.get("countyname", "") for it in items)
    print(f"    countyname: {dict(counties.most_common(7))}")

    return items


def build_params(item_params, date_params):
    """공통 인증 + 품목 + 날짜 파라미터 조합"""
    base = {
        "action": "periodProductList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_product_cls_code": "01",
        "p_country_code": "1101",
        "p_convert_kg_yn": "Y",
    }
    base.update(item_params)
    base.update(date_params)
    return base


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS periodProductList 최종 파라미터 확인")
    print("=" * 70)

    # ================================================================
    # Test 1: 날짜 파라미터 — p_strartday (KAMIS 공식 오타) vs p_startday
    # 바나나 (cat=400, item=416) 고정
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Test 1: 날짜 파라미터 비교 (바나나)")
    print(f"{'─'*70}")

    banana_item = {"p_itemcategorycode": "400", "p_itemcode": "416"}

    # 1-A: p_startday (현재 코드)
    call_api("p_startday + p_endday (현재)", build_params(
        banana_item,
        {"p_startday": "2023-01-01", "p_endday": "2023-03-31"}
    ))

    # 1-B: p_strartday (KAMIS 공식 오타)
    call_api("p_strartday + p_endday (공식 오타)", build_params(
        banana_item,
        {"p_strartday": "2023-01-01", "p_endday": "2023-03-31"}
    ))

    # ================================================================
    # Test 2: 품목별 비교 — p_itemcategorycode + p_itemcode (둘 다 붙여쓰기)
    #         + p_strartday (공식 오타)
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Test 2: 품목별 비교 (p_strartday 사용)")
    print(f"{'─'*70}")

    date_params = {"p_strartday": "2023-01-01", "p_endday": "2023-06-30"}

    targets = [
        ("바나나",  {"p_itemcategorycode": "400", "p_itemcode": "416"}),
        ("오렌지",  {"p_itemcategorycode": "400", "p_itemcode": "420"}),
        ("땅콩",    {"p_itemcategorycode": "300", "p_itemcode": "313"}),
        ("쇠고기",  {"p_itemcategorycode": "500", "p_itemcode": "511"}),
    ]

    for name, item_p in targets:
        call_api(f"{name}", build_params(item_p, date_params))

    # ================================================================
    # Test 3: 혼합 방식과 비교 (p_itemcategorycode + p_item_code)
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Test 3: 혼합 방식 비교 (바나나, p_strartday)")
    print(f"{'─'*70}")

    # 3-A: 둘 다 붙여쓰기
    call_api("p_itemcategorycode + p_itemcode (둘다 붙여쓰기)", build_params(
        {"p_itemcategorycode": "400", "p_itemcode": "416"},
        {"p_strartday": "2023-01-01", "p_endday": "2023-03-31"}
    ))

    # 3-B: 혼합
    call_api("p_itemcategorycode + p_item_code (혼합)", build_params(
        {"p_itemcategorycode": "400", "p_item_code": "416"},
        {"p_strartday": "2023-01-01", "p_endday": "2023-03-31"}
    ))

    # 3-C: 둘 다 언더스코어 (현재 코드)
    call_api("p_item_category_code + p_item_code (둘다 언더스코어)", build_params(
        {"p_item_category_code": "400", "p_item_code": "416"},
        {"p_strartday": "2023-01-01", "p_endday": "2023-03-31"}
    ))

    print(f"\n{'='*70}")
    print(f"  테스트 완료")
    print(f"{'='*70}")
