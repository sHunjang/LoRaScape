# LoRaScape

**(주)솔루윈스 SmartCity LoRaWAN Network Simulator**

대도시 도심지·하천/공원·주거상업 지역 등 스마트시티 환경에서 LoRa 기반 LPWAN 게이트웨이(GW)의 무선 커버리지를 계산하고, 설치된 단말(Node)에 대해 최적의 GW 위치를 찾아주는 망 설계 도구입니다.

---

## 주요 기능

- **전파 커버리지 계산**: Song's Model(SmartCity 전파모델) + Deygout 회절손실 모델 기반 경로손실 계산
- **GW 배치 검증 및 보강**: 기존 설치된 GW로 Node 커버리지를 검증하고, 목표 미달 시 부족한 만큼만 추가 배치 위치를 제안
- **신규 GW 배치 추천**: GW가 없는 상태에서 Node 위치만으로 K-means + Song's Model 기반 최적 배치 추천
- **ATDI 스타일 격자 커버리지 히트맵**: GW별(또는 다중 GW 동시) 신호세기 시각화, 색상/해상도 조절 가능
- **지형 단면도**: GW-Node 간 LOS/NLOS 판정, Fresnel 존 시각화
- **거리 분석, 거리 측정, 우클릭 컨텍스트 메뉴** 등 실무 편의 기능
- **엑셀 인벤토리 연동**: GW/Node 정보를 엑셀에서 개별적으로 불러오기, CSV 가져오기/내보내기
- **로컬 HMAC 기반 라이선스 인증**: 서버 없이 동작, 별도 발급 도구(`licenser_tool`) 제공

---

## 설치

```powershell
conda activate lorascape   # Python 3.10 또는 3.11
pip install -r requirements.txt
pip install -e .
```

### 로컬 데이터 준비

`sample_data/`는 git에서 제외됩니다 (고객사 실측 데이터 및 대용량 GIS 파일 포함). 아래 파일들을 직접 넣어야 테스트와 앱 실행이 정상 동작합니다:

- `sample_data/AIoT네트워크단말대장v2.xlsx`
- `sample_data/(AIoT 실증) 현장 설치 인프라 총괄표.xlsx`
- `sample_data/seongnam/dem_build_seongnam_3857-2.img` (+ `.img.aux.xml`)
- `sample_data/seongnam/Outline_Seongnam_3857.*` (shapefile 세트)

---

## 실행

### 본체 프로그램

```powershell
python scripts/run_app.py
```

실행 흐름: **라이선스 인증 → 지역 데이터 선택(Shapefile/DEM) → 스플래시 화면 → 메인 화면**

### 라이선스 발급 도구 (사내 전용, 본체와 독립 실행)

```powershell
cd licenser_tool
python keygen_gui.py
```

---

## 테스트

```powershell
pytest tests/ -v
```

---

## 프로젝트 구조
```bash
lorascape/
├── core/ # 순수 계산 엔진 (전파모델, 회절손실, 링크버짓, 최적화) - GUI 의존성 없음
│ ├── propagation/ # Song's Model, COST-231 Hata
│ ├── diffraction/ # Deygout 회절손실 모델
│ ├── linkbudget/ # 수신전력, SNR, ADR, ToA, 매크로 다이버시티, ALOHA
│ └── optimization/ # K-means 기반 GW 배치 최적화, 커버리지 히트맵 계산
├── data/ # 좌표변환, DEM 로더, 엑셀 인벤토리 파서, 데이터 스키마
├── license/ # HMAC 기반 라이선스 검증/발급 핵심 로직 (licenser_tool과 공유)
└── gui/ # PyQt5 기반 데스크톱 앱 (Folium 지도, 각종 창/다이얼로그)

licenser_tool/ # 라이선스 발급 도구 (본체와 완전히 독립적인 별도 프로그램)
scripts/ # 실행 진입점, 유지보수 스크립트
tests/ # pytest 테스트 스위트

```

---

## 개발 워크플로우

이 프로젝트는 **Git Flow**(AVH Edition) 브랜치 전략을 따릅니다.

```powershell
git flow feature start <기능명>
# 작업...
git add .
git commit -m "..."
git push -u origin feature/<기능명>
git flow feature finish <기능명>
git push origin develop
```

라이선스 관련 공유 파일(`normalize.py`, `issuer_core.py`)을 수정한 경우, 반드시 아래 스크립트로 `licenser_tool/`과 동기화해야 합니다:

```powershell
.\scripts\sync_license_shared.ps1
```

---

## 라이선스 인증 관련 참고

- 비밀키(`license.key`)는 exe에 내장하지 않고 exe 옆의 외부 파일로 배포합니다.
- 인증코드 생성/발급은 본체와 완전히 분리된 `licenser_tool`에서만 수행합니다.
- 발급 이력(`licenser_tool/issue_history.json`)과 비밀키 파일(`licenser_tool/keys/`)은 민감 정보이므로 git에 커밋되지 않습니다.