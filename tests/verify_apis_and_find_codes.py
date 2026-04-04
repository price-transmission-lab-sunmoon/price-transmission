"""
Phase 0 — API 키 검증 및 품목코드 조회 스크립트
=========================================================
사전 조건: .env 파일에 API 키 입력 완료
실행 방법: python tests/verify_apis_and_find_codes.py

04.02 기준
현재 Kamis 부분은 오류가 있음. 그 부분 수정은 아직 안하고 따로 해당 부분을 코드로 만듬.(check_kamis_items.py)

"""

import os
import sys
import csv
import time
import json
import requests
from pathlib import Path
from datetime import datetime, date, timedelta

# 프로젝트 루트 찾기 (tests/ 하위에서 실행해도 루트의 .env를 찾음)
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "tests" else script_dir

# .env 로드
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if not env_path.exists():
        print(f"❌ .env 파일이 없습니다: {env_path}")
        print("   cp .env.example .env 후 API 키를 입력하세요.")
        sys.exit(1)
    load_dotenv(env_path)
except ImportError:
    print("❌ python-dotenv가 설치되지 않았습니다. pip install python-dotenv")
    sys.exit(1)

ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")
EXIM_API_KEY = os.getenv("EXIM_API_KEY", "")
KAMIS_CERT_KEY = os.getenv("KAMIS_CERT_KEY", "")
KAMIS_CERT_ID = os.getenv("KAMIS_CERT_ID", "")

# 키 존재 확인
missing = []
if not ECOS_API_KEY or "여기에" in ECOS_API_KEY:
    missing.append("ECOS_API_KEY")
if not EXIM_API_KEY or "여기에" in EXIM_API_KEY:
    missing.append("EXIM_API_KEY")

if missing:
    print(f"⚠️  .env에 다음 키가 누락되었습니다: {', '.join(missing)}")
    print("   .env 파일을 열어 키를 입력하세요.")
    sys.exit(1)


# ============================================================
# 1. ECOS 품목코드 조회
# ============================================================
def query_ecos_item_list(stat_code, stat_name, keywords):
    """ECOS 통계표의 품목코드 목록 조회 후 키워드 필터링"""
    print(f"\n{'='*70}")
    print(f"  [{stat_name}] 통계표코드: {stat_code}")
    print(f"{'='*70}")

    url = (
        f"https://ecos.bok.or.kr/api/StatisticItemList/"
        f"{ECOS_API_KEY}/json/kr/1/2000/{stat_code}"
    )

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  ❌ API 호출 실패: {e}")
        return []

    if "RESULT" in data:
        msg = data["RESULT"].get("MESSAGE", "Unknown")
        print(f"  ❌ API 에러: {msg}")
        return []

    items = data.get("StatisticItemList", {}).get("row", [])
    print(f"  전체 품목 수: {len(items)}")

    matched = []
    for item in items:
        name = item.get("ITEM_NAME", "")
        code = item.get("ITEM_CODE", "")
        grp = item.get("GROUP_NAME", "")
        start = item.get("START_TIME", "")
        end = item.get("END_TIME", "")

        if any(kw in name for kw in keywords):
            matched.append({
                "stat_code": stat_code,
                "stat_name": stat_name,
                "item_code": code,
                "item_name": name,
                "group_name": grp,
                "start_time": start,
                "end_time": end,
            })

    if matched:
        print(f"\n  📌 키워드 매칭 결과: {len(matched)}건")
        print(f"  {'코드':<15} {'이름':<25} {'그룹':<20} {'기간'}")
        print(f"  {'-'*80}")
        for m in matched:
            print(
                f"  {m['item_code']:<15} {m['item_name']:<25} "
                f"{m['group_name']:<20} {m['start_time']}~{m['end_time']}"
            )
    else:
        print(f"\n  ⚠️ 키워드 매칭 결과 없음. 전체 목록 앞 20개:")
        for item in items[:20]:
            print(f"    {item.get('ITEM_CODE',''):<15} {item.get('ITEM_NAME','')}")

    return matched


def query_ecos_sample_data(stat_code, item_code, item_name):
    """특정 품목의 최근 데이터 샘플 조회"""
    print(f"\n  📊 샘플: {item_name} ({item_code})")
    url = (
        f"https://ecos.bok.or.kr/api/StatisticSearch/"
        f"{ECOS_API_KEY}/json/kr/1/6/{stat_code}/M/202501/202512/{item_code}"
    )
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"    ❌ {e}")
        return
    if "RESULT" in data:
        print(f"    ❌ {data['RESULT'].get('MESSAGE','')}")
        return
    for r in data.get("StatisticSearch", {}).get("row", []):
        print(f"    {r.get('TIME','')} : {r.get('DATA_VALUE','')} {r.get('UNIT_NAME','')}")


# ============================================================
# 2. 한국수출입은행 환율 API 테스트
# ============================================================
def test_exchange_rate_api():
    print(f"\n{'='*70}")
    print(f"  [한국수출입은행 환율 API 테스트]")
    print(f"{'='*70}")

    test_date = date.today()
    for _ in range(7):
        if test_date.weekday() < 5:
            break
        test_date -= timedelta(days=1)

    date_str = test_date.strftime("%Y%m%d")

    # 기존 도메인 → 새 도메인 순서로 시도
    urls = [
        f"https://www.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={EXIM_API_KEY}&searchdate={date_str}&data=AP01",
        f"https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON?authkey={EXIM_API_KEY}&searchdate={date_str}&data=AP01",
    ]

    data = None
    for url in urls:
        try:
            resp = requests.get(url, timeout=15)
            data = resp.json()
            if data:
                break
        except Exception:
            continue

    if not data:
        print(f"  ❌ 환율 데이터 조회 실패 (날짜: {date_str})")
        return

    print(f"  ✅ API 키 유효! 조회일: {date_str}, 통화 {len(data)}개")
    for d in data:
        if d.get("cur_unit") == "USD":
            print(f"  USD/KRW 매매기준율: {d.get('deal_bas_r','N/A')}")
            break


# ============================================================
# 3. KAMIS 품목코드 조회 (키가 있을 때만)
# ============================================================
def test_kamis_api():
    if not KAMIS_CERT_KEY or "여기에" in KAMIS_CERT_KEY:
        print(f"\n{'='*70}")
        print(f"  [KAMIS] 키 미입력 — 건너뜀 (나중에 입력 후 재실행)")
        print(f"{'='*70}")
        return []

    print(f"\n{'='*70}")
    print(f"  [KAMIS 도매가 품목코드 조회]")
    print(f"{'='*70}")

    url = "http://www.kamis.or.kr/service/price/xml.do"
    params = {
        "action": "ItemCodeList",
        "p_cert_key": KAMIS_CERT_KEY,
        "p_cert_id": KAMIS_CERT_ID,
        "p_returntype": "json",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
    except Exception as e:
        print(f"  ❌ KAMIS API 호출 실패: {e}")
        return []

    items = data.get("item", [])
    print(f"  전체 품목 수: {len(items)}")

    keywords = ["밀", "콩", "대두", "옥수수", "식용유", "사료", "밀가루", "전분"]
    matched = []
    for item in items:
        name = item.get("item_name", "")
        code = item.get("item_code", "")
        if any(kw in name for kw in keywords):
            matched.append({"code": code, "name": name})
            print(f"  ★ 코드: {code:<10} 이름: {name}")

    if not matched:
        print("  ⚠️ 밀/옥수수/대두 관련 품목 없음. 전체 목록 앞 20개:")
        for item in items[:20]:
            print(f"    {item.get('item_code',''):<10} {item.get('item_name','')}")

    return matched


# ============================================================
# 메인
# ============================================================
if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Phase 0 — API 키 검증 및 품목코드 조회                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # PPI
    ppi_kw = [
        "밀가루", "제분", "전분", "배합사료", "사료",
        "대두유", "식용유", "유지", "식물성", "두부",
        "옥수수", "소맥", "대두", "곡물"
    ]
    ppi_results = query_ecos_item_list("404Y014", "생산자물가지수(품목별)", ppi_kw)

    # CPI
    cpi_kw = [
        "밀가루", "빵", "라면", "국수", "면류",
        "식용유", "두부", "된장", "간장", "콩나물",
        "돼지고기", "닭고기", "달걀", "계란"
    ]
    cpi_results = query_ecos_item_list("901Y009", "소비자물가지수(품목별)", cpi_kw)

    # 샘플 데이터
    print(f"\n{'='*70}")
    print(f"  [샘플 데이터 조회]")
    print(f"{'='*70}")
    for r in (ppi_results[:2] + cpi_results[:1]):
        query_ecos_sample_data(r["stat_code"], r["item_code"], r["item_name"])
        time.sleep(0.5)

    # 환율
    test_exchange_rate_api()

    # KAMIS
    kamis_results = test_kamis_api()

    # CSV 저장
    all_results = ppi_results + cpi_results
    if all_results:
        os.makedirs("data/output", exist_ok=True)
        csv_path = "data/output/ecos_matched_item_codes.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\n  💾 매칭 품목코드 저장: {csv_path}")

    # 요약
    print(f"\n{'='*70}")
    print(f"  📋 결과 요약")
    print(f"{'='*70}")
    print(f"  PPI 매칭: {len(ppi_results)}건")
    print(f"  CPI 매칭: {len(cpi_results)}건")
    print(f"  KAMIS:    {'조회 완료' if kamis_results else '키 미입력 또는 매칭 없음'}")
    print()
    print(f"  ▶ 다음 단계:")
    print(f"    1. 위 결과에서 품목별 최종 코드 확정")
    print(f"    2. config/commodity_mapping.json 업데이트")
    print(f"    3. World Bank Pink Sheet 다운로드")
    print(f"    4. 수집 파이프라인 코드 작성")