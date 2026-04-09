"""
KAMIS monthlySalesList 정밀 테스트
==============================================
목적:
  1. monthlySalesList가 과거 데이터를 제대로 반환하는지
  2. p_itemcode별로 올바른 품목이 나오는지 (caption 확인)
  3. productclscode별 도매/소매 구분
  4. 쇠고기도 되는지

실행: python tests/debug_kamis_monthly_v2.py
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


def test_monthly(label, cat_code, item_code, year="2020", period="3"):
    """monthlySalesList 호출 후 caption별 요약"""
    params = {
        "action": "monthlySalesList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_yyyy": year,
        "p_period": period,
        "p_itemcategorycode": cat_code,
        "p_itemcode": item_code,
        "p_kindcode": "",
        "p_graderank": "",
        "p_countycode": "1101",
        "p_convert_kg_yn": "Y",
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=45)
        data = resp.json()
    except Exception as e:
        print(f"\n  [{label}]")
        print(f"    ❌ {type(e).__name__}: {str(e)[:100]}")
        return

    print(f"\n  [{label}]  (cat={cat_code}, item={item_code}, year={year})")

    error_code = data.get("error_code", "")
    print(f"    error_code: {error_code}")

    prices = data.get("price", [])
    if not prices:
        print(f"    price 없음. 응답 키: {list(data.keys())}")
        raw = json.dumps(data, ensure_ascii=False)
        print(f"    응답 (500자): {raw[:500]}")
        return

    print(f"    price 블록 수: {len(prices)}")

    for i, p in enumerate(prices):
        cls = p.get("productclscode", "?")
        caption = p.get("caption", "")
        items = p.get("item", [])
        year_count = len(items) if isinstance(items, list) else 0

        # cls 해석
        cls_label = {"01": "도매", "02": "소매(중도매인)"}.get(cls, f"cls={cls}")

        print(f"\n    [{i}] {cls_label}")
        print(f"        caption: {caption}")
        print(f"        연도 수: {year_count}")

        # 첫 연도 데이터 출력
        if items and isinstance(items, list) and isinstance(items[0], dict):
            first = items[0]
            yyyy = first.get("yyyy", "")
            # 월별 값 수집
            monthly_vals = []
            for m in range(1, 13):
                val = first.get(f"m{m}", "-")
                monthly_vals.append(val)
            avg = first.get("yearavg", "-")
            print(f"        {yyyy}년: {monthly_vals}")
            print(f"        연평균: {avg}")

            # 마지막 연도도
            if len(items) > 1:
                last = items[-1]
                yyyy_l = last.get("yyyy", "")
                monthly_l = [last.get(f"m{m}", "-") for m in range(1, 13)]
                avg_l = last.get("yearavg", "-")
                print(f"        {yyyy_l}년: {monthly_l}")
                print(f"        연평균: {avg_l}")


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS monthlySalesList 정밀 테스트")
    print("=" * 70)

    # ================================================================
    # Test 1: 바나나 (cat=400, item=416) — 2020년
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Test 1: 바나나")
    print(f"{'─'*70}")
    test_monthly("바나나", "400", "416", year="2020")

    # ================================================================
    # Test 2: 오렌지 (cat=400, item=420) — 2020년
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Test 2: 오렌지")
    print(f"{'─'*70}")
    test_monthly("오렌지", "400", "420", year="2020")

    # ================================================================
    # Test 3: 땅콩 (cat=300, item=313) — 2020년
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Test 3: 땅콩")
    print(f"{'─'*70}")
    test_monthly("땅콩", "300", "313", year="2020")

    # ================================================================
    # Test 4: 쇠고기 (cat=500, item=511) — 2020년
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Test 4: 쇠고기")
    print(f"{'─'*70}")
    test_monthly("쇠고기", "500", "511", year="2020")

    # ================================================================
    # Test 5: 바나나 — 다양한 연도 (과거 데이터 범위 확인)
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  Test 5: 바나나 — 연도별 커버리지 확인")
    print(f"{'─'*70}")
    for y in ["2024", "2015", "2010", "2005", "2000"]:
        test_monthly(f"바나나 {y}년", "400", "416", year=y, period="1")

    print(f"\n{'='*70}")
    print(f"  테스트 완료")
    print(f"{'='*70}")
