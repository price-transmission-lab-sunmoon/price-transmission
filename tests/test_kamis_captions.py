"""KAMIS monthlySalesList - 4개 품목 caption 확인"""
import requests, json, os
from dotenv import load_dotenv
load_dotenv(".env")

CERT_KEY = os.getenv("KAMIS_CERT_KEY")
CERT_ID = os.getenv("KAMIS_CERT_ID")

items = [
    {"name": "쇠고기", "cat": "500", "code": "511"},
    {"name": "땅콩", "cat": "300", "code": "313"},
    {"name": "바나나", "cat": "400", "code": "416"},
    {"name": "오렌지", "cat": "400", "code": "420"},
]

for item in items:
    print(f"\n{'='*60}")
    print(f"  [{item['name']}] 부류:{item['cat']}, 품목:{item['code']}")
    print(f"{'='*60}")

    r = requests.get("http://www.kamis.or.kr/service/price/xml.do", params={
        "action": "monthlySalesList",
        "p_cert_key": CERT_KEY,
        "p_cert_id": CERT_ID,
        "p_returntype": "json",
        "p_yyyy": "2024",
        "p_period": "1",
        "p_itemcategorycode": item["cat"],
        "p_itemcode": item["code"],
        "p_kindcode": "",
        "p_graderank": "",
        "p_countycode": "1101",
        "p_convert_kg_yn": "Y",
    }, timeout=30)

    data = r.json()
    error = data.get("error_code", "")
    print(f"  error_code: {error}")

    prices = data.get("price", [])
    if not prices:
        print(f"  price 없음. 응답 키: {list(data.keys())}")
        continue

    print(f"  price 항목 수: {len(prices)}")
    for i, p in enumerate(prices):
        cls = p.get("productclscode", "")
        cap = p.get("caption", "")
        item_count = len(p.get("item", []))
        print(f"    [{i}] cls:{cls} 연도수:{item_count} caption: {cap}")
