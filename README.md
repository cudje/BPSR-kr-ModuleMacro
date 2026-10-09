# BPSR-kr-ModuleMacro

BPSR 모듈 리세마라를 위한 자동 계정 생성 및 모듈 조합 결과 저장 매크로입니다.
※게임이용약관 위반으로 발생할 수 있는 불이익에 대해 책임을 지지 않습니다.
**1920×1080** 에서만 동작합니다.

## 테스트 환경 (개발 환경이며 프로그램 동작 사양을 뜻하는게 아닙니다.)

- CPU : AMD Ryzen 5 5600X
- GPU : NVIDIA GeForce RTX 4060 Ti

매크로가 느리면 `delay_ms` 를 올립니다. `delay_ms=0` 은 이 PC 기준입니다.

## 준비

1. Python 3.11–3.14 64비트에서 `pip install -r requirements.txt`
2. [Npcap](https://npcap.com/#download) 설치.

## 3. user_info

`user_info.example.txt` 를 `user_info.txt` 로 바꾼 뒤 값을 수정합니다.

```text
email=qwe@gmail.com
index=1
step_gap=0.04
min_score=1675
server=jp
delay_ms=0
```

- `email` : 인증메일을 받을 Gmail 주소입니다. 게임에는 이 주소 뒤에 번호가 붙어 입력됩니다.
- `index` : 지금 돌릴 계정 번호입니다. `email=qwe@gmail.com`, `index=1` 이면 로그인 입력은 `qwe+1@gmail.com` 입니다. 캐릭터 슬롯이 가득 차면 `index` 가 1 올라가고, 다음은 `qwe+2@gmail.com` 으로 로그인합니다.
- `step_gap` : 매크로 각 스텝 직후 텀(초)입니다. 기본 `0.04`. `delay_ms` 와는 따로 적용됩니다.
- `min_score` : 1위 점수가 이 값 이상이면 `good_results`, 아니면 `results` 에 저장합니다. 줄을 빼면 항상 `results` 에 저장합니다.
- `server` : `kr` 은 한섭, `jp` 는 일섭입니다.
- `delay_ms` : 사양이 낮을 때 매크로 1·2의 대기마다 더하는 시간(밀리초)입니다. `100` 이면 각 대기에 0.1초가 더해집니다.

## 4. Gmail API

인증번호를 메일에서 읽으려면 Google 연동이 필요합니다. 동의하는 Gmail 은 `user_info.txt` 의 `email` 과 같아야 합니다.

1. [Google Cloud Console](https://console.cloud.google.com/) 에서 프로젝트를 만듭니다.
2. **Gmail API** 를 사용 설정합니다.
3. OAuth 동의 화면을 만들고, 테스트 사용자에 본인 Gmail 을 추가합니다.
4. OAuth 클라이언트 ID 를 **데스크톱 앱**으로 만든 뒤 JSON 을 받습니다. 프로젝트 폴더에 `credentials.json` 으로 저장합니다.

`token.json` 은 직접 만들지 않습니다. 프로그램이 처음 메일을 읽을 때 브라우저가 열립니다. 같은 Gmail 로 로그인한 뒤 권한 허용을 누르면 `token.json` 이 생깁니다. 허용하는 동안 자동화가 잠시 멈추거나 시간 초과될 수 있습니다. 허용이 끝나면 이후에는 브라우저 없이 동작하고, 토큰이 만료되면 조용히 갱신됩니다.

토큰이 꼬이면 `token.json` 만 지우고 다시 허용하면 됩니다.

## 실행

게임 및 디스플레이 해상도를 1920×1080 으로 설정한 뒤 게임을 실행합니다.
서버 선택 화면 / 로그인 대기 화면 상태에서,
관리자 권한으로 명령 프롬프트를 실행한 후 아래 명령어를 입력합니다.
```
python main.py
```

- 8 : 시작
- 9 : 영역 보기
- 0 : 중단
- ; : 패킷 검사. 15초 안에 채널을 바꾸면 조합을 저장
- ' : 마우스 좌표
- Ctrl+C : 종료

8 로 시작하면 매크로 후 조합을 저장하고 로그아웃합니다.
가능한 모듈 조합 중 가장 높은 스코어가 `min_score` 이상이면 `good_results`, 아니면 `results` 에 저장합니다.
시작한 후 사용자가 별도로 멈추지 않는 한 계속 모듈 조합 결과를 저장해 나갑니다.
