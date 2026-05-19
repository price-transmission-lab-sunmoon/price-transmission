"""
KAMIS 품목 전체 탐색 스크립트
부류별 품목코드를 직접 지정해서 조회 가능 여부를 확인합니다.
실행: python tests/explore_kamis_items.py
"""

import requests
import time
from pathlib import Path
from dotenv import load_dotenv
import os

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "tests" else script_dir
load_dotenv(project_root / ".env")

CERT_KEY = os.getenv("KAMIS_CERT_KEY", "")
CERT_ID = os.getenv("KAMIS_CERT_ID", "")

BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"

# KAMIS 알려진 품목코드 (KAMIS 홈페이지 참조)
# 부류코드: 100=식량작물, 200=채소류, 300=특용작물, 400=과일류, 500=축산물, 600=수산물
KNOWN_ITEMS = {
    # 식량작물 (100)
    "100": {
        "111": "쌀", "112": "찹쌀", "141": "콩", "142": "팥",
        "143": "녹두", "144": "메밀", "151": "고구마", "152": "감자",
    },
    # 채소류 (200)
    "200": {
        "211": "배추", "212": "양배추", "213": "시금치", "214": "상추",
        "215": "얼갈이배추", "216": "갓", "221": "수박", "222": "참외",
        "223": "오이", "224": "호박", "225": "토마토", "226": "딸기",
        "231": "무", "232": "당근", "233": "열무",
        "241": "건고추", "242": "풋고추", "243": "붉은고추", "244": "피마늘",
        "245": "양파", "246": "파", "247": "생강", "248": "고춧잎",
        "251": "미나리", "252": "깻잎", "253": "부추", "254": "피망",
        "255": "파프리카", "256": "멜론", "257": "깐마늘",
    },
    # 특용작물 (300)
    "300": {
        "311": "참깨", "312": "들깨", "313": "땅콩", "314": "느타리버섯",
        "315": "팽이버섯", "316": "새송이버섯", "317": "호두", "318": "아몬드",
    },
    # 과일류 (400)
    "400": {
        "411": "사과", "412": "배", "413": "포도", "414": "감귤",
        "415": "단감", "416": "바나나", "418": "참다래", "419": "파인애플",
        "420": "오렌지", "421": "레몬", "422": "체리", "423": "건포도",
        "424": "건망고", "425": "망고",
    },
    # 축산물 (500)
    "500": {
        "511": "쇠고기", "512": "돼지고기", "513": "닭고기", "514": "달걀",
        "515": "우유",
    },
    # 수산물 (600)
    "600": {
        "611": "고등어", "612": "꽁치", "613": "갈치", "614": "명태",
        "615": "물오징어", "616": "건멸치", "619": "새우젓", "638": "건오징어",
        "639": "김", "640": "건미역", "641": "굴",
    },
}


def check_item(category_code, item_code, item_name, cls_code="01"):
    """품목코드로 직접 조회해서 데이터 존재 여부 확인"""
    params = {
        "action": "periodProductList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_product_cls_code": cls_code,
        "p_country_code": "1101",
        "p_startday": "2026-03-01",
        "p_endday": "2026-03-31",
        "p_convert_kg_yn": "Y",
        "p_item_category_code": category_code,
        "p_item_code": item_code,
        "p_kind_code": "",
        "p_product_rank_code": "",
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        data = resp.json()
        items = data.get("data", {}).get("item", [])

        # 가격이 있는 항목만 카운트
        prices = [it for it in items if it.get("price") and it.get("price") != "-"]
        return len(prices)
    except Exception as e:
        return -1


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS 품목별 도매가 존재 여부 전수 조사")
    print("=" * 70)

    category_names = {
        "100": "식량작물", "200": "채소류", "300": "특용작물",
        "400": "과일류", "500": "축산물", "600": "수산물",
    }

    all_results = []

    for cat_code, items in KNOWN_ITEMS.items():
        cat_name = category_names[cat_code]
        print(f"\n  [{cat_name}] ({cat_code})")
        print(f"  {'-'*50}")

        for item_code, item_name in items.items():
            # 도매(01)로 조회
            count = check_item(cat_code, item_code, item_name, "01")
            status = f"✅ {count}건" if count > 0 else ("❌ 없음" if count == 0 else "⚠️ 에러")

            result = {
                "category_code": cat_code,
                "category_name": cat_name,
                "item_code": item_code,
                "item_name": item_name,
                "wholesale_count": count,
                "has_wholesale": count > 0,
            }
            all_results.append(result)

            print(f"    {item_code:<6} {item_name:<12} 도매: {status}")
            time.sleep(0.3)

    # 요약
    available = [r for r in all_results if r["has_wholesale"]]
    unavailable = [r for r in all_results if not r["has_wholesale"]]

    print(f"\n{'='*70}")
    print(f"  📋 결과 요약")
    print(f"{'='*70}")
    print(f"  전체 조회: {len(all_results)}개 품목")
    print(f"  도매가 있음: {len(available)}개")
    print(f"  도매가 없음: {len(unavailable)}개")

    print(f"\n  🎯 도매가 존재 품목 목록:")
    for r in available:
        print(f"    {r['category_name']:<8} {r['item_code']:<6} {r['item_name']}")

    # 프로젝트 관심 품목 하이라이트
    target_items = ["돼지고기", "닭고기", "달걀", "쇠고기", "배추", "사과", "쌀", "콩"]
    print(f"\n  ★ 프로젝트 관심 품목:")
    for r in all_results:
        if r["item_name"] in target_items:
            status = "✅ 도매가 있음" if r["has_wholesale"] else "❌ 도매가 없음"
            print(f"    {r['item_name']:<10} ({r['item_code']}) → {status}")
