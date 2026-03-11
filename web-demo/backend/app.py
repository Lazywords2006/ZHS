from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fucker import CaptchaException, Fucker
from utils import cookie_jar_to_list

LOGIN_PAGE = (
    "https://passport.zhihuishu.com/login"
    "?service=https://onlineservice-api.zhihuishu.com/login/gologin"
)
QR_PAGE = "https://passport.zhihuishu.com/qrCodeLogin/getLoginQrImg"
QUERY_PAGE = "https://passport.zhihuishu.com/qrCodeLogin/getLoginQrInfo"
RUNTIME_DIR = Path(__file__).resolve().parent / "runtime"
ACCOUNTS_FILE = RUNTIME_DIR / "accounts.json"
LOGIN_FILE = RUNTIME_DIR / "login_data.json"
POLL_INTERVAL_SECONDS = 1.5
VERIFICATION_REQUIRED_STATUS = "verification_required"
VERIFICATION_REQUIRED_MESSAGE = "检测到智慧树要求人工验证，请先在浏览器或官方客户端完成验证后再重试。"


def parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def default_account_record(account_id: str, name: str) -> dict[str, Any]:
    return {
        "id": account_id,
        "name": name,
        "avatar": f"https://api.dicebear.com/9.x/thumbs/svg?seed={account_id}",
        "status": "offline",
        "courseProgress": 0,
        "currentCourse": "未开始",
        "useWatchLimit": False,
        "watchMinutes": 30,
        "autoRunDaily": False,
        "autoRunDays": 1,
        "autoRunUntil": "",
        "courseIds": [],
        "lastRunMessage": "",
    }


def default_login_record() -> dict[str, Any]:
    return {
        "cookies": [],
        "courseCache": [],
        "lastLoginError": "",
    }


def is_legacy_scaffold(accounts: list[dict[str, Any]]) -> bool:
    expected = ["acc-1", "acc-2", "acc-3"]
    if len(accounts) != len(expected):
        return False
    for index, account in enumerate(accounts):
        if str(account.get("id")) != expected[index]:
            return False
        if account.get("courseIds"):
            return False
        if account.get("cookies"):
            return False
        if account.get("courseCache"):
            return False
        if account.get("lastLoginError"):
            return False
        if account.get("lastRunMessage"):
            return False
        if int(account.get("courseProgress", 0)) != 0:
            return False
    return True


def is_empty_legacy_placeholder(account: dict[str, Any], login: dict[str, Any]) -> bool:
    return (
        account["id"] in {"acc-1", "acc-2", "acc-3"}
        and account["name"].startswith("本地账号 ")
        and not account.get("courseIds")
        and account.get("status") == "offline"
        and not account.get("lastRunMessage")
        and not login.get("cookies")
        and not login.get("courseCache")
        and not login.get("lastLoginError")
    )


def normalize_account(raw: dict[str, Any]) -> dict[str, Any]:
    account_id = str(raw.get("id") or f"acc-{uuid.uuid4().hex[:8]}")
    account = default_account_record(account_id, str(raw.get("name") or f"账号 {account_id[-4:]}"))
    account.update(raw or {})
    account["id"] = account_id
    account["name"] = str(account.get("name") or f"账号 {account_id[-4:]}")
    account["avatar"] = str(account.get("avatar") or f"https://api.dicebear.com/9.x/thumbs/svg?seed={account_id}")
    account["useWatchLimit"] = bool(account.get("useWatchLimit", False))
    account["watchMinutes"] = max(1, int(account.get("watchMinutes", 30)))
    account["autoRunDaily"] = bool(account.get("autoRunDaily", False))
    account["autoRunDays"] = max(1, min(int(account.get("autoRunDays", 1)), 365))
    account["autoRunUntil"] = str(account.get("autoRunUntil") or "")
    if account["autoRunDaily"] and not account["autoRunUntil"]:
        account["autoRunUntil"] = compute_auto_run_until(account["autoRunDays"])
    if not account["autoRunDaily"]:
        account["autoRunUntil"] = ""
    account["courseProgress"] = int(account.get("courseProgress", 0))
    raw_status = str(account.get("status") or "offline")
    allowed_statuses = {"online", "offline", "running", VERIFICATION_REQUIRED_STATUS}
    account["status"] = raw_status if raw_status in allowed_statuses else "offline"
    account["courseIds"] = [str(item) for item in account.get("courseIds", [])]
    account["currentCourse"] = str(account.get("currentCourse") or "未开始")
    account["lastRunMessage"] = str(account.get("lastRunMessage") or "")
    account.pop("cookies", None)
    account.pop("courseCache", None)
    account.pop("lastLoginError", None)
    return account


def normalize_login_record(raw: dict[str, Any] | None) -> dict[str, Any]:
    login = default_login_record()
    raw = raw or {}
    login["cookies"] = raw.get("cookies", login["cookies"])
    login["courseCache"] = raw.get("courseCache", login["courseCache"])
    login["lastLoginError"] = raw.get("lastLoginError", login["lastLoginError"])
    login["courseCache"] = [
        {"id": str(item["id"]), "name": str(item["name"])}
        for item in login.get("courseCache", [])
        if isinstance(item, dict) and "id" in item and "name" in item
    ]
    login["cookies"] = list(login.get("cookies", []))
    login["lastLoginError"] = str(login.get("lastLoginError") or "")
    return login


def derive_current_course(account: dict[str, Any]) -> str:
    selected = set(account.get("courseIds", []))
    courses = account.get("courseCache", [])
    for course in courses:
        if course["id"] in selected:
            return course["name"]
    if courses:
        return courses[0]["name"]
    return "未开始"


def is_verification_required_error(error: Exception | str) -> bool:
    if isinstance(error, CaptchaException):
        return True
    message = str(error).lower()
    keywords = [
        "captcha",
        "requires captcha",
        "验证码",
        "安全验证",
        "验证短信",
        "人工验证",
    ]
    return any(keyword in message for keyword in keywords)


def verification_required_message(error: Exception | str) -> str:
    detail = str(error).strip()
    if not detail:
        return VERIFICATION_REQUIRED_MESSAGE
    return f"{VERIFICATION_REQUIRED_MESSAGE} 原因：{detail}"


def compute_auto_run_until(days: int) -> str:
    offset = max(int(days) - 1, 0)
    return (datetime.now().date() + timedelta(days=offset)).isoformat()


class AccountConfigPayload(BaseModel):
    courseIds: list[str] = Field(default_factory=list)
    useWatchLimit: bool = False
    watchMinutes: int = Field(default=30, ge=1, le=180)
    autoRunDaily: bool = False
    autoRunDays: int = Field(default=1, ge=1, le=365)


class CreateAccountPayload(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class StateStore:
    def __init__(self, accounts_path: Path, login_path: Path):
        self.accounts_path = accounts_path
        self.login_path = login_path
        self.lock = threading.RLock()
        self.accounts_state, self.login_state = self._load()

    def _load(self) -> tuple[dict[str, Any], dict[str, Any]]:
        self.accounts_path.parent.mkdir(parents=True, exist_ok=True)
        raw_accounts = []
        extracted_login: dict[str, Any] = {}

        if self.accounts_path.exists():
            raw = json.loads(self.accounts_path.read_text("utf-8") or "{}")
            raw_accounts = raw.get("accounts", [])
            if raw_accounts and not self.login_path.exists():
                for account in raw_accounts:
                    account_id = str(account.get("id") or "")
                    if not account_id:
                        continue
                    extracted_login[account_id] = normalize_login_record(account)

        if raw_accounts and is_legacy_scaffold(raw_accounts) and not any(
            record.get("cookies") or record.get("courseCache")
            for record in extracted_login.values()
        ):
            raw_accounts = []

        if self.login_path.exists():
            raw_login = json.loads(self.login_path.read_text("utf-8") or "{}")
            raw_login_accounts = raw_login.get("accounts", {})
        else:
            raw_login_accounts = extracted_login

        normalized_accounts = [normalize_account(account) for account in raw_accounts]
        login_accounts = {}
        accounts = []
        for account in normalized_accounts:
            login = normalize_login_record(raw_login_accounts.get(account["id"]))
            if is_empty_legacy_placeholder(account, login):
                continue
            accounts.append(account)
            login_accounts[account["id"]] = login

        accounts_state = {"accounts": accounts}

        login_state = {"accounts": login_accounts}
        self._write_accounts_unlocked(accounts_state)
        self._write_logins_unlocked(login_state)
        return accounts_state, login_state

    def _write_accounts_unlocked(self, state: dict[str, Any] | None = None) -> None:
        payload = state or self.accounts_state
        self.accounts_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _write_logins_unlocked(self, state: dict[str, Any] | None = None) -> None:
        payload = state or self.login_state
        self.login_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _find_account_unlocked(self, account_id: str) -> dict[str, Any]:
        for account in self.accounts_state["accounts"]:
            if account["id"] == account_id:
                return account
        raise KeyError(account_id)

    def _find_login_unlocked(self, account_id: str) -> dict[str, Any]:
        accounts = self.login_state["accounts"]
        if account_id not in accounts:
            accounts[account_id] = default_login_record()
        return accounts[account_id]

    def _merged_account_unlocked(self, account_id: str) -> dict[str, Any]:
        account = deepcopy(self._find_account_unlocked(account_id))
        login = deepcopy(self._find_login_unlocked(account_id))
        account.update(login)
        return account

    def _serialize_unlocked(self, account_id: str) -> dict[str, Any]:
        merged = self._merged_account_unlocked(account_id)
        clean = {k: v for k, v in merged.items() if k not in {"cookies", "courseCache"}}
        clean["currentCourse"] = str(merged.get("currentCourse") or derive_current_course(merged))
        clean["hasSavedLogin"] = bool(merged.get("cookies"))
        return clean

    def list_accounts(self) -> list[dict[str, Any]]:
        with self.lock:
            return [self._serialize_unlocked(account["id"]) for account in self.accounts_state["accounts"]]

    def get_account(self, account_id: str) -> dict[str, Any]:
        with self.lock:
            return deepcopy(self._merged_account_unlocked(account_id))

    def create_account(self, name: str) -> dict[str, Any]:
        with self.lock:
            account_id = f"acc-{uuid.uuid4().hex[:8]}"
            clean_name = name.strip() or f"账号 {len(self.accounts_state['accounts']) + 1}"
            account = default_account_record(account_id, clean_name)
            self.accounts_state["accounts"].append(account)
            self.login_state["accounts"][account_id] = default_login_record()
            self._write_accounts_unlocked()
            self._write_logins_unlocked()
            return self._serialize_unlocked(account_id)

    def delete_account(self, account_id: str) -> None:
        with self.lock:
            self._find_account_unlocked(account_id)
            self.accounts_state["accounts"] = [
                account
                for account in self.accounts_state["accounts"]
                if account["id"] != account_id
            ]
            self.login_state["accounts"].pop(account_id, None)
            self._write_accounts_unlocked()
            self._write_logins_unlocked()

    def update_account_config(self, account_id: str, payload: AccountConfigPayload) -> dict[str, Any]:
        with self.lock:
            account = self._find_account_unlocked(account_id)
            account["courseIds"] = [str(item) for item in payload.courseIds]
            account["useWatchLimit"] = payload.useWatchLimit
            account["watchMinutes"] = payload.watchMinutes
            account["autoRunDaily"] = payload.autoRunDaily
            account["autoRunDays"] = payload.autoRunDays
            account["autoRunUntil"] = compute_auto_run_until(payload.autoRunDays) if payload.autoRunDaily else ""
            merged = self._merged_account_unlocked(account_id)
            account["currentCourse"] = derive_current_course(merged)
            self._write_accounts_unlocked()
            return self._serialize_unlocked(account_id)

    def get_cached_courses(self, account_id: str) -> list[dict[str, str]]:
        with self.lock:
            login = self._find_login_unlocked(account_id)
            return deepcopy(login.get("courseCache", []))

    def save_courses(self, account_id: str, courses: list[dict[str, str]]) -> None:
        with self.lock:
            login = self._find_login_unlocked(account_id)
            login["courseCache"] = courses
            account = self._find_account_unlocked(account_id)
            if account.get("status") != "running":
                merged = self._merged_account_unlocked(account_id)
                account["currentCourse"] = derive_current_course(merged)
            self._write_accounts_unlocked()
            self._write_logins_unlocked()

    def refresh_persisted_login(
        self,
        account_id: str,
        *,
        cookies: list[dict[str, Any]] | None = None,
        courses: list[dict[str, str]] | None = None,
        status: str | None = None,
        last_run_message: str | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            login = self._find_login_unlocked(account_id)
            if cookies is not None:
                login["cookies"] = cookies
            if courses is not None:
                login["courseCache"] = courses
            login["lastLoginError"] = ""

            account = self._find_account_unlocked(account_id)
            if status is not None and account.get("status") != "running":
                account["status"] = status

            merged = self._merged_account_unlocked(account_id)
            if account.get("status") != "running":
                account["currentCourse"] = derive_current_course(merged)
            if last_run_message is not None:
                account["lastRunMessage"] = str(last_run_message)

            self._write_accounts_unlocked()
            self._write_logins_unlocked()
            return self._serialize_unlocked(account_id)

    def save_login_success(self, account_id: str, cookies: list[dict[str, Any]], courses: list[dict[str, str]]) -> None:
        self.refresh_persisted_login(
            account_id,
            cookies=cookies,
            courses=courses,
            status="online",
            last_run_message="登录成功，可开始刷课",
        )

    def save_login_error(self, account_id: str, message: str) -> None:
        with self.lock:
            login = self._find_login_unlocked(account_id)
            login["lastLoginError"] = message
            account = self._find_account_unlocked(account_id)
            account["status"] = "offline"
            account["lastRunMessage"] = ""
            self._write_accounts_unlocked()
            self._write_logins_unlocked()

    def save_verification_required(self, account_id: str, message: str) -> None:
        with self.lock:
            account = self._find_account_unlocked(account_id)
            account["status"] = VERIFICATION_REQUIRED_STATUS
            account["lastRunMessage"] = str(message or VERIFICATION_REQUIRED_MESSAGE)
            self._write_accounts_unlocked()

    def save_offline(self, account_id: str) -> None:
        with self.lock:
            account = self._find_account_unlocked(account_id)
            account["status"] = "offline"
            self._write_accounts_unlocked()

    def update_runtime(
        self,
        account_id: str,
        *,
        status: str | None = None,
        course_progress: int | None = None,
        current_course: str | None = None,
        last_run_message: str | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            account = self._find_account_unlocked(account_id)
            if status is not None:
                account["status"] = status
            if course_progress is not None:
                account["courseProgress"] = max(0, min(int(course_progress), 100))
            if current_course is not None:
                account["currentCourse"] = str(current_course or "未开始")
            if last_run_message is not None:
                account["lastRunMessage"] = str(last_run_message)
            self._write_accounts_unlocked()
            return self._serialize_unlocked(account_id)


def build_fucker_for_account(account: dict[str, Any]) -> Fucker:
    limit = account.get("watchMinutes", 30) if account.get("useWatchLimit") else 0
    fucker = Fucker(limit=limit)
    cookies = account.get("cookies", [])
    if cookies:
        fucker.cookies = cookies
    return fucker


def map_courses(fucker: Fucker) -> list[dict[str, str]]:
    courses: list[dict[str, str]] = []
    seen: set[str] = set()

    for course in fucker.getZhidaoList():
        cid = str(course.get("secret"))
        name = str(course.get("courseName") or course.get("name") or cid)
        if cid and cid not in seen:
            seen.add(cid)
            courses.append({"id": cid, "name": name})

    for course in fucker.getHikeList():
        cid = str(course.get("courseId"))
        name = str(course.get("courseName") or course.get("name") or cid)
        if cid and cid not in seen:
            seen.add(cid)
            courses.append({"id": cid, "name": name})

    return courses


def fetch_courses_for_account(account: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    if not account.get("cookies"):
        return account.get("courseCache", []), account.get("cookies", [])
    fucker = build_fucker_for_account(account)
    courses = map_courses(fucker)
    refreshed_cookies = cookie_jar_to_list(fucker.session.cookies.copy())
    return courses, refreshed_cookies


def restore_account_session(store: StateStore, account_id: str) -> None:
    try:
        account = store.get_account(account_id)
    except KeyError:
        return

    if not account.get("cookies"):
        return

    try:
        courses, refreshed_cookies = fetch_courses_for_account(account)
    except Exception as exc:
        if is_verification_required_error(exc):
            store.save_verification_required(account_id, verification_required_message(exc))
        else:
            store.save_offline(account_id)
        return

    store.refresh_persisted_login(
        account_id,
        cookies=refreshed_cookies,
        courses=courses,
        status="online",
        last_run_message="已恢复本地保存的登录态",
    )


def restore_saved_sessions(store: StateStore) -> None:
    for account in store.list_accounts():
        if account.get("hasSavedLogin"):
            restore_account_session(store, str(account["id"]))


@dataclass
class PendingQrLogin:
    session_id: str
    account_id: str
    qr_token: str
    image_data_url: str
    expires_at: float
    fucker: Fucker
    status: str = "pending"
    message: str = "等待扫码"


class QrLoginManager:
    def __init__(self, store: StateStore):
        self.store = store
        self.lock = threading.RLock()
        self.sessions: dict[str, PendingQrLogin] = {}
        self.current_by_account: dict[str, str] = {}

    def start(self, account_id: str) -> dict[str, Any]:
        account = self.store.get_account(account_id)
        limit = account.get("watchMinutes", 30) if account.get("useWatchLimit") else 0
        fucker = Fucker(limit=limit)
        fucker._sessionReady()
        response = fucker.session.get(QR_PAGE, timeout=10).json()
        qr_token = response["qrToken"]
        image_data_url = f"data:image/png;base64,{response['img']}"
        session_id = uuid.uuid4().hex
        pending = PendingQrLogin(
            session_id=session_id,
            account_id=account_id,
            qr_token=qr_token,
            image_data_url=image_data_url,
            expires_at=time.time() + 120,
            fucker=fucker,
        )
        with self.lock:
            self.sessions[session_id] = pending
            self.current_by_account[account_id] = session_id

        thread = threading.Thread(target=self._poll, args=(pending,), daemon=True)
        thread.start()
        return {
            "token": session_id,
            "expiresIn": 120,
            "imageDataUrl": image_data_url,
            "status": pending.status,
        }

    def _is_current(self, account_id: str, session_id: str) -> bool:
        with self.lock:
            return self.current_by_account.get(account_id) == session_id

    def _update_status(self, session_id: str, status: str, message: str) -> None:
        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                return
            session.status = status
            session.message = message

    def _poll(self, pending: PendingQrLogin) -> None:
        while True:
            if not self._is_current(pending.account_id, pending.session_id):
                self._update_status(pending.session_id, "cancelled", "二维码已刷新")
                return
            if time.time() >= pending.expires_at:
                self._update_status(pending.session_id, "expired", "二维码已过期")
                return

            try:
                payload = pending.fucker.session.get(
                    QUERY_PAGE,
                    params={"qrToken": pending.qr_token},
                    timeout=10,
                ).json()
                status = payload.get("status")
                message = str(payload.get("msg") or "")
                if status == -1:
                    self._update_status(pending.session_id, "pending", "等待扫码")
                elif status == 0:
                    self._update_status(pending.session_id, "scanned", "已扫码，请在手机上确认")
                elif status == 1:
                    if not self._is_current(pending.account_id, pending.session_id):
                        self._update_status(pending.session_id, "cancelled", "二维码已刷新")
                        return
                    pending.fucker.session.get(
                        LOGIN_PAGE,
                        params={"pwd": payload["oncePassword"]},
                        proxies=pending.fucker.proxies,
                        timeout=10,
                    )
                    pending.fucker.cookies = pending.fucker.session.cookies.copy()
                    cookies = cookie_jar_to_list(pending.fucker.cookies)
                    courses = map_courses(pending.fucker)
                    self.store.save_login_success(pending.account_id, cookies, courses)
                    self._update_status(pending.session_id, "confirmed", "登录成功")
                    return
                elif status == 2:
                    self._update_status(pending.session_id, "expired", message or "二维码已过期")
                    return
                elif status == 3:
                    self._update_status(pending.session_id, "cancelled", message or "登录已取消")
                    return
                else:
                    self.store.save_login_error(pending.account_id, message or "未知登录状态")
                    self._update_status(pending.session_id, "error", message or "未知登录状态")
                    return
            except Exception as exc:
                if is_verification_required_error(exc):
                    self.store.save_verification_required(
                        pending.account_id,
                        verification_required_message(exc),
                    )
                else:
                    self.store.save_login_error(pending.account_id, str(exc))
                self._update_status(pending.session_id, "error", str(exc))
                return

            time.sleep(POLL_INTERVAL_SECONDS)

    def status(self, account_id: str, session_id: str) -> dict[str, str]:
        with self.lock:
            session = self.sessions.get(session_id)
            if not session or session.account_id != account_id:
                raise KeyError(session_id)
            return {"status": session.status, "message": session.message}

    def cancel_account(self, account_id: str) -> None:
        with self.lock:
            current_session_id = self.current_by_account.pop(account_id, None)
            if current_session_id and current_session_id in self.sessions:
                self.sessions[current_session_id].status = "cancelled"
                self.sessions[current_session_id].message = "账号已删除"


@dataclass
class RunTask:
    task_id: str
    account_id: str
    course_ids: list[str]
    stop_requested: bool = False
    thread: threading.Thread | None = None


class RunManager:
    def __init__(self, store: StateStore):
        self.store = store
        self.lock = threading.RLock()
        self.tasks: dict[str, RunTask] = {}

    def start(self, account_id: str) -> dict[str, str]:
        account = self.store.get_account(account_id)
        if not account.get("cookies"):
            raise ValueError("请先扫码登录")
        course_ids = [str(item) for item in account.get("courseIds", [])]
        if not course_ids:
            raise ValueError("请先选择至少一门课程")

        with self.lock:
            current = self.tasks.get(account_id)
            if current and current.thread and current.thread.is_alive():
                raise RuntimeError("该账号已有运行中的任务")
            task = RunTask(
                task_id=uuid.uuid4().hex,
                account_id=account_id,
                course_ids=course_ids,
            )
            first_course = next(
                (
                    str(course["name"])
                    for course in account.get("courseCache", [])
                    if isinstance(course, dict) and str(course.get("id")) == course_ids[0]
                ),
                course_ids[0],
            )
            self.store.update_runtime(
                account_id,
                status="running",
                course_progress=0,
                current_course=first_course,
                last_run_message=f"任务已启动，共 {len(course_ids)} 门课",
            )
            thread = threading.Thread(target=self._run, args=(task,), daemon=True)
            task.thread = thread
            self.tasks[account_id] = task
            thread.start()

        return {"status": "running", "message": "刷课任务已启动"}

    def stop(self, account_id: str) -> dict[str, str]:
        with self.lock:
            task = self.tasks.get(account_id)
            if not task or not task.thread or not task.thread.is_alive():
                raise KeyError(account_id)
            task.stop_requested = True

        self.store.update_runtime(
            account_id,
            last_run_message="已请求停止，当前课程结束后生效",
        )
        return {"status": "stopping", "message": "停止请求已提交"}

    def ensure_not_running(self, account_id: str) -> None:
        with self.lock:
            task = self.tasks.get(account_id)
            if task and task.thread and task.thread.is_alive():
                raise RuntimeError("请先停止该账号的刷课任务，再删除账号")

    def _clear(self, account_id: str, task_id: str) -> None:
        with self.lock:
            current = self.tasks.get(account_id)
            if current and current.task_id == task_id:
                self.tasks.pop(account_id, None)

    def _run(self, task: RunTask) -> None:
        account = self.store.get_account(task.account_id)
        course_names = {
            str(course["id"]): str(course["name"])
            for course in account.get("courseCache", [])
            if isinstance(course, dict) and "id" in course and "name" in course
        }
        total = len(task.course_ids)
        errors: list[str] = []
        fucker: Fucker | None = None

        try:
            fucker = build_fucker_for_account(account)
            fucker.limit = account.get("watchMinutes", 30) if account.get("useWatchLimit") else 0
            self.store.update_runtime(
                task.account_id,
                status="running",
                course_progress=0,
                current_course=course_names.get(task.course_ids[0], task.course_ids[0]),
                last_run_message=f"任务已启动，共 {total} 门课",
            )

            for index, course_id in enumerate(task.course_ids, start=1):
                if task.stop_requested:
                    completed = index - 1
                    self.store.update_runtime(
                        task.account_id,
                        status="online",
                        course_progress=int(completed * 100 / total),
                        current_course=derive_current_course(self.store.get_account(task.account_id)),
                        last_run_message=f"已停止，完成 {completed}/{total} 门课",
                    )
                    return

                course_name = course_names.get(course_id, course_id)
                self.store.update_runtime(
                    task.account_id,
                    status="running",
                    course_progress=int((index - 1) * 100 / total),
                    current_course=course_name,
                    last_run_message=f"正在刷第 {index}/{total} 门课",
                )
                try:
                    fucker.fuckCourse(course_id=course_id, tree_view=False)
                except Exception as exc:
                    if is_verification_required_error(exc):
                        self.store.update_runtime(
                            task.account_id,
                            status=VERIFICATION_REQUIRED_STATUS,
                            current_course=course_name,
                            last_run_message=verification_required_message(exc),
                        )
                        return
                    errors.append(f"{course_name}: {exc}")
                    self.store.update_runtime(
                        task.account_id,
                        status="running",
                        current_course=course_name,
                        last_run_message=f"{course_name} 执行失败，继续下一门",
                    )
                else:
                    self.store.update_runtime(
                        task.account_id,
                        status="running",
                        course_progress=int(index * 100 / total),
                        current_course=course_name,
                        last_run_message=f"已完成 {index}/{total} 门课",
                    )

            final_message = "任务完成"
            if errors:
                final_message = f"任务完成，但有 {len(errors)} 门课失败"
            self.store.update_runtime(
                task.account_id,
                status="online",
                course_progress=100,
                current_course=derive_current_course(self.store.get_account(task.account_id)),
                last_run_message=final_message,
            )
        except Exception as exc:
            if is_verification_required_error(exc):
                self.store.update_runtime(
                    task.account_id,
                    status=VERIFICATION_REQUIRED_STATUS,
                    current_course=derive_current_course(self.store.get_account(task.account_id)),
                    last_run_message=verification_required_message(exc),
                )
            else:
                self.store.update_runtime(
                    task.account_id,
                    status="online",
                    current_course=derive_current_course(self.store.get_account(task.account_id)),
                    last_run_message=f"任务失败: {exc}",
                )
        finally:
            if fucker is not None:
                try:
                    refreshed_cookies = cookie_jar_to_list(fucker.session.cookies.copy())
                    if refreshed_cookies:
                        self.store.refresh_persisted_login(
                            task.account_id,
                            cookies=refreshed_cookies,
                            courses=self.store.get_cached_courses(task.account_id),
                        )
                except Exception:
                    pass
            self._clear(task.account_id, task.task_id)


store = StateStore(ACCOUNTS_FILE, LOGIN_FILE)
qr_manager = QrLoginManager(store)
run_manager = RunManager(store)

app = FastAPI(title="fuckZHS web-demo backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_csv_env(
        "CORS_ALLOW_ORIGINS",
        ["http://127.0.0.1:5173", "http://localhost:5173"],
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def restore_sessions_on_startup() -> None:
    thread = threading.Thread(target=restore_saved_sessions, args=(store,), daemon=True)
    thread.start()


@app.get("/api/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "accounts": len(store.list_accounts()),
        "time": int(time.time()),
    }


@app.get("/api/accounts")
def get_accounts() -> list[dict[str, Any]]:
    return store.list_accounts()


@app.post("/api/accounts")
def create_account(payload: CreateAccountPayload) -> dict[str, Any]:
    return store.create_account(payload.name)


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str) -> dict[str, str]:
    try:
        run_manager.ensure_not_running(account_id)
        qr_manager.cancel_account(account_id)
        store.delete_account(account_id)
        return {"status": "deleted", "message": "账号已删除"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="账号不存在") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/courses")
def get_courses(accountId: str = Query(..., min_length=1)) -> list[dict[str, str]]:
    try:
        account = store.get_account(accountId)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="账号不存在") from exc

    try:
        courses, refreshed_cookies = fetch_courses_for_account(account)
    except Exception as exc:
        if is_verification_required_error(exc):
            store.save_verification_required(accountId, verification_required_message(exc))
            cached = store.get_cached_courses(accountId)
            if cached:
                return cached
            raise HTTPException(status_code=409, detail=verification_required_message(exc)) from exc
        store.save_offline(accountId)
        cached = store.get_cached_courses(accountId)
        if cached:
            return cached
        raise HTTPException(status_code=502, detail=f"课程拉取失败: {exc}") from exc

    store.refresh_persisted_login(
        accountId,
        cookies=refreshed_cookies,
        courses=courses,
        status="online",
    )
    return courses


@app.post("/api/accounts/{account_id}/config")
def save_account_config(account_id: str, payload: AccountConfigPayload) -> dict[str, Any]:
    try:
        return store.update_account_config(account_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="账号不存在") from exc


@app.post("/api/accounts/{account_id}/login/qr")
def fetch_qr_code(account_id: str) -> dict[str, Any]:
    try:
        store.get_account(account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="账号不存在") from exc
    try:
        return qr_manager.start(account_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"二维码获取失败: {exc}") from exc


@app.post("/api/accounts/{account_id}/login/qr/refresh")
def refresh_qr_code(account_id: str) -> dict[str, Any]:
    return fetch_qr_code(account_id)


@app.get("/api/accounts/{account_id}/login/qr/status")
def get_qr_status(account_id: str, token: str = Query(..., min_length=1)) -> dict[str, str]:
    try:
        return qr_manager.status(account_id, token)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="二维码会话不存在") from exc


@app.post("/api/accounts/{account_id}/run/start")
def start_run(account_id: str) -> dict[str, str]:
    try:
        return run_manager.start(account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="账号不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/accounts/{account_id}/run/stop")
def stop_run(account_id: str) -> dict[str, str]:
    try:
        return run_manager.stop(account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="当前没有运行中的任务") from exc
