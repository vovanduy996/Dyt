"""Aster AI Desktop - CustomTkinter Modern UI Edition with Vision (Image Attach) & Auto-Updater."""
import base64
import ctypes
import json
import os
import queue
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes

import customtkinter as ctk
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, filedialog

# --------------------------------------------------------------------------- #
# Hằng số & Cấu hình Theme
# --------------------------------------------------------------------------- #
APP_VERSION = "1.2.0"
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/aster-ai/releases/main/version.json"

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AsterAI")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
CHATS_PATH = os.path.join(APP_DIR, "chats.dat")
MCP_CONFIG_PATH = os.path.join(APP_DIR, "mcp_config.json")

DEFAULT_URL = "https://openrouter.ai/api"
DEFAULT_MODEL = "google/gemini-2.0-flash-lite-001:free"
NEW_CHAT_TITLE = "Cuộc trò chuyện mới"
FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"

MAX_REQUEST_MESSAGES = 16
MAX_REQUEST_CHARS = 24000

# Palette Màu Sắc Cyber Midnight / Electric Indigo
COLOR_BG = "#0b0e17"
COLOR_SIDEBAR = "#111625"
COLOR_PANEL = "#171d2e"
COLOR_PANEL_HOVER = "#21283d"
COLOR_LINE = "#20273b"
COLOR_ACCENT = "#6366f1"
COLOR_ACCENT_HOVER = "#818cf8"
COLOR_USER_BUBBLE = "#4f46e5"
COLOR_ASSIST_BUBBLE = "#181e2d"
COLOR_ASSIST_BORDER = "#28324a"
COLOR_CODE_BG = "#0d1117"
COLOR_CODE_HEADER = "#161b22"
COLOR_MODEL_BG = "#2a1b4e"
COLOR_MODEL_BORDER = "#6b21a8"
COLOR_MODEL_TEXT = "#e9d5ff"
COLOR_TEXT = "#f8fafc"
COLOR_MUTED = "#94a3b8"
COLOR_GREEN = "#10b981"
COLOR_ERROR = "#f43f5e"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def alive(widget):
    try:
        return widget is not None and bool(widget.winfo_exists())
    except tk.TclError:
        return False


# --------------------------------------------------------------------------- #
# Auto-Updater System
# --------------------------------------------------------------------------- #
def parse_version(v_str):
    try:
        return tuple(int(x) for x in re.findall(r"\d+", str(v_str)))
    except Exception:
        return (0, 0, 0)


def check_remote_update(current_version, check_url=UPDATE_CHECK_URL):
    try:
        req = urllib.request.Request(check_url, headers={"User-Agent": "AsterAI-Updater"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        remote_ver = data.get("version") or "0.0.0"
        if parse_version(remote_ver) > parse_version(current_version):
            return {
                "has_update": True,
                "version": remote_ver,
                "download_url": data.get("download_url"),
                "changelog": data.get("changelog") or "Cập nhật hiệu năng và bổ sung tính năng mới."
            }
    except Exception:
        pass
    return {"has_update": False}


def apply_exe_update(download_url, progress_callback=None):
    import sys, tempfile, subprocess
    try:
        current_exe = sys.executable
        temp_dir = tempfile.gettempdir()
        new_exe_path = os.path.join(temp_dir, "Aster-AI-Desktop-New.exe")
        bat_script_path = os.path.join(temp_dir, "aster_updater.bat")

        req = urllib.request.Request(download_url, headers={"User-Agent": "AsterAI-Updater"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024
            with open(new_exe_path, "wb") as out_file:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded / total_size)

        bat_content = f"""@echo off
timeout /t 1 /nobreak > NUL
copy /Y "{new_exe_path}" "{current_exe}"
start "" "{current_exe}"
del "{new_exe_path}"
del "%~f0"
"""
        with open(bat_script_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(["cmd.exe", "/c", bat_script_path], startupinfo=startupinfo)
        os._exit(0)
    except Exception as e:
        raise Exception(f"Không thể thực thi cập nhật: {e}")


# --------------------------------------------------------------------------- #
# Windows: DPI, DPAPI & Titlebar Tối
# --------------------------------------------------------------------------- #
def enable_dpi():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AsterAI.Desktop")
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def dark_titlebar(win):
    try:
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        for attr in (20, 19):
            val = ctypes.c_int(1)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except Exception:
        pass


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data, protect_mode):
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    src = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    dst = _Blob()
    if protect_mode:
        ok = crypt32.CryptProtectData(ctypes.byref(src), "AsterAI", None, None, None, 0, ctypes.byref(dst))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst))
    if not ok:
        raise OSError("DPAPI không khả dụng")
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        kernel32.LocalFree(dst.pbData)


def protect(data):
    return _dpapi(data, True)


def unprotect(data):
    return _dpapi(data, False)


# --------------------------------------------------------------------------- #
# Lưu trữ Cấu hình & Lịch sử
# --------------------------------------------------------------------------- #
def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config):
    try:
        _atomic_write(CONFIG_PATH, json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8"))
    except OSError:
        pass


def load_chats():
    try:
        with open(CHATS_PATH, "rb") as f:
            data = json.loads(unprotect(f.read()).decode("utf-8"))
    except Exception:
        return []
    chats = []
    if isinstance(data, list):
        for c in data:
            if not isinstance(c, dict) or not isinstance(c.get("messages"), list):
                continue
            msgs = []
            for m in c["messages"]:
                if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
                    continue
                content = m.get("content")
                if (isinstance(content, str) and content) or (isinstance(content, list) and content):
                    msgs.append({"role": m["role"], "content": content})
            if msgs:
                chats.append({"title": str(c.get("title") or NEW_CHAT_TITLE)[:60], "messages": msgs})
    return chats


def save_chats(chats):
    try:
        data = [c for c in chats if c["messages"]][:200]
        _atomic_write(CHATS_PATH, protect(json.dumps(data, ensure_ascii=False).encode("utf-8")))
    except Exception:
        pass


def request_history(messages):
    selected, total = [], 0
    for message in reversed(messages):
        content = message.get("content") if isinstance(message, dict) else None
        role = message.get("role") if isinstance(message, dict) else None
        if role not in ("user", "assistant") or not content:
            continue
        if isinstance(content, list):
            text_part = next((item.get("text") for item in content if isinstance(item, dict) and item.get("type") == "text"), "")
            cost = len(text_part)
            if selected and (len(selected) >= MAX_REQUEST_MESSAGES or total + cost > MAX_REQUEST_CHARS):
                break
            selected.append({"role": role, "content": content})
            total += cost
        else:
            cost = len(content)
            if selected and (len(selected) >= MAX_REQUEST_MESSAGES or total + cost > MAX_REQUEST_CHARS):
                break
            selected.append({"role": role, "content": content})
            total += cost
    return list(reversed(selected))


# --------------------------------------------------------------------------- #
# MCP (Model Context Protocol) & Local MCP Servers Manager
# --------------------------------------------------------------------------- #
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Đọc nội dung của một file văn bản từ đĩa cứng.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Đường dẫn tuyệt đối hoặc tương đối tới file cần đọc"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Tạo mới hoặc ghi nội dung văn bản vào một file trên đĩa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Đường dẫn file cần tạo/ghi"},
                    "content": {"type": "string", "description": "Nội dung cần ghi vào file"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Liệt kê các file và thư mục trong một đường dẫn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Đường dẫn thư mục (mặc định là thư mục hiện tại '.')"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_web",
            "description": "Tải và đọc nội dung văn bản từ một địa chỉ trang web (URL).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Đường dẫn URL trang web"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Thực thi một lệnh PowerShell / Terminal trên máy tính.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Lệnh PowerShell cần chạy"}
                },
                "required": ["command"]
            }
        }
    }
]


def execute_mcp_tool(name, args):
    try:
        if name == "read_file":
            path = args.get("path")
            if not path or not os.path.exists(path):
                return f"Lỗi: File '{path}' không tồn tại."
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(12000)
            return f"Nội dung file '{path}':\n{content}"

        elif name == "write_file":
            path = args.get("path")
            content = args.get("content", "")
            if not path:
                return "Lỗi: Chưa cung cấp đường dẫn file."
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Đã ghi thành công vào file '{path}' ({len(content)} ký tự)."

        elif name == "list_directory":
            path = args.get("path") or "."
            if not os.path.exists(path):
                return f"Lỗi: Thư mục '{path}' không tồn tại."
            items = os.listdir(path)[:100]
            result = []
            for item in items:
                full = os.path.join(path, item)
                is_dir = os.path.isdir(full)
                result.append(f"[{'DIR' if is_dir else 'FILE'}] {item}")
            return f"Danh sách file/thư mục tại '{path}':\n" + "\n".join(result)

        elif name == "fetch_web":
            url = args.get("url")
            if not url or "://" not in url:
                url = "https://" + (url or "")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                text = re.sub(r"<script[\s\S]*?</script>", "", html)
                text = re.sub(r"<style[\s\S]*?</style>", "", text)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                return f"Nội dung trang web '{url}':\n{text[:8000]}"

        elif name == "run_command":
            cmd = args.get("command")
            if not cmd:
                return "Lỗi: Lệnh trống."
            import subprocess
            res = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=15)
            output = (res.stdout or res.stderr or "Đã thực thi thành công.").strip()
            return f"Kết quả lệnh '{cmd}':\n{output[:4000]}"

        return f"Lỗi: Không tìm thấy tool '{name}'."
    except Exception as ex:
        return f"Lỗi thực thi tool '{name}': {ex}"


def load_mcp_config():
    if not os.path.exists(MCP_CONFIG_PATH):
        default_cfg = {
            "mcpServers": {
                "houdini": {
                    "command": "python",
                    "args": ["D:\\scripts\\mcp_bridge.py"]
                },
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "D:\\"]
                }
            }
        }
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            with open(MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default_cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return default_cfg
    try:
        with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"mcpServers": {}}


def save_mcp_config(cfg):
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


class ExternalMCPServer:
    """Quản lý một subprocess MCP Server giao tiếp bằng stdio JSON-RPC 2.0."""

    def __init__(self, name, command, args):
        self.name = name
        self.command = command
        self.args = args or []
        self.process = None
        self.status = "Stopped"
        self.tools = []
        self.req_id = 1
        self.lock = threading.Lock()

    def start(self):
        import subprocess, shutil
        try:
            cmd_path = shutil.which(self.command)
            if not cmd_path:
                self.status = f"Stopped (Chưa cài {self.command})"
                return False

            full_cmd = [cmd_path] + self.args
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                startupinfo=startupinfo
            )

            init_res = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "AsterAI", "version": "1.0"}
            })
            if not init_res or "error" in init_res:
                self.status = "Error: Handshake"
                return False

            self._send_notification("notifications/initialized", {})

            tools_res = self._send_request("tools/list", {})
            if tools_res and "result" in tools_res:
                raw_tools = tools_res["result"].get("tools") or []
                self.tools = []
                for t in raw_tools:
                    openai_tool = {
                        "type": "function",
                        "function": {
                            "name": f"mcp__{self.name}__{t['name']}",
                            "description": f"[{self.name}] {t.get('description', '')}",
                            "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}
                        }
                    }
                    self.tools.append(openai_tool)
                self.status = "Running"
                return True
            else:
                self.status = "Error: No tools"
                return False
        except Exception as e:
            self.status = f"Error: {e}"
            return False

    def _send_request(self, method, params, timeout=5):
        if not self.process or self.process.poll() is not None:
            return None
        with self.lock:
            self.req_id += 1
            msg = {"jsonrpc": "2.0", "id": self.req_id, "method": method, "params": params}
            try:
                self.process.stdin.write(json.dumps(msg) + "\n")
                self.process.stdin.flush()
                line = self.process.stdout.readline()
                if not line:
                    return None
                return json.loads(line)
            except Exception:
                return None

    def _send_notification(self, method, params):
        if not self.process or self.process.poll() is not None:
            return
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        try:
            self.process.stdin.write(json.dumps(msg) + "\n")
            self.process.stdin.flush()
        except Exception:
            pass

    def call_tool(self, tool_name, args):
        actual_name = tool_name.replace(f"mcp__{self.name}__", "")
        res = self._send_request("tools/call", {"name": actual_name, "arguments": args}, timeout=20)
        if not res or "error" in res:
            err_msg = res.get("error", {}).get("message") if isinstance(res, dict) else "No response"
            return f"Lỗi MCP Tool '{tool_name}': {err_msg}"
        result_obj = res.get("result", {})
        content_items = result_obj.get("content", [])
        output = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "text":
                output.append(item.get("text", ""))
        return "\n".join(output) if output else json.dumps(result_obj, ensure_ascii=False)

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        self.status = "Stopped"


class MCPManager:
    """Quản lý các Local MCP Servers từ mcp_config.json."""

    def __init__(self):
        self.servers = {}
        self.reload()

    def reload(self):
        for s in self.servers.values():
            s.stop()
        self.servers = {}

        cfg = load_mcp_config()
        mcp_servers = cfg.get("mcpServers") or {}
        for s_name, s_info in mcp_servers.items():
            if isinstance(s_info, dict) and s_info.get("command"):
                cmd = s_info.get("command")
                args = s_info.get("args") or []
                srv = ExternalMCPServer(s_name, cmd, args)
                self.servers[s_name] = srv

        for srv in self.servers.values():
            threading.Thread(target=srv.start, daemon=True).start()

    def get_all_tools(self):
        all_tools = list(MCP_TOOLS)
        for srv in self.servers.values():
            if srv.status == "Running":
                all_tools.extend(srv.tools)
        return all_tools

    def execute_tool(self, name, args):
        if name.startswith("mcp__"):
            parts = name.split("__", 2)
            if len(parts) >= 3:
                server_name = parts[1]
                srv = self.servers.get(server_name)
                if srv and srv.status == "Running":
                    return srv.call_tool(name, args)
                return f"Lỗi: MCP Server '{server_name}' đang dừng hoặc lỗi ({srv.status if srv else 'không tồn tại'})."
        return execute_mcp_tool(name, args)


# --------------------------------------------------------------------------- #
# Kết nối API & Xử lý URL
# --------------------------------------------------------------------------- #
class ApiError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect())


def _is_local_host(host):
    if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local"):
        return True
    m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", host)
    if m:
        ip = [int(x) for x in m.groups()]
        if ip[0] == 10 or (ip[0] == 192 and ip[1] == 168) or (ip[0] == 172 and 16 <= ip[1] <= 31):
            return True
    return False


def normalize_url(raw):
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        raise ApiError("Vui lòng nhập Cloud API URL.")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urllib.parse.urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host:
        raise ApiError("Cloud API URL không hợp lệ.")
    if parsed.scheme == "http" and not _is_local_host(host):
        raise ApiError("Chỉ cho phép https:// để bảo vệ API key (http:// chỉ dùng được với localhost hoặc mạng LAN).")
    return raw


def api_post(base, path, payload, token=None, timeout=60):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(normalize_url(base) + path, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    return _opener.open(req, timeout=timeout)


def api_get(base, path, token, timeout=10):
    req = urllib.request.Request(normalize_url(base) + path, headers={"Authorization": "Bearer " + token,
                                                                      "Accept": "application/json"})
    return _opener.open(req, timeout=timeout)


def http_message(e, ctx="chat"):
    code, detail = e.code, ""
    try:
        body = json.loads(e.read().decode("utf-8", "replace"))
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                detail = str(err.get("message") or "")
            elif isinstance(err, str):
                detail = err
            else:
                detail = str(body.get("message") or "")
    except Exception:
        pass
    if code == 401:
        msg = ("API key không hợp lệ, hết hạn hoặc đã bị thu hồi." if ctx == "activate"
               else "Phiên đăng nhập đã hết hạn. Hãy kích hoạt lại bằng API key.")
    elif code == 403:
        msg = "API key không có quyền truy cập (HTTP 403)."
    elif code == 404:
        msg = "Không tìm thấy endpoint trên máy chủ (HTTP 404). Hãy kiểm tra lại Cloud API URL."
    elif code == 429:
        msg = "Máy chủ đang giới hạn tốc độ (HTTP 429). Hãy thử lại sau ít phút."
    elif code in (301, 302, 303, 307, 308):
        msg = "Máy chủ chuyển hướng yêu cầu (HTTP %d). Hãy dùng đúng Cloud API URL (https) cuối cùng." % code
    elif code in (400, 422):
        msg = "Máy chủ từ chối yêu cầu (HTTP %d)." % code
    elif code >= 500:
        msg = "Máy chủ đang gặp lỗi (HTTP %d). Hãy thử lại sau." % code
    else:
        msg = "Máy chủ trả về lỗi HTTP %d." % code
    detail = detail.strip()[:200]
    return "%s (%s)" % (msg, detail) if detail else msg


def net_message(e):
    if isinstance(e, ApiError):
        return str(e)
    if isinstance(e, (TimeoutError, socket.timeout)):
        return "Hết thời gian chờ phản hồi từ máy chủ."
    if isinstance(e, urllib.error.URLError):
        if isinstance(e.reason, (TimeoutError, socket.timeout)):
            return "Hết thời gian chờ phản hồi từ máy chủ."
        return "Không thể kết nối tới máy chủ: %s" % e.reason
    if isinstance(e, ValueError):
        return "Máy chủ trả về dữ liệu không hợp lệ."
    return "Không thể kết nối AI server. (%s)" % e


def iter_completion(response, cancel):
    ctype = response.headers.get("Content-Type", "")
    if "text/event-stream" in ctype:
        for raw in response:
            if cancel.is_set():
                return
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            choice = (obj.get("choices") or [{}])[0] if isinstance(obj, dict) else {}
            piece = (choice.get("delta") or {}).get("content") or (choice.get("message") or {}).get("content") or ""
            if piece:
                yield piece
    else:
        data = json.loads(response.read().decode("utf-8"))
        choice = (data.get("choices") or [{}])[0] if isinstance(data, dict) else {}
        text = (choice.get("message") or {}).get("content")
        if text:
            yield text


def pretty(model_id):
    return model_id.replace("-", " ").replace("_", " ").title()


# --------------------------------------------------------------------------- #
# Logo Tự Vẽ Khử Răng Cưa (Pixel Precision)
# --------------------------------------------------------------------------- #
_LOGO_CACHE = {}
_P23 = 2.0 / 3.0


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _in_round(x, y, s, r):
    dx = max(r - x, 0, x - (s - r))
    dy = max(r - y, 0, y - (s - r))
    return dx * dx + dy * dy <= r * r


_R1, _R2 = 0.27 ** _P23, 0.115 ** _P23


def _in_star(u, v):
    return (abs(u - 0.43) ** _P23 + abs(v - 0.58) ** _P23 <= _R1) or \
           (abs(u - 0.745) ** _P23 + abs(v - 0.27) ** _P23 <= _R2)


def make_logo(size, bg=COLOR_BG, transparent=False):
    key = (size, bg, transparent)
    if key in _LOGO_CACHE:
        return _LOGO_CACHE[key]
    img = tk.PhotoImage(width=size, height=size)
    bgc, c1, c2, white = _hex(bg), (142, 133, 255), (88, 78, 230), (255, 255, 255)
    r, ss = size * 0.27, 2
    total = ss * ss
    rows, clear = [], []
    for y in range(size):
        row = []
        for x in range(size):
            m = s = 0
            for i in range(ss):
                for j in range(ss):
                    sx, sy = x + (i + .5) / ss, y + (j + .5) / ss
                    if _in_round(sx, sy, size, r):
                        m += 1
                        if _in_star(sx / size, sy / size):
                            s += 1
            m, s = m / total, s / total
            tile = _lerp(c1, c2, (x + y) / (2.0 * size))
            row.append("#%02x%02x%02x" % _lerp(_lerp(bgc, tile, m), white, s))
            if transparent and m < 0.5:
                clear.append((x, y))
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows))
    for x, y in clear:
        img.transparency_set(x, y, True)
    _LOGO_CACHE[key] = img
    return img


# --------------------------------------------------------------------------- #
# Component Khung Bong Bóng Chat (Message Block & Code Block)
# --------------------------------------------------------------------------- #
class ChatMessageBlock(ctk.CTkFrame):
    """Component hiển thị bong bóng chat với hỗ trợ Khối Code & Thumbnail Ảnh."""

    def __init__(self, parent, role, content, copy_callback):
        self.role = role
        self.raw_content = content
        self.copy_callback = copy_callback
        is_user = role == "user"

        bg_col = COLOR_USER_BUBBLE if is_user else COLOR_ASSIST_BUBBLE
        border_col = COLOR_USER_BUBBLE if is_user else COLOR_ASSIST_BORDER

        super().__init__(parent, fg_color="transparent")

        self.card = ctk.CTkFrame(
            self,
            fg_color=bg_col,
            border_color=border_col,
            border_width=1,
            corner_radius=18
        )
        if is_user:
            self.card.pack(side="right", padx=(60, 0), pady=4)
        else:
            self.card.pack(side="left", padx=(0, 60), pady=4)

        self.body_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=14, pady=10)

        self.render_content(content)

    def render_content(self, content):
        for w in self.body_frame.winfo_children():
            w.destroy()

        text_val = ""
        image_url = None

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_val += item.get("text", "")
                    elif item.get("type") == "image_url":
                        image_url = item.get("image_url", {}).get("url")
        else:
            text_val = str(content or "")

        if image_url:
            try:
                if "," in image_url:
                    b64_data = image_url.split(",")[1]
                    img_bytes = base64.b64decode(b64_data)
                    self.img_ref = tk.PhotoImage(data=img_bytes)
                    lbl_img = tk.Label(self.body_frame, image=self.img_ref, bg=self.card.cget("fg_color"))
                    lbl_img.pack(anchor="w", pady=(0, 8))
            except Exception:
                pass

        if not text_val and not image_url:
            lbl = ctk.CTkLabel(self.body_frame, text="Aster đang suy nghĩ…", font=(FONT_FAMILY, 12, "italic"), text_color=COLOR_MUTED)
            lbl.pack(anchor="w")
            return

        if text_val:
            parts = re.split(r"(```[\s\S]*?```)", text_val)
            for part in parts:
                if not part:
                    continue
                if part.startswith("```") and part.endswith("```"):
                    lines = part[3:-3].split("\n", 1)
                    lang = lines[0].strip() if len(lines) > 1 else ""
                    code_text = lines[1] if len(lines) > 1 else lines[0]
                    self._add_code_block(lang, code_text.rstrip())
                else:
                    self._add_text_block(part.strip())

        if self.role == "assistant":
            btn_copy = ctk.CTkButton(
                self.body_frame,
                text="📋 Sao chép câu trả lời",
                font=(FONT_FAMILY, 11),
                fg_color="transparent",
                hover_color=COLOR_PANEL_HOVER,
                text_color=COLOR_MUTED,
                height=24,
                command=lambda: self.copy_callback(text_val)
            )
            btn_copy.pack(anchor="w", pady=(6, 0))

    def _add_text_block(self, text):
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        lbl = ctk.CTkLabel(
            self.body_frame,
            text=cleaned,
            font=(FONT_FAMILY, 13),
            text_color=COLOR_TEXT,
            justify="left",
            wraplength=620
        )
        lbl.pack(anchor="w", pady=2)

    def _add_code_block(self, lang, code):
        box = ctk.CTkFrame(self.body_frame, fg_color=COLOR_CODE_BG, border_color=COLOR_LINE, border_width=1, corner_radius=10)
        box.pack(fill="x", pady=6)

        header = ctk.CTkFrame(box, fg_color=COLOR_CODE_HEADER, height=28, corner_radius=10)
        header.pack(fill="x")

        lbl_lang = ctk.CTkLabel(header, text="💻 Code " + (f"[{lang}]" if lang else ""), font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_MUTED)
        lbl_lang.pack(side="left", padx=10)

        btn_copy = ctk.CTkButton(
            header,
            text="Sao chép code",
            font=(FONT_FAMILY, 10),
            fg_color="transparent",
            hover_color=COLOR_PANEL_HOVER,
            text_color=COLOR_ACCENT_HOVER,
            width=80,
            height=22,
            command=lambda: self.copy_callback(code)
        )
        btn_copy.pack(side="right", padx=6)

        txt = tk.Text(
            box,
            bg=COLOR_CODE_BG,
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            bd=0,
            font=(FONT_MONO, 11),
            wrap="none",
            padx=10,
            pady=8
        )
        txt.insert("1.0", code)
        txt.configure(state="disabled")
        line_cnt = max(2, min(16, code.count("\n") + 1))
        txt.configure(height=line_cnt)
        txt.pack(fill="x", padx=4, pady=4)

    def update_text(self, new_text):
        if new_text != self.raw_content:
            self.raw_content = new_text
            self.render_content(new_text)


# --------------------------------------------------------------------------- #
# Ứng Dụng Chính (AsterApp)
# --------------------------------------------------------------------------- #
class AsterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Aster AI Desktop")
        self.geometry("1180x760")
        self.minsize(920, 600)
        self.configure(fg_color=COLOR_BG)

        self.icons = [make_logo(32, transparent=True), make_logo(64, transparent=True)]
        try:
            self.iconphoto(True, *self.icons)
        except tk.TclError:
            pass

        self.events = queue.Queue()
        self.config_data = load_config()
        self.session = self.restore_session()
        self.model = self.config_data.get("model") or DEFAULT_MODEL
        self.models = [(pretty(self.model), self.model)] if self.model != DEFAULT_MODEL else [("Gemini 2.0 Flash Free", DEFAULT_MODEL)]
        self.chats = load_chats()
        fresh = {"title": NEW_CHAT_TITLE, "messages": []}
        self.chats.insert(0, fresh)
        self.active = fresh

        self.mcp_manager = MCPManager()
        self.attached_image = None

        self.job = None
        self.stream_ui = None
        self.blocks = []

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(120, lambda: dark_titlebar(self))
        self.after(35, self.pump)

        # Khởi chạy kiểm tra cập nhật ngầm
        threading.Thread(target=self.background_update_check, daemon=True).start()

        self.build()

    def logo(self, size, bg):
        return make_logo(size, bg)

    def report_callback_exception(self, exc, val, tb):
        import traceback
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            with open(os.path.join(APP_DIR, "error.log"), "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + "".join(traceback.format_exception(exc, val, tb)) + "\n")
        except Exception:
            pass

    # ----- Restore Session --------------------------------------------------
    def restore_session(self):
        cfg = self.config_data
        enc, user = cfg.get("token_enc"), cfg.get("user")
        if enc and isinstance(user, dict):
            try:
                return {"accessToken": unprotect(base64.b64decode(enc)).decode("utf-8"), "user": user}
            except Exception:
                cfg.pop("token_enc", None)
                cfg.pop("user", None)
                save_config(cfg)
        return None

    def store_session(self, data):
        self.session = data
        self.config_data["user"] = data["user"]
        try:
            self.config_data["token_enc"] = base64.b64encode(protect(data["accessToken"].encode("utf-8"))).decode("ascii")
        except Exception:
            self.config_data.pop("token_enc", None)
        save_config(self.config_data)

    def clear_session(self):
        for key in ("token_enc", "user"):
            self.config_data.pop(key, None)
        self.session = None
        save_config(self.config_data)

    # ----- Event Pump -------------------------------------------------------
    def ui_call(self, fn):
        self.events.put(("call", fn))

    def pump(self):
        deltas, dones = False, []
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "delta":
                    deltas = True
                elif kind == "done":
                    dones.append(payload)
                elif kind == "call":
                    payload()
        except queue.Empty:
            pass
        finally:
            try:
                if deltas and self.job:
                    self.render_stream(self.job)
                for job in dones:
                    if job is self.job:
                        self.end_job(job, job.get("error"), job.get("status"))
            finally:
                self.after(35, self.pump)

    def on_close(self):
        save_chats(self.chats)
        self.destroy()

    # ----- Vision / Image Attachment Methods --------------------------------
    def on_attach_click(self):
        path = filedialog.askopenfilename(
            title="Chọn hình ảnh minh họa",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.gif")]
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                b64_bytes = base64.b64encode(f.read())
                b64_str = b64_bytes.decode("ascii")
            ext = path.split(".")[-1].lower()
            mime = "image/png" if ext == "png" else ("image/webp" if ext == "webp" else "image/jpeg")
            data_url = f"data:{mime};base64,{b64_str}"
            self.attached_image = {"path": path, "name": os.path.basename(path), "data_url": data_url, "b64": b64_str}
            self.show_attachment_preview()
        except Exception as e:
            messagebox.showerror("Lỗi đính kèm", f"Không thể đọc file ảnh: {e}")

    def show_attachment_preview(self):
        if hasattr(self, "preview_frame") and alive(self.preview_frame):
            self.preview_frame.destroy()
        if not self.attached_image:
            return
        self.preview_frame = ctk.CTkFrame(self.content, fg_color=COLOR_PANEL, border_color=COLOR_LINE, border_width=1, corner_radius=12, height=36)
        self.preview_frame.pack(side="bottom", fill="x", padx=24, pady=(0, 4))
        self.preview_frame.pack_propagate(False)

        ctk.CTkLabel(self.preview_frame, text=f"📎 Đã đính kèm ảnh: {self.attached_image['name']}", font=(FONT_FAMILY, 11), text_color=COLOR_ACCENT_HOVER).pack(side="left", padx=12)
        ctk.CTkButton(
            self.preview_frame,
            text="✕",
            font=(FONT_FAMILY, 11, "bold"),
            fg_color="transparent",
            hover_color=COLOR_ERROR,
            text_color=COLOR_MUTED,
            width=24,
            height=24,
            corner_radius=12,
            command=self.remove_attachment
        ).pack(side="right", padx=8, pady=6)

    def remove_attachment(self):
        self.attached_image = None
        if hasattr(self, "preview_frame") and alive(self.preview_frame):
            self.preview_frame.destroy()

    # ----- Auto-Updater Methods ---------------------------------------------
    def background_update_check(self):
        url = self.config_data.get("update_check_url") or UPDATE_CHECK_URL
        info = check_remote_update(APP_VERSION, url)
        if info.get("has_update"):
            self.ui_call(lambda: self.prompt_update_dialog(info))

    def manual_check_update(self):
        url = self.config_data.get("update_check_url") or UPDATE_CHECK_URL
        info = check_remote_update(APP_VERSION, url)
        if info.get("has_update"):
            self.prompt_update_dialog(info)
        else:
            messagebox.showinfo("Tự Động Cập Nhật", f"Bạn đang sử dụng phiên bản mới nhất (v{APP_VERSION}).")

    def prompt_update_dialog(self, info):
        ver = info.get("version")
        dl_url = info.get("download_url")
        changelog = info.get("changelog")

        if not dl_url:
            return

        win = ctk.CTkToplevel(self)
        win.title("Cập Nhật Aster AI Desktop")
        win.geometry("460x280")
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(win, text=f"🚀 Đã có phiên bản mới v{ver}!", font=(FONT_FAMILY, 18, "bold"), text_color=COLOR_TEXT).pack(pady=(20, 4))
        ctk.CTkLabel(win, text=f"Phiên bản hiện tại: v{APP_VERSION}", font=(FONT_FAMILY, 11), text_color=COLOR_MUTED).pack()

        lbl_log = ctk.CTkLabel(win, text=f"Nội dung cập nhật:\n{changelog}", font=(FONT_FAMILY, 11), text_color=COLOR_TEXT, wraplength=400, justify="left")
        lbl_log.pack(pady=16)

        lbl_status = ctk.CTkLabel(win, text="", font=(FONT_FAMILY, 11), text_color=COLOR_ACCENT)
        lbl_status.pack(pady=4)

        def start_download():
            lbl_status.configure(text="📥 Đang tải bản cập nhật...")
            def work():
                try:
                    def on_progress(p):
                        percent = int(p * 100)
                        self.ui_call(lambda: lbl_status.configure(text=f"📥 Đang tải bản cập nhật: {percent}%"))
                    apply_exe_update(dl_url, progress_callback=on_progress)
                except Exception as ex:
                    self.ui_call(lambda: messagebox.showerror("Lỗi Cập Nhật", str(ex)))
            threading.Thread(target=work, daemon=True).start()

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=20)

        ctk.CTkButton(btn_frame, text="Cập Nhật Ngay", font=(FONT_FAMILY, 12, "bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=start_download).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Để Sau", font=(FONT_FAMILY, 12), fg_color=COLOR_PANEL, hover_color=COLOR_PANEL_HOVER, command=win.destroy).pack(side="left", padx=10)

    # ----- Dựng Màn Hình ----------------------------------------------------
    def build(self, notice=""):
        for w in self.winfo_children():
            w.destroy()
        if self.session:
            self.build_main()
        else:
            self.build_activation(notice)

    # ----- Màn hình Kích Hoạt ------------------------------------------------
    def build_activation(self, notice=""):
        root = ctk.CTkFrame(self, fg_color=COLOR_BG)
        root.pack(expand=True, fill="both")

        card = ctk.CTkFrame(root, width=460, fg_color=COLOR_PANEL, border_color=COLOR_LINE, border_width=1, corner_radius=22)
        card.place(relx=0.5, rely=0.5, anchor="center")

        lbl_logo = tk.Label(card, image=self.logo(52, COLOR_PANEL), bg=COLOR_PANEL)
        lbl_logo.pack(anchor="w", padx=32, pady=(28, 0))

        ctk.CTkLabel(card, text="ASTER AI DESKTOP", font=(FONT_FAMILY, 10, "bold"), text_color="#a5b4fc").pack(anchor="w", padx=32, pady=(16, 2))
        ctk.CTkLabel(card, text="Kích hoạt không gian AI của bạn", font=(FONT_FAMILY, 20, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=32)
        ctk.CTkLabel(card, text="Nhập Cloud API URL và API key để kết nối vào ứng dụng.", font=(FONT_FAMILY, 12), text_color=COLOR_MUTED).pack(anchor="w", padx=32, pady=(4, 20))

        ctk.CTkLabel(card, text="Cloud API URL", font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=32)
        self.url_entry = ctk.CTkEntry(card, fg_color=COLOR_BG, border_color=COLOR_LINE, font=(FONT_FAMILY, 12), height=38, corner_radius=10)
        self.url_entry.insert(0, self.config_data.get("api_base_url", DEFAULT_URL))
        self.url_entry.pack(fill="x", padx=32, pady=(4, 14))

        ctk.CTkLabel(card, text="API Key", font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=32)
        self.key_entry = ctk.CTkEntry(card, fg_color=COLOR_BG, border_color=COLOR_LINE, font=(FONT_FAMILY, 12), show="•", height=38, corner_radius=10)
        self.key_entry.pack(fill="x", padx=32, pady=(4, 10))

        self.error_label = ctk.CTkLabel(card, text=notice, font=(FONT_FAMILY, 11), text_color=COLOR_ERROR, wraplength=380, justify="left")
        self.error_label.pack(anchor="w", padx=32)

        self.activate_button = ctk.CTkButton(
            card,
            text="Kích hoạt và tiếp tục  →",
            font=(FONT_FAMILY, 13, "bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            height=42,
            corner_radius=12,
            command=self.activate
        )
        self.activate_button.pack(fill="x", padx=32, pady=(12, 28))

        self.url_entry.bind("<Return>", lambda _e: self.activate())
        self.key_entry.bind("<Return>", lambda _e: self.activate())

    def activate(self):
        try:
            url = normalize_url(self.url_entry.get())
        except ApiError as e:
            self.error_label.configure(text=str(e))
            return
        key = self.key_entry.get().strip()
        if not key:
            self.error_label.configure(text="Vui lòng nhập API key.")
            return

        self.activate_button.configure(state="disabled", text="Đang xác thực…")
        self.error_label.configure(text="")

        def work():
            try:
                try:
                    with api_post(url, "/v1/auth/activate", {"apiKey": key, "deviceName": "Aster Windows Desktop"}, timeout=30) as response:
                        data = json.loads(response.read().decode("utf-8"))
                    if not isinstance(data, dict) or not data.get("accessToken") or not isinstance(data.get("user"), dict):
                        raise ApiError("Máy chủ trả về dữ liệu kích hoạt không hợp lệ.")
                except urllib.error.HTTPError as err:
                    if err.code in (404, 405):
                        data = {"accessToken": key, "user": {"name": "Tài khoản Cloud", "plan": "API Key"}}
                    else:
                        raise
                self.ui_call(lambda: self.activated(url, data))
            except urllib.error.HTTPError as e:
                msg = http_message(e, "activate")
                self.ui_call(lambda: self.activation_failed(msg))
            except Exception as e:
                msg = net_message(e)
                self.ui_call(lambda: self.activation_failed(msg))

        threading.Thread(target=work, daemon=True).start()

    def activated(self, url, data):
        self.config_data["api_base_url"] = url
        self.store_session(data)
        self.build()

    def activation_failed(self, message):
        if alive(self.error_label):
            self.error_label.configure(text=message)
            self.activate_button.configure(state="normal", text="Kích hoạt và tiếp tục  →")

    # ----- Màn hình Chính ---------------------------------------------------
    def build_main(self):
        shell = ctk.CTkFrame(self, fg_color=COLOR_BG)
        shell.pack(expand=True, fill="both")

        # Sidebar
        side = ctk.CTkFrame(shell, fg_color=COLOR_SIDEBAR, width=260, corner_radius=0)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(18, 14))
        tk.Label(brand, image=self.logo(34, COLOR_SIDEBAR), bg=COLOR_SIDEBAR).pack(side="left")
        ctk.CTkLabel(brand, text="Aster AI", font=(FONT_FAMILY, 16, "bold"), text_color=COLOR_TEXT).pack(side="left", padx=10)

        ctk.CTkButton(
            side,
            text="+  Cuộc trò chuyện mới",
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            height=38,
            corner_radius=12,
            command=self.new_chat
        ).pack(fill="x", padx=14, pady=(0, 16))

        ctk.CTkLabel(side, text="GẦN ĐÂY", font=(FONT_FAMILY, 10, "bold"), text_color=COLOR_MUTED).pack(anchor="w", padx=20, pady=(0, 6))

        bottom = ctk.CTkFrame(side, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=14, pady=16)

        ctk.CTkButton(
            bottom,
            text="⚙️ Cài đặt",
            font=(FONT_FAMILY, 11),
            fg_color=COLOR_PANEL,
            hover_color=COLOR_PANEL_HOVER,
            text_color=COLOR_TEXT,
            height=34,
            corner_radius=10,
            command=self.show_settings
        ).pack(fill="x", pady=(0, 12))

        user = self.session["user"]
        name, plan = str(user.get("name") or "Tài khoản"), str(user.get("plan") or "Standard")
        prow = ctk.CTkFrame(bottom, fg_color="transparent")
        prow.pack(fill="x")
        d = 34
        av = tk.Canvas(prow, width=d, height=d, bg=COLOR_SIDEBAR, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, d - 1, d - 1, fill="#6366f1", outline="#6366f1")
        av.create_text(d / 2, d / 2, text=name[:1].upper(), fill="white", font=(FONT_FAMILY, 11, "bold"))
        col = ctk.CTkFrame(prow, fg_color="transparent")
        col.pack(side="left", padx=10)
        ctk.CTkLabel(col, text=name[:20], font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_TEXT).pack(anchor="w")
        ctk.CTkLabel(col, text=plan, font=(FONT_FAMILY, 10), text_color=COLOR_MUTED).pack(anchor="w")

        self.history = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self.history.pack(fill="both", expand=True, padx=6)
        self.draw_history()

        self.content = ctk.CTkFrame(shell, fg_color=COLOR_BG)
        self.content.pack(side="left", fill="both", expand=True)

        self.show_chat()
        self.fetch_models()

    # ----- Lịch sử Sidebar --------------------------------------------------
    def draw_history(self):
        if not alive(self.history):
            return
        for w in self.history.winfo_children():
            w.destroy()
        for chat in self.chats:
            is_active = chat is self.active
            row = ctk.CTkFrame(self.history, fg_color="transparent")
            row.pack(fill="x", pady=1)

            btn = ctk.CTkButton(
                row,
                text=chat["title"][:26],
                font=(FONT_FAMILY, 11),
                fg_color=COLOR_MODEL_BG if is_active else "transparent",
                hover_color=COLOR_PANEL_HOVER,
                text_color=COLOR_MODEL_TEXT if is_active else COLOR_TEXT,
                anchor="w",
                height=34,
                corner_radius=10,
                command=lambda c=chat: self.select_chat(c)
            )
            btn.pack(side="left", fill="x", expand=True)

            if len(self.chats) > 1:
                btn_del = ctk.CTkButton(
                    row,
                    text="×",
                    font=(FONT_FAMILY, 12, "bold"),
                    fg_color="transparent",
                    hover_color=COLOR_ERROR,
                    text_color=COLOR_MUTED,
                    width=26,
                    height=34,
                    corner_radius=8,
                    command=lambda c=chat: self.delete_chat(c)
                )
                btn_del.pack(side="right", padx=(2, 0))

    def delete_chat(self, chat):
        if chat["messages"] and not messagebox.askyesno("Xóa cuộc trò chuyện", "Bạn có chắc muốn xóa cuộc trò chuyện này?"):
            return
        if self.job and self.job["chat"] is chat:
            self.cancel_job()
        self.chats = [c for c in self.chats if c is not chat]
        if not self.chats:
            self.chats.append({"title": NEW_CHAT_TITLE, "messages": []})
        if chat is self.active:
            self.active = self.chats[0]
        save_chats(self.chats)
        self.draw_history()
        self.show_chat()

    def select_chat(self, chat):
        self.active = chat
        self.draw_history()
        self.show_chat()

    def new_chat(self):
        if self.active["messages"]:
            fresh = {"title": NEW_CHAT_TITLE, "messages": []}
            self.chats.insert(0, fresh)
            self.active = fresh
        self.draw_history()
        self.show_chat()

    # ----- Màn Hình Chat ----------------------------------------------------
    def show_chat(self):
        for w in self.content.winfo_children():
            w.destroy()
        chat = self.active

        # Header
        header = ctk.CTkFrame(self.content, fg_color=COLOR_BG, height=60, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        self.title_label = ctk.CTkLabel(header, text=chat["title"], font=(FONT_FAMILY, 14, "bold"), text_color=COLOR_TEXT)
        self.title_label.pack(side="left", padx=24)

        self.status_dot = tk.Canvas(header, width=10, height=10, bg=COLOR_BG, highlightthickness=0)
        self.status_dot.create_oval(1, 1, 9, 9, fill=COLOR_GREEN, outline=COLOR_GREEN, tags="dot")
        self.status_dot.pack(side="left", padx=(12, 6))

        self.status_label = ctk.CTkLabel(header, text="Sẵn sàng", font=(FONT_FAMILY, 10), text_color=COLOR_MUTED)
        self.status_label.pack(side="left")

        self.model_button = ctk.CTkButton(
            header,
            text="✨  " + self.model_label() + "  ▾",
            font=(FONT_FAMILY, 11, "bold"),
            fg_color=COLOR_MODEL_BG,
            hover_color="#3b1f6e",
            text_color=COLOR_MODEL_TEXT,
            border_color=COLOR_MODEL_BORDER,
            border_width=1,
            height=32,
            corner_radius=12,
            command=self.show_model_menu
        )
        self.model_button.pack(side="right", padx=24)

        ctk.CTkFrame(self.content, fg_color=COLOR_LINE, height=1).pack(fill="x")

        # Footer info
        ctk.CTkLabel(self.content, text="Aster AI có thể mắc lỗi.  •  Shift+Enter để xuống dòng", font=(FONT_FAMILY, 10), text_color=COLOR_MUTED).pack(side="bottom", pady=(0, 8))

        # Composer Box
        wrap = ctk.CTkFrame(self.content, fg_color="transparent")
        wrap.pack(side="bottom", fill="x", padx=24, pady=(8, 6))

        self.composer = ctk.CTkFrame(wrap, fg_color=COLOR_PANEL, border_color=COLOR_LINE, border_width=1, corner_radius=22)
        self.composer.pack(fill="x", padx=10)

        self.send_button = ctk.CTkButton(
            self.composer,
            text="▲",
            font=(FONT_FAMILY, 14, "bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            width=36,
            height=36,
            corner_radius=18,
            command=self.on_send_click
        )
        self.send_button.pack(side="right", padx=8, pady=8)

        self.attach_button = ctk.CTkButton(
            self.composer,
            text="📎",
            font=(FONT_FAMILY, 14),
            fg_color="transparent",
            hover_color=COLOR_PANEL_HOVER,
            text_color=COLOR_MUTED,
            width=34,
            height=36,
            corner_radius=17,
            command=self.on_attach_click
        )
        self.attach_button.pack(side="right", padx=(0, 4), pady=8)

        self.prompt = tk.Text(
            self.composer,
            height=2,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT,
            relief="flat",
            bd=0,
            font=(FONT_FAMILY, 12),
            wrap="word"
        )
        self.prompt.pack(side="left", fill="x", expand=True, padx=(16, 8), pady=8)
        self.prompt.bind("<Return>", self.on_return)

        # ScrollFrame Chat Messages
        self.scroll = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=16, pady=8)

        if not chat["messages"]:
            self.show_hero()

        for msg in chat["messages"]:
            streaming = bool(self.job and msg is self.job["msg"])
            blk = ChatMessageBlock(self.scroll, msg["role"], msg["content"], self.copy_text)
            blk.pack(fill="x", pady=4)
            if streaming:
                self.stream_ui = blk

        self.prompt.focus_set()

    def show_hero(self):
        h = ctk.CTkFrame(self.scroll, fg_color="transparent")
        h.pack(fill="x", pady=(40, 0))

        lbl_logo = tk.Label(h, image=self.logo(68, COLOR_BG), bg=COLOR_BG)
        lbl_logo.pack()

        ctk.CTkLabel(h, text="Xin chào, mình là Aster AI 👋", font=(FONT_FAMILY, 22, "bold"), text_color=COLOR_TEXT).pack(pady=(16, 4))
        ctk.CTkLabel(h, text="Hôm nay mình có thể giúp gì cho bạn?", font=(FONT_FAMILY, 12), text_color=COLOR_MUTED).pack()

        chips = ctk.CTkFrame(h, fg_color="transparent")
        chips.pack(pady=(24, 0))

        for text in ("📂  Liệt kê file trong thư mục", "📄  Đọc file README.md", "💻  Chạy lệnh git status"):
            ctk.CTkButton(
                chips,
                text=text,
                font=(FONT_FAMILY, 11),
                fg_color=COLOR_PANEL,
                hover_color=COLOR_PANEL_HOVER,
                border_color=COLOR_LINE,
                border_width=1,
                corner_radius=14,
                height=38,
                command=lambda t=text[4:]: self.use_suggestion(t)
            ).pack(side="left", padx=6)

    def use_suggestion(self, text):
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", text + " ")
        self.prompt.focus_set()

    def copy_text(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def on_return(self, e):
        if e.state & 0x0001:
            return None
        self.send_message()
        return "break"

    def on_send_click(self):
        if self.job:
            self.cancel_job()
        else:
            self.send_message()

    def send_message(self):
        if self.job or not alive(self.prompt):
            return
        text = self.prompt.get("1.0", "end").strip()
        if not text and not self.attached_image:
            return
        self.prompt.delete("1.0", "end")

        if self.attached_image:
            content = [
                {"type": "text", "text": text or "Hãy xem hình ảnh này và đưa ra nhận xét."},
                {"type": "image_url", "image_url": {"url": self.attached_image["data_url"]}}
            ]
            self.attached_image = None
            if hasattr(self, "preview_frame") and alive(self.preview_frame):
                self.preview_frame.destroy()
        else:
            content = text

        chat = self.active
        user_msg = {"role": "user", "content": content}
        chat["messages"].append(user_msg)

        display_text = text if text else "[Hình ảnh đính kèm]"
        if len(chat["messages"]) == 1:
            chat["title"] = re.sub(r"\s+", " ", display_text)[:36]
            self.title_label.configure(text=chat["title"])
            self.draw_history()

        blk = ChatMessageBlock(self.scroll, "user", content, self.copy_text)
        blk.pack(fill="x", pady=4)

        save_chats(self.chats)
        self.begin_generation()

    def begin_generation(self):
        chat = self.active
        history = request_history(chat["messages"])
        asst = {"role": "assistant", "content": ""}
        chat["messages"].append(asst)

        blk = ChatMessageBlock(self.scroll, "assistant", "", self.copy_text)
        blk.pack(fill="x", pady=4)
        self.stream_ui = blk

        job = {"chat": chat, "msg": asst, "cancel": threading.Event(), "error": None, "status": None}
        self.job = job
        self.set_busy(True)

        args = (job, history, self.config_data.get("api_base_url", ""), self.session["accessToken"], self.model)
        threading.Thread(target=self.run_job, args=args, daemon=True).start()

    def run_job(self, job, history, base, token, model):
        try:
            all_mcp_tools = self.mcp_manager.get_all_tools()
            payload = {
                "model": model,
                "messages": history,
                "tools": all_mcp_tools,
                "stream": False
            }
            try:
                resp = api_post(base, "/v1/chat/completions", payload, token, timeout=90)
                data = json.loads(resp.read().decode("utf-8"))
            except Exception:
                resp = api_post(base, "/v1/chat/completions", {"model": model, "messages": history, "stream": True}, token, timeout=90)
                with resp:
                    for piece in iter_completion(resp, job["cancel"]):
                        if job["cancel"].is_set():
                            break
                        job["msg"]["content"] += piece
                        self.events.put(("delta", job))
                return

            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            tool_calls = message.get("tool_calls")

            if tool_calls and isinstance(tool_calls, list):
                updated_history = list(history)
                updated_history.append(message)

                for call in tool_calls:
                    if job["cancel"].is_set():
                        return
                    func = call.get("function") or {}
                    tool_name = func.get("name")
                    call_id = call.get("id")
                    raw_args = func.get("arguments") or "{}"

                    try:
                        tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        tool_args = {}

                    job["msg"]["content"] += f"⚙️ *[MCP Action]* Đang chạy công cụ **`{tool_name}`**...\n"
                    self.events.put(("delta", job))

                    tool_result = self.mcp_manager.execute_tool(tool_name, tool_args)

                    job["msg"]["content"] += f"✅ *[MCP Complete]* Kết quả từ `{tool_name}`:\n```\n{tool_result[:800]}\n```\n\n"
                    self.events.put(("delta", job))

                    updated_history.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": tool_result
                    })

                job["msg"]["content"] += "🤖 **Aster AI:**\n"
                self.events.put(("delta", job))

                resp_final = api_post(base, "/v1/chat/completions", {"model": model, "messages": updated_history, "stream": True}, token, timeout=90)
                with resp_final:
                    for piece in iter_completion(resp_final, job["cancel"]):
                        if job["cancel"].is_set():
                            break
                        job["msg"]["content"] += piece
                        self.events.put(("delta", job))
            else:
                content = message.get("content") or ""
                job["msg"]["content"] = content
                self.events.put(("delta", job))

            if not job["msg"]["content"] and not job["cancel"].is_set():
                raise ApiError("Phản hồi model không có nội dung.")
        except urllib.error.HTTPError as e:
            job["status"] = e.code
            job["error"] = http_message(e, "chat")
        except Exception as e:
            job["error"] = net_message(e)
        finally:
            self.events.put(("done", job))

    def render_stream(self, job):
        if self.stream_ui and alive(self.stream_ui):
            self.stream_ui.update_text(job["msg"]["content"])

    def end_job(self, job, error=None, status=None):
        if job is not self.job:
            return
        self.job = None
        self.stream_ui = None
        self.set_busy(False)
        save_chats(self.chats)

    def cancel_job(self):
        if self.job:
            self.job["cancel"].set()
            self.end_job(self.job)

    def set_busy(self, busy):
        if alive(self.send_button):
            self.send_button.configure(text="■" if busy else "▲")
        if alive(self.status_label):
            self.status_label.configure(text="Aster đang suy nghĩ…" if busy else "Sẵn sàng")

    # ----- Chọn Model & Settings -------------------------------------------
    def model_label(self):
        return next((label for label, mid in self.models if mid == self.model), pretty(self.model))

    def show_model_menu(self):
        menu = tk.Menu(self, tearoff=0, bg=COLOR_PANEL, fg=COLOR_TEXT, activebackground=COLOR_ACCENT, activeforeground="white", bd=0)
        for label, mid in self.models:
            menu.add_command(label=("✓  " if mid == self.model else "     ") + label, command=lambda m=mid: self.set_model(m))
        b = self.model_button
        try:
            menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 4)
        finally:
            menu.grab_release()

    def set_model(self, model_id):
        self.model = model_id
        self.config_data["model"] = model_id
        save_config(self.config_data)
        if alive(self.model_button):
            self.model_button.configure(text="✨  " + self.model_label() + "  ▾")

    def fetch_models(self):
        base, token = self.config_data.get("api_base_url", ""), self.session["accessToken"]

        def work():
            try:
                with api_get(base, "/v1/models", token, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                items = data.get("data") if isinstance(data, dict) else None
                models = []
                for it in items or []:
                    if isinstance(it, dict) and isinstance(it.get("id"), str):
                        mid = it["id"]
                        name = it.get("name") if isinstance(it.get("name"), str) else pretty(mid)
                        if ":free" in mid or "free" in name.lower():
                            models.insert(0, (name, mid))
                        else:
                            models.append((name, mid))
                if models:
                    self.ui_call(lambda: self.apply_models(models[:30]))
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def apply_models(self, models):
        self.models = models
        if self.model not in [mid for _, mid in models]:
            self.model = models[0][1]
            self.config_data["model"] = self.model
            save_config(self.config_data)
        if alive(self.model_button):
            self.model_button.configure(text="✨  " + self.model_label() + "  ▾")

    # ----- Cài đặt & Quản lý MCP Servers ------------------------------------
    def show_settings(self):
        for w in self.content.winfo_children():
            w.destroy()

        scroll_settings = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        scroll_settings.pack(fill="both", expand=True, padx=30, pady=20)

        ctk.CTkLabel(scroll_settings, text="Cài đặt", font=(FONT_FAMILY, 24, "bold"), text_color=COLOR_TEXT).pack(anchor="w")
        ctk.CTkLabel(scroll_settings, text="Quản lý kết nối Cloud API, tài khoản, Auto-Update và Local MCP Servers.", font=(FONT_FAMILY, 12), text_color=COLOR_MUTED).pack(anchor="w", pady=(2, 16))

        # 1. Cloud API Card
        c1 = ctk.CTkFrame(scroll_settings, fg_color=COLOR_PANEL, border_color=COLOR_LINE, border_width=1, corner_radius=16)
        c1.pack(fill="x", pady=8)

        ctk.CTkLabel(c1, text="Kết nối Cloud API", font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=20, pady=(16, 2))
        self.settings_url = ctk.CTkEntry(c1, fg_color=COLOR_BG, border_color=COLOR_LINE, font=(FONT_FAMILY, 12), height=36)
        self.settings_url.insert(0, self.config_data.get("api_base_url", ""))
        self.settings_url.pack(fill="x", padx=20, pady=8)

        ctk.CTkButton(c1, text="Lưu & Đổi máy chủ", font=(FONT_FAMILY, 11), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.change_url).pack(anchor="e", padx=20, pady=(4, 16))

        # 2. Auto-Updater Card
        c_upd = ctk.CTkFrame(scroll_settings, fg_color=COLOR_PANEL, border_color=COLOR_LINE, border_width=1, corner_radius=16)
        c_upd.pack(fill="x", pady=8)

        upd_hdr = ctk.CTkFrame(c_upd, fg_color="transparent")
        upd_hdr.pack(fill="x", padx=20, pady=(16, 12))

        upd_info = ctk.CTkFrame(upd_hdr, fg_color="transparent")
        upd_info.pack(side="left")

        ctk.CTkLabel(upd_info, text="Tự Động Cập Nhật (Auto-Update)", font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT).pack(anchor="w")
        ctk.CTkLabel(upd_info, text=f"Phiên bản hiện tại: v{APP_VERSION}", font=(FONT_FAMILY, 11), text_color=COLOR_MUTED).pack(anchor="w")

        btn_check_upd = ctk.CTkButton(
            upd_hdr,
            text="🔄 Kiểm tra bản mới",
            font=(FONT_FAMILY, 11),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            height=32,
            corner_radius=8,
            command=self.manual_check_update
        )
        btn_check_upd.pack(side="right")

        ctk.CTkLabel(c_upd, text="Đường dẫn kiểm tra update (JSON URL)", font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=20, pady=(4, 0))
        self.settings_upd_url = ctk.CTkEntry(c_upd, fg_color=COLOR_BG, border_color=COLOR_LINE, font=(FONT_FAMILY, 12), height=34)
        self.settings_upd_url.insert(0, self.config_data.get("update_check_url", UPDATE_CHECK_URL))
        self.settings_upd_url.pack(fill="x", padx=20, pady=(4, 8))

        ctk.CTkButton(c_upd, text="Lưu URL Update", font=(FONT_FAMILY, 11), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self.save_update_url).pack(anchor="e", padx=20, pady=(0, 16))

        # 3. Local MCP Servers Card (Giống hệt Claude Desktop)
        c_mcp = ctk.CTkFrame(scroll_settings, fg_color=COLOR_PANEL, border_color=COLOR_LINE, border_width=1, corner_radius=16)
        c_mcp.pack(fill="x", pady=8)

        mcp_hdr = ctk.CTkFrame(c_mcp, fg_color="transparent")
        mcp_hdr.pack(fill="x", padx=20, pady=(16, 4))

        mcp_info = ctk.CTkFrame(mcp_hdr, fg_color="transparent")
        mcp_info.pack(side="left")

        ctk.CTkLabel(mcp_info, text="Local MCP servers", font=(FONT_FAMILY, 15, "bold"), text_color=COLOR_TEXT).pack(anchor="w")
        ctk.CTkLabel(mcp_info, text="Add and manage MCP servers (Houdini, Maya, Blender, Filesystem...)", font=(FONT_FAMILY, 11), text_color=COLOR_MUTED).pack(anchor="w")

        btn_edit_cfg = ctk.CTkButton(
            mcp_hdr,
            text="Edit config",
            font=(FONT_FAMILY, 11, "bold"),
            fg_color=COLOR_PANEL_HOVER,
            hover_color=COLOR_LINE,
            text_color=COLOR_TEXT,
            height=32,
            corner_radius=8,
            command=self.open_mcp_config
        )
        btn_edit_cfg.pack(side="right", padx=(8, 0))

        btn_reload_mcp = ctk.CTkButton(
            mcp_hdr,
            text="🔄 Reload",
            font=(FONT_FAMILY, 11),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            height=32,
            corner_radius=8,
            command=self.reload_mcp_servers
        )
        btn_reload_mcp.pack(side="right")

        mcp_list_frame = ctk.CTkFrame(c_mcp, fg_color="transparent")
        mcp_list_frame.pack(fill="x", padx=20, pady=(8, 16))

        cfg_mcp = load_mcp_config().get("mcpServers") or {}
        if not cfg_mcp:
            ctk.CTkLabel(mcp_list_frame, text="Chưa có MCP Server nào. Bấm 'Edit config' để thêm.", font=(FONT_FAMILY, 11, "italic"), text_color=COLOR_MUTED).pack(anchor="w", pady=10)

        for s_name, srv_obj in self.mcp_manager.servers.items():
            s_card = ctk.CTkFrame(mcp_list_frame, fg_color=COLOR_BG, border_color=COLOR_LINE, border_width=1, corner_radius=12)
            s_card.pack(fill="x", pady=6)

            shdr = ctk.CTkFrame(s_card, fg_color="transparent")
            shdr.pack(fill="x", padx=14, pady=(12, 4))

            ctk.CTkLabel(shdr, text=s_name, font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT).pack(side="left")

            status = srv_obj.status
            status_col = COLOR_GREEN if status == "Running" else (COLOR_ERROR if "Error" in status else COLOR_MUTED)
            badge = ctk.CTkLabel(shdr, text=f" {status} ", font=(FONT_FAMILY, 10, "bold"), fg_color=COLOR_PANEL, text_color=status_col, corner_radius=6)
            badge.pack(side="left", padx=10)

            btn_del_srv = ctk.CTkButton(
                shdr,
                text="🗑️",
                font=(FONT_FAMILY, 11),
                fg_color="transparent",
                hover_color=COLOR_ERROR,
                width=28,
                height=28,
                command=lambda name=s_name: self.delete_mcp_server(name)
            )
            btn_del_srv.pack(side="right")

            cmd_str = srv_obj.command
            args_str = " ".join(srv_obj.args)

            ctk.CTkLabel(s_card, text="Command", font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_MUTED).pack(anchor="w", padx=14, pady=(4, 0))
            ctk.CTkLabel(s_card, text=cmd_str, font=(FONT_MONO, 11), text_color=COLOR_TEXT).pack(anchor="w", padx=14)

            ctk.CTkLabel(s_card, text="Arguments", font=(FONT_FAMILY, 11, "bold"), text_color=COLOR_MUTED).pack(anchor="w", padx=14, pady=(6, 0))
            ctk.CTkLabel(s_card, text=args_str, font=(FONT_MONO, 11), text_color=COLOR_TEXT, wraplength=520, justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        # 4. Account Card
        user = self.session["user"]
        c2 = ctk.CTkFrame(scroll_settings, fg_color=COLOR_PANEL, border_color=COLOR_LINE, border_width=1, corner_radius=16)
        c2.pack(fill="x", pady=8)

        ctk.CTkLabel(c2, text="Tài khoản", font=(FONT_FAMILY, 13, "bold"), text_color=COLOR_TEXT).pack(anchor="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(c2, text=f"{user.get('name') or 'Tài khoản'} · {user.get('plan') or 'Standard'}", font=(FONT_FAMILY, 11), text_color=COLOR_MUTED).pack(anchor="w", padx=20)
        ctk.CTkButton(c2, text="Đăng xuất", font=(FONT_FAMILY, 11), fg_color=COLOR_ERROR, hover_color="#e11d48", command=self.logout).pack(anchor="e", padx=20, pady=(4, 16))

        ctk.CTkButton(scroll_settings, text="← Quay lại chat", font=(FONT_FAMILY, 12), fg_color=COLOR_PANEL, hover_color=COLOR_PANEL_HOVER, command=self.show_chat).pack(anchor="w", pady=20)

    def open_mcp_config(self):
        try:
            if os.name == "nt":
                os.startfile(MCP_CONFIG_PATH)
            else:
                import subprocess
                subprocess.Popen(["open", MCP_CONFIG_PATH])
        except Exception:
            import subprocess
            subprocess.Popen(["notepad.exe", MCP_CONFIG_PATH])

    def reload_mcp_servers(self):
        self.mcp_manager.reload()
        self.show_settings()

    def delete_mcp_server(self, name):
        cfg = load_mcp_config()
        if "mcpServers" in cfg and name in cfg["mcpServers"]:
            del cfg["mcpServers"][name]
            save_mcp_config(cfg)
            self.reload_mcp_servers()

    def save_update_url(self):
        url = self.settings_upd_url.get().strip()
        self.config_data["update_check_url"] = url
        save_config(self.config_data)
        messagebox.showinfo("Cài đặt Update", "Đã lưu đường dẫn kiểm tra cập nhật thành công!")

    def change_url(self):
        try:
            url = normalize_url(self.settings_url.get())
        except ApiError as e:
            messagebox.showwarning("Cloud API URL", str(e))
            return
        self.config_data["api_base_url"] = url
        self.clear_session()
        self.build()

    def logout(self):
        if messagebox.askyesno("Đăng xuất", "Xóa phiên đăng nhập khỏi thiết bị này?"):
            self.clear_session()
            self.build()


if __name__ == "__main__":
    enable_dpi()
    AsterApp().mainloop()
