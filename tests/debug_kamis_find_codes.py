"""
KAMIS monthlySalesList 품목 코드 탐색
==============================================
목적: caption에서 실제 품목명(바나나, 오렌지, 땅콩, 쇠고기)이 나오는
      item_code를 찾기

방법: 각 부류 내에서 품목 코드를 순회하며 caption 확인

KAMIS 코드 구조 추정:
  - 부류 400(과일류) 내 품목: 411~430 정도?
  - 부류 300(특용작물) 내 품목: 311~320 정도?
  - 부류 500(축산물) 내 품목: 511~520 정도?

실행: python tests/debug_kamis_find_codes.py
"""

import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent if script_dir.name == "tests" else script_dir
load_dotenv(project_root / ".env")

CERT_KEY = os.getenv("KAMIS_CERT_KEY", "")
CERT_ID = os.getenv("KAMIS_CERT_ID", "")
BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"


def get_caption(cat_code, item_code):
    """monthlySalesList로 caption 조회"""
    params = {
        "action": "monthlySalesList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_yyyy": "2023",
        "p_period": "1",
        "p_itemcategorycode": cat_code,
        "p_itemcode": item_code,
        "p_kindcode": "",
        "p_graderank": "",
        "p_countycode": "1101",
        "p_convert_kg_yn": "Y",
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        data = resp.json()
    except Exception:
        return None

    prices = data.get("price", [])
    if not prices:
        return None

    # 첫 번째 price 블록의 caption
    caption = prices[0].get("caption", "")
    return caption


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS 품목 코드 탐색 (caption 기반)")
    print("=" * 70)

    # ================================================================
    # 과일류 (400) — 바나나, 오렌지 찾기
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  과일류 (400): 품목코드 411 ~ 430 스캔")
    print(f"{'─'*70}")

    for code in range(411, 431):
        caption = get_caption("400", str(code))
        if caption:
            # 품목명 추출 (caption 형식: "xxx > 과일류 > 품목명 > ...")
            mark = ""
            if "바나나" in caption:
                mark = " ★★★ 바나나!"
            elif "오렌지" in caption:
                mark = " ★★★ 오렌지!"
            print(f"    {code}: {caption[:60]}{mark}")
        else:
            print(f"    {code}: (데이터 없음)")
        time.sleep(0.2)

    # 범위 확장 — 431~450
    print(f"\n  과일류 (400): 품목코드 431 ~ 450 스캔")
    for code in range(431, 451):
        caption = get_caption("400", str(code))
        if caption:
            mark = ""
            if "바나나" in caption:
                mark = " ★★★ 바나나!"
            elif "오렌지" in caption:
                mark = " ★★★ 오렌지!"
            print(f"    {code}: {caption[:60]}{mark}")
        else:
            print(f"    {code}: (데이터 없음)")
        time.sleep(0.2)

    # ================================================================
    # 특용작물 (300) — 땅콩 찾기
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  특용작물 (300): 품목코드 311 ~ 330 스캔")
    print(f"{'─'*70}")

    for code in range(311, 331):
        caption = get_caption("300", str(code))
        if caption:
            mark = ""
            if "땅콩" in caption:
                mark = " ★★★ 땅콩!"
            print(f"    {code}: {caption[:60]}{mark}")
        else:
            print(f"    {code}: (데이터 없음)")
        time.sleep(0.2)

    # ================================================================
    # 축산물 (500) — 쇠고기 찾기
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  축산물 (500): 품목코드 511 ~ 530 스캔")
    print(f"{'─'*70}")

    for code in range(511, 531):
        caption = get_caption("500", str(code))
        if caption:
            mark = ""
            if "쇠고기" in caption or "한우" in caption or "소고기" in caption:
                mark = " ★★★ 쇠고기!"
            print(f"    {code}: {caption[:60]}{mark}")
        else:
            print(f"    {code}: (데이터 없음)")
        time.sleep(0.2)

    # ================================================================
    # 식량작물 (100) — 코드 구조 참고용
    # ================================================================
    print(f"\n{'─'*70}")
    print(f"  식량작물 (100): 품목코드 111 ~ 120 스캔 (참고)")
    print(f"{'─'*70}")

    for code in range(111, 121):
        caption = get_caption("100", str(code))
        if caption:
            print(f"    {code}: {caption[:60]}")
        else:
            print(f"    {code}: (데이터 없음)")
        time.sleep(0.2)

    print(f"\n{'='*70}")
    print(f"  스캔 완료")
    print(f"{'='*70}")
