"""
10개 품목 ECOS 코드 전수 조회
==============================================
PPI: 404Y016 (품목별) — 단일 품목 수준
CPI: 901Y009 (품목별)
실행: python tests/find_all_10_items_codes.py
"""

import os
import sys
import csv
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "tests" else script_dir
load_dotenv(project_root / ".env")

ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")
if not ECOS_API_KEY:
    print("❌ .env에 ECOS_API_KEY가 없습니다.")
    sys.exit(1)

OUTPUT_DIR = project_root / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 10개 품목별 PPI/CPI 검색 키워드
ITEMS_TO_FIND = {
    "wheat": {
        "name_kr": "밀",
        "ppi_keywords": ["소맥분", "밀가루", "소맥", "제분"],
        "cpi_keywords": ["밀가루", "식빵", "빵", "라면", "국수"],
    },
    "maize": {
        "name_kr": "옥수수",
        "ppi_keywords": ["전분", "곡물가공", "옥수수"],
        "cpi_keywords": ["과자류", "음료류", "과자", "음료"],
    },
    "soybean": {
        "name_kr": "대두",
        "ppi_keywords": ["대두", "기타작물"],
        "cpi_keywords": ["두부", "된장", "간장", "식용유"],
    },
    "palmoil": {
        "name_kr": "팜유",
        "ppi_keywords": ["유지", "팜유", "식물성유", "식용유지"],
        "cpi_keywords": ["식용유"],
    },
    "sugar": {
        "name_kr": "설탕",
        "ppi_keywords": ["정제당", "설탕", "정당"],
        "cpi_keywords": ["설탕"],
    },
    "coffee": {
        "name_kr": "커피",
        "ppi_keywords": ["원두커피", "커피", "볶은커피", "원두"],
        "cpi_keywords": ["커피"],
    },
    "beef": {
        "name_kr": "쇠고기",
        "ppi_keywords": ["쇠고기", "소고기"],
        "cpi_keywords": ["쇠고기", "국산쇠고기", "수입쇠고기"],
    },
    "groundnuts": {
        "name_kr": "땅콩",
        "ppi_keywords": ["견과가공", "견과", "땅콩"],
        "cpi_keywords": ["땅콩"],
    },
    "banana": {
        "name_kr": "바나나",
        "ppi_keywords": ["과실", "바나나"],
        "cpi_keywords": ["바나나"],
    },
    "orange": {
        "name_kr": "오렌지",
        "ppi_keywords": ["과실", "오렌지"],
        "cpi_keywords": ["오렌지"],
    },
}

# 조회할 통계표
TABLES = {
    "ppi_basic": {"code": "404Y014", "name": "PPI 기본분류"},
    "ppi_item": {"code": "404Y016", "name": "PPI 품목별"},
    "cpi": {"code": "901Y009", "name": "CPI 품목별"},
}


def query_item_list(stat_code):
    """ECOS 통계표 품목코드 월별 목록 조회"""
    url = f"https://ecos.bok.or.kr/api/StatisticItemList/{ECOS_API_KEY}/json/kr/1/5000/{stat_code}"
    try:
        resp = requests.get(url, timeout=30)
        data = resp.json()
    except Exception as e:
        print(f"  ❌ API 호출 실패: {e}")
        return []

    if "RESULT" in data:
        print(f"  ❌ {data['RESULT'].get('MESSAGE', '')}")
        return []

    items = data.get("StatisticItemList", {}).get("row", [])
    # 월별만 (YYYYMM 형식)
    monthly = [it for it in items if len(it.get("START_TIME", "")) == 6 and it.get("START_TIME", "").isdigit()]
    return monthly


def search_items(items, keywords):
    """키워드 매칭"""
    matched = []
    for item in items:
        name = item.get("ITEM_NAME", "")
        if any(kw in name for kw in keywords):
            matched.append({
                "item_code": item.get("ITEM_CODE", ""),
                "item_name": name,
                "start": item.get("START_TIME", ""),
                "end": item.get("END_TIME", ""),
            })
    return matched


if __name__ == "__main__":
    print("=" * 70)
    print("  10개 품목 ECOS PPI·CPI 코드 전수 조회")
    print("=" * 70)

    # 통계표별 전체 목록 캐싱
    table_items = {}
    for key, info in TABLES.items():
        print(f"\n  [{info['name']}] {info['code']} 로딩 중...")
        table_items[key] = query_item_list(info["code"])
        print(f"  → {len(table_items[key])}개 월별 품목")
        time.sleep(0.5)

    # 품목별 검색
    all_results = []

    for commodity_id, config in ITEMS_TO_FIND.items():
        name_kr = config["name_kr"]
        print(f"\n{'─'*70}")
        print(f"  [{name_kr}] ({commodity_id})")
        print(f"{'─'*70}")

        # PPI 기본분류
        print(f"\n  📌 PPI 기본분류 (404Y014):")
        ppi_basic = search_items(table_items["ppi_basic"], config["ppi_keywords"])
        if ppi_basic:
            for m in ppi_basic:
                print(f"    {m['item_code']:<15} {m['item_name']:<20} {m['start']}~{m['end']}")
                all_results.append({"commodity_id": commodity_id, "table": "404Y014", **m})
        else:
            print(f"    (매칭 없음)")

        # PPI 품목별
        print(f"\n  📌 PPI 품목별 (404Y016):")
        ppi_item = search_items(table_items["ppi_item"], config["ppi_keywords"])
        if ppi_item:
            for m in ppi_item:
                print(f"    {m['item_code']:<15} {m['item_name']:<20} {m['start']}~{m['end']}")
                all_results.append({"commodity_id": commodity_id, "table": "404Y016", **m})
        else:
            print(f"    (매칭 없음)")

        # CPI
        print(f"\n  📌 CPI 품목별 (901Y009):")
        cpi = search_items(table_items["cpi"], config["cpi_keywords"])
        if cpi:
            for m in cpi:
                print(f"    {m['item_code']:<15} {m['item_name']:<20} {m['start']}~{m['end']}")
                all_results.append({"commodity_id": commodity_id, "table": "901Y009", **m})
        else:
            print(f"    (매칭 없음)")

    # CSV 저장
    if all_results:
        csv_path = OUTPUT_DIR / "ecos_10_items_all_codes.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["commodity_id", "table", "item_code", "item_name", "start", "end"])
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\n  💾 저장: {csv_path}")

    # 요약
    print(f"\n{'='*70}")
    print(f"  📋 요약 — 품목별 코드 후보")
    print(f"{'='*70}")
    for commodity_id, config in ITEMS_TO_FIND.items():
        name_kr = config["name_kr"]
        item_results = [r for r in all_results if r["commodity_id"] == commodity_id]
        ppi_count = len([r for r in item_results if r["table"].startswith("404Y")])
        cpi_count = len([r for r in item_results if r["table"] == "901Y009"])
        print(f"  {name_kr:<8} ({commodity_id:<12}) PPI후보: {ppi_count}개  CPI후보: {cpi_count}개")
