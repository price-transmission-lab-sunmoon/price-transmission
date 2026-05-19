"""
KAMIS monthlySalesList API 테스트
실행: python tests/test_kamis_monthly.py
"""

import requests
import os
from pathlib import Path
from dotenv import load_dotenv

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "tests" else script_dir
load_dotenv(project_root / ".env")

CERT_KEY = os.getenv("KAMIS_CERT_KEY", "")
CERT_ID = os.getenv("KAMIS_CERT_ID", "")

BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"

# 테스트할 품목들
TEST_ITEMS = [
    {"name": "쇠고기", "category": "500", "item": "511", "kind": "01", "grade": "2"},
    {"name": "땅콩", "category": "300", "item": "313", "kind": "01", "grade": "2"},
    {"name": "바나나", "category": "400", "item": "416", "kind": "01", "grade": "2"},
    {"name": "오렌지", "category": "400", "item": "420", "kind": "01", "grade": "2"},
]

print("=" * 70)
print("  KAMIS monthlySalesList API 테스트")
print("=" * 70)

for item in TEST_ITEMS:
    print(f"\n  [{item['name']}] (부류:{item['category']}, 품목:{item['item']})")
    print(f"  {'─'*50}")

    # 도매(02) 조회 — monthlySalesList에서 도매는 productclscode=02
    params = {
        "action": "monthlySalesList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_yyyy": "2024",
        "p_period": "3",
        "p_itemcategorycode": item["category"],
        "p_itemcode": item["item"],
        "p_kindcode": item["kind"],
        "p_graderank": item["grade"],
        "p_countycode": "1101",
        "p_convert_kg_yn": "Y",
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        data = resp.json()
    except Exception as e:
        print(f"  ❌ 호출 실패: {e}")
        continue

    # 에러 체크
    error = data.get("data", {}).get("error_code", "")
    if error and error != "000":
        print(f"  ❌ 에러: {error}")
        continue

    # 응답 구조 확인
    price_items = data.get("price", [])
    
    if not price_items:
        # 다른 응답 구조일 수 있음
        print(f"  응답 키: {list(data.keys())}")
        # 전체 출력해서 구조 파악
        import json as jsonmod
        print(f"  응답 (처음 500자): {jsonmod.dumps(data, ensure_ascii=False)[:500]}")
        continue

    print(f"  결과: {len(price_items)}건")
    for p in price_items[:5]:
        print(f"    {p}")

# 추가 테스트: productclscode 분리
print(f"\n{'='*70}")
print(f"  추가 테스트: 도매/소매 구분 확인")
print(f"{'='*70}")

params = {
    "action": "monthlySalesList",
    "p_cert_key": CERT_KEY,
    "p_cert_id": CERT_ID,
    "p_returntype": "json",
    "p_yyyy": "2024",
    "p_period": "1",
    "p_itemcategorycode": "400",
    "p_itemcode": "416",
    "p_kindcode": "",
    "p_graderank": "",
    "p_countycode": "1101",
    "p_convert_kg_yn": "Y",
}

resp = requests.get(BASE_URL, params=params, timeout=30)
data = resp.json()

import json as jsonmod
print(f"\n  바나나 전체 응답:")
print(jsonmod.dumps(data, ensure_ascii=False, indent=2)[:2000])
