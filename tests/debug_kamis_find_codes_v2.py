"""
KAMIS 품목 코드 탐색 - 땅콩, 쇠고기만 집중
==============================================
이미 확인된 코드:
  바나나: 418 (기존 416은 단감)
  오렌지: 421 (기존 420은 파인애플)

실행: python tests/debug_kamis_find_codes_v2.py
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
    if not prices or not isinstance(prices, list):
        return None
    if not isinstance(prices[0], dict):
        return None

    return prices[0].get("caption", "")


if __name__ == "__main__":
    print("=" * 70)
    print("  KAMIS 품목 코드 탐색 v2 — 땅콩 + 쇠고기")
    print("=" * 70)

    # ================================================================
    # 특용작물 (300) — 땅콩 찾기
    # ================================================================
    print(f"\n  특용작물 (300): 품목코드 311 ~ 330")
    print(f"  {'─'*60}")

    for code in range(311, 331):
        caption = get_caption("300", str(code))
        if caption:
            mark = " ★★★ 땅콩!" if "땅콩" in caption else ""
            print(f"    {code}: {caption[:65]}{mark}")
        else:
            print(f"    {code}: (없음)")
        time.sleep(0.2)

    # ================================================================
    # 축산물 (500) — 쇠고기 찾기
    # ================================================================
    print(f"\n  축산물 (500): 품목코드 511 ~ 535")
    print(f"  {'─'*60}")

    for code in range(511, 536):
        caption = get_caption("500", str(code))
        if caption:
            mark = ""
            if any(kw in caption for kw in ["쇠고기", "한우", "소고기", "육우"]):
                mark = " ★★★ 쇠고기!"
            print(f"    {code}: {caption[:65]}{mark}")
        else:
            print(f"    {code}: (없음)")
        time.sleep(0.2)

    # ================================================================
    # 확인된 코드 검증 — 바나나(418), 오렌지(421)
    # ================================================================
    print(f"\n  확인된 코드 검증:")
    print(f"  {'─'*60}")
    for name, cat, code in [("바나나", "400", "418"), ("오렌지", "400", "421")]:
        caption = get_caption(cat, code)
        print(f"    {name} ({cat}/{code}): {caption}")

    print(f"\n{'='*70}")
    print(f"  스캔 완료")
    print(f"{'='*70}")
