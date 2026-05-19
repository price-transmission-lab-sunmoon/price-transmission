"""
Phase 1 계절성 강도 히트맵 시각화
phase1_summary.csv의 seasonal_pct_of_mean 값을 품목 X 컬럼 히트맵으로 시각화
"""


import os
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
 
# ── 경로 설정 ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY_PATH = os.path.join(BASE_DIR, "data", "processed", "phase1", "phase1_summary.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "seasonal_strength_heatmap.png")
 
# ── 한글 폰트 설정 ──
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
 
# ── 데이터 로드 ──
summary = pd.read_csv(SUMMARY_PATH)
 
# ── 히트맵용 피벗 테이블 생성 ──
pivot = summary.pivot(index='commodity_id', columns='column', values='seasonal_pct_of_mean')
 
# 품목 순서 (계절성 강한 순)
order = ['banana', 'orange', 'groundnuts', 'palmoil', 'coffee', 'beef', 'sugar', 'wheat', 'maize', 'soybean']
col_order = ['intl_price_krw', 'import_price_usd', 'ppi', 'cpi', 'wholesale_price']
col_labels = ['국제가(원화)', '수입단가', 'PPI', 'CPI', '도매가']
 
pivot = pivot.reindex(index=order, columns=col_order)
 
# 품목명 한글로 변환
name_map = {
    'banana': '바나나', 'orange': '오렌지', 'groundnuts': '땅콩', 'palmoil': '팜유',
    'coffee': '커피', 'beef': '쇠고기', 'sugar': '설탕', 'wheat': '밀', 'maize': '옥수수', 'soybean': '대두'
}
pivot.index = [name_map[x] for x in pivot.index]
 
# ── 히트맵 그리기 ──
fig, ax = plt.subplots(figsize=(10, 7))
im = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto', vmin=0, vmax=120)
 
ax.set_xticks(range(len(col_order)))
ax.set_xticklabels(col_labels, fontsize=11)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels(pivot.index, fontsize=11)
 
# 셀 안에 % 값 표시
for i in range(len(pivot.index)):
    for j in range(len(col_order)):
        val = pivot.values[i, j]
        if np.isnan(val):
            ax.text(j, i, '—', ha='center', va='center', fontsize=10, color='gray')
        else:
            color = 'white' if val > 60 else 'black'
            ax.text(j, i, f'{val:.0f}%', ha='center', va='center', fontsize=10,
                    fontweight='bold' if val > 50 else 'normal', color=color)
 
cbar = plt.colorbar(im, ax=ax, shrink=0.8, label='계절 변동 범위 / 원본 평균 (%)')
ax.set_title('품목·컬럼별 계절성 강도 (seasonal_pct_of_mean)', fontsize=14, fontweight='bold', pad=15)
 
# ── 저장 ──
os.makedirs(OUTPUT_DIR, exist_ok=True)
plt.tight_layout()
plt.savefig(OUTPUT_PATH, dpi=180, bbox_inches='tight', facecolor='white', edgecolor='none')
plt.close()
print(f"저장 완료: {OUTPUT_PATH}")