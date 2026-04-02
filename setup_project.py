#!/usr/bin/env python3
"""
=============================================================
  price-transmission 프로젝트 초기 셋업 스크립트
=============================================================
  실행 방법:
    python setup_project.py

  이 스크립트가 하는 일:
    1. 프로젝트 폴더 구조 생성
    2. requirements.txt 생성
    3. .env.example 생성 (API 키 템플릿)
    4. .gitignore 생성
    5. Python 버전 확인
    6. 가상환경 생성 + 패키지 설치
    7. 설치 검증 (import 테스트)
    8. .env 파일 생성 안내

  주의:
    - 프로젝트 루트 폴더에서 실행하세요
    - Python 3.10 이상 필요
=============================================================
"""

import os
import sys
import subprocess
import platform

# ============================================================
# 0. Python 버전 확인
# ============================================================
def check_python_version():
    major, minor = sys.version_info[:2]
    print(f"\n[1/8] Python 버전 확인")
    print(f"  현재: Python {major}.{minor}.{sys.version_info[2]}")
    if major < 3 or (major == 3 and minor < 10):
        print(f"  ❌ Python 3.10 이상이 필요합니다. 현재: {major}.{minor}")
        print(f"  https://www.python.org/downloads/ 에서 설치해주세요.")
        sys.exit(1)
    print(f"  ✅ OK")


# ============================================================
# 1. 폴더 구조 생성
# ============================================================
DIRS = [
    "data/raw/worldbank",       # World Bank Pink Sheet 원본
    "data/raw/fao",             # FAO FFPI 원본
    "data/raw/customs",         # 관세청 수입단가 원본
    "data/raw/exchange_rate",   # 환율 원본
    "data/raw/ecos",            # ECOS PPI/CPI 원본
    "data/raw/kamis",           # KAMIS 도매가 원본
    "data/processed",           # 전처리 완료 데이터 (월별 통합)
    "data/output",              # 분석 결과 (IRF, 탐지 결과 등)
    "src/collectors",           # 데이터 수집 모듈 (소스별)
    "src/preprocessing",        # 전처리 모듈 (Phase 0~1)
    "src/analysis",             # 분석 모듈 (Phase 2~7)
    "src/ml",                   # ML 보조 교차검증 (Phase 7-ML)
    "src/utils",                # 공통 유틸리티
    "config",                   # 설정 파일 (매핑 테이블 등)
    "notebooks",                # Jupyter 탐색적 분석
    "docs",                     # 문서 (파이프라인 명세, 패턴 정의 등)
    "tests",                    # 테스트 코드
]

def create_directories():
    print(f"\n[2/8] 폴더 구조 생성")
    for d in DIRS:
        os.makedirs(d, exist_ok=True)
        # 빈 폴더도 git에 추적되도록 .gitkeep 생성
        gitkeep = os.path.join(d, ".gitkeep")
        if not os.path.exists(gitkeep):
            open(gitkeep, "w").close()
    
    # src 패키지 __init__.py 생성
    for pkg in ["src", "src/collectors", "src/preprocessing", 
                "src/analysis", "src/ml", "src/utils", "config"]:
        init_path = os.path.join(pkg, "__init__.py")
        if not os.path.exists(init_path):
            open(init_path, "w").close()
    
    print(f"  ✅ {len(DIRS)}개 폴더 생성 완료")


# ============================================================
# 2. requirements.txt 생성
# ============================================================
REQUIREMENTS = """\
# =============================================================
# price-transmission 프로젝트 의존성
# 신청서 기준 버전 + Phase 0 데이터 수집에 필요한 패키지
# =============================================================

# --- 데이터 처리 ---
pandas>=2.0,<3.0
numpy>=1.24,<2.0

# --- 계량경제학 (Phase 2~4: 검정, VAR/VECM, IRF) ---
statsmodels>=0.14,<1.0
scipy>=1.11,<2.0

# --- 구조 변화 탐지 (Phase 6: Bai-Perron) ---
ruptures>=1.1,<2.0

# --- ML 보조 교차검증 (Phase 7-ML) ---
scikit-learn>=1.4,<2.0

# --- 시각화 ---
matplotlib>=3.7,<4.0
seaborn>=0.13,<1.0

# --- 데이터 수집 (Phase 0: API 호출) ---
requests>=2.31,<3.0
python-dotenv>=1.0,<2.0

# --- Jupyter 탐색적 분석 ---
jupyter>=1.0
jupyterlab>=4.0

# --- 유틸리티 ---
openpyxl>=3.1          # Excel 파일 읽기 (World Bank Pink Sheet)
xlrd>=2.0              # 구버전 .xls 파일 지원
tqdm>=4.65             # 진행률 표시
"""

def create_requirements():
    print(f"\n[3/8] requirements.txt 생성")
    path = "requirements.txt"
    if os.path.exists(path):
        print(f"  ⚠️  이미 존재함 — 덮어쓰지 않음")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(REQUIREMENTS)
    print(f"  ✅ requirements.txt 생성 완료")


# ============================================================
# 3. .env.example 생성
# ============================================================
ENV_EXAMPLE = """\
# =============================================================
# API 키 설정 — 이 파일을 .env로 복사한 뒤 실제 키를 입력하세요
# cp .env.example .env
# =============================================================

# 한국은행 ECOS (PPI, CPI 수집용)
# 발급: https://ecos.bok.or.kr → 회원가입 → Open API → 인증키 신청
ECOS_API_KEY=여기에_ECOS_인증키_입력

# 한국수출입은행 (환율 수집용)
# 발급: https://www.koreaexim.go.kr/ir/HPHKIR020M01?apino=2&viewtype=C
EXIM_API_KEY=여기에_수출입은행_인증키_입력

# KAMIS 농산물유통정보 (도매가 수집용)
# 발급: https://www.kamis.or.kr → 회원가입 → Open-API 사용신청
KAMIS_CERT_KEY=여기에_KAMIS_인증키_입력
KAMIS_CERT_ID=여기에_KAMIS_계정아이디_입력
"""

def create_env_example():
    print(f"\n[4/8] .env.example 생성")
    path = ".env.example"
    if os.path.exists(path):
        print(f"  ⚠️  이미 존재함 — 덮어쓰지 않음")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(ENV_EXAMPLE)
    print(f"  ✅ .env.example 생성 완료")


# ============================================================
# 4. .gitignore 생성
# ============================================================
GITIGNORE = """\
# === Python ===
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
*.egg

# === 가상환경 ===
.venv/
venv/
env/

# === API 키 (절대 커밋 금지) ===
.env

# === 데이터 원본 (용량 큰 파일) ===
data/raw/**/*.xlsx
data/raw/**/*.xls
data/raw/**/*.csv
!data/raw/**/.gitkeep

# === 분석 결과 (재현 가능하므로 커밋 불필요) ===
data/output/
!data/output/.gitkeep

# === Jupyter 체크포인트 ===
.ipynb_checkpoints/

# === IDE ===
.vscode/
.idea/
*.swp
*.swo
.DS_Store
Thumbs.db

# === 기타 ===
*.log
"""

def create_gitignore():
    print(f"\n[5/8] .gitignore 생성")
    path = ".gitignore"
    if os.path.exists(path):
        print(f"  ⚠️  이미 존재함 — 덮어쓰지 않음")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(GITIGNORE)
    print(f"  ✅ .gitignore 생성 완료")


# ============================================================
# 5. config/settings.py 생성 (프로젝트 공통 설정)
# ============================================================
SETTINGS_PY = '''\
"""
프로젝트 공통 설정
- API 키는 .env 파일에서 로드
- 파이프라인 파라미터는 신청서 기준값 사전 고정
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# === 프로젝트 경로 ===
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_OUTPUT = PROJECT_ROOT / "data" / "output"

# === API 키 ===
ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")
EXIM_API_KEY = os.getenv("EXIM_API_KEY", "")
KAMIS_CERT_KEY = os.getenv("KAMIS_CERT_KEY", "")
KAMIS_CERT_ID = os.getenv("KAMIS_CERT_ID", "")

# === 분석 기간 (데이터 가용성 확인 후 확정) ===
ANALYSIS_START = "2000-01"   # 잠정
ANALYSIS_END = "2025-12"     # 잠정

# === 파이프라인 파라미터 (신청서 기준값) ===
RANDOM_STATE = 42

# Phase 1: STL
STL_PERIOD = 12              # 월별 데이터 계절 주기
STL_ROBUST = True            # 이상치 강건 STL

# Phase 2: 정상성 검정
ADF_SIGNIFICANCE = 0.05
KPSS_SIGNIFICANCE = 0.05

# Phase 3: Johansen 공적분 검정
JOHANSEN_DET_ORDER = 0       # 결정론적 추세 없음

# Phase 4: VAR/VECM
LAG_SEARCH_RANGE = range(1, 5)  # 1~4

# Phase 6: 구조 변화
MIN_SUBPERIOD_OBS = 60       # 하위 기간 최소 관측치

# Phase 7: 이상 탐지
ROLLING_WINDOW = 48          # 기본 롤링 윈도우 크기 (개월)
ROLLING_WINDOW_ROBUSTNESS = [36, 48, 60]  # 로버스트니스 체크용
ZSCORE_WARNING = 2.0         # Z-score 주의 임계값
ZSCORE_ALERT = 2.5           # Z-score 경보 임계값
IQR_MULTIPLIER = 1.5         # Tukey 표준
STABILITY_THRESHOLD = 0.03   # 국제가 안정 구간 (±3%)
PATTERN3_N_VALUES = [2, 3, 6]  # N값 3단계

# Phase 7-ML: ML 파라미터
IF_N_ESTIMATORS = 100
CONTAMINATION_RANGE = [0.05, 0.10, 0.15]
LOF_N_NEIGHBORS_RANGE = range(5, 21)
SVM_KERNEL = "rbf"

# Phase 0: 결측치 처리
MAX_MISSING_RATE = 0.10      # 10% 이상 결측 품목 제외
MAX_CONSECUTIVE_MISSING = 3  # 연속 결측 3개월 이상 플래그
'''

def create_settings():
    print(f"\n[6/8] config/settings.py 생성")
    path = os.path.join("config", "settings.py")
    if os.path.exists(path):
        print(f"  ⚠️  이미 존재함 — 덮어쓰지 않음")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(SETTINGS_PY)
    print(f"  ✅ config/settings.py 생성 완료")


# ============================================================
# 6. 가상환경 생성 + 패키지 설치
# ============================================================
def setup_venv():
    print(f"\n[7/8] 가상환경 생성 + 패키지 설치")
    
    venv_dir = ".venv"
    
    if os.path.exists(venv_dir):
        print(f"  ℹ️  .venv 이미 존재 — 패키지 설치만 진행")
    else:
        print(f"  가상환경 생성 중... (.venv)")
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
        print(f"  ✅ .venv 생성 완료")
    
    # OS별 pip 경로
    if platform.system() == "Windows":
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
        python_path = os.path.join(venv_dir, "Scripts", "python")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
        python_path = os.path.join(venv_dir, "bin", "python")
    
    # pip 업그레이드
    print(f"  pip 업그레이드 중...")
    subprocess.run([pip_path, "install", "--upgrade", "pip"], 
                   capture_output=True, check=True)
    
    # requirements.txt 설치
    print(f"  패키지 설치 중... (2~5분 소요)")
    result = subprocess.run(
        [pip_path, "install", "-r", "requirements.txt"],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print(f"  ❌ 설치 실패:")
        print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
        return python_path
    
    print(f"  ✅ 패키지 설치 완료")
    return python_path


# ============================================================
# 7. 설치 검증
# ============================================================
def verify_installation(python_path):
    print(f"\n[8/8] 설치 검증")
    
    verify_code = """
import sys
results = []
packages = [
    ("pandas",      "pandas",       "2.0"),
    ("numpy",       "numpy",        "1.24"),
    ("statsmodels", "statsmodels",  "0.14"),
    ("scipy",       "scipy",        "1.11"),
    ("ruptures",    "ruptures",     "1.1"),
    ("scikit-learn","sklearn",      "1.4"),
    ("matplotlib",  "matplotlib",   "3.7"),
    ("seaborn",     "seaborn",      "0.13"),
    ("requests",    "requests",     "2.31"),
    ("dotenv",      "dotenv",       "1.0"),
    ("openpyxl",    "openpyxl",     "3.1"),
    ("tqdm",        "tqdm",         "4.65"),
]

all_ok = True
for display_name, import_name, min_ver in packages:
    try:
        mod = __import__(import_name)
        ver = getattr(mod, "__version__", "?")
        print(f"  ✅ {display_name:<15} {ver}")
    except ImportError:
        print(f"  ❌ {display_name:<15} 설치 안 됨")
        all_ok = False

# STL 분해 테스트
try:
    from statsmodels.tsa.seasonal import STL
    print(f"  ✅ {'STL 분해':<15} 사용 가능")
except ImportError:
    print(f"  ❌ {'STL 분해':<15} 사용 불가")
    all_ok = False

# VAR/VECM 테스트
try:
    from statsmodels.tsa.vector_ar.var_model import VAR
    from statsmodels.tsa.vector_ar.vecm import VECM
    print(f"  ✅ {'VAR/VECM':<15} 사용 가능")
except ImportError:
    print(f"  ❌ {'VAR/VECM':<15} 사용 불가")
    all_ok = False

if all_ok:
    print(f"\\n  🎉 모든 패키지 정상 설치!")
else:
    print(f"\\n  ⚠️  일부 패키지 누락 — 위 목록 확인 후 수동 설치")

sys.exit(0 if all_ok else 1)
"""
    
    result = subprocess.run(
        [python_path, "-c", verify_code],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr[-300:])


# ============================================================
# 8. 최종 안내 출력
# ============================================================
def print_next_steps():
    is_win = platform.system() == "Windows"
    activate_cmd = r".venv\Scripts\activate" if is_win else "source .venv/bin/activate"
    
    print(f"""
{'='*60}
  ✅ 프로젝트 셋업 완료!
{'='*60}

  다음 단계:

  1) .env 파일 생성 (API 키 입력)
     {'copy' if is_win else 'cp'} .env.example .env
     → .env 열어서 실제 API 키 붙여넣기

  2) 가상환경 활성화
     {activate_cmd}

  3) API 검증 + 품목코드 조회 실행
     python verify_apis_and_find_codes.py

  📁 프로젝트 폴더 구조:
  ├── data/
  │   ├── raw/          ← 원본 데이터 (소스별)
  │   ├── processed/    ← 전처리 완료 데이터
  │   └── output/       ← 분석 결과
  ├── src/
  │   ├── collectors/   ← 데이터 수집 모듈
  │   ├── preprocessing/← Phase 0~1
  │   ├── analysis/     ← Phase 2~7
  │   ├── ml/           ← Phase 7-ML
  │   └── utils/        ← 공통 유틸
  ├── config/
  │   └── settings.py   ← 전체 파라미터 관리
  ├── notebooks/        ← Jupyter 탐색 분석
  ├── docs/             ← 문서
  ├── tests/            ← 테스트
  ├── .env              ← API 키 (git 추적 안 됨)
  ├── .env.example      ← API 키 템플릿
  ├── .gitignore
  └── requirements.txt
""")


# ============================================================
# 메인
# ============================================================
if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  price-transmission 프로젝트 초기 셋업                  ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    check_python_version()      # [1/8]
    create_directories()        # [2/8]
    create_requirements()       # [3/8]
    create_env_example()        # [4/8]
    create_gitignore()          # [5/8]
    create_settings()           # [6/8]
    python_path = setup_venv()  # [7/8]
    verify_installation(python_path)  # [8/8]
    print_next_steps()
