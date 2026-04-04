"""
KAMIS 도매가 품목 목록 전체 조회
실행: python tests/check_kamis_items.py
04.02 기준
API 응답에서 p_category_code가 제대로 필터링이 안 되고 있어서 추후 수정 필요.
현재는 콩만 확인. Kamis가 신선제품, 국산품 위주
콩도 국산품이다.
추후에 
"""

import os
import sys
import requests
from pathlib import Path

# .env 로드
try:
    from dotenv import load_dotenv
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent if script_dir.name == "tests" else script_dir
    load_dotenv(project_root / ".env")
except ImportError:
    print("❌ pip install python-dotenv 먼저 실행하세요")
    sys.exit(1)

CERT_KEY = os.getenv("KAMIS_CERT_KEY", "")
CERT_ID = os.getenv("KAMIS_CERT_ID", "")

if not CERT_KEY:
    print("❌ .env에 KAMIS_CERT_KEY가 없습니다")
    sys.exit(1)

BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"

# KAMIS 부류 코드 (공식 문서 기준)
CATEGORIES = {
    "100": "식량작물",
    "200": "채소류",
    "300": "특용작물",
    "400": "과일류",
    "500": "축산물",
    "600": "수산물",
}

# 도매(01) + 소매(02)
PRODUCT_CLS = {"01": "도매", "02": "소매"}


def fetch_items(category_code, product_cls_code, regday="2026-04-02"):
    params = {
        "action": "dailyPriceByCategoryList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_product_cls_code": product_cls_code,
        "p_country_code": "1101",
        "p_regday": regday,
        "p_convert_kg_yn": "Y",
        "p_category_code": category_code,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        data = resp.json()
        return data.get("data", {}).get("item", [])
    except Exception as e:
        print(f"  ❌ 조회 실패 ({category_code}): {e}")
        return []


if __name__ == "__main__":
    print("=" * 60)
    print("  KAMIS 전체 품목 목록 조회")
    print("=" * 60)

    # 우리가 찾는 키워드
    target_keywords = ["밀", "콩", "대두", "옥수수", "식용유", "사료", "밀가루", "전분", "두부", "유지"]
    found_targets = []

    all_items = {}  # (code, name) -> set of cls

    for cls_code, cls_name in PRODUCT_CLS.items():
        print(f"\n{'─'*60}")
        print(f"  [{cls_name}] 품목 조회 중...")
        print(f"{'─'*60}")

        for cat_code, cat_name in CATEGORIES.items():
            items = fetch_items(cat_code, cls_code)
            seen_in_cat = set()

            for it in items:
                code = it.get("item_code", "")
                name = it.get("item_name", "")
                kind = it.get("kind_name", "")
                key = (code, name)

                if key not in seen_in_cat:
                    seen_in_cat.add(key)
                    if key not in all_items:
                        all_items[key] = {"categories": set(), "cls": set(), "kinds": set()}
                    all_items[key]["categories"].add(cat_name)
                    all_items[key]["cls"].add(cls_name)
                    all_items[key]["kinds"].add(kind)

            if seen_in_cat:
                print(f"  {cat_name}({cat_code}): {len(seen_in_cat)}개 품목")
                for code, name in sorted(seen_in_cat):
                    # 키워드 매칭 표시
                    mark = ""
                    if any(kw in name for kw in target_keywords):
                        mark = " ★"
                        found_targets.append((code, name, cls_name, cat_name))
                    print(f"    {code:<10} {name}{mark}")

    # 결과 요약
    print(f"\n{'=' * 60}")
    print(f"  📋 전체 품목 수: {len(all_items)}개")
    print(f"{'=' * 60}")

    if found_targets:
        print(f"\n  🎯 밀/옥수수/대두 관련 매칭 품목:")
        for code, name, cls_name, cat_name in found_targets:
            print(f"    ★ {code:<10} {name:<15} ({cls_name}, {cat_name})")
    else:
        print(f"\n  ⚠️ 밀/옥수수/대두 직접 관련 품목 없음")
        print(f"     → KAMIS는 신선 농산물 위주라 가공품(밀가루/식용유)은 미제공 가능성 높음")
        print(f"     → 구간 C·D는 연구 한계로 설정 (신청서와 일관)")