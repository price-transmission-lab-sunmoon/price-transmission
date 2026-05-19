"""
ECOS 생산자물가지수 관련 통계표코드 전체 목록 조회
실행: python tests/find_ecos_ppi_stat_codes.py
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "tests" else script_dir
load_dotenv(project_root / ".env")

key = os.getenv("ECOS_API_KEY")

print("=" * 70)
print("  ECOS 생산자물가지수 관련 통계표코드 조회")
print("=" * 70)

# 방법 1: 전체 통계표 목록에서 "생산자물가" 키워드 검색
url = f"https://ecos.bok.or.kr/api/StatisticTableList/{key}/json/kr/1/1000/"
r = requests.get(url, timeout=30)
data = r.json()
items = data.get("StatisticTableList", {}).get("row", [])

print(f"\n  전체 통계표 수: {len(items)}")
print(f"\n  '생산자물가' 포함 통계표:")
print(f"  {'코드':<15} {'이름'}")
print(f"  {'-'*60}")

ppi_tables = []
for it in items:
    code = it.get("STAT_CODE", "")
    name = it.get("STAT_NAME", "")
    if "생산자물가" in name:
        print(f"  {code:<15} {name}")
        ppi_tables.append(code)

# 방법 2: 404Y로 시작하는 코드 모두 출력
print(f"\n  '404Y' 시작 통계표:")
print(f"  {'코드':<15} {'이름'}")
print(f"  {'-'*60}")
for it in items:
    code = it.get("STAT_CODE", "")
    name = it.get("STAT_NAME", "")
    if code.startswith("404Y"):
        print(f"  {code:<15} {name}")

# 발견된 PPI 통계표 각각의 품목코드 조회
print(f"\n{'='*70}")
print(f"  발견된 PPI 통계표별 품목 샘플 조회")
print(f"{'='*70}")

for stat_code in ppi_tables:
    url2 = f"https://ecos.bok.or.kr/api/StatisticItemList/{key}/json/kr/1/5000/{stat_code}"
    r2 = requests.get(url2, timeout=30)
    data2 = r2.json()

    if "RESULT" in data2:
        print(f"\n  [{stat_code}] ❌ {data2['RESULT'].get('MESSAGE','')}")
        continue

    items2 = data2.get("StatisticItemList", {}).get("row", [])

    # 월별만 필터
    monthly = [it for it in items2 if len(it.get("START_TIME", "")) == 6]

    # 키워드 검색
    keywords = ["밀가루", "돼지고기", "닭고기", "달걀", "쇠고기", "식용유", "대두", 
                 "배합사료", "밀", "옥수수", "쌀", "배추", "사과"]
    matched = [it for it in monthly if any(kw in it.get("ITEM_NAME", "") for kw in keywords)]

    print(f"\n  [{stat_code}] 전체: {len(items2)}개 / 월별: {len(monthly)}개 / 키워드 매칭: {len(matched)}개")

    if matched:
        print(f"  {'코드':<15} {'이름':<20} {'기간'}")
        print(f"  {'-'*55}")
        for m in matched:
            print(f"  {m.get('ITEM_CODE',''):<15} {m.get('ITEM_NAME',''):<20} {m.get('START_TIME','')}~{m.get('END_TIME','')}")
    elif monthly:
        print(f"  키워드 미매칭. 월별 품목 처음 20개:")
        for m in monthly[:20]:
            print(f"  {m.get('ITEM_CODE',''):<15} {m.get('ITEM_NAME','')}")
