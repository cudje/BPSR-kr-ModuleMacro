# ModuleMacro

게임 로그인 · 캐릭터 슬롯 처리 · 매크로를 돌리는 자동화 도구입니다.

**1920×1080 환경에서만 동작합니다.**  
화면 인식용 이미지(`assets/images/`)와 좌표는 이 해상도 기준으로 이미 포함되어 있습니다. 다른 해상도에서는 맞추지 않습니다.

---

## 세팅 (이것만)

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
```

그다음 두 가지만 맞추면 됩니다.

| 해야 할 일 | 파일 |
|------------|------|
| 계정 정보 | `user_info.example.txt` → `user_info.txt` |
| Gmail 연동 | `credentials.json` → 첫 실행 시 `token.json` 자동 생성 |

---

## 1. `user_info.txt`

`user_info.example.txt`를 복사하거나 이름을 **`user_info.txt`** 로 바꾼 뒤, 값을 수정하세요.

```powershell
copy user_info.example.txt user_info.txt
```

```text
email=qwe@gmail.com
index=10
step_gap=0.04
```

- 게임 입력: `qwe+10@gmail.com`
- 인증메일 수신: `qwe@gmail.com`
- 슬롯이 꽉 차면 `index`가 +1 → 다음엔 `qwe+11@gmail.com`
- `step_gap`: 매크로 각 스텝 직후 대기(초). 생략하면 `0.04`

`user_info.txt`는 git에 올리지 않습니다 (개인 계정 정보).

---

## 2. Gmail (`credentials.json` / `token.json`)

인증번호를 메일에서 읽으려면 Google 연동이 필요합니다.

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성  
2. **Gmail API** 사용 설정  
3. OAuth 동의 화면 설정 (테스트 사용자에 **본인 메일** 추가)  
4. OAuth 클라이언트(데스크톱) 만들어 JSON 다운로드 → 프로젝트 루트에 `credentials.json`으로 저장  

`token.json`은 **직접 만들지 않습니다.** 프로그램이 처음 메일을 읽을 때 생깁니다.

### 첫 실행은 “반자동”입니다

Gmail을 **처음** 건드리는 순간 브라우저가 열립니다.  
여기서 **본인이 직접** 같은 Gmail로 로그인한 뒤 **권한 허용**을 눌러야 합니다.

그 과정 동안 자동화는 멈추거나 타임아웃 날 수 있습니다.  
정상입니다. 동의만 끝나면 `token.json`이 생기고, **이후에는 브라우저 없이** 동작합니다.  
(액세스 토큰이 만료되면 조용히 갱신되며, 매번 동의가 필요하지는 않습니다.)

동의할 계정 = `user_info.txt`의 `email` = Cloud에 로그인한 계정 — 세 개가 같아야 합니다.

토큰이 꼬이면 `token.json`만 지우고 다시 동의하면 됩니다.

---

## 실행 & 키

```powershell
.\env\Scripts\Activate.ps1
python main.py
```

게임을 **1920×1080**으로 켜 둔 뒤 실행하세요.

| 키 | 동작 |
|----|------|
| **8** | 시작 |
| **7** | 저사양 시작 (잠금) |
| **9** | 영역 보기 ON/OFF |
| **0** | 중단 → 메뉴로 |
| **'** | 마우스 좌표 로그 |
| **Ctrl+C** | 강제 종료 |

안 되면 관리자 권한 터미널로 한 번 실행해 보세요.

---

## 막힐 때

| 증상 | 확인 |
|------|------|
| 메일을 못 읽음 | `credentials.json` / 첫 동의 / OAuth 테스트 사용자 등록 |
| 버튼을 못 찾음 | 해상도가 **1920×1080**인지, **9**로 영역 위치 |
| 앱이 확인되지 않음 | OAuth 테스트 사용자에 본인 메일 추가 |

---

## 체크

- [ ] `python -m venv env` → 활성화 → `pip install -r requirements.txt`
- [ ] `user_info.example.txt` → `user_info.txt` 로 복사/이름 변경 후 email·index 수정
- [ ] `credentials.json` 배치
- [ ] 게임 해상도 **1920×1080**
- [ ] `python main.py` → **첫 실행에서 브라우저 권한 허용** → `token.json` 확인
- [ ] 한 번 더 돌려서 자동 구간이 이어지는지 확인
