"""Gmail API — 인증번호 메일 조회."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from agent.user_info import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
# 제목 예: "977614 인증 코드를 확인하세요"
SUBJECT_CODE_RE = re.compile(r"(\d{6})\s*인증\s*코드")
GMAIL_QUERY = "newer_than:1d 인증 코드"
DEFAULT_TIMEOUT_SEC = 60.0
POLL_INTERVAL_SEC = 2.5


@dataclass(frozen=True)
class AuthMail:
    message_id: str
    code: str
    subject: str
    internal_date_ms: int


def get_gmail_service():
    """OAuth 준비된 Gmail API 서비스. 최초 실행 시 브라우저 동의 → token.json."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not GMAIL_CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(
            f"credentials.json 이 없습니다: {GMAIL_CREDENTIALS_PATH}\n"
            "README의 Gmail API 연동 절차를 확인하세요."
        )

    creds = None
    if GMAIL_TOKEN_PATH.is_file():
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("[Gmail] 토큰 갱신 중…")
            creds.refresh(Request())
        else:
            log.info("[Gmail] 브라우저에서 계정 동의가 필요합니다…")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(GMAIL_CREDENTIALS_PATH),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)
        GMAIL_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        log.info("[Gmail] token.json 저장 → %s", GMAIL_TOKEN_PATH)

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def extract_code_from_subject(subject: str) -> str | None:
    match = SUBJECT_CODE_RE.search(subject or "")
    return match.group(1) if match else None


def _header_map(payload_headers: list) -> dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in payload_headers}


def fetch_latest_auth_mails(service, *, max_results: int = 8) -> list[AuthMail]:
    """최근 인증 코드 메일 목록 (최신순)."""
    listed = (
        service.users()
        .messages()
        .list(userId="me", q=GMAIL_QUERY, maxResults=max_results)
        .execute()
    )
    out: list[AuthMail] = []
    for ref in listed.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["Subject"],
            )
            .execute()
        )
        headers = _header_map(msg.get("payload", {}).get("headers", []))
        subject = headers.get("subject", "")
        code = extract_code_from_subject(subject)
        if not code:
            continue
        out.append(
            AuthMail(
                message_id=msg["id"],
                code=code,
                subject=subject,
                internal_date_ms=int(msg.get("internalDate", 0)),
            )
        )
    out.sort(key=lambda m: m.internal_date_ms, reverse=True)
    return out


def snapshot_latest_auth_id(service) -> tuple[str | None, int]:
    """발송 직전 기준점: (message_id, internal_date_ms)."""
    mails = fetch_latest_auth_mails(service, max_results=3)
    if not mails:
        return None, 0
    return mails[0].message_id, mails[0].internal_date_ms


def wait_for_auth_code(
    *,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    not_before_ms: int = 0,
    exclude_message_id: str | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> AuthMail | None:
    """Post 클릭 이후 도착한 새 인증메일에서 6자리 코드 대기."""
    service = get_gmail_service()
    deadline = time.monotonic() + timeout_sec

    while True:
        if should_continue is not None and not should_continue():
            return None

        for mail in fetch_latest_auth_mails(service):
            if exclude_message_id and mail.message_id == exclude_message_id:
                continue
            if mail.internal_date_ms < not_before_ms:
                continue
            return mail

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            log.warning("[Gmail] 인증메일 타임아웃 (%.0fs)", timeout_sec)
            return None
        time.sleep(min(POLL_INTERVAL_SEC, remaining))
