"""
KAMIS periodProductList 파라미터명 테스트
==============================================
목적: API가 품목 코드를 무시하는 원인 파악
     → 파라미터명이 잘못되었을 가능성 테스트

KAMIS API 문서에 따르면 파라미터명이 action마다 다를 수 있음:
  - dailyPriceByCategoryList: p_category_code, p_item_code 등
  - monthlySalesList:         p_itemcategorycode, p_itemcode 등
  - periodProductList:        p_item_category_code? p_itemcategorycode?

실행: python tests/debug_kamis_params.py
"""

import os
import json
import requests
from pathlib import Path
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
        "p_product_cls_code": "01",    # 도매
        "p_country_code": "1101",
        "p_startday": "2024-01-01",
        "p_endday": "2024-03-31",      # 3개월만
        "p_convert_kg_yn": "Y",
    }
    base.update(extra_params)

    try:
        resp = requests.get(BASE_URL, params=base, timeout=30)
        data = resp.json()
    except Exception as e:
        print(f"  ❌ {label}: 호출 실패 - {e}")
        return

    error_code = data.get("data", {}).get("error_code", "")
    items = data.get("data", {}).get("item", [])

    if not items or not isinstance(items, list):
        item_count = 0
        first_item = None
    else:
        item_count = len(items)
        first_item = items[0]

    print(f"\n  [{label}]")
    print(f"    error_code: {error_code}")
    print(f"    item 개수: {item_count}")

    if first_item:
        # 핵심 필드만 출력
        print(f"    첫 item:")
        print(f"      itemname   = {first_item.get('itemname', '?')}")
        print(f"      kindname   = {first_item.get('kindname', '?')}")
        print(f"      countyname = {first_item.get('countyname', '?')}")
        print(f"      yyyy       = {first_item.get('yyyy', '?')}")
        print(f"      regday     = {first_item.get('regday', '?')}")
        print(f"      price      = {first_item.get('price', '?')}")

        # 고유 날짜 수
        dates = set(f"{it.get('yyyy')}-{it.get('regday')}" for it in items)
        print(f"    고유 날짜 수: {len(dates)}")
        sorted_dates = sorted(dates)
        print(f"    날짜 범위: {sorted_dates[0]} ~ {sorted_dates[-1]}")

        # countyname 분포
        from collections import Counter
        counties = Counter(it.get("countyname", "") for it in items)
        print(f"    countyname: {dict(counties.most_common(5))}")

        # item_name 분포
        inames = Counter(it.get("item_name", "") for it in items)
        if any(n for n in inames if n):
            print(f"    item_name: {dict(inames.most_common(5))}")
    else:
        # item이 없으면 전체 응답 일부 출력
        raw = json.dumps(data, ensure_ascii=False)
        print(f"    응답 (처음 500자): {raw[:500]}")


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS periodProductList 파라미터명 테스트")
    print("  대상: 바나나 (부류:400, 품목:416)")
    print("=" * 70)

    # ── 테스트 1: 현재 코드의 파라미터명 (언더스코어 방식) ──
    test_params("현재코드 (p_item_category_code / p_item_code)", {
        "p_item_category_code": "400",
        "p_item_code": "416",
        "p_kind_code": "",
        "p_product_rank_code": "",
    })

    # ── 테스트 2: monthlySalesList 스타일 (붙여쓰기 방식) ──
    test_params("붙여쓰기 (p_itemcategorycode / p_itemcode)", {
        "p_itemcategorycode": "400",
        "p_itemcode": "416",
        "p_kindcode": "",
        "p_graderank": "",
    })

    # ── 테스트 3: dailyPriceByCategoryList 스타일 ──
    test_params("daily 스타일 (p_category_code / p_item_code)", {
        "p_category_code": "400",
        "p_item_code": "416",
        "p_kind_code": "",
        "p_product_rank_code": "",
    })

    # ── 테스트 4: 혼합 (카테고리는 붙여쓰기, 아이템은 언더스코어) ──
    test_params("혼합1 (p_itemcategorycode / p_item_code)", {
        "p_itemcategorycode": "400",
        "p_item_code": "416",
        "p_kind_code": "",
        "p_product_rank_code": "",
    })

    # ── 테스트 5: 쇠고기로 바꿔서 - 테스트2 방식 ──
    print(f"\n{'─'*70}")
    print(f"  비교: 쇠고기 (부류:500, 품목:511) - 붙여쓰기 방식")
    print(f"{'─'*70}")
    test_params("쇠고기 붙여쓰기", {
        "p_itemcategorycode": "500",
        "p_itemcode": "511",
        "p_kindcode": "",
        "p_graderank": "",
    })

    # ── 테스트 6: 땅콩 - 테스트2 방식 ──
    test_params("땅콩 붙여쓰기", {
        "p_itemcategorycode": "300",
        "p_itemcode": "313",
        "p_kindcode": "",
        "p_graderank": "",
    })

    # ── 테스트 7: 바나나 + kind_code 지정 ──
    test_params("바나나 + kind=00 (붙여쓰기)", {
        "p_itemcategorycode": "400",
        "p_itemcode": "416",
        "p_kindcode": "00",
        "p_graderank": "",
    })

    test_params("바나나 + kind=01 (붙여쓰기)", {
        "p_itemcategorycode": "400",
        "p_itemcode": "416",
        "p_kindcode": "01",
        "p_graderank": "",
    })

    print(f"\n{'='*70}")
    print(f"  테스트 완료")
    print(f"{'='*70}")
