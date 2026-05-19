"""
Phase 2 적분 차수 분포 시각화
- stationarity_results.csv의 integration_order 값을 막대 그래프로 시각화
- 연구노트 및 발표 자료용
"""

import os
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

# ── 경로 설정 ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_PATH = os.path.join(BASE_DIR, "data", "processed", "phase2", "stationarity_results.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "integration_order_distribution.png")

# ── 한글 폰트 설정 ──
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ── 데이터 로드 ──
results = pd.read_csv(RESULTS_PATH)

# ── 적분 차수별 집계 ──
i0 = len(results[results['integration_order'] == 0])
i1 = len(results[results['integration_order'] == 1])
i2 = len(results[results['integration_order'] == 2])
total = len(results)

# ── 막대 그래프 ──
fig, ax = plt.subplots(figsize=(8, 5))

categories = ['I(0)\n수준 정상', 'I(1)\n1차 차분 후 정상', 'I(2)\n2차 차분 필요']
counts = [i0, i1, i2]
colors = ['#94A3B8', '#059669', '#DC2626']

bars = ax.bar(categories, counts, color=colors, width=0.5, edgecolor='white', linewidth=1.5)

# 값 표시
for bar, count in zip(bars, counts):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
            f'{count}개', ha='center', va='bottom', fontsize=14, fontweight='bold')

# 비율 표시
for bar, count in zip(bars, counts):
    if count > 0:
        pct = count / total * 100
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() / 2,
                f'{pct:.1f}%', ha='center', va='center', fontsize=12,
                color='white', fontweight='bold')

# I(2) 상세 주석
i2_details = results[results['integration_order'] == 2][['commodity_id', 'column']]
if len(i2_details) > 0:
    lines = []
    for _, row in i2_details.iterrows():
        if row['commodity_id'] == 'groundnuts':
            lines.append(f"• 땅콩 {row['column']} (관측치 85개)")
        elif row['commodity_id'] == 'orange':
            lines.append(f"• 오렌지 {row['column']} (2024 급등)")
        else:
            lines.append(f"• {row['commodity_id']} {row['column']}")

    ax.annotate('\n'.join(lines),
                xy=(2, i2), xytext=(1.15, 15),
                fontsize=9, color='#DC2626',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#FEF2F2',
                          edgecolor='#DC2626', alpha=0.9),
                arrowprops=dict(arrowstyle='->', color='#DC2626', lw=1.2))

ax.set_ylabel('시계열 수', fontsize=11)
ax.set_title(f'Phase 2 정상성 검정 결과 — 적분 차수 분포 (총 {total}개 시계열)',
             fontsize=13, fontweight='bold', pad=12)
ax.set_ylim(0, max(counts) + 7)
ax.grid(True, alpha=0.15, axis='y')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# ── 저장 ──
os.makedirs(OUTPUT_DIR, exist_ok=True)
plt.tight_layout()
plt.savefig(OUTPUT_PATH, dpi=180, bbox_inches='tight', facecolor='white', edgecolor='none')
plt.close()
print(f"저장 완료: {OUTPUT_PATH}")
