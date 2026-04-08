"""
ECOS PPI 통계표 3종 전수 조회
==============================================
404Y013 (기본분류), 404Y014 (품목별), 404Y015 (특수분류)
세 통계표의 품목코드를 모두 조회하여 키워드 매칭 결과를 비교합니다.
실행: python tests/explore_ecos_ppi_tables.py
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

# 조회할 통계표
STAT_TABLES = {
    "404Y013": "생산자물가지수(기본분류)",
    "404Y014": "생산자물가지수(품목별)",
    "404Y015": "생산자물가지수(특수분류)",
}

# 검색 키워드 — 기존 3품목 + 축산물 + 신선농산물 관련
KEYWORDS = [
    # 밀 관련
    "밀", "밀가루", "제분", "소맥", "면류",
    # 옥수수 관련
    "옥수수", "전분", "사료", "배합사료",
    # 대두 관련
    "대두", "대두유", "유지", "식용유", "식물성", "두부", "된장", "간장",
    # 축산물 관련
    "돼지", "닭", "계란", "달걀", "우유", "쇠고기", "소고기", "축산","한우",
    # 신선농산물 관련
    "쌀", "배추", "사과", "감자", "양파",
    # 곡물 전체
    "곡물", "식량",
]


def query_item_list(stat_code):
    """ECOS 통계표 품목코드 전체 목록 조회"""
    url = (
        f"https://ecos.bok.or.kr/api/StatisticItemList/"
        f"{ECOS_API_KEY}/json/kr/1/5000/{stat_code}"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  ❌ API 호출 실패: {e}")
        return []

    if "RESULT" in data:
        print(f"  ❌ API 에러: {data['RESULT'].get('MESSAGE', '')}")
        return []

    items = data.get("StatisticItemList", {}).get("row", [])
    return items


def filter_monthly(items):
    """월별 데이터(YYYYMM 형식)만 필터링"""
    monthly = []
    for item in items:
        start = item.get("START_TIME", "")
        # YYYYMM 형식 = 6자리 숫자
        if len(start) == 6 and start.isdigit():
            monthly.append(item)
    return monthly


def search_keywords(items, keywords):
    """키워드 매칭"""
    matched = []
    for item in items:
        name = item.get("ITEM_NAME", "")
        if any(kw in name for kw in keywords):
            matched.append(item)
    return matched


if __name__ == "__main__":
    print("=" * 70)
    print("  ECOS PPI 통계표 3종 전수 조회")
    print("=" * 70)

    all_results = []

    for stat_code, stat_name in STAT_TABLES.items():
        print(f"\n{'─'*70}")
        print(f"  [{stat_name}] 통계표코드: {stat_code}")
        print(f"{'─'*70}")

        # 전체 목록 조회
        items = query_item_list(stat_code)
        print(f"  전체 품목 수: {len(items)}")

        # 월별만 필터링
        monthly = filter_monthly(items)
        print(f"  월별 데이터: {len(monthly)}개")

        # 키워드 매칭
        matched = search_keywords(monthly, KEYWORDS)
        print(f"  키워드 매칭: {len(matched)}개")

        if matched:
            print(f"\n  {'코드':<15} {'이름':<20} {'기간'}")
            print(f"  {'-'*60}")
            for m in matched:
                code = m.get("ITEM_CODE", "")
                name = m.get("ITEM_NAME", "")
                start = m.get("START_TIME", "")
                end = m.get("END_TIME", "")
                print(f"  {code:<15} {name:<20} {start}~{end}")

                all_results.append({
                    "stat_code": stat_code,
                    "stat_name": stat_name,
                    "item_code": code,
                    "item_name": name,
                    "start_time": start,
                    "end_time": end,
                })

        time.sleep(0.5)

    # 통계표 간 비교
    print(f"\n{'='*70}")
    print(f"  📋 통계표 간 비교 — 같은 품목이 어디에 있는지")
    print(f"{'='*70}")

    # 품목명 기준으로 그룹핑
    name_to_tables = {}
    for r in all_results:
        name = r["item_name"]
        if name not in name_to_tables:
            name_to_tables[name] = []
        name_to_tables[name].append(f"{r['stat_code']}({r['item_code']})")

    for name in sorted(name_to_tables.keys()):
        tables = name_to_tables[name]
        print(f"  {name:<20} → {', '.join(tables)}")

    # CSV 저장
    if all_results:
        csv_path = OUTPUT_DIR / "ecos_ppi_all_tables_matched.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\n  💾 저장 완료: {csv_path}")

    # 현재 사용 중인 코드와 비교
    print(f"\n{'='*70}")
    print(f"  🔍 현재 commodity_mapping.json에서 사용 중인 PPI 코드 대조")
    print(f"{'='*70}")

    current_codes = {
        "wheat": ("301131AA", "제분"),
        "maize": ("301181AA", "사료"),
        "soybean": ("301162AA", "유지"),
    }

    for cid, (code, name) in current_codes.items():
        found_in = []
        for r in all_results:
            if r["item_code"] == code:
                found_in.append(r["stat_code"])
        tables_str = ", ".join(found_in) if found_in else "❌ 미발견"
        print(f"  {cid:<10} {code} ({name}) → {tables_str}")

    print(f"\n  ✅ 조회 완료!")
