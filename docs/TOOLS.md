# Codex 연구 도구 사용

## 프로젝트 MCP와 스킬

Codex에서 프로젝트 루트를 연다. 프로젝트 설정을 허용한 작업공간에서 `.codex/config.toml`이 Windows용 `frontier-training` stdio 서버를 등록한다. `.agents/skills`의 네 스킬은 요청 내용으로 선택한다. 다른 PC에 설치할 때는 아래 전용 환경의 Python에 `uv pip install --python <python.exe> -r tools/requirements.txt`로 SDK를 포함한 의존성을 설치하고, 그 PC의 실행기 및 비공개 저장소를 local-tools.json에 설정한다.

| MCP 도구 | 입출력 |
| --- | --- |
| search_papers · read_source | 공개 검색어로 논문 후보를 조회한다. PMID는 초록, PMCID는 공개 본문을 읽고 발췌 위치와 다음 읽기 위치를 반환한다. |
| inspect_video · read_activity | 지정된 비공개 records/inbox 아래의 파일명을 받는다. 영상은 타임스탬프별 프레임, CSV·FIT는 페이지별 관측을 반환한다. |
| run_analysis | 같은 단위의 전후 수열을 받아 평균·변화·변동 폭을 반환한다. 역학 시뮬레이션은 아래 별도 로컬 실행기를 쓴다. |
| append_record · read_record | records/training.sqlite3에 기록을 추가하거나 ID·주제로 조회한다. 같은 쓰기 요청은 한 번만 반영하고 정정은 기존 항목에 연결한다. 읽기만 하면 빈 DB를 만들지 않는다. |

공개 문헌 조회만 외부 문헌 서비스로 요청한다. 영상 프레임·개인 기록을 도구 결과로 요청하면 해당 내용이 사용 중인 Codex 모델 문맥에 들어간다. 개인 자료나 식별자를 공개 검색에 포함하지 않는다. 사용자에게서 분석 권한을 받은 파일만 inbox에 넣는다. Exa·Firecrawl과 전문 시뮬레이터는 아래 기존 연결을 그대로 이용한다.

프로젝트 설정을 읽었는지는 루트에서 `codex mcp list`로 확인한다. 변경 후 새 세션을 연다. Windows의 다른 폴더에서 MCP를 단독 검증하려면 프로젝트 루트로 이동해 `tools/start-mcp.ps1`을 stdio 클라이언트로 실행한다.

## CLI와 개별 도구

프로젝트 루트에서 공개 문헌을 검색한다. Windows 연구 환경은 사용자 앱 데이터의 `FrontierTraining`이다. 아래 명령은 개인 자료를 전송하지 않는다.

```powershell
./tools/research.ps1 pubmed "motor learning" --limit 2
./tools/research.ps1 abstract 31452104
./tools/research.ps1 europepmc "OPEN_ACCESS:Y AND TITLE:exercise sort_date:y" --limit 2
./tools/research.ps1 pmc-xml PMC13695092
./tools/research.ps1 bioc PMC4960517
./tools/research.ps1 jstage exercise --limit 1
./tools/research.ps1 sportrxiv exercise --limit 2
./tools/research.ps1 datacite biomechanics --limit 2
./tools/research.ps1 retractions exercise --limit 2
./tools/research.ps1 openalex "motor learning" --limit 2
./tools/research.ps1 arxiv-feed q-bio.QM
./tools/research.ps1 feed https://journals.plos.org/plosone/feed/atom --limit 2
```

**검색과 신착.** PubMed 검색 결과의 PMID로 초록을 열고, Europe PMC의 공개 PMCID로 원문 XML 또는 BioC를 읽는다. PDF는 페이지 번호, XML은 표·문단 ID와 함께 확인한다. Crossref의 retractions는 철회 고지 검색이며 결과의 update-to와 source를 읽어 대상 DOI와 Retraction Watch 제공 여부를 확인한다. Europe PMC 저장 검색은 공개 검색식을 재사용하고 생성한 HTTPS RSS 주소는 feed에 전달한다. 학술지 및 arXiv 피드는 실행 시점의 공지를 반환하며 정상 0건도 가능하다. 개인 맞춤 알림은 서비스 계정 설정에 따른다.

| 자료와 도구 | 접근 방법 |
| --- | --- |
| 웹·공개 영상 | Codex의 Exa 검색과 Firecrawl 읽기로 공개 원 URL을 찾는다. Trafilatura는 확보한 HTML의 본문을 로컬에서 추출한다. 허용된 로컬 영상은 FFmpeg와 ffprobe로 검토한다. YouTube Data API v3의 검색은 YOUTUBE_API_KEY 설정 후 `research.ps1 youtube 검색어`로 호출한다. |
| 스포츠 문헌·등록 | [SportRxiv 공개 검색](https://sportrxiv.org/index.php/server/search), [WHO ICTRP 등록 검색](https://trialsearch.who.int/), [SPORTDiscus](https://www.ebsco.com/products/research-databases/sportdiscus). 공개 페이지에서 찾은 영구 링크·내보낸 자료를 사용한다. SPORTDiscus 기관 구독 필요 시 PubMed·Europe PMC·OpenAlex에서 공개 문헌을 찾는다. |
| Semantic Scholar | `research.ps1 semantic-scholar 검색어`는 Academic Graph API다. 익명 호출의 429는 요청 제한으로 표시한다. S2_API_KEY가 있으면 사용한다. 개인 Research Feeds는 [서비스 계정](https://www.semanticscholar.org/faq)을 사용한다. |
| Zotero | Zotero Web API 읽기는 `research.ps1 zotero 검색어`. 공개 그룹은 ZOTERO_LIBRARY_TYPE=groups와 공개 그룹의 ZOTERO_LIBRARY_ID, 비공개 서재는 허가된 ZOTERO_API_KEY도 필요하다. 개인 계정이 없으면 공개 DOI/PMID 또는 내보낸 서지 파일을 사용한다. |
| 문서·분석 | 전용 Python에서 pypdf, pypdfium2, pandas, NumPy, SciPy, garmin_fit_sdk를 import한다. 설치 목록은 [requirements.txt](../tools/requirements.txt)다. CSV와 FIT 원본은 로컬에서 읽는다. |
| 자세·역학 | MediaPipe Pose Landmarker는 로컬 모델을 사용한다. Kinovea는 Windows 데스크톱에서 영상을 열어 보정·판독한다. OpenSim과 Moco는 host 설정에 지정된 별도 Python에서 실행한다. 개인 영상 없이도 로컬 계산은 가능하다. [OpenCap](https://app.opencap.ai/)의 촬영·클라우드 처리에는 계정과 지원 촬영 환경이 필요하다. |
| 개인 기록 | 비공개 기록은 host 설정의 records에 저장한다. 연구 예측·일상 기록·원본 파일을 공개 Git 저장소 밖에 둔다. |

**이 PC에서 도구 위치 읽기.** 로컬 설정에는 경로만 저장된다. API 키는 필요한 경우 사용자 환경에서만 읽는다.

SportRxiv 명령은 Crossref에서 10.51224 접두사의 색인 기록을 조회한다. 이전에 다른 DOI로 등록된 자료는 공개 사이트에서도 찾아본다. Zotero의 무계정 읽기를 확인하려면 현재 PowerShell 세션에서 `$env:ZOTERO_LIBRARY_TYPE='groups'`, `$env:ZOTERO_LIBRARY_ID='3411160'`을 설정하고 공개 그룹에 `./tools/research.ps1 zotero '' --limit 1`을 실행한다.

```powershell
$root = Join-Path $env:USERPROFILE 'AppData/Local/FrontierTraining'
$runtime = Get-Content -Raw (Join-Path $root 'local-tools.json') | ConvertFrom-Json
& $runtime.python -c "import pandas, scipy, pypdf, mediapipe"
& $runtime.opensim_python -c "import opensim as o; print(o.MocoStudy().getConcreteClassName())"
& $runtime.ffprobe -version
```

이 설정의 `pose_model`, `kinovea`, `opencap_source`, `ffmpeg`, `records`도 각 도구의 실제 위치다. 개인 정보가 들어간 파일이나 검색식을 외부 서비스에 전송할 때는 프로젝트 지침을 따른다.
