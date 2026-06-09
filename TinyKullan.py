#!/usr/bin/env python3
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
import ctypes as _ct
import logging
import sys

try:
    _ct.windll.kernel32.FreeConsole()
except Exception:
    pass

import atexit
import base64
import configparser
import http.server
import json
import os
import threading
import time
import tkinter as tk
import tkinter.messagebox
import webbrowser
import winsound
from ctypes import wintypes
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=64)
def get_cached_template(image_path: str):
    """
    Win 1+4: True LRU cache with lazy imports.
    Python's built-in lru_cache handles eviction correctly (least recently used).
    cv2 is imported on first call only, keeping GUI startup instant.
    """
    import cv2

    if not image_path or not os.path.exists(image_path):
        return None
    try:
        return cv2.imread(image_path, cv2.IMREAD_COLOR)
    except Exception:
        return None


from tkinter import colorchooser, filedialog, ttk

try:
    import cv2
    import mss as _mss

    # cv2 and numpy are lazy-loaded via get_cached_template() for fast startup
    import numpy as np  # kept for inline uses in _find_best_match / _check_images
    import requests
    from discord_webhook import DiscordEmbed, DiscordWebhook
    from PIL import Image, ImageGrab, ImageTk
    from pynput import keyboard as _pkb
    from pynput import mouse as _pmouse

    cv2_present = True
    np_present = True
except ImportError as e:
    msg = f"TinyKullan - Missing Dependencies\n\n{e}\n\nPlease run install.bat first, or paste this in your terminal:\npip install pynput pillow requests mss opencv-python numpy discord-webhook keyboard pystray"
    try:
        _ct.windll.user32.MessageBoxW(0, msg, "TinyKullan", 0x10)
    except Exception:
        print(msg, file=sys.stderr)
    cv2_present = False
    np_present = False
    sys.exit(1)

try:
    import keyboard as _kb
except ImportError:

    class MockKeyboard:
        def hook(self, *a, **k):
            return None

        def unhook(self, *a, **k):
            pass

        def unhook_all_hotkeys(self, *a, **k):
            pass

        def add_hotkey(self, *a, **k):
            pass

    _kb = MockKeyboard()

try:
    winsound.Beep = lambda *a, **k: None
    winsound.MessageBeep = lambda *a, **k: None
    winsound.PlaySound = lambda *a, **k: None
except Exception:
    pass

_LOG = logging.getLogger("TinyKullan")
_LOG.setLevel(logging.DEBUG)

# SendInput Structures (32-bit & 64-bit alignment)
ULONG_PTR = _ct.c_size_t

if sys.platform == "win32":
    user32 = _ct.windll.user32
    from ctypes import wintypes

    try:
        _ct.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

    class MOUSEINPUT(_ct.Structure):
        _fields_ = (
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ct.c_size_t),
        )

    class KEYBDINPUT(_ct.Structure):
        _fields_ = (
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ct.c_size_t),
        )

    class HARDWAREINPUT(_ct.Structure):
        _fields_ = (
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        )

    class _INPUT_UNION(_ct.Union):
        _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))

    class INPUT(_ct.Structure):
        _fields_ = (("type", wintypes.DWORD), ("union", _INPUT_UNION))

    user32.GetCursorPos.argtypes = [
        _ct.POINTER(
            POINT := type(
                "POINT",
                (_ct.Structure,),
                {"_fields_": [("x", wintypes.LONG), ("y", wintypes.LONG)]},
            )
        )
    ]
    user32.SendInput.argtypes = (wintypes.UINT, _ct.c_void_p, _ct.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.SetCursorPos.argtypes = (wintypes.INT, wintypes.INT)
    user32.SetCursorPos.restype = wintypes.BOOL

    class RECT(_ct.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetClientRect.argtypes = [wintypes.HWND, _ct.c_void_p]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, _ct.c_void_p]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, _ct.c_void_p]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.mouse_event.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ULONG_PTR,
    ]

    # System Tray (Shell_NotifyIcon)
    NIM_ADD = 0x00000000
    NIM_DELETE = 0x00000002
    NIF_MESSAGE = 0x00000001
    NIF_ICON = 0x00000002
    NIF_TIP = 0x00000004
    WMAPP_NOTIFYCALLBACK = 0x8001
    MF_STRING = 0x00000000
    MF_SEPARATOR = 0x00000800
    TPM_RIGHTBUTTON = 0x00000002
    TPM_RETURNCMD = 0x00000100

    class NOTIFYICONDATAW(_ct.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uVersion", wintypes.UINT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
            ("guidItem", _ct.c_byte * 16),
            ("hBalloonIcon", wintypes.HICON),
        ]

    shell32 = _ct.windll.shell32
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, _ct.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL

    user32.RegisterClassExW.argtypes = [_ct.c_void_p]
    user32.RegisterClassExW.restype = wintypes.ATOM

    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        _ct.c_int,
        _ct.c_int,
        _ct.c_int,
        _ct.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND

    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        _ct.c_int,
        _ct.c_int,
        wintypes.UINT,
    ]
    user32.LoadImageW.restype = wintypes.HANDLE

    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
    user32.LoadIconW.restype = wintypes.HICON

    user32.CreatePopupMenu.argtypes = []
    user32.CreatePopupMenu.restype = wintypes.HMENU

    user32.AppendMenuW.argtypes = [
        wintypes.HMENU,
        wintypes.UINT,
        ULONG_PTR,
        wintypes.LPCWSTR,
    ]
    user32.AppendMenuW.restype = wintypes.BOOL

    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.DestroyMenu.restype = wintypes.BOOL

    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL

    user32.TrackPopupMenu.argtypes = [
        wintypes.HMENU,
        wintypes.UINT,
        _ct.c_int,
        _ct.c_int,
        _ct.c_int,
        wintypes.HWND,
        _ct.c_void_p,
    ]
    user32.TrackPopupMenu.restype = wintypes.BOOL

    user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        ULONG_PTR,
        ULONG_PTR,
    ]
    user32.PostMessageW.restype = wintypes.BOOL

    user32.GetWindowLongW.argtypes = [wintypes.HWND, _ct.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG

    user32.SetWindowLongW.argtypes = [wintypes.HWND, _ct.c_int, wintypes.LONG]
    user32.SetWindowLongW.restype = wintypes.LONG

    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        _ct.c_int,
        _ct.c_int,
        _ct.c_int,
        _ct.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    # Window procedure callback type (LRESULT CALLBACK(HWND, UINT, WPARAM, LPARAM))
    _WNDPROC = _ct.WINFUNCTYPE(
        _ct.c_long, wintypes.HWND, wintypes.UINT, _ct.c_size_t, _ct.c_size_t
    )

_WM_TASKBARCREATED = 0


def _register_tray_msg():
    global _WM_TASKBARCREATED
    try:
        _WM_TASKBARCREATED = _ct.windll.user32.RegisterWindowMessageW("TaskbarCreated")
    except Exception:
        _WM_TASKBARCREATED = 0


def _send_input(*inputs):
    n = len(inputs)
    if n == 0:
        return
    arr = (INPUT * n)()
    for i in range(n):
        arr[i] = inputs[i]
    res = user32.SendInput(n, _ct.byref(arr), _ct.sizeof(INPUT))
    if res == 0:
        _LOG.error("SendInput failed to inject hardware events.")


def _find_autohotkey():
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, r"AutoHotkeyScript\Shell\Open\Command"
        ) as key:
            val, _ = winreg.QueryValue(key, "")
            import re

            m = re.search(r'"([^"]+)"', val)
            if m:
                cmd_path = m.group(1)
            else:
                cmd_path = val.split()[0]
            if os.path.exists(cmd_path):
                return cmd_path
    except Exception:
        pass

    try:
        local_appdata = os.environ.get("LocalAppData")
        if local_appdata:
            paths = [
                os.path.join(local_appdata, r"Programs\AutoHotkey\AutoHotkey.exe"),
                os.path.join(local_appdata, r"Programs\AutoHotkey\v2\AutoHotkey.exe"),
                os.path.join(local_appdata, r"Programs\AutoHotkey\v2\AutoHotkey64.exe"),
            ]
            for p in paths:
                if os.path.exists(p):
                    return p
    except Exception:
        pass

    pf = os.environ.get("ProgramFiles")
    pf86 = os.environ.get("ProgramFiles(x86)")
    for base in (pf, pf86):
        if base:
            paths = [
                os.path.join(base, r"AutoHotkey\AutoHotkey.exe"),
                os.path.join(base, r"AutoHotkey\v2\AutoHotkey64.exe"),
                os.path.join(base, r"AutoHotkey\v2\AutoHotkey.exe"),
                os.path.join(base, r"AutoHotkey\v1.1\AutoHotkey.exe"),
            ]
            for p in paths:
                if os.path.exists(p):
                    return p

    import shutil

    p = shutil.which("AutoHotkey") or shutil.which("AutoHotkey.exe")
    if p:
        return p

    return "AutoHotkey.exe"


def _ahk_imgclick(x, y):
    """Spawn AHK with /imgclick x y to fire a hardware left-click at (x, y).
    This bypasses Python SendInput so Roblox accepts the click.
    Falls back to SetCursorPos + _send_input if AHK is unavailable."""
    import subprocess

    try:
        ahk = _find_autohotkey()
        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "TinyKullan.ahk"
        )
        if os.path.exists(script):
            proc = subprocess.Popen(
                [ahk, script, "/imgclick", str(int(x)), str(int(y))],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.wait(timeout=2)
            return
    except Exception:
        pass
    # Fallback - use hardware-level mouse_event which Roblox accepts
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.04)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
    time.sleep(0.04)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # left up


# ── AHK persistent worker (module-level state) ────────────────────────────────
_ahk_worker_proc = None  # subprocess.Popen handle
_ahk_worker_script = None  # resolved path to TinyKullan.ahk
_ahk_worker_lock = None  # threading.Lock, initialised on first use


def _get_ahk_worker_lock():
    global _ahk_worker_lock
    if _ahk_worker_lock is None:
        _ahk_worker_lock = threading.Lock()
    return _ahk_worker_lock


def _start_ahk_worker():
    """Launch TinyKullan.ahk once with /worker and keep the Popen reference."""
    import subprocess

    global _ahk_worker_proc, _ahk_worker_script

    with _get_ahk_worker_lock():
        if _ahk_worker_proc is not None and _ahk_worker_proc.poll() is None:
            return True

        try:
            ahk = _find_autohotkey()
            script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "TinyKullan.ahk"
            )
            if not os.path.exists(script):
                return False

            _ahk_worker_script = script
            _ahk_worker_proc = subprocess.Popen(
                [ahk, script, "/worker"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            _ahk_worker_proc = None
            return False


def _ahk_send_command(cmd):
    """Write *cmd* to a temp signal file that the AHK /worker process polls."""
    global _ahk_worker_proc

    with _get_ahk_worker_lock():
        if _ahk_worker_proc is None or _ahk_worker_proc.poll() is not None:
            return False

    try:
        tmp_dir = (
            os.environ.get("TEMP")
            or os.environ.get("TMP")
            or os.path.dirname(os.path.abspath(__file__))
        )
        signal_path = os.path.join(tmp_dir, "TinyKullan_ahk_cmd.txt")
        with open(signal_path, "w", encoding="utf-8") as fh:
            fh.write(cmd + "\n")
        return True
    except Exception:
        return False


def _write_csv_macro(events, filepath):
    import csv
    import urllib.parse

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        for ev in events:
            t = ev.get("t", "")
            x = int(ev.get("x", 0))
            y = int(ev.get("y", 0))
            btn = ev.get("btn", ev.get("b", ""))
            vk = int(ev.get("vk", 0))
            scan = int(ev.get("scan", ev.get("sc", 0)))
            ext = 1 if ev.get("ext", False) else 0
            delta = int(ev.get("delta", 0))
            custom_name = urllib.parse.quote(ev.get("custom_name", ""), safe="")
            if "up" in ev:
                # Recorded event: single row with inter-event delay
                d = int(ev.get("d", 0))
                up = 1 if ev.get("up", False) else 0
                writer.writerow(
                    [t, d, x, y, btn, up, vk, scan, ext, delta, custom_name]
                )
            elif t in ("C", "K"):
                # Hand-crafted click/key: emit down+up pair so AHK respects hold.
                # AHK's LoadMacroFile accumulates delay BEFORE assigning ev.d,
                # so the hold delay must be on the UP row.
                hold_ms = max(1, int(ev.get("d", 0)))
                writer.writerow([t, 0, x, y, btn, 0, vk, scan, ext, delta, custom_name])
                writer.writerow(
                    [t, hold_ms, x, y, btn, 1, vk, scan, ext, delta, custom_name]
                )
            else:
                # Move / scroll / delay / other
                d = int(ev.get("d", 0))
                up = 1 if ev.get("s", "Down") == "Up" else 0
                writer.writerow(
                    [t, d, x, y, btn, up, vk, scan, ext, delta, custom_name]
                )


def _read_csv_macro(filepath):
    if not os.path.exists(filepath):
        return []

    import csv
    import urllib.parse

    events = []
    with open(filepath, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for parts in reader:
            if not parts:
                continue
            if len(parts) < 10:
                continue
            t = parts[0]
            d = int(parts[1])
            x = int(parts[2])
            y = int(parts[3])
            btn = parts[4]
            up = parts[5] == "1"
            vk = int(parts[6])
            scan = int(parts[7])
            ext = parts[8] == "1"
            delta = int(parts[9])
            custom_name = ""
            if len(parts) >= 11:
                custom_name = urllib.parse.unquote(parts[10])

            ev = {
                "t": t,
                "d": d,
                "x": x,
                "y": y,
                "up": up,
                "vk": vk,
                "scan": scan,
                "ext": ext,
                "delta": delta,
            }
            if custom_name:
                ev["custom_name"] = custom_name
            if t in ("C", "click"):
                ev["btn"] = btn
            if t in ("K", "key"):
                ev["sc"] = scan
            if t in ("C", "K"):
                ev["s"] = "Up" if up else "Down"
            events.append(ev)
    return events


# ── Compact run file format ───────────────────────────────────────────────────
# TYPE|DURATION|DATA
# Types: MOVE, MOUSE_DOWN, MOUSE_UP, KEY_DOWN, KEY_UP, SCROLL, SCROLL_H
# Duration: ms since previous event
#

_VK_READABLE = {
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    0x10: "Shift",
    0x11: "Control",
    0x12: "Alt",
    0x1B: "Escape",
    0x20: "Space",
    0x2E: "Delete",
    0x5B: "LWin",
    0x5C: "RWin",
    0xA0: "LShift",
    0xA1: "RShift",
    0xA2: "LControl",
    0xA3: "RControl",
    0xA4: "LAlt",
    0xA5: "RAlt",
}


def _vk_to_compact_name(vk, scan=0):
    """Convert VK code to readable key name for compact format."""
    if not vk:
        return ""
    if vk in _VK_READABLE:
        return _VK_READABLE[vk]
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return f"VK{vk}"


def _write_compact_run(events, filepath):
    """Save events in compact pipe-delimited format.
    Produces files ~80% smaller than JSON with no structural bloat.
    """
    import urllib.parse

    total = len(events)
    now_str = datetime.now().strftime("%Y%m%d%H%M%S")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# TinyKullan Recording\n")
        f.write(f"# Generated: {now_str}\n")
        f.write(f"# Total Events: {total}\n")
        f.write("#\n")
        f.write("# TYPE|DURATION|DATA\n")
        f.write("#\n")

        for ev in events:
            t = ev.get("t", "")
            d = ev.get("d", 0)
            if isinstance(d, float):
                d = max(0, int(d))
            else:
                d = max(0, int(d))

            if t == "M":
                x = ev.get("x", 0)
                y = ev.get("y", 0)
                prefix = "REL_" if ev.get("rel") else ""
                f.write(f"{prefix}MOVE|{d}|{x},{y}\n")

            elif t == "C":
                up = ev.get("up", False)
                typ = "MOUSE_UP" if up else "MOUSE_DOWN"
                if ev.get("rel"):
                    typ = "REL_" + typ
                x = ev.get("x", 0)
                y = ev.get("y", 0)
                btn = ev.get("btn", "left")
                f.write(f"{typ}|{d}|{x},{y}|{btn}\n")

            elif t == "K":
                up = ev.get("up", False)
                typ = "KEY_UP" if up else "KEY_DOWN"
                vk = ev.get("vk", 0)
                scan = ev.get("scan", 0)
                name = _vk_to_compact_name(vk, scan)
                if name:
                    f.write(f"{typ}|{d}|{name}\n")
                else:
                    f.write(f"{typ}|{d}|VK{vk}\n")

            elif t in ("W", "WH"):
                typ = "SCROLL_H" if t == "WH" else "SCROLL"
                delta = ev.get("delta", 0)
                f.write(f"{typ}|{d}|{delta}\n")

            elif t == "I":
                name = urllib.parse.quote(ev.get("name", ""), safe="")
                action = ev.get("action", "click")
                f.write(f"IMAGE|{d}|{name}|{action}\n")

            elif t == "B":
                name = urllib.parse.quote(ev.get("name", ""), safe="")
                skip = ev.get("skip", 1)
                f.write(f"BRANCH|{d}|{name}|{skip}\n")

            elif t == "R":
                name = urllib.parse.quote(ev.get("name", ""), safe="")
                f.write(f"RUN|{d}|{name}\n")

            elif t == "D":
                f.write(f"DELAY|{d}|\n")


def _read_compact_run(filepath):
    """Load events from compact pipe-delimited format."""
    import urllib.parse

    events = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if len(parts) < 2:
                continue

            typ = parts[0]
            try:
                d = int(parts[1])
            except ValueError:
                d = 0

            if typ in ("MOVE", "REL_MOVE"):
                rel = typ.startswith("REL_")
                if len(parts) >= 3 and "," in parts[2]:
                    try:
                        xy = parts[2].split(",")
                        x, y = int(xy[0]), int(xy[1])
                    except (ValueError, IndexError):
                        continue
                    ev = {"t": "M", "d": d, "x": x, "y": y}
                    if rel:
                        ev["rel"] = True
                    events.append(ev)

            elif typ in ("MOUSE_DOWN", "MOUSE_UP", "REL_MOUSE_DOWN", "REL_MOUSE_UP"):
                rel = typ.startswith("REL_")
                up = typ.endswith("_UP") or typ == "MOUSE_UP" or typ == "REL_MOUSE_UP"
                if len(parts) >= 3 and "," in parts[2]:
                    try:
                        xy = parts[2].split(",")
                        x, y = int(xy[0]), int(xy[1])
                    except (ValueError, IndexError):
                        continue
                    btn = parts[3] if len(parts) >= 4 else "left"
                    ev = {"t": "C", "d": d, "btn": btn, "up": up, "x": x, "y": y}
                    if rel:
                        ev["rel"] = True
                    events.append(ev)

            elif typ in ("KEY_DOWN", "KEY_UP"):
                up = typ == "KEY_UP"
                key_name = parts[2] if len(parts) >= 3 else ""
                vk = _name_to_vk(key_name)
                scan = 0
                if vk:
                    try:
                        scan = user32.MapVirtualKeyW(vk, 0)
                    except Exception:
                        pass
                if not vk and key_name.startswith("VK"):
                    try:
                        vk = int(key_name[2:])
                    except ValueError:
                        vk = 0
                events.append({"t": "K", "d": d, "vk": vk, "scan": scan, "up": up})

            elif typ == "SCROLL":
                try:
                    delta = int(parts[2]) if len(parts) >= 3 else 0
                except ValueError:
                    delta = 0
                events.append({"t": "W", "d": d, "delta": delta})

            elif typ == "SCROLL_H":
                try:
                    delta = int(parts[2]) if len(parts) >= 3 else 0
                except ValueError:
                    delta = 0
                events.append({"t": "WH", "d": d, "delta": delta})

            elif typ == "IMAGE":
                name = urllib.parse.unquote(parts[2]) if len(parts) >= 3 else ""
                action = parts[3] if len(parts) >= 4 else "click"
                events.append(
                    {"t": "I", "d": d, "name": name, "img": name, "action": action}
                )

            elif typ == "BRANCH":
                name = urllib.parse.unquote(parts[2]) if len(parts) >= 3 else ""
                try:
                    skip = int(parts[3]) if len(parts) >= 4 else 1
                except ValueError:
                    skip = 1
                events.append(
                    {"t": "B", "d": d, "name": name, "img": name, "skip": skip}
                )

            elif typ == "RUN":
                name = urllib.parse.unquote(parts[2]) if len(parts) >= 3 else ""
                events.append({"t": "R", "d": d, "name": name})

            elif typ == "DELAY":
                events.append({"t": "D", "d": d})

    return events


def _abs(x, y):
    sw = user32.GetSystemMetrics(78)
    sh = user32.GetSystemMetrics(79)
    sx = user32.GetSystemMetrics(76)
    sy = user32.GetSystemMetrics(77)
    if sw == 0 or sh == 0:
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        sx = sy = 0
    return int(round((x - sx) * 65535.0 / max(sw - 1, 1))), int(
        round((y - sy) * 65535.0 / max(sh - 1, 1))
    )


def _mouse_move(x, y):
    ax, ay = _abs(x, y)
    i = INPUT()
    i.type = 0
    i.union.mi.dx = ax
    i.union.mi.dy = ay
    i.union.mi.mouseData = 0
    i.union.mi.dwFlags = 0x0001 | 0x8000 | 0x4000  # MOVE | ABSOLUTE | VIRTUALDESK
    i.union.mi.time = 0
    i.union.mi.dwExtraInfo = 0
    return i


def _mouse_move_rel(dx, dy):
    i = INPUT()
    i.type = 0
    i.union.mi.dx = int(dx)
    i.union.mi.dy = int(dy)
    i.union.mi.mouseData = 0
    i.union.mi.dwFlags = 0x0001
    i.union.mi.time = 0
    i.union.mi.dwExtraInfo = 0
    return i


_BTN_FLAGS = {
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
    "x1": (0x0080, 0x0100),
    "x2": (0x0080, 0x0100),
}


def _mouse_click(x, y, btn, up):
    ax, ay = _abs(x, y)
    i = INPUT()
    i.type = 0
    i.union.mi.dx = ax
    i.union.mi.dy = ay

    b = btn.lower().replace("button.", "")
    down_f, up_f = _BTN_FLAGS.get(b, (0, 0))
    flags = 0x0001 | 0x8000 | 0x4000  # MOVE | ABSOLUTE | VIRTUALDESK
    flags |= up_f if up else down_f

    i.union.mi.dwFlags = flags
    if b == "x1":
        i.union.mi.mouseData = 0x0001
    elif b == "x2":
        i.union.mi.mouseData = 0x0002
    else:
        i.union.mi.mouseData = 0

    i.union.mi.time = 0
    i.union.mi.dwExtraInfo = 0
    return i


def _mouse_button(btn, up, use_abs=False):
    """Fire a mouse button event at the current cursor position.
    C-6: x1/x2 differ only by mouseData (not flags) — handled below.
    Caller is responsible for moving the cursor first via SetCursorPos or _mouse_move_rel."""
    i = INPUT()
    i.type = 0
    i.union.mi.dx = 0
    i.union.mi.dy = 0
    i.union.mi.dwFlags = 0  # no MOVE — cursor is already at target

    b = btn.lower().replace("button.", "")
    down_f, up_f = _BTN_FLAGS.get(b, (0, 0))
    i.union.mi.dwFlags |= up_f if up else down_f
    if b == "x1":
        i.union.mi.mouseData = 0x0001
    elif b == "x2":
        i.union.mi.mouseData = 0x0002
    else:
        i.union.mi.mouseData = 0
    i.union.mi.time = 0
    i.union.mi.dwExtraInfo = 0
    return i


def _mouse_wheel(x, y, delta, h=False):
    ax, ay = _abs(x, y)
    i = INPUT()
    i.type = 0
    i.union.mi.dx = ax
    i.union.mi.dy = ay
    i.union.mi.dwFlags = 0x0001 | 0x8000 | 0x4000 | (0x1000 if h else 0x0800)
    i.union.mi.mouseData = _ct.c_ulong(delta & 0xFFFFFFFF).value
    i.union.mi.time = 0
    i.union.mi.dwExtraInfo = 0
    return i


def _make_key(vk, scan, up, ext=False):
    i = INPUT()
    i.type = 1
    i.union.ki.wVk = vk
    i.union.ki.wScan = scan
    flags = 0
    if scan:
        flags |= 0x0008  # KEYEVENTF_SCANCODE
    if up:
        flags |= 0x0002  # KEYEVENTF_KEYUP
    if ext:
        flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
    i.union.ki.dwFlags = flags
    i.union.ki.time = 0
    i.union.ki.dwExtraInfo = 0
    return i


def _is_physically_down(vk):
    """Return True if the key is physically held (hardware press).

    GetAsyncKeyState reads the physical interrupt-level keyboard state.
    Injected events from SendInput do NOT set this bit, so this reliably
    distinguishes real user keypresses from macro-replayed ones.
    """
    return (user32.GetAsyncKeyState(vk) & 0x8000) != 0


_PYNPUT_BTN = {
    _pmouse.Button.left: "left",
    _pmouse.Button.right: "right",
    _pmouse.Button.middle: "middle",
}
try:
    _PYNPUT_BTN[_pmouse.Button.x1] = "x1"
    _PYNPUT_BTN[_pmouse.Button.x2] = "x2"
except AttributeError:
    pass

_EXTENDED_VKS = {
    0xA1,  # right shift
    0xA3,  # right ctrl
    0xA5,  # right alt
    0x5B,  # left windows
    0x5C,  # right windows
    0x21,  # page up
    0x22,  # page down
    0x23,  # end
    0x24,  # home
    0x25,  # left arrow
    0x26,  # up arrow
    0x27,  # right arrow
    0x28,  # down arrow
    0x2D,  # insert
    0x2E,  # delete
    0x6F,  # numpad divide
    0x2C,  # print screen
    0x90,  # num lock
}


def _vk_to_name(vk):
    if isinstance(vk, str):
        return vk
    if not vk:
        return ""
    vk = int(vk)
    names = {
        0x08: "backspace",
        0x09: "tab",
        0x0D: "enter",
        0x10: "shift",
        0x11: "ctrl",
        0x12: "alt",
        0x1B: "esc",
        0x20: "space",
        0x25: "left",
        0x26: "up",
        0x27: "right",
        0x28: "down",
        0x2E: "delete",
        0x5B: "win",
    }
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return names.get(vk, f"0x{vk:02X}")


def _normalize_key_name(name):
    """Normalize pynput left/right modifier variants to canonical names."""
    _MOD_MAP = {
        "shift_l": "shift",
        "shift_r": "shift",
        "ctrl_l": "ctrl",
        "ctrl_r": "ctrl",
        "alt_l": "alt",
        "alt_gr": "alt",
        "cmd_l": "cmd",
        "cmd_r": "cmd",
    }
    return _MOD_MAP.get(name, name)


def _key_to_vk(key):
    if hasattr(key, "vk") and key.vk:
        vk = key.vk
    elif hasattr(key, "value") and hasattr(key.value, "vk") and key.value.vk:
        vk = key.value.vk
    else:
        k_str = str(key).lower()
        if k_str in ("key.shift", "key.shift_r", "key.shift_l"):
            vk = 0x10
        elif k_str in ("key.ctrl", "key.ctrl_l", "key.ctrl_r"):
            vk = 0x11
        elif k_str in ("key.alt", "key.alt_l", "key.alt_gr"):
            vk = 0x12
        elif k_str in ("key.cmd", "key.cmd_r", "key.cmd_l"):
            vk = 0x5B
        elif k_str == "key.tab":
            vk = 0x09
        elif k_str == "key.esc":
            vk = 0x1B
        elif k_str == "key.space":
            vk = 0x20
        elif k_str == "key.enter":
            vk = 0x0D
        elif k_str == "key.backspace":
            vk = 0x08
        elif k_str == "key.delete":
            vk = 0x2E
        else:
            ch = getattr(key, "char", None)
            if ch and len(ch) == 1:
                if "a" <= ch.lower() <= "z":
                    vk = ord(ch.upper())
                elif "0" <= ch <= "9":
                    vk = ord(ch)
                else:
                    vk = 0
            else:
                vk = 0
    if vk and vk not in _VK_SCAN_CACHE:
        _VK_SCAN_CACHE[vk] = user32.MapVirtualKeyW(vk, 0)
    return vk, _VK_SCAN_CACHE.get(vk, 0), (vk in _EXTENDED_VKS)


_VK_SCAN_CACHE = {}
SPI_GETBEEP = 0x0001
SPI_SETBEEP = 0x0002
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020


class _UIGrid:
    """Responsive grid config — edit once, propagates everywhere."""

    WW: int = 343  # window width
    TH: int = 28  # title-bar height
    BH: int = 54  # button-bar height
    CW: int = 49  # column width


# Standard layout grid parameters (Default/Tiny Mode)
_STD_WW: int = 343  # Window Width
_STD_TH: int = 28  # Title Bar Height
_STD_BH: int = 54  # Button Row Height
_STD_CW: int = 49  # Column Widget Width

# BIG Mode layout grid parameters
_BIG_WW: int = 490  # Expanded Window Width
_BIG_TH: int = 28  # Title bar height (always matches STD — uniform across modes)
_BIG_BH: int = 80  # Expanded Button Row Height
_BIG_CW: int = 70  # Expanded Column Widget Width

_UI = _UIGrid()
WW, TH, BH, CW = _STD_WW, _STD_TH, _STD_BH, _STD_CW
BWW, BTH, BBH, BCW = _BIG_WW, _BIG_TH, _BIG_BH, _BIG_CW


def _get_save_dir():
    # Dynamic cross-platform desktop/documents directory detector
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        return desktop / "TinyKullan"
    documents = Path.home() / "Documents"
    if documents.is_dir():
        return documents / "TinyKullan"
    return Path.home() / "TinyKullan"


BASE_SAVE_PATH = _get_save_dir()
INI_PATH = BASE_SAVE_PATH / "Saves" / "TinyKullan.ini"
RUNS_PATH = BASE_SAVE_PATH / "Saves" / "runs"
RUN_FAV_PATH = BASE_SAVE_PATH / "Saves" / "run_favorites.json"
IMAGE_DET_JSON = BASE_SAVE_PATH / "Saves" / "image_detection.json"
IMAGES_PATH = BASE_SAVE_PATH / "Saves" / "images"
SHOT_PATH = Path(r"C:\TinyKullan\Assets\ScreenShots")
_log_path = BASE_SAVE_PATH / "Saves" / "tinykullan.log"
try:
    _log_path.parent.mkdir(parents=True, exist_ok=True)
    _fh = logging.FileHandler(str(_log_path), encoding="utf-8")
    _fh.setLevel(logging.WARNING)
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _LOG.addHandler(_fh)
except Exception:
    pass

# ── Auto-create folder structure on first run ────────────────────────────────
for _dir in [
    RUNS_PATH,
    IMAGES_PATH,
    SHOT_PATH,
]:
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

DEFAULT_THEME = {"primary": "#1D1128", "secondary": "#C3A5E5", "accent": "#7c5cfc"}
_FC = {"go": "#22c55e", "rec": "#ef4444", "loop": "#f59e0b"}


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_hex(r, g, b):
    return f"#{max(0, min(255, int(r))):02x}{max(0, min(255, int(g))):02x}{max(0, min(255, int(b))):02x}"


def _blend(c1, c2, t):
    r1, g1, b1 = _hex_rgb(c1)
    r2, g2, b2 = _hex_rgb(c2)
    return _rgb_hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


def _lighten(c, f):
    r, g, b = _hex_rgb(c)
    return _rgb_hex(r + (255 - r) * f, g + (255 - g) * f, b + (255 - b) * f)


def _darken(c, f):
    r, g, b = _hex_rgb(c)
    return _rgb_hex(r * (1 - f), g * (1 - f), b * (1 - f))


def _derive(theme):
    pri, sec, acc = theme["primary"], theme["secondary"], theme["accent"]
    return {
        "top": pri,
        "bg": sec,
        "sep": pri,
        "pill": _blend(pri, sec, 0.3),
        "acc": _blend(sec, acc, 0.4),
        "go": _FC["go"],
        "rec": _FC["rec"],
        "loop": _FC["loop"],
        "icon_fg": pri,
        "lbl_fg": pri,
        "title_fg": sec,
        "status_fg": "#ffffff",
        "font_fg": _lighten(sec, 0.9),
    }


_C = _derive(DEFAULT_THEME)
SBG = SSURF = SBORD = SACC = SACC_D = SREC = SPLAY = STEXT = SMUTED = SED = SEDB = ""


def _update_sp(theme=None):
    global SBG, SSURF, SBORD, SACC, SACC_D, SREC, SPLAY, STEXT, SMUTED, SED, SEDB
    pri = _C["top"]
    acc = (
        theme.get("accent", "#7c5cfc")
        if theme
        else DEFAULT_THEME.get("accent", "#7c5cfc")
    )
    SBG = _darken(pri, 0.3)
    SSURF = _blend(SBG, pri, 0.4)
    SBORD = _blend(SBG, "#ffffff", 0.15)
    SACC = acc
    SACC_D = _darken(acc, 0.25)
    SREC = _FC["rec"]
    SPLAY = _FC["go"]
    STEXT = _lighten(pri, 0.85)
    SMUTED = _blend(STEXT, SBG, 0.35)
    SED = _blend(SBG, pri, 0.3)
    SEDB = _blend(SED, "#ffffff", 0.15)


_update_sp()
_SPIN = ["⬡", "⬣", "⬡", "⬢"]
_DICE = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
_APP_PAD = 8


def _round_hwnd(hwnd):
    if sys.platform != "win32":
        return
    try:
        _ct.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, _ct.byref(_ct.c_int(2)), 4)
    except Exception:
        pass


def _set_alpha(hwnd, alpha):
    if sys.platform != "win32":
        return
    try:
        alpha = max(0, min(255, int(alpha)))
        s = _ct.windll.user32.GetWindowLongW(hwnd, -20)
        _ct.windll.user32.SetWindowLongW(hwnd, -20, s | 0x80000)
        _ct.windll.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, 0x02)
    except Exception as e:
        _LOG.warning("_set_alpha: %s", e)


def _get_hwnd(wid):
    GA_ROOT = 2
    hwnd = _ct.windll.user32.GetAncestor(wid, GA_ROOT)
    return hwnd or wid


def _make_single_desktop_app_window(hwnd):
    if sys.platform != "win32":
        return
    try:
        exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        exstyle = (exstyle & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)
        user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
    except Exception as e:
        _LOG.warning("single desktop window style failed: %s", e)


def _load_tray_icon(path_str):
    """Load a PNG, resize to tray-icon sizes, save as .ico, return HICON.
    If path is empty or missing, generates a high-quality custom theme-colored icon."""
    if sys.platform != "win32":
        return 0
    try:
        from PIL import Image, ImageDraw

        if path_str and os.path.exists(path_str):
            img = Image.open(path_str).convert("RGBA")
        else:
            # Generate custom high-quality violet round play icon matching the TinyKullan theme
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((4, 4, 60, 60), fill="#7c5cfc", outline="#a38eff", width=4)
            draw.polygon([(24, 18), (24, 48), (48, 33)], fill="white")

        img = img.resize((32, 32), Image.Resampling.LANCZOS)
        # Choose a safe write path
        if path_str:
            tmp = Path(path_str).parent / "_tray_icon.ico"
        else:
            tmp = Path.cwd() / "_tray_icon.ico"

        img.save(str(tmp), format="ICO", sizes=[(16, 16), (32, 32)])
        hicon = _ct.windll.user32.LoadImageW(0, str(tmp), 1, 0, 0, 0x00000010)
        if hicon:
            return hicon
        _LOG.warning("LoadImageW returned null for %s", str(tmp))
    except Exception as e:
        _LOG.warning("Tray icon load failed (attempting fallback): %s", e)
    try:
        return _ct.windll.user32.LoadIconW(0, 32512)  # IDI_APPLICATION
    except Exception:
        return 0


def _ping():
    pass


def _pick_directory(parent=None, title="Select Folder", initial_dir=None):
    if initial_dir is None:
        initial_dir = str(Path.home())
    return (
        filedialog.askdirectory(parent=parent, title=title, initialdir=initial_dir)
        or ""
    )


def _pick_file(parent=None, title="Select File", filetypes=None, initial_dir=None):
    if initial_dir is None:
        initial_dir = str(Path.home())
    return (
        filedialog.askopenfilename(
            parent=parent,
            title=title,
            filetypes=filetypes or [],
            initialdir=initial_dir,
        )
        or ""
    )


def _save_file(
    parent=None,
    title="Save File",
    default_ext=".json",
    filetypes=None,
    initial_dir=None,
):
    if initial_dir is None:
        initial_dir = str(Path.home())
    return (
        filedialog.asksaveasfilename(
            parent=parent,
            title=title,
            defaultextension=default_ext,
            filetypes=filetypes or [],
            initialdir=initial_dir,
        )
        or ""
    )


def _ms():
    return int(time.perf_counter() * 1000)


def _grab_screen(mss_instance=None):
    """M-2 fix: accepts optional persistent mss instance for reuse. Falls back to ImageGrab."""
    try:
        if mss_instance is not None:
            monitor = mss_instance.monitors[0]
            img = mss_instance.grab(monitor)
            return Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
        with _mss.mss() as sct:
            monitor = sct.monitors[0]
            img = sct.grab(monitor)
            return Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
    except Exception:
        return ImageGrab.grab()


def _valid_ev(ev):
    if not (isinstance(ev, dict) and "d" in ev):
        return False
    t = ev.get("t", "")
    if t not in ("M", "C", "K", "W", "WH", "I", "R", "D", "B"):
        return False
    if t == "M" and ("x" not in ev or "y" not in ev):
        return False
    if t == "C" and ("x" not in ev or "y" not in ev):
        return False
    if t == "K" and ("vk" not in ev):
        return False
    return True


def _fmt_frog_dur(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"


class Config:
    def __init__(self):
        self.key_record: str = "f5"
        self.key_play: str = "f6"
        self.key_loop: str = "f7"
        self.key_save: str = "f8"
        self.key_autoclick: str = "f4"
        self.key_pause: str = "f9"
        self.key_stop: str = "esc"
        self.save_path: str = ""
        self.shot_folder: str = r"C:\TinyKullan\Assets\ScreenShots"
        self.webhook_url: str = ""
        self.mention_id: str = ""
        self.wh_record: bool = True
        self.wh_play: bool = True
        self.wh_loop: bool = True
        self.wh_save: bool = False
        self.wh_screenshot: bool = True
        self.img_det_enabled: bool = True
        self.img_detect_while_recording: bool = False
        self.speed: float = 1.0
        self.alpha_focused: int = 245
        self.alpha_unfocused: int = 160
        self.tiny_mode: bool = False
        self.tiny_record: bool = True
        self.tiny_play: bool = True
        self.tiny_loop: bool = True
        self.tiny_save: bool = True
        self.tiny_pause: bool = True
        self.tiny_delete: bool = True
        self.tiny_edit: bool = True
        self.tiny_settings: bool = True
        self.autoclick_cps: float = 10.0
        self.autoclick_btn: str = "Left"
        self.draw_width: float = 5.0
        self.draw_opacity: int = 100
        self.ico_record: str = "\U0001f3b2"
        self.ico_play: str = "\u25b6"
        self.ico_loop: str = "\u2733"
        self.ico_save: str = "\U0001f4be"
        self.ico_delete: str = "\U0001f5d1"
        self.ico_settings: str = "\u2699"
        self.auto_focus: bool = False
        self.theme: dict = dict(DEFAULT_THEME)
        self.stats_total_minutes: float = 0.0
        self.stats_run_count: int = 0
        self.stats_custom_title: str = ""
        self.dash_badge_texts: dict = None
        self.dash_badge_icons: dict = None
        self.dash_title: str = "Macro<br>Dashboard"
        self.dash_subtitle: str = "A polished performance card for showing your TinyKullan grind: total runs, playtime, rank progress, badges, and session flex stats."
        self.dash_bg_color: str = "#090511"
        self.dash_rank_names: dict = None
        self.dash_rank_emojis: dict = None
        self.roblox_enabled: bool = False
        self.roblox_disconnect_img: str = ""
        self.roblox_server_link: str = ""
        self.roblox_mode: str = "Deeplink"
        self.roblox_wait_time: float = 5.0
        self.roblox_recovery_run: str = ""
        self.always_on_top: bool = False
        self.record_relative_to_window: bool = False
        self.big_mode: bool = False

    @property
    def DEFAULTS(self):
        return {
            "key_record": "f5",
            "key_play": "f6",
            "key_loop": "f7",
            "key_save": "f8",
            "key_autoclick": "f4",
            "key_pause": "f9",
            "key_stop": "esc",
            "save_path": "",
            "shot_folder": r"C:\TinyKullan\Assets\ScreenShots",
            "webhook_url": "",
            "mention_id": "",
            "wh_record": True,
            "wh_play": True,
            "wh_loop": True,
            "wh_save": False,
            "wh_screenshot": True,
            "img_det_enabled": True,
            "img_detect_while_recording": False,
            "speed": 1.0,
            "alpha_focused": 245,
            "alpha_unfocused": 160,
            "tiny_mode": False,
            "tiny_record": True,
            "tiny_play": True,
            "tiny_loop": True,
            "tiny_save": True,
            "tiny_pause": True,
            "tiny_delete": True,
            "tiny_edit": True,
            "tiny_settings": True,
            "autoclick_cps": 10.0,
            "autoclick_btn": "Left",
            "draw_width": 5.0,
            "draw_opacity": 100,
            "ico_record": "\U0001f3b2",
            "ico_play": "\u25b6",
            "ico_loop": "\u2733",
            "ico_save": "\U0001f4be",
            "ico_delete": "\U0001f5d1",
            "ico_settings": "\u2699",
            "auto_focus": False,
            "stats_total_minutes": 0.0,
            "stats_run_count": 0,
            "stats_custom_title": "",
            "dash_badge_texts": "{}",
            "dash_badge_icons": "{}",
            "dash_title": "Macro<br>Dashboard",
            "dash_subtitle": "A polished performance card for showing your TinyKullan grind: total runs, playtime, rank progress, badges, and session flex stats.",
            "dash_bg_color": "#090511",
            "dash_rank_names": "{}",
            "dash_rank_emojis": "{}",
            "roblox_enabled": False,
            "roblox_disconnect_img": "",
            "roblox_server_link": "",
            "roblox_mode": "Deeplink",
            "roblox_wait_time": 5.0,
            "roblox_recovery_run": "",
            "always_on_top": False,
            "record_relative_to_window": False,
            "big_mode": False,
        }

    def load(self):
        if not INI_PATH.exists():
            return
        cfg = configparser.ConfigParser()
        for enc in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                cfg.read(INI_PATH, encoding=enc)
                break
            except Exception:
                continue

        g = cfg.get

        def b(s, k, fb):
            return cfg.getboolean(s, k, fallback=fb)

        self.key_record = g("Hotkeys", "Record", fallback=self.key_record)
        self.key_play = g("Hotkeys", "Play", fallback=self.key_play)
        self.key_loop = g("Hotkeys", "Loop", fallback=self.key_loop)
        self.key_save = g("Hotkeys", "Save", fallback=self.key_save)
        self.key_autoclick = g("Hotkeys", "AutoClick", fallback=self.key_autoclick)
        self.key_pause = g("Hotkeys", "Pause", fallback=self.key_pause)
        self.key_stop = g("Hotkeys", "Stop", fallback=self.key_stop)
        self.save_path = g("UI", "SavePath", fallback="")
        self.shot_folder = g("UI", "ShotFolder", fallback=self.shot_folder) or self.shot_folder
        for attr, section, key, cast in [
            ("speed", "UI", "Speed", float),
            ("alpha_focused", "UI", "AlphaFocused", int),
            ("alpha_unfocused", "UI", "AlphaUnfocused", int),
        ]:
            try:
                setattr(
                    self, attr, cast(g(section, key, fallback=str(getattr(self, attr))))
                )
            except ValueError:
                pass
        self.webhook_url = g("Webhook", "URL", fallback="")
        self.mention_id = g("Webhook", "MentionID", fallback="")
        self.wh_record = b("Webhook", "OnRecord", True)
        self.wh_play = b("Webhook", "OnPlay", True)
        self.wh_loop = b("Webhook", "OnLoop", True)
        self.wh_save = b("Webhook", "OnSave", False)
        self.wh_screenshot = b("Webhook", "Screenshot", True)
        self.img_det_enabled = b("ImageDetection", "Enabled", True)
        self.img_detect_while_recording = b("ImageDetection", "WhileRecording", False)
        self.roblox_enabled = b("Roblox", "Enabled", False)
        self.roblox_disconnect_img = g("Roblox", "DisconnectImg", fallback="")
        self.roblox_server_link = g("Roblox", "ServerLink", fallback="")
        self.roblox_mode = g("Roblox", "Mode", fallback="Deeplink")
        self.roblox_recovery_run = g("Roblox", "RecoveryRun", fallback="")
        try:
            self.roblox_wait_time = float(g("Roblox", "WaitTime", fallback="5.0"))
        except ValueError:
            pass
        self.tiny_mode = b("UI", "TinyMode", False)
        self.tiny_record = b("UI", "TinyRecord", True)
        self.tiny_play = b("UI", "TinyPlay", True)
        self.tiny_loop = b("UI", "TinyLoop", True)
        self.tiny_save = b("UI", "TinySave", True)
        self.tiny_pause = b("UI", "TinyPause", True)
        self.tiny_delete = b("UI", "TinyDelete", True)
        self.tiny_edit = b("UI", "TinyEdit", True)
        self.tiny_settings = b("UI", "TinySettings", True)
        try:
            self.draw_width = float(
                g("Drawing", "Width", fallback=str(self.draw_width))
            )
        except ValueError:
            pass
        try:
            self.draw_opacity = int(
                g("Drawing", "Opacity", fallback=str(self.draw_opacity))
            )
        except ValueError:
            pass
        try:
            self.autoclick_cps = float(
                g("AutoClick", "CPS", fallback=str(self.autoclick_cps))
            )
        except ValueError:
            pass
        self.autoclick_btn = g("AutoClick", "Button", fallback=self.autoclick_btn)
        self.auto_focus = b("UI", "AutoFocus", False)
        self.always_on_top = b("UI", "AlwaysOnTop", False)
        self.record_relative_to_window = b("UI", "RecordRelToWindow", False)
        self.big_mode = b("UI", "BigMode", False)
        try:
            self.stats_total_minutes = float(g("Stats", "TotalMinutes", fallback="0"))
        except ValueError:
            pass
        try:
            self.stats_run_count = int(g("Stats", "RunCount", fallback="0"))
        except ValueError:
            pass
        self.stats_custom_title = g("Stats", "CustomTitle", fallback="")
        try:
            self.dash_badge_texts = json.loads(
                g("Dashboard", "BadgeTexts", fallback="{}")
            )
        except Exception:
            self.dash_badge_texts = {}
        try:
            self.dash_badge_icons = json.loads(
                g("Dashboard", "BadgeIcons", fallback="{}")
            )
        except Exception:
            self.dash_badge_icons = {}
        self.dash_title = g("Dashboard", "Title", fallback=self.dash_title)
        self.dash_subtitle = g("Dashboard", "Subtitle", fallback=self.dash_subtitle)
        self.dash_bg_color = g("Dashboard", "BgColor", fallback=self.dash_bg_color)
        try:
            self.dash_rank_names = json.loads(
                g("Dashboard", "RankNames", fallback="{}")
            )
        except Exception:
            self.dash_rank_names = {}
        try:
            self.dash_rank_emojis = json.loads(
                g("Dashboard", "RankEmojis", fallback="{}")
            )
        except Exception:
            self.dash_rank_emojis = {}
        if cfg.has_section("Icons"):
            for attr, key in [
                ("ico_record", "Record"),
                ("ico_play", "Play"),
                ("ico_loop", "Loop"),
                ("ico_save", "Save"),
                ("ico_delete", "Delete"),
                ("ico_settings", "Settings"),
            ]:
                val = cfg.get("Icons", key, fallback="")
                if val:
                    setattr(self, attr, val)
        if cfg.has_section("Theme"):
            for k in self.theme:
                self.theme[k] = cfg.get("Theme", k, fallback=self.theme[k])

    def save(self):
        INI_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg = configparser.ConfigParser()
        cfg["Hotkeys"] = {
            "Record": self.key_record,
            "Play": self.key_play,
            "Loop": self.key_loop,
            "Save": self.key_save,
            "AutoClick": self.key_autoclick,
            "Pause": self.key_pause,
            "Stop": self.key_stop,
        }
        cfg["UI"] = {
            "SavePath": self.save_path,
            "ShotFolder": self.shot_folder,
            "Speed": str(self.speed),
            "AlphaFocused": str(self.alpha_focused),
            "AlphaUnfocused": str(self.alpha_unfocused),
            "AutoFocus": "1" if self.auto_focus else "0",
            "AlwaysOnTop": "1" if self.always_on_top else "0",
            "RecordRelToWindow": "1" if self.record_relative_to_window else "0",
            "BigMode": "1" if self.big_mode else "0",
            **{
                f"Tiny{k.capitalize()}": "1" if getattr(self, f"tiny_{k}") else "0"
                for k in (
                    "mode",
                    "record",
                    "play",
                    "loop",
                    "save",
                    "pause",
                    "delete",
                    "edit",
                    "settings",
                )
            },
        }
        cfg["Icons"] = {
            "Record": self.ico_record,
            "Play": self.ico_play,
            "Loop": self.ico_loop,
            "Save": self.ico_save,
            "Delete": self.ico_delete,
            "Settings": self.ico_settings,
        }
        cfg["AutoClick"] = {
            "CPS": str(self.autoclick_cps),
            "Button": self.autoclick_btn,
        }
        cfg["Drawing"] = {
            "Width": str(self.draw_width),
            "Opacity": str(self.draw_opacity),
        }
        cfg["Webhook"] = {
            "URL": self.webhook_url,
            "MentionID": self.mention_id,
            "OnRecord": "1" if self.wh_record else "0",
            "OnPlay": "1" if self.wh_play else "0",
            "OnLoop": "1" if self.wh_loop else "0",
            "OnSave": "1" if self.wh_save else "0",
            "Screenshot": "1" if self.wh_screenshot else "0",
        }
        cfg["ImageDetection"] = {
            "Enabled": "1" if self.img_det_enabled else "0",
            "WhileRecording": "1" if self.img_detect_while_recording else "0",
        }
        cfg["Roblox"] = {
            "Enabled": "1" if self.roblox_enabled else "0",
            "DisconnectImg": self.roblox_disconnect_img,
            "ServerLink": self.roblox_server_link,
            "Mode": self.roblox_mode,
            "WaitTime": str(self.roblox_wait_time),
            "RecoveryRun": self.roblox_recovery_run,
        }
        cfg["Dashboard"] = {
            "BadgeTexts": json.dumps(self.dash_badge_texts or {}),
            "BadgeIcons": json.dumps(self.dash_badge_icons or {}),
            "Title": self.dash_title,
            "Subtitle": self.dash_subtitle,
            "BgColor": self.dash_bg_color,
            "RankNames": json.dumps(self.dash_rank_names or {}),
            "RankEmojis": json.dumps(self.dash_rank_emojis or {}),
        }
        cfg["Stats"] = {
            "TotalMinutes": str(self.stats_total_minutes),
            "RunCount": str(self.stats_run_count),
            "CustomTitle": self.stats_custom_title,
        }
        cfg["Theme"] = dict(self.theme)
        with open(INI_PATH, "w", encoding="utf-8") as f:
            cfg.write(f)


class Col:
    def __init__(self, parent, idx, icon, label, cb, hotkey=""):
        self.parent = parent
        self.cb = cb
        self.hotkey = hotkey.upper() if hotkey else ""
        self.active = False

        # Base container setup
        self.frame = tk.Frame(parent, bg=_C["bg"], bd=0, highlightthickness=0)

        self.ico = tk.Label(
            self.frame,
            text=icon,
            bg=_C["bg"],
            fg=_C["icon_fg"],
            font=("Segoe UI Emoji", 14),
            cursor="hand2",
            bd=0,
        )

        self.lbl = tk.Label(
            self.frame,
            text=label,
            bg=_C["bg"],
            fg=_C["lbl_fg"],
            font=("Segoe UI", 6, "bold"),
            cursor="hand2",
            bd=0,
        )

        # Hotkey indicator (Rendered exclusively in BIG Mode)
        self.hk_lbl = tk.Label(
            self.frame,
            text=self.hotkey,
            bg=_C["bg"],
            fg=_C.get("lbl_fg", "#888"),
            font=("Segoe UI", 6, "bold"),
            cursor="hand2",
            bd=0,
        )

        # Dual-state Activity Status Dot [Active] / [Inactive]
        self.dot = tk.Label(
            self.frame,
            text="",
            bg=_C["bg"],
            fg="#22c55e",
            font=("Segoe UI", 10),
            cursor="hand2",
            bd=0,
        )

        # Bubble-up click bindings across all structural elements
        for w in (self.frame, self.ico, self.lbl, self.hk_lbl, self.dot):
            w.bind("<Button-1>", lambda _: self.cb())
            w.bind(
                "<Enter>",
                lambda _: (
                    self._set_all_bg(_C["acc"]) if not parent._app_busy() else None
                ),
            )
            w.bind("<Leave>", lambda _: self._set_all_bg(_C["bg"]))

    def _set_all_bg(self, bg):
        for w in (self.frame, self.ico, self.lbl, self.hk_lbl, self.dot):
            if w.winfo_exists():
                w.config(bg=bg)

    def reposition(self, idx, big=False):
        """Dynamic structural morphing between Standard/Tiny and BIG modes."""
        if big:
            cw, th, bh = _BIG_CW, _BIG_TH, _BIG_BH
            self.frame.place(x=idx * cw, y=th + 1, width=cw, height=bh)

            # Icon: large, centered
            self.ico.place(x=0, y=3, width=cw, height=38)
            self.ico.config(font=("Segoe UI Emoji", 20))

            # Label: bold 8pt
            self.lbl.place(x=0, y=42, width=cw, height=14)
            self.lbl.config(font=("Segoe UI", 8, "bold"))

            # Hotkey: accent purple 7pt, shown below label
            self.hk_lbl.place(x=0, y=57, width=cw, height=13)
            self.hk_lbl.config(
                font=("Segoe UI", 7, "bold"),
                fg="#a38eff",
                text=self.hotkey if self.hotkey else "NONE",
            )

            # Active dot: top-right corner of button cell
            self.dot.place(x=cw - 14, y=3, width=10, height=10)
            self.dot.config(font=("Segoe UI", 8))
        else:
            cw, th, bh = _STD_CW, _STD_TH, _STD_BH
            self.frame.place(x=idx * cw, y=th + 1, width=cw, height=bh)
            self.ico.place(x=0, y=2, width=cw, height=30)
            self.ico.config(font=("Segoe UI Emoji", 14))
            self.lbl.place(x=0, y=33, width=cw, height=13)
            self.lbl.config(font=("Segoe UI", 6, "bold"))

            # Remove hotkey and state dot labels from view in standard modes
            self.hk_lbl.place_forget()
            self.dot.place_forget()

    def set_active(self, val):
        self.active = val
        self.dot.config(text="●" if val else "", fg="#22c55e" if val else _C["bg"])

    def update_hotkey_text(self, new_hk):
        self.hotkey = new_hk.upper() if new_hk else ""
        if self.hk_lbl.winfo_exists():
            self.hk_lbl.config(text=self.hotkey if self.hotkey else "NONE")

    def hide(self):
        self.frame.place_forget()

    def show(self, idx, big=False):
        self.reposition(idx, big)

    def refresh(self):
        self._set_all_bg(_C["bg"])
        self.ico.config(fg=_C["icon_fg"])
        self.lbl.config(fg=_C["lbl_fg"])
        self.ico.config(fg=_C["icon_fg"])
        self.lbl.config(fg=_C["lbl_fg"])


class ScrollFrame:
    def __init__(self, parent, bg, width, height):
        self.outer = tk.Frame(parent, bg=bg, width=width, height=height)
        self.outer.pack_propagate(False)
        self._sb = tk.Scrollbar(
            self.outer,
            orient="vertical",
            troughcolor=SSURF,
            bg=SBORD,
            activebackground=SACC,
            width=5,
            relief="flat",
            bd=0,
        )
        self._sb.pack(side="right", fill="y")
        self._cv = tk.Canvas(
            self.outer, bg=bg, highlightthickness=0, bd=0, yscrollcommand=self._sb.set
        )
        self._cv.pack(side="left", fill="both", expand=True)
        self._sb.config(command=self._cv.yview)
        self.inner = tk.Frame(self._cv, bg=bg)
        win = self._cv.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>",
            lambda _: self._cv.configure(scrollregion=self._cv.bbox("all")),
        )
        self._cv.bind("<Configure>", lambda e: self._cv.itemconfig(win, width=e.width))
        self._bound = None
        self.outer.bind("<Enter>", self._bind)
        self.outer.bind("<Leave>", self._unbind)

    def _on_scroll(self, e):
        if e.num == 4:
            self._cv.yview_scroll(-3, "units")
        elif e.num == 5:
            self._cv.yview_scroll(3, "units")
        elif e.delta:
            self._cv.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _bind(self, _=None):
        if not self._bound:
            self._cv.bind_all("<MouseWheel>", self._on_scroll)
            self._cv.bind_all("<Button-4>", self._on_scroll)
            self._cv.bind_all("<Button-5>", self._on_scroll)
            self._bound = True

    def _unbind(self, _=None):
        if self._bound:
            self._cv.unbind_all("<MouseWheel>")
            self._cv.unbind_all("<Button-4>")
            self._cv.unbind_all("<Button-5>")
            self._bound = None

    def destroy(self):
        self._unbind()


class HotkeyEntry:
    def __init__(self, parent, initial, on_change):
        self.value, self.on_change = initial, on_change
        self.recording = False
        self.pressed = set()
        self.hook = None
        self._hk_listener = None
        self.frame = tk.Frame(
            parent, bg=SED, highlightbackground=SEDB, highlightthickness=1
        )
        self.frame.pack(fill="x", padx=10, pady=(2, 5))
        self.entry = tk.Label(
            self.frame,
            text=initial,
            bg=SED,
            fg=STEXT,
            relief="flat",
            bd=4,
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.btn = tk.Label(
            self.frame,
            text=" ⏺ ",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        self.btn.pack(side="right")
        self.btn.bind("<Button-1>", lambda _: self._toggle())

    def _toggle(self):
        if self.recording:
            self._stop()
        else:
            self._start()

    def _start(self):
        self.recording = True
        self.pressed.clear()
        self.btn.config(text=" ⏹ ", bg=SREC)
        self.entry.config(text="Press keys…", fg=SACC)
        # Use clean and robust pynput listener for Hotkey configuration
        self._hk_listener = _pkb.Listener(
            on_press=self._on_pynput_press,
            on_release=self._on_pynput_release,
            suppress=True,
        )
        self._hk_listener.start()

    def _on_key(self, e):
        if e.event_type == "down":
            self.pressed.add(e.name)
        elif e.event_type == "up" and self.recording and self.pressed:
            combo = "+".join(sorted(self.pressed, key=lambda k: (len(k), k)))
            self.value = combo
            self.entry.config(text=combo, fg=STEXT)
            self._stop()
            if self.on_change:
                self.on_change(combo)

    def _pynput_key_str(self, key):
        from pynput.keyboard import Key, KeyCode

        if isinstance(key, Key):
            return _normalize_key_name(str(key).replace("Key.", ""))
        elif isinstance(key, KeyCode):
            if hasattr(key, "vk") and key.vk:
                vk = key.vk
                if 0x41 <= vk <= 0x5A:
                    return chr(vk).lower()
                elif 0x61 <= vk <= 0x7A:
                    return chr(vk)
                elif 0x30 <= vk <= 0x39:
                    return chr(vk)
            if key.char and len(key.char) == 1:
                if 1 <= ord(key.char) <= 26:
                    return chr(ord(key.char) + 96)
                if key.char.isprintable():
                    return key.char.lower()
        return ""

    def _on_pynput_press(self, key):
        k_str = self._pynput_key_str(key)
        if k_str:
            self.pressed.add(k_str)

    def _on_pynput_release(self, key):
        # Match Windows behaviour: build combo from all keys that were pressed,
        # then stop. Do NOT discard from pressed first.
        if self.recording and self.pressed:
            combo = "+".join(sorted(self.pressed, key=lambda k: (len(k), k)))
            self.value = combo
            self.entry.config(text=combo, fg=STEXT)
            self._stop()
            if self.on_change:
                self.on_change(combo)
        k_str = self._pynput_key_str(key)
        self.pressed.discard(k_str)

    def _stop(self):
        self.recording = False
        self.btn.config(text=" ⏺ ", bg=SACC_D)
        if self._hk_listener is not None:
            try:
                self._hk_listener.stop()
            except Exception:
                pass
            self._hk_listener = None
        if self.hook:
            try:
                _kb.unhook(self.hook)
            except Exception:
                pass
            self.hook = None

    def __del__(self):
        self._stop()


class App:
    def __init__(self, root):
        self.master = root
        self.root = root
        self.root.deiconify()
        self.cfg = Config()
        self.cfg.load()
        _C.update(_derive(self.cfg.theme))
        _update_sp(self.cfg.theme)
        self.events = []
        self.recording = self.playing = self.looping = self.autoclicking = False
        self._ahk_proc = None
        self._pause_playback = False
        self._recovering = False
        self._clicked_images = set()
        self._clicked_this_run = set()
        self.temp_image_det_list = []
        self._stop_ev = threading.Event()
        self._autoclick_stop_ev = threading.Event()
        self._ev_lock = threading.Lock()
        self._held_vks = set()
        self._held_keys = {}
        self._held_btns = set()
        self._kb_ctrl = _pkb.Controller()
        self._mouse_ctrl = _pmouse.Controller()
        self._last_reinject = 0.0
        self._last_ms = self._rec_start = self._rec_dur = 0
        self._cached_swin_bounds = None
        self._spin_i = 0
        self._dice_i = 0
        self._blink_after = self._status_after = None
        self._swin = None
        self._scroll_frames = []
        self._dx = self._dy = 0
        self._sleeping = False
        self._focused = True
        self._ss_lock = threading.Lock()
        self._click_lock = threading.Lock()  # S-2: protects _clicked_this_run set
        self._stats_lock = threading.Lock()  # S-9: protects stats increment + save
        self._held_lock = (
            threading.Lock()
        )  # S-5: protects _held_vks/_held_keys/_held_btns
        self._img_cache_lock = (
            threading.Lock()
        )  # S-1: protects image_det_list reads (template cache uses @lru_cache)
        self._recover_lock = (
            threading.Lock()
        )  # C-2: protects _recovering state transitions
        self._last_move_x = self._last_move_y = 0
        self._last_move_ms = 0
        self._cached_bounds_ts = 0
        self._cached_rects = None
        self._cached_swin_hwnd = None
        self.draw_mode = False
        self._draw_overlay = None
        self._draw_tools = None
        self._draw_canvas = None
        self._draw_btn_pen = None
        self._draw_color = "#00ffff"  # Match your reference image cyan
        self._draw_last_pos = None
        self._pen_enabled = True
        self._draw_lines = []
        self._current_line = []
        self._is_drawing = False
        self._mouse_l = self._kb_l = None
        self._hk_vks = set()
        self._currently_pressed_vks = set()
        self._hotkeys_active = set()
        self._hotkey_defs = []
        self._global_kb_listener = None
        self._kv_after = self._kv_anim_after = None
        self._run_count = 0
        self._kv_dots = 0
        self._session_start = time.time()
        self._last_kv_ms = 0
        self._hk_suppressed = False

        if sys.platform == "win32":
            self._orig_beep = wintypes.BOOL()
            try:
                user32.SystemParametersInfoW(
                    SPI_GETBEEP, 0, _ct.byref(self._orig_beep), 0
                )
            except Exception:
                self._orig_beep.value = 1
            try:
                user32.SystemParametersInfoW(SPI_SETBEEP, 0, None, 0)
            except Exception:
                pass
        else:
            self._orig_beep = None

        self._build_gui()
        _register_tray_msg()
        try:
            self._setup_tray()
        except Exception:
            _LOG.warning("Tray setup failed", exc_info=True)
            self._tray_added = False
        atexit.register(self._remove_tray)

        self._register_hotkeys()
        self._setup_focus_suppression()

        # Start permanent global keyboard listener for reliable hotkeys and recording
        self._global_kb_listener = _pkb.Listener(
            on_press=self._global_on_press,
            on_release=self._global_on_release,
            suppress=False,
        )
        self._global_kb_listener.start()
        if self.cfg.save_path and Path(self.cfg.save_path).is_file():
            self._load_events(self.cfg.save_path)
        elif RUNS_PATH.exists():
            _runs = sorted(
                [p for p in RUNS_PATH.glob("*.txt") if p.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if len(_runs) == 1:
                self.cfg.save_path = str(_runs[0])
                self._load_events(str(_runs[0]))
            elif len(_runs) > 1:
                self.root.after(300, self._open_run_picker)
        self._kv_anim()
        self._spin()
        self.root.mainloop()

    def _build_gui(self):
        self.root.title("TinyKullan")
        self.root.overrideredirect(True)
        self.root.configure(bg=_C["bg"])
        self.root.attributes("-topmost", self.cfg.always_on_top)
        self.root.resizable(True, True)
        self.root.minsize(WW, TH + BH + 22)
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"{WW}x{TH + BH + 22}+{(sw - WW) // 2}+40")
        self.root._app_busy = lambda: (
            self.recording
            or self.playing
            or self.autoclicking
            or getattr(self, "running_all_images", False)
        )

        self._tb = tk.Frame(
            self.root, bg=_C["top"], height=TH, bd=0, highlightthickness=0
        )
        self._tb.place(x=0, y=0, width=WW, height=TH)
        self._ico = tk.Label(
            self._tb,
            text="✦",
            bg=_C["top"],
            fg=_C["title_fg"],
            font=("Segoe UI Symbol", 11, "bold"),
            bd=0,
        )
        self._ico.place(x=7, y=5, width=20, height=20)
        self._title = tk.Label(
            self._tb,
            text="TinyKullan",
            bg=_C["top"],
            fg=_C["title_fg"],
            font=("Segoe UI", 8, "bold"),
            bd=0,
        )
        self._title.place(x=30, y=6)
        self._pill = tk.Frame(self._tb, bg=_C["pill"], bd=0)
        self._pill.place(x=120, y=8, width=42, height=14)
        self._slbl = tk.Label(
            self._pill,
            text="Ready",
            bg=_C["pill"],
            fg=_C["status_fg"],
            font=("Segoe UI", 5, "bold"),
            bd=0,
        )
        self._slbl.place(x=0, y=2, width=42, height=12)

        self._btn_runs_top = tk.Label(
            self._tb,
            text="❇️",
            bg=_C["top"],
            fg=_C["title_fg"],
            font=("Segoe UI Emoji", 8),
            cursor="hand2",
            bd=0,
        )
        self._btn_runs_top.place(x=164, y=4, width=18, height=18)
        self._btn_runs_top.bind("<Button-1>", lambda _: self._open_run_picker())
        self._kv_f = tk.Frame(self._tb, bg=_C["bg"], bd=0)
        self._kv_f.place(x=185, y=7, width=42, height=14)
        self._kv = tk.Label(
            self._kv_f,
            text="",
            bg=_C["bg"],
            fg=_C["top"],
            font=("Segoe UI", 6, "bold"),
            bd=0,
        )
        self._kv.pack(fill="both", expand=True)

        # BIG mode toggle button
        self._btn_big = tk.Label(
            self._tb,
            text="⬜",
            bg=_C["top"],
            fg=_C["title_fg"],
            font=("Segoe UI Symbol", 10, "bold"),
            cursor="hand2",
            bd=0,
        )
        self._btn_big.place(x=WW - 90, y=0, width=22, height=TH)
        self._btn_big.bind("<Button-1>", lambda _: self._toggle_big_mode())

        self._btn_draw = tk.Label(
            self._tb,
            text="✎",
            bg=_C["top"],
            fg="#1D1128",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            bd=0,
        )
        self._btn_draw.place(x=WW - 68, y=0, width=22, height=TH)
        self._btn_draw.bind("<Button-1>", lambda _: self._toggle_draw_mode())

        self._btn_min = tk.Label(
            self._tb,
            text="–",
            bg="#F4BF4F",
            fg="#1D1128",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            bd=0,
        )
        self._btn_min.place(x=WW - 46, y=0, width=22, height=TH)
        self._btn_min.bind("<Button-1>", lambda _: self._minimize())

        self._btn_close = tk.Label(
            self._tb,
            text="×",
            bg="#ED6A5E",
            fg="#1D1128",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            bd=0,
        )
        self._btn_close.place(x=WW - 24, y=0, width=22, height=TH)
        self._btn_close.bind("<Button-1>", lambda _: self._quit())

        self._sep = tk.Frame(self.root, bg=_C["sep"], height=1, bd=0)
        self._sep.place(x=0, y=TH, width=WW)
        tk.Frame(self.root, bg=_C["bg"], bd=0).place(x=0, y=TH + 1, width=WW, height=BH)

        # Tiny mode: single-line log bar
        self._log_f = tk.Frame(self.root, bg=_C["pill"], bd=0)
        self._log_f.place(x=0, y=TH + BH + 2, width=WW, height=20)
        self._log_lbl = tk.Label(
            self._log_f,
            bg=_C["pill"],
            fg="#fff",
            font=("Segoe UI", 7),
            anchor="w",
            padx=6,
            text="",
        )
        self._log_lbl.pack(side="left", fill="both", expand=True)
        self._log_after = None
        self._loop_warn_active = False

        # Per-button active/inactive status labels (BIG mode only)
        self._status_row_frame = tk.Frame(self.root, bg=_C["top"], height=18)
        self._col_status_labels = {}

        self.c_rec = Col(
            self.root,
            0,
            self.cfg.ico_record,
            "Record",
            self.toggle_record,
            hotkey=self.cfg.key_record,
        )
        self.c_play = Col(
            self.root,
            1,
            self.cfg.ico_play,
            "Play",
            self.toggle_play,
            hotkey=self.cfg.key_play,
        )
        self.c_loop = Col(
            self.root,
            2,
            self.cfg.ico_loop,
            "Loop",
            self.toggle_loop,
            hotkey=self.cfg.key_loop,
        )
        self.c_save = Col(
            self.root,
            3,
            self.cfg.ico_save,
            "Save",
            self.save_events,
            hotkey=self.cfg.key_save,
        )
        self.c_pause = Col(
            self.root, 4, "⏸", "Pause", self._toggle_pause, hotkey=self.cfg.key_pause
        )
        self.c_edit = Col(self.root, 5, "✏", "Edit", self._open_macro_editor)
        self.c_set = Col(
            self.root, 6, self.cfg.ico_settings, "Settings", self._open_settings
        )

        self._all_cols = [
            ("record", self.c_rec),
            ("play", self.c_play),
            ("loop", self.c_loop),
            ("save", self.c_save),
            ("pause", self.c_pause),
            ("edit", self.c_edit),
            ("settings", self.c_set),
        ]

        # Create status labels for BIG mode status row
        for name, col in self._all_cols:
            lbl = tk.Label(
                self._status_row_frame,
                text="[unactive]",
                bg=_C["top"],
                fg="#ef4444",
                font=("Segoe UI", 7, "bold"),
                anchor="center",
            )
            self._col_status_labels[name] = lbl

        self._apply_tiny()
        if self.cfg.big_mode:
            self.root.after(50, self._apply_big)

        for w in (self._tb, self._ico, self._title, self._pill, self._slbl):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<Double-Button-1>", self._snap_settings_to_main)

        self.root.bind("<Enter>", lambda _: self._focus(True))
        self.root.bind("<Leave>", lambda _: self._focus(False))
        self.root.update_idletasks()
        if sys.platform == "win32":
            self._hwnd = _get_hwnd(self.root.winfo_id())
            _make_single_desktop_app_window(self._hwnd)
            _round_hwnd(self._hwnd)
            _set_alpha(self._hwnd, self._get_alpha())
        else:
            self._hwnd = 0
        # Fix 3: Force taskbar icon to register immediately on startup without
        # requiring the user to manually minimize and restore the window first.
        self.root.withdraw()
        self.root.after(80, self.root.deiconify)
        self.image_det_list = []
        self.load_image_detection()
        threading.Thread(target=self._image_search_worker, daemon=True).start()

    def _toggle_big_mode(self):
        self.cfg.big_mode = not self.cfg.big_mode
        self._apply_big()

    def _apply_big(self):
        """Toggle between BIG and standard mode.
        Title bar stays EXACTLY the same size in all modes.
        Only the button row, status row, and log panel expand."""
        big = self.cfg.big_mode

        # Button row uses BIG or STD column widths/heights
        cw = _BIG_CW if big else _STD_CW
        bh = _BIG_BH if big else _STD_BH
        # Title bar ALWAYS standard height
        th = _STD_TH

        # -- Toggle button icon --
        self._btn_big.config(
            text="▣" if big else "⬜",
            fg="#7c5cfc" if big else _C["title_fg"],
        )

        # -- Determine visible columns --
        if not self.cfg.tiny_mode:
            visible_cols = [col for _, col in self._all_cols]
            visible_names = [name for name, _ in self._all_cols]
        else:
            toggle_map = {
                "record": self.cfg.tiny_record,
                "play": self.cfg.tiny_play,
                "loop": self.cfg.tiny_loop,
                "save": self.cfg.tiny_save,
                "pause": self.cfg.tiny_pause,
                "edit": self.cfg.tiny_edit,
                "settings": True,
            }
            visible_pairs = [
                (n, c) for n, c in self._all_cols if toggle_map.get(n, True)
            ]
            if len(visible_pairs) < 3:
                visible_pairs = [
                    p for p in self._all_cols if p[0] in ("record", "play", "settings")
                ]
            visible_cols = [c for _, c in visible_pairs]
            visible_names = [n for n, _ in visible_pairs]

        n_cols = len(visible_cols)

        # -- Window geometry --
        STATUS_H = 18
        LOG_H = 72
        if big:
            calc_w = n_cols * cw
            calc_h = th + bh + STATUS_H + LOG_H + 4
        else:
            calc_w = n_cols * cw
            calc_h = th + bh + 22

        geo = self.root.geometry()
        parts = geo.split("+")
        pos_x = parts[1] if len(parts) > 1 else "100"
        pos_y = parts[2] if len(parts) > 2 else "100"
        self.root.geometry(f"{calc_w}x{calc_h}+{pos_x}+{pos_y}")

        # -- Resize title bar (always std height) --
        self._tb.place_configure(width=calc_w, height=th)
        self._sep.place_configure(width=calc_w, y=th)

        # -- Reposition window controls (22px, standard size) --
        self._btn_close.place_configure(x=calc_w - 24, y=0, width=22, height=th)
        self._btn_min.place_configure(x=calc_w - 46, y=0, width=22, height=th)
        self._btn_draw.place_configure(x=calc_w - 68, y=0, width=22, height=th)
        self._btn_big.place_configure(x=calc_w - 90, y=0, width=22, height=th)

        # Title bar elements — always standard tiny sizes, just repositioned
        self._ico.place_configure(x=7, y=4, width=20, height=20)
        self._ico.config(font=("Segoe UI Symbol", 11, "bold"))
        self._title.place_configure(x=30, y=6)
        self._title.config(font=("Segoe UI", 8, "bold"))
        self._pill.place_configure(
            x=120, y=7, width=42, height=14, relx=0.0, anchor="nw"
        )
        self._slbl.place_configure(x=0, y=1, width=42, height=12)
        self._slbl.config(font=("Segoe UI", 5, "bold"))
        self._btn_runs_top.place_configure(x=164, y=4, width=18, height=18)
        self._kv_f.place_configure(x=185, y=7, relx=0.0, anchor="nw")

        # -- Column buttons --
        hidden_ids = set(id(c) for c in visible_cols)
        for _, col in self._all_cols:
            if id(col) not in hidden_ids:
                col.hide()

        for idx, col in enumerate(visible_cols):
            col.show(idx, big=big)
            if col is self.c_rec:
                col.set_active(self.recording)
            elif col is self.c_play:
                col.set_active(self.playing or self.looping)
            elif col is self.c_pause:
                col.set_active(self._pause_playback)
            else:
                col.set_active(False)

        # -- BIG mode extra rows --
        if big:
            self._status_row_frame.place(
                x=0, y=th + bh + 1, width=calc_w, height=STATUS_H
            )
            self._status_row_frame.config(bg=_C["top"])

            for i, name in enumerate(visible_names):
                lbl = self._col_status_labels.get(name)
                if lbl:
                    lbl.place(x=i * cw, y=0, width=cw, height=STATUS_H)
                    lbl.config(bg=_C["top"])
            for name in [n for n, _ in self._all_cols]:
                if name not in visible_names:
                    lbl = self._col_status_labels.get(name)
                    if lbl:
                        lbl.place_forget()

            self._update_status_row()

            # BIG mode log: simple text widget, no frame/decorations
            log_y = th + bh + STATUS_H + 2
            if (
                not hasattr(self, "_log_text_panel")
                or not self._log_text_panel.winfo_exists()
            ):
                self._log_text_panel = tk.Text(
                    self.root,
                    bg="#0a0614",
                    fg="#00ffff",
                    font=("Consolas", 8),
                    bd=0,
                    highlightthickness=0,
                    wrap="word",
                    state="disabled",
                    height=5,
                )
            self._log_text_panel.place(x=2, y=log_y, width=calc_w - 4, height=72)
            self._log_f.place_forget()

        else:
            self._status_row_frame.place_forget()
            if hasattr(self, "_log_text_panel") and self._log_text_panel.winfo_exists():
                self._log_text_panel.place_forget()
            self._log_f.place(x=0, y=th + bh + 2, width=calc_w, height=20)

        self.root.update_idletasks()
        if sys.platform == "win32" and hasattr(self, "_hwnd"):
            _round_hwnd(self._hwnd)

    def _apply_tiny(self):
        visible = []
        if not self.cfg.tiny_mode:
            # Restore pill/slbl to standard bounds regardless of big_mode
            self._pill.place_configure(
                x=120, y=8, width=42, height=14, relx=0.0, anchor="nw"
            )
            self._slbl.place_configure(x=0, y=2, width=42, height=12)
            self._slbl.config(font=("Segoe UI", 5, "bold"))
            for i, (_, col) in enumerate(self._all_cols):
                col.show(i, big=self.cfg.big_mode)
            new_w = len(self._all_cols) * CW
            hide_ctrls = False
        else:
            # Force settings always visible (otherwise user can't access settings)
            self.cfg.tiny_settings = True
            toggle = {
                "record": self.cfg.tiny_record,
                "play": self.cfg.tiny_play,
                "loop": self.cfg.tiny_loop,
                "save": self.cfg.tiny_save,
                "pause": self.cfg.tiny_pause,
                "edit": self.cfg.tiny_edit,
                "settings": True,
            }
            visible = [col for name, col in self._all_cols if toggle.get(name, True)]
            # Enforce minimum 3 visible buttons
            if len(visible) < 3:
                # Auto-enable record, play, settings as fallback minimum set
                forced = {"record", "play", "settings"}
                for name in forced:
                    setattr(self.cfg, f"tiny_{name}", True)
                visible = [
                    col
                    for name, col in self._all_cols
                    if (toggle.get(name, True) or name in forced)
                ]
            visible_set = set(id(c) for c in visible)
            for _, col in self._all_cols:
                if id(col) not in visible_set:
                    col.hide()
            for i, col in enumerate(visible):
                col.show(i, big=self.cfg.big_mode)
            new_w = max(len(visible) * CW, 3 * CW)
            hide_ctrls = False  # Always show min/close/draw controls

        cur = self.root.geometry().split("+")
        x, y = (cur[1] if len(cur) > 1 else "0"), (cur[2] if len(cur) > 2 else "40")
        # Use proper height: BIG mode lets _apply_big override, else standard
        use_h = TH + BH + 22
        self.root.geometry(f"{new_w}x{use_h}+{x}+{y}")
        self._tb.place_configure(width=new_w)
        self._sep.place_configure(width=new_w)

        for lbl, ox in [
            (self._btn_draw, new_w - 68),
            (self._btn_min, new_w - 46),
            (self._btn_close, new_w - 24),
        ]:
            try:
                if hide_ctrls:
                    lbl.place_forget()
                else:
                    lbl.place(x=ox, y=0, width=22, height=TH)
            except Exception:
                pass

        if not self.cfg.tiny_mode:
            self._title.place_configure(x=30)
            self._pill.place_configure(x=120, y=7, relx=0.0, anchor="nw")
            self._btn_runs_top.place_configure(x=164, y=4)
            self._kv_f.place_configure(x=185, y=7, relx=0.0, anchor="nw")
        else:
            n_visible = len(visible)
            if n_visible <= 3:
                # Hide title text + Ready pill + waiting label, show only hex + runs + min/x
                self._title.place_forget()
                self._pill.place_forget()
                self._kv_f.place_forget()
                self._btn_runs_top.place_configure(x=(new_w // 2) - 9, y=4)
            elif n_visible == 4:
                # Hide title text + key detector, show pill + runs next to hex icon
                self._title.place_forget()
                self._kv_f.place_forget()
                self._pill.place_configure(x=30, y=7, relx=0.0, anchor="nw")
                self._btn_runs_top.place_configure(x=76, y=4)
            elif n_visible == 5:
                # Hide title text, show pill + runs + waiting next to hex icon
                self._title.place_forget()
                self._pill.place_configure(x=30, y=7, relx=0.0, anchor="nw")
                self._btn_runs_top.place_configure(x=76, y=4)
                self._kv_f.place_configure(x=98, y=7, relx=0.0, anchor="nw")
            else:
                self._title.place_configure(x=30)
                self._pill.place_configure(x=120, y=7, relx=0.0, anchor="nw")
                self._btn_runs_top.place_configure(x=164, y=4)
                self._kv_f.place_configure(x=185, y=7, relx=0.0, anchor="nw")

        # Let _build_gui handle the initial _apply_big call

    def _update_status_row(self):
        """Refresh the [active]/[unactive] labels under each button in BIG mode."""
        if not self.cfg.big_mode:
            return
        states = {
            "record": self.recording,
            "play": self.playing and not self.looping,
            "loop": self.looping,
            "save": False,
            "pause": self._pause_playback,
            "edit": False,
            "settings": False,
        }
        for name, lbl in self._col_status_labels.items():
            active = states.get(name, False)
            lbl.config(
                text="[active]" if active else "[unactive]",
                fg="#22c55e" if active else "#ef4444",
            )

    def _get_alpha(self):
        return self.cfg.alpha_focused if self._focused else self.cfg.alpha_unfocused

    def _apply_icons(self):
        self.c_rec.ico.config(text=self.cfg.ico_record)
        self.c_play.ico.config(text=self.cfg.ico_play)
        self.c_loop.ico.config(text=self.cfg.ico_loop)
        self.c_save.ico.config(text=self.cfg.ico_save)
        self.c_set.ico.config(text=self.cfg.ico_settings)

    def _focus(self, on):
        self._focused = on
        _set_alpha(self._hwnd, self._get_alpha())
        if on and not self.cfg.auto_focus:
            self.root.lift()

    def _drag_start(self, e):
        self._dx, self._dy = (
            e.x_root - self.root.winfo_x(),
            e.y_root - self.root.winfo_y(),
        )

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _reapply_chrome(self):
        if sys.platform != "win32":
            self.root.overrideredirect(True)
            self.root.lift()
            self.root.attributes("-topmost", self.cfg.always_on_top)
            try:
                self.root.attributes("-alpha", self._get_alpha() / 255.0)
            except Exception:
                pass
            return
        try:
            _round_hwnd(self._hwnd)
            _set_alpha(self._hwnd, self._get_alpha())
            self.root.overrideredirect(True)
            _make_single_desktop_app_window(self._hwnd)
            self.root.lift()
            self.root.attributes("-topmost", self.cfg.always_on_top)
        except Exception:
            pass

    def _setup_tray(self):
        """Create system tray icon using a dedicated hidden message window on a background thread."""
        script_dir = (
            Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
        )
        icon_path = script_dir / "_tray_icon.ico"
        if not icon_path.is_file():
            for ext in ("Kul.png", "icon.png"):
                p = script_dir / ext
                if p.is_file():
                    icon_path = p
                    break

        self._tray_icon = _load_tray_icon(str(icon_path) if icon_path.is_file() else "")
        if not self._tray_icon:
            _LOG.warning("Tray icon not loaded - tray disabled")
            self._tray_added = False
            return
        self._tray_added = False
        self._tray_hwnd = None

        def _tray_thread():
            """Runs a dedicated message-only window for tray callbacks."""
            WS_EX_TOOLWINDOW = 0x00000080
            WS_POPUP = 0x80000000
            CW_USEDEFAULT = 0x80000000

            WNDCLASSEXW = type(
                "WNDCLASSEXW",
                (_ct.Structure,),
                {
                    "_fields_": [
                        ("cbSize", wintypes.UINT),
                        ("style", wintypes.UINT),
                        ("lpfnWndProc", _WNDPROC),
                        ("cbClsExtra", _ct.c_int),
                        ("cbWndExtra", _ct.c_int),
                        ("hInstance", wintypes.HINSTANCE),
                        ("hIcon", wintypes.HICON),
                        ("hCursor", wintypes.HANDLE),
                        ("hbrBackground", wintypes.HBRUSH),
                        ("lpszMenuName", wintypes.LPCWSTR),
                        ("lpszClassName", wintypes.LPCWSTR),
                        ("hIconSm", wintypes.HICON),
                    ]
                },
            )

            @_WNDPROC
            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == WMAPP_NOTIFYCALLBACK:
                    ev = lparam & 0xFFFF
                    if ev in (0x0205, 0x007B):  # WM_RBUTTONUP / WM_CONTEXTMENU
                        self.root.after(0, self._show_tray_menu)
                    elif ev in (0x0202, 0x0203):  # WM_LBUTTONUP / WM_LBUTTONDBLCLK
                        if self._sleeping:
                            self.root.after(0, self._restore_from_tray)
                        else:
                            self.root.after(0, self._minimize)
                elif msg == _WM_TASKBARCREATED and _WM_TASKBARCREATED:
                    self._tray_added = False
                    self.root.after(200, self._add_tray_icon)
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            # Keep reference alive
            self._tray_wndproc = wnd_proc

            hInst = _ct.windll.kernel32.GetModuleHandleW(None)
            class_name = "TinyKullanTrayClass"

            wc = WNDCLASSEXW()
            wc.cbSize = _ct.sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = wnd_proc
            wc.hInstance = hInst
            wc.lpszClassName = class_name

            atom = user32.RegisterClassExW(_ct.byref(wc))
            if not atom:
                _LOG.warning("RegisterClassExW failed for tray window")
                return

            hwnd = user32.CreateWindowExW(
                WS_EX_TOOLWINDOW,
                class_name,
                "TinyKullanTray",
                WS_POPUP,
                0,
                0,
                0,
                0,
                0,
                0,
                hInst,
                0,
            )
            if not hwnd:
                _LOG.warning("CreateWindowExW failed for tray window")
                return

            self._tray_hwnd = hwnd
            self.root.after(0, self._add_tray_icon)

            # Message pump
            msg_struct = wintypes.MSG()
            while user32.GetMessageW(_ct.byref(msg_struct), 0, 0, 0) > 0:
                user32.TranslateMessage(_ct.byref(msg_struct))
                user32.DispatchMessageW(_ct.byref(msg_struct))

        # Ensure DefWindowProcW is available
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            ULONG_PTR,
            ULONG_PTR,
        ]
        if _ct.sizeof(_ct.c_void_p) == 8:
            user32.DefWindowProcW.restype = _ct.c_longlong
        else:
            user32.DefWindowProcW.restype = _ct.c_long

        t = threading.Thread(target=_tray_thread, daemon=True)
        t.start()

    def _add_tray_icon(self):
        if (
            self._tray_added
            or not getattr(self, "_tray_icon", 0)
            or not self._tray_hwnd
        ):
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = _ct.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._tray_hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WMAPP_NOTIFYCALLBACK
        nid.hIcon = self._tray_icon
        nid.szTip = "TinyKullan"
        ok = shell32.Shell_NotifyIconW(NIM_ADD, _ct.byref(nid))
        if not ok:
            try:
                err = _ct.windll.kernel32.GetLastError()
            except Exception:
                err = "?"
            _LOG.warning("Shell_NotifyIconW NIM_ADD failed (err=%s)", err)
        else:
            self._tray_added = True

    def _show_tray_menu(self):
        if sys.platform != "win32":
            return
        menu = _ct.windll.user32.CreatePopupMenu()
        rec_label = (
            "Stop Recording"
            if self.recording
            else f"Record  ({self.cfg.key_record.upper()})"
        )
        play_label = (
            "Stop Playing"
            if (self.playing or self.looping)
            else f"Play  ({self.cfg.key_play.upper()})"
        )
        pause_label = (
            "Resume" if self._pause_playback else "Pause"
        ) + f"  ({self.cfg.key_pause.upper()})"
        _ct.windll.user32.AppendMenuW(menu, MF_STRING, 1002, rec_label)
        _ct.windll.user32.AppendMenuW(menu, MF_STRING, 1003, play_label)
        _ct.windll.user32.AppendMenuW(menu, MF_STRING, 1005, pause_label)
        _ct.windll.user32.AppendMenuW(menu, MF_STRING, 1008, "Edit")
        _ct.windll.user32.AppendMenuW(menu, MF_SEPARATOR, 0, 0)
        _ct.windll.user32.AppendMenuW(menu, MF_STRING, 1099, "Exit")
        pt = POINT()
        _ct.windll.user32.GetCursorPos(_ct.byref(pt))
        _ct.windll.user32.SetForegroundWindow(self._tray_hwnd)
        cmd = _ct.windll.user32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self._tray_hwnd, 0
        )
        _ct.windll.user32.DestroyMenu(menu)
        if cmd:
            self._tray_menu_cmd(cmd)

    def _tray_menu_cmd(self, cmd):
        if cmd == 1001:
            self._restore_from_tray()
        elif cmd == 1002:
            self.root.after(0, self.toggle_record)
        elif cmd == 1003:
            self.root.after(0, self.toggle_play)
        elif cmd == 1005:
            self.root.after(0, self._toggle_pause)
        elif cmd == 1008:
            self._restore_from_tray()
            self.root.after(100, self._open_macro_editor)
        elif cmd == 1099:
            self.root.after(0, self._quit)

    def _restore_from_tray(self):
        self._sleeping = False
        self.root.deiconify()
        self.root.overrideredirect(True)
        _make_single_desktop_app_window(self._hwnd)
        self.root.lift()
        self.root.attributes("-topmost", self.cfg.always_on_top)
        self.root.focus_force()

    def _remove_tray(self):
        if sys.platform == "win32":
            if getattr(self, "_tray_added", False) and getattr(self, "_tray_hwnd", 0):
                nid = NOTIFYICONDATAW()
                nid.cbSize = _ct.sizeof(NOTIFYICONDATAW)
                nid.hWnd = self._tray_hwnd
                nid.uID = 1
                shell32.Shell_NotifyIconW(NIM_DELETE, _ct.byref(nid))
                self._tray_added = False
            # Post WM_QUIT to stop the tray thread message loop
            if getattr(self, "_tray_hwnd", 0):
                try:
                    user32.PostMessageW(self._tray_hwnd, 0x0012, 0, 0)  # WM_QUIT
                except Exception:
                    pass

    def _minimize(self):
        _ping()
        if getattr(self, "_tray_icon", 0) and self._tray_icon:
            self.root.withdraw()
            self._sleeping = True
        else:
            self.root.overrideredirect(False)
            self.root.iconify()
            self._sleeping = True

            def _on_restore(e=None):
                if self.root.state() == "normal":
                    self._sleeping = False
                    self.root.overrideredirect(True)
                    _make_single_desktop_app_window(self._hwnd)
                    self.root.lift()
                    self.root.after(50, self._reapply_chrome)
                    self.root.unbind("<Map>")

            self.root.bind("<Map>", _on_restore)

    # Drawing feature (Ctrl+M1)

    def _toggle_draw_mode(self):
        self.draw_mode = not self.draw_mode
        if self.draw_mode:
            self._btn_draw.config(fg=_C["go"])
            if self._draw_overlay is None:
                self._build_draw_overlay()
            else:
                if self._draw_overlay is not None:
                    self._draw_overlay.deiconify()
                    if sys.platform != "win32":
                        self._draw_overlay.lift()
                        self._draw_overlay.focus_force()
                if self._draw_tools is not None:
                    self._draw_tools.deiconify()
                self._redraw_lines()
            self._pen_enabled = True
            if self._draw_btn_pen is not None:
                self._draw_btn_pen.config(relief="sunken", bd=2)

            # Start background mouse watcher
            self._is_drawing = False
            self._draw_loop()
        else:
            self._btn_draw.config(fg="#1D1128")
            if self._draw_overlay is not None:
                self._draw_overlay.withdraw()
            if self._draw_tools is not None:
                self._draw_tools.withdraw()

    def _draw_loop(self):
        # Stop looping if we closed draw mode
        if not self.draw_mode:
            return

        if self._pen_enabled and self._draw_canvas is not None:
            try:
                # 0x11 = VK_CONTROL, 0x01 = VK_LBUTTON
                # We check the most significant bit (0x8000) to see if key is CURRENTLY pressed
                ctrl_pressed = bool(_ct.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
                m1_pressed = bool(_ct.windll.user32.GetAsyncKeyState(0x01) & 0x8000)

                if ctrl_pressed and m1_pressed:
                    pt = POINT()
                    _ct.windll.user32.GetCursorPos(_ct.byref(pt))
                    x, y = pt.x, pt.y

                    if not self._is_drawing:
                        # Just clicked: Start a new line
                        self._is_drawing = True
                        self._draw_last_pos = (x, y)
                        self._current_line = [x, y]
                    else:
                        # Dragging: Continue drawing
                        if self._draw_last_pos is not None:
                            lx, ly = self._draw_last_pos
                            if lx != x or ly != y:  # Only draw if mouse actually moved
                                width = getattr(self.cfg, "draw_width", 5.0)
                                self._draw_canvas.create_line(
                                    lx,
                                    ly,
                                    x,
                                    y,
                                    fill=self._draw_color,
                                    width=width,
                                    capstyle=tk.ROUND,
                                    smooth=True,
                                )
                                self._current_line.extend([lx, ly, x, y])
                                self._draw_last_pos = (x, y)
                else:
                    # Not holding both Ctrl and M1
                    if self._is_drawing:
                        self._is_drawing = False
                        # Save the stroke to memory for redraw/erase purposes
                        if len(self._current_line) >= 4:
                            self._draw_lines.append(
                                (
                                    self._current_line.copy(),
                                    self._draw_color,
                                    getattr(self.cfg, "draw_width", 5.0),
                                )
                            )
                        self._current_line = []
                        self._draw_last_pos = None

            except Exception:
                _LOG.debug("Draw loop error", exc_info=True)

        # Loop at high frequency (10ms) to ensure smooth lines
        self.root.after(10, self._draw_loop)

    def _build_draw_overlay(self):
        self._draw_color = "#00ffff"  # Match reference image cyan

        # full-screen transparent overlay
        self._draw_overlay = tk.Toplevel(self.root)
        if sys.platform == "win32":
            self._draw_overlay.overrideredirect(True)
        self._draw_overlay.attributes("-topmost", True)

        # Colour Key (Makes background 100% physically transparent to Windows OS)
        trans_color = "#000001"
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self._draw_overlay.geometry(f"{sw}x{sh}+0+0")

        if sys.platform == "win32":
            self._draw_overlay.config(bg=trans_color)
            self._draw_overlay.attributes("-transparentcolor", trans_color)
        else:
            # Linux: transparentcolor is Windows-only; use alpha transparency
            self._draw_overlay.config(bg="black")
            self._draw_overlay.attributes("-alpha", 0.3)
            self._draw_overlay.lift()
            self._draw_overlay.focus_force()

        canvas_bg = trans_color if sys.platform == "win32" else "black"
        self._draw_canvas = tk.Canvas(
            self._draw_overlay, bg=canvas_bg, highlightthickness=0, cursor="arrow"
        )
        self._draw_canvas.pack(fill="both", expand=True)

        self.root.update_idletasks()

        # Force window to be fully click-through Layered Window
        if sys.platform == "win32":
            hwnd = _get_hwnd(self._draw_overlay.winfo_id())
            s = user32.GetWindowLongW(hwnd, -20)
            user32.SetWindowLongW(hwnd, -20, s | WS_EX_LAYERED | WS_EX_TRANSPARENT)

        # floating tools window
        self._draw_tools = tk.Toplevel(self.root)
        self._draw_tools.overrideredirect(True)
        self._draw_tools.attributes("-topmost", True)

        # WIDENED window to 290px so the label has plenty of room to fit
        self._draw_tools.geometry(
            f"290x32+{self.root.winfo_x()}+{max(0, self.root.winfo_y() - 36)}"
        )
        self._draw_tools.config(bg=SBG)
        self.root.update_idletasks()
        try:
            _round_hwnd(_get_hwnd(self._draw_tools.winfo_id()))
        except Exception:
            pass

        tb = tk.Frame(self._draw_tools, bg=SBG)
        tb.pack(fill="both", expand=True)

        # Drag handle
        drag = tk.Label(
            tb, text="☰", bg=SBG, fg=STEXT, cursor="fleur", font=("Segoe UI", 9)
        )
        drag.pack(side="left", padx=(4, 2))
        sdx, sdy = [0], [0]

        def _drag_set(e):
            if self._draw_tools is not None:
                sdx[0] = e.x_root - self._draw_tools.winfo_x()
                sdy[0] = e.y_root - self._draw_tools.winfo_y()

        def _drag_apply(e):
            if self._draw_tools is not None:
                self._draw_tools.geometry(f"+{e.x_root - sdx[0]}+{e.y_root - sdy[0]}")

        drag.bind("<ButtonPress-1>", _drag_set)
        drag.bind("<B1-Motion>", _drag_apply)

        # Pen button
        self._draw_btn_pen = tk.Label(
            tb,
            text="✎",
            bg=self._draw_color,
            fg="#1D1128",
            font=("Segoe UI", 10),
            cursor="hand2",
            width=2,
            relief="sunken",
            bd=2,
        )
        self._draw_btn_pen.pack(side="left", padx=2, pady=3)
        self._draw_btn_pen.bind("<Button-1>", lambda _: self._toggle_pen())

        # Colour picker button
        btn_color = tk.Label(
            tb,
            text="●",
            bg=SBG,
            fg=SACC,
            font=("Segoe UI", 12),
            cursor="hand2",
            width=2,
        )
        btn_color.pack(side="left", padx=2, pady=3)
        btn_color.bind("<Button-1>", lambda _: self._show_color_palette())

        # Undo button (Delete Single Action)
        btn_undo = tk.Label(
            tb,
            text="↶",
            bg=SBG,
            fg=STEXT,
            font=("Segoe UI", 12, "bold"),
            cursor="hand2",
            width=2,
        )
        btn_undo.pack(side="left", padx=2, pady=3)
        btn_undo.bind("<Button-1>", lambda _: self._undo_drawing())

        # Erase button (Full Delete)
        btn_erase = tk.Label(
            tb,
            text="✕",
            bg=SBG,
            fg="#ED6A5E",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            width=2,
        )
        btn_erase.pack(side="left", padx=2, pady=3)
        btn_erase.bind("<Button-1>", lambda _: self._clear_drawing())

        # Settings button (Draw thickness, etc)
        btn_settings = tk.Label(
            tb,
            text="⚙",
            bg=SBG,
            fg=SMUTED,
            font=("Segoe UI", 11),
            cursor="hand2",
            width=2,
        )
        btn_settings.pack(side="left", padx=2, pady=3)
        btn_settings.bind("<Button-1>", lambda _: self._show_draw_settings())

        # Permanent Text Label replacing the old tooltips
        lbl_warning = tk.Label(
            tb,
            text="Ctrl+M1 to draw",
            bg=SBG,
            fg=SMUTED,
            font=("Segoe UI", 8, "bold"),
        )
        lbl_warning.pack(side="left", padx=(6, 2))

        self._redraw_lines()

    def _undo_drawing(self):
        if self._draw_lines:
            self._draw_lines.pop()
            self._redraw_lines()

    def _clear_drawing(self):
        self._draw_lines.clear()
        if self._draw_canvas is not None:
            self._draw_canvas.delete("all")

    def _redraw_lines(self):
        if self._draw_canvas is None:
            return
        self._draw_canvas.delete("all")
        for entry in self._draw_lines:
            if len(entry) == 3:
                coords, color, width = entry
            else:
                coords, color = entry
                width = 5.0
            # Normalise mixed-format coords (old saves) to flat list
            if coords and isinstance(coords[0], tuple):
                flat = []
                for pt in coords:
                    if isinstance(pt, tuple):
                        flat.extend(pt)
                    else:
                        flat.append(pt)
                coords = flat
            self._draw_canvas.create_line(
                coords, fill=color, width=width, capstyle=tk.ROUND, smooth=True
            )

    def _show_draw_settings(self):
        if self._draw_tools is None:
            return
        pop = tk.Toplevel(self._draw_tools)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.config(bg=SBORD, padx=1, pady=1)
        mx, my = self._draw_tools.winfo_rootx(), self._draw_tools.winfo_rooty()
        # Position slightly below the tools window
        pop.geometry(f"160x60+{mx + 20}+{my + 35}")

        frame = tk.Frame(pop, bg=SBG)
        frame.pack(fill="both", expand=True)

        header = tk.Frame(frame, bg=SBG)
        header.pack(fill="x", padx=4, pady=2)

        lbl = tk.Label(
            header, text="Thickness", bg=SBG, fg=STEXT, font=("Segoe UI", 8, "bold")
        )
        lbl.pack(side="left")

        close_btn = tk.Label(header, text="✕", bg=SBG, fg="#ED6A5E", cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda _: pop.destroy())

        var = tk.DoubleVar(value=getattr(self.cfg, "draw_width", 5.0))

        def _update_width(v):
            setattr(self.cfg, "draw_width", float(v))

        scale = tk.Scale(
            frame,
            from_=1.0,
            to=25.0,
            resolution=1.0,
            orient="horizontal",
            variable=var,
            bg=SBG,
            fg=STEXT,
            highlightthickness=0,
            bd=0,
            troughcolor=SSURF,
            command=_update_width,
            showvalue=False,
        )
        scale.pack(fill="x", padx=10, pady=(0, 5))

    def _show_color_palette(self):
        if self._draw_tools is None:
            return
        colors = [
            ("#00ffff", "cyan"),
            ("#ff0000", "red"),
            ("#00ff00", "green"),
            ("#0000ff", "blue"),
            ("#ffff00", "yellow"),
            ("#ffffff", "white"),
            ("#000000", "black"),
            ("#ff69b4", "pink"),
        ]
        pop = tk.Toplevel(self._draw_tools)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.config(bg=SBORD, padx=2, pady=2)
        mx, my = self._draw_tools.winfo_rootx(), self._draw_tools.winfo_rooty()
        pop.geometry(f"+{mx + 60}+{my + 35}")
        for i, (c, _) in enumerate(colors):
            f = tk.Frame(
                pop,
                bg=c,
                width=22,
                height=22,
                cursor="hand2",
                highlightbackground=SBORD,
                highlightthickness=1,
            )
            f.grid(row=i // 4, column=i % 4, padx=1, pady=1)
            f.bind("<Button-1>", lambda _, color=c: self._set_draw_color(color, pop))

    def _set_draw_color(self, color, pop=None):
        self._draw_color = color
        if self._draw_btn_pen is not None:
            self._draw_btn_pen.config(bg=color)
        if pop is not None:
            pop.destroy()

    def _toggle_pen(self):
        self._pen_enabled = not self._pen_enabled
        if self._draw_btn_pen is not None:
            if self._pen_enabled:
                self._draw_btn_pen.config(relief="sunken", bd=2)
            else:
                self._draw_btn_pen.config(relief="flat", bd=0)

    # End drawing feature

    def set_status(self, text, color=None, revert_ms=0):
        bg = color or _C["pill"]
        self._pill.config(bg=bg)
        self._slbl.config(text=text, bg=bg)
        if self._status_after is not None:
            self.root.after_cancel(self._status_after)
            self._status_after = None
        if revert_ms:
            self._status_after = self.root.after(
                revert_ms,
                lambda: (
                    self._pill.config(bg=_C["pill"]),
                    self._slbl.config(text="Ready", bg=_C["pill"]),
                ),
            )

    def _log_message(self, text):
        """Log a line. Tiny: 1 line + warning if looping. BIG: max 5 lines, warning at bottom."""
        if not hasattr(self, "_log_lbl"):
            return
        stop_key = self.cfg.key_stop or "esc"
        # Tiny/standard mode
        if hasattr(self, "_log_lbl") and self._log_lbl.winfo_exists():
            if self._loop_warn_active:
                self._log_lbl.config(text=f"{text}  |  {stop_key} = stop")
            else:
                self._log_lbl.config(text=text)
            if self._log_after is not None:
                self.root.after_cancel(self._log_after)
            if not self._loop_warn_active:
                self._log_after = self.root.after(
                    2500, lambda: self._log_lbl.config(text="")
                )
        # BIG mode
        if hasattr(self, "_log_text_panel") and self._log_text_panel.winfo_exists():
            try:
                self._log_text_panel.config(state="normal")
                # Remove old warning if present (last non-empty line starting with "> esc" etc)
                end = self._log_text_panel.index("end-1c")
                last_line = self._log_text_panel.get("end-2l", "end-1c").strip()
                if self._loop_warn_active and ("= stop" in last_line):
                    self._log_text_panel.delete("end-2l", "end-1c")
                # Append new log
                self._log_text_panel.insert("end", text + "\n")
                # Append warning if looping
                if self._loop_warn_active:
                    self._log_text_panel.insert("end", f"> {stop_key} = stop\n")
                # Trim to 5 lines
                count = int(self._log_text_panel.index("end-1c").split(".")[0])
                if count > 5:
                    self._log_text_panel.delete("1.0", f"{count - 5}.0")
                self._log_text_panel.see("end")
                self._log_text_panel.config(state="disabled")
            except Exception:
                pass

    def _update_kv(self, text):
        if self._kv_after is not None:
            self.root.after_cancel(self._kv_after)
            self._kv_after = None
        if self._kv_anim_after is not None:
            self.root.after_cancel(self._kv_anim_after)
            self._kv_anim_after = None
        self._kv.config(text=text)
        self._kv_after = self.root.after(1200, self._kv_anim)

    def _maybe_update_kv(self, text):
        self._last_kv_ms = _ms()
        self._update_kv(text)

    def _kv_anim(self):
        if self.recording:
            return
        self._kv_dots = (self._kv_dots + 1) % 4
        self._kv.config(text="waiting" + "." * self._kv_dots)
        self._kv_anim_after = self.root.after(500, self._kv_anim)

    def _spin(self):
        if not self._sleeping:
            self._spin_i = (self._spin_i + 1) % len(_SPIN)
            self._ico.config(text=_SPIN[self._spin_i])
        self.root.after(300, self._spin)

    def _anim_tick(self):
        """Dice-roll animation for recording / playing / looping states."""
        if self._sleeping:
            if self.recording or self.playing or self.looping:
                self._blink_after = self.root.after(180, self._anim_tick)
            return
        if self.recording:
            # Roll dice on status label + pill pulse
            self._dice_i = (self._dice_i + 1) % len(_DICE)
            dice = _DICE[self._dice_i]
            cur = self._slbl.cget("bg")
            nc = _C["bg"] if cur == _C["rec"] else _C["rec"]
            self._pill.config(bg=nc)
            self._slbl.config(text=f"{dice} REC", bg=nc)
            # Roll dice face on the record button icon too
            self.c_rec.ico.config(text=dice)

        if self.playing and not self.looping:
            self._dice_i = (self._dice_i + 1) % len(_DICE)
            dice = _DICE[self._dice_i]
            cur = self._slbl.cget("bg")
            nc = _C["bg"] if cur == _C["go"] else _C["go"]
            self._pill.config(bg=nc)
            self._slbl.config(text=f"{dice} PLAY", bg=nc)
            self.c_play.ico.config(text=dice)

        if self.looping:
            self._dice_i = (self._dice_i + 1) % len(_DICE)
            dice = _DICE[self._dice_i]
            cur = self._slbl.cget("bg")
            nc = _C["bg"] if cur == _C["loop"] else _C["loop"]
            self._pill.config(bg=nc)
            self._slbl.config(text=f"{dice} LOOP", bg=nc)
            self.c_loop.ico.config(text=dice)

        if self.recording or self.playing or self.looping:
            self._blink_after = self.root.after(180, self._anim_tick)

    def _quit(self):
        try:
            self.cfg.save()
        except Exception:
            _LOG.exception("Failed to save config on quit")
        self._remove_tray()
        self._stop_recording()
        self._stop_ev.set()
        self._autoclick_stop_ev.set()
        self.autoclicking = False
        # Terminate AHK process if running
        if self._ahk_proc is not None:
            try:
                self._ahk_proc.terminate()
            except Exception:
                _LOG.exception("Failed to terminate AHK playback process")
            self._ahk_proc = None
        # Terminate AHK persistent worker if active
        global _ahk_worker_proc
        if _ahk_worker_proc is not None:
            try:
                _ahk_worker_proc.terminate()
            except Exception:
                _LOG.exception("Failed to terminate AHK worker process")
            _ahk_worker_proc = None
        # Release ALL held keys — prevent stuck modifiers
        try:
            self._release_held()
        except Exception:
            _LOG.exception("Failed to release held keys on quit")
        # Emergency key release: brute-force all modifier and action VKs
        # Must match TinyKullan.ahk ReleaseAllHeld() to prevent stuck keys
        _EMERGENCY_VKS = (
            0x10,
            0x11,
            0x12,
            0x5B,
            0x5C,  # Shift, Ctrl, Alt, LWin, RWin
            0xA0,
            0xA1,
            0xA2,
            0xA3,
            0xA4,
            0xA5,  # L/R variants
            0x57,
            0x41,
            0x53,
            0x44,  # WASD
            0x25,
            0x26,
            0x27,
            0x28,  # Arrows
            0x20,
            0x0D,
            0x1B,
            0x09,  # Space, Enter, Esc, Tab
            0x51,
            0x45,
            0x52,
            0x46,  # Q, E, R, F
            0x08,
            0x2E,
            0x14,  # BS, Del, Caps
            0x70,
            0x71,
            0x72,
            0x73,
            0x74,
            0x75,
            0x76,
            0x77,  # F1-F8
            0x21,
            0x22,
            0x23,
            0x24,
            0x2D,
            0x2E,  # PgUp, PgDn, End, Home, Ins, Del
        )
        for vk in _EMERGENCY_VKS:
            try:
                sc = user32.MapVirtualKeyW(vk, 0)
                _send_input(_make_key(vk, sc, True, vk in _EXTENDED_VKS))
            except Exception:
                pass
        try:
            _kb.unhook_all_hotkeys()
        except Exception:
            pass
        try:
            if sys.platform == "win32" and self._orig_beep is not None:
                user32.SystemParametersInfoW(
                    SPI_SETBEEP, self._orig_beep.value, None, 0
                )
        except Exception:
            pass
        # Bug 1: Stop pynput mouse listener if active
        if self._mouse_l:
            try:
                self._mouse_l.stop()
            except Exception:
                pass

        # Bug 15: Stop the global keyboard listener so the process can exit cleanly
        if self._global_kb_listener:
            try:
                self._global_kb_listener.stop()
            except Exception:
                pass

        self.draw_mode = False  # stop draw loop

        if hasattr(self, "master") and self.master:
            self.master.destroy()
        else:
            self.root.destroy()

    def _build_hk_vks(self):
        self._hk_vks.clear()
        self._hotkey_defs = []
        self._hotkey_map = {}  # Fast direct VK→func lookup for simple hotkeys

        # Build stop-key VK set (only used during playback)
        self._stop_key_vks = set()
        stop_raw = self.cfg.key_stop
        if stop_raw and isinstance(stop_raw, str):
            for part in stop_raw.lower().replace(" ", "").split("+"):
                vk = _name_to_vk(part)
                if vk:
                    self._stop_key_vks.add(vk)
                    if vk == 0x10:
                        self._stop_key_vks.update({0xA0, 0xA1})
                    elif vk == 0x11:
                        self._stop_key_vks.update({0xA2, 0xA3})
                    elif vk == 0x12:
                        self._stop_key_vks.update({0xA4, 0xA5})
        _MODIFIER_VKS = {
            0x10,
            0x11,
            0x12,
            0x5B,
            0x5C,
            0xA0,
            0xA1,
            0xA2,
            0xA3,
            0xA4,
            0xA5,
        }
        for hk, f in [
            (self.cfg.key_record, self.toggle_record),
            (self.cfg.key_play, self.toggle_play),
            (self.cfg.key_loop, self.toggle_loop),
            (self.cfg.key_save, self.save_events),
            (self.cfg.key_autoclick, self.toggle_autoclick),
            (self.cfg.key_pause, self._toggle_pause),
        ]:
            if not hk or not isinstance(hk, str):
                continue
            parts = hk.lower().replace(" ", "").split("+")
            hk_vk_set = set()
            for part in parts:
                vk = _name_to_vk(part)
                if not vk:
                    continue
                hk_vk_set.add(vk)
                self._hk_vks.add(vk)
                if vk == 0x10:
                    self._hk_vks.update({0xA0, 0xA1})
                    hk_vk_set.update({0xA0, 0xA1})
                elif vk == 0x11:
                    self._hk_vks.update({0xA2, 0xA3})
                    hk_vk_set.update({0xA2, 0xA3})
                elif vk == 0x12:
                    self._hk_vks.update({0xA4, 0xA5})
                    hk_vk_set.update({0xA4, 0xA5})
            if hk_vk_set:
                self._hotkey_defs.append((hk_vk_set, f, hk))
                # Simple single-key hotkeys: fast direct VK lookup
                if len(parts) == 1:
                    vk = _name_to_vk(parts[0])
                    if vk:
                        self._hotkey_map[vk] = f

    def _register_hotkeys(self):
        self._build_hk_vks()
        self.update_application_hotkey_manifest()

    def update_application_hotkey_manifest(self):
        """Call this anytime hotkeys are updated to refresh the button hints instantly."""
        if hasattr(self, "c_rec"):
            self.c_rec.update_hotkey_text(self.cfg.key_record)
            self.c_play.update_hotkey_text(self.cfg.key_play)
            self.c_loop.update_hotkey_text(self.cfg.key_loop)
            self.c_save.update_hotkey_text(self.cfg.key_save)
            self.c_pause.update_hotkey_text(self.cfg.key_pause)

    def _global_on_press(self, key):
        vk, scan, ext = _key_to_vk(key)
        if not vk:
            return

        is_auto_repeat = vk in self._currently_pressed_vks
        self._currently_pressed_vks.add(vk)
        if vk == 0x10:
            self._currently_pressed_vks.update({0xA0, 0xA1})
        elif vk == 0x11:
            self._currently_pressed_vks.update({0xA2, 0xA3})
        elif vk == 0x12:
            self._currently_pressed_vks.update({0xA4, 0xA5})

        # Escape always stops playback
        if vk == 0x1B and not is_auto_repeat:
            if self.playing or self.looping:
                self.root.after(0, self._stop_playback)
                return

        # During playback: check stop key
        if not is_auto_repeat and (self.playing or self.looping):
            if self._stop_key_vks:
                # Single-key stop: trust it (the macro won't send esc/f-keys alone)
                if len(self._stop_key_vks) == 1:
                    if vk in self._stop_key_vks:
                        self.root.after(0, self._stop_playback)
                        return
                # Combo stop: verify all modifiers are physically held
                else:
                    all_held = True
                    for svk in self._stop_key_vks:
                        if svk in (0x10, 0xA0, 0xA1):
                            if not (
                                (
                                    user32.GetAsyncKeyState(0x10)
                                    | user32.GetAsyncKeyState(0xA0)
                                    | user32.GetAsyncKeyState(0xA1)
                                )
                                & 0x8000
                            ):
                                all_held = False
                                break
                        elif svk in (0x11, 0xA2, 0xA3):
                            if not (
                                (
                                    user32.GetAsyncKeyState(0x11)
                                    | user32.GetAsyncKeyState(0xA2)
                                    | user32.GetAsyncKeyState(0xA3)
                                )
                                & 0x8000
                            ):
                                all_held = False
                                break
                        elif svk in (0x12, 0xA4, 0xA5):
                            if not (
                                (
                                    user32.GetAsyncKeyState(0x12)
                                    | user32.GetAsyncKeyState(0xA4)
                                    | user32.GetAsyncKeyState(0xA5)
                                )
                                & 0x8000
                            ):
                                all_held = False
                                break
                        elif svk in (0x5B, 0x5C):
                            if not (
                                (
                                    user32.GetAsyncKeyState(0x5B)
                                    | user32.GetAsyncKeyState(0x5C)
                                )
                                & 0x8000
                            ):
                                all_held = False
                                break
                        elif svk not in self._currently_pressed_vks:
                            all_held = False
                            break
                    if all_held:
                        self.root.after(0, self._stop_playback)
                        return
            if not self.recording:
                self._on_key_press(key, is_auto_repeat=is_auto_repeat)
            return

        if getattr(self, "_hk_suppressed", False):
            self._on_key_press(key, is_auto_repeat=is_auto_repeat)
            return

        triggered_func = None
        triggered_func = self._hotkey_map.get(vk)
        if not triggered_func:
            for hk_vk_set, func, hk_name in self._hotkey_defs:
                matched = True
                for h_vk in hk_vk_set:
                    if h_vk in (0x10, 0xA0, 0xA1):
                        if not (
                            0x10 in self._currently_pressed_vks
                            or 0xA0 in self._currently_pressed_vks
                            or 0xA1 in self._currently_pressed_vks
                        ):
                            matched = False
                            break
                    elif h_vk in (0x11, 0xA2, 0xA3):
                        if not (
                            0x11 in self._currently_pressed_vks
                            or 0xA2 in self._currently_pressed_vks
                            or 0xA3 in self._currently_pressed_vks
                        ):
                            matched = False
                            break
                    elif h_vk in (0x12, 0xA4, 0xA5):
                        if not (
                            0x12 in self._currently_pressed_vks
                            or 0xA4 in self._currently_pressed_vks
                            or 0xA5 in self._currently_pressed_vks
                        ):
                            matched = False
                            break
                    else:
                        if h_vk not in self._currently_pressed_vks:
                            matched = False
                            break
                if matched:
                    triggered_func = func
                    break

        if triggered_func:
            if not is_auto_repeat:
                if not (self.playing or self.looping):
                    self.root.after(0, triggered_func)
            return

        if not self.recording:
            self._on_key_press(key, is_auto_repeat=is_auto_repeat)

    def _global_on_release(self, key):
        vk, scan, ext = _key_to_vk(key)
        if not vk:
            return

        self._currently_pressed_vks.discard(vk)
        if vk == 0x10:
            self._currently_pressed_vks.difference_update({0xA0, 0xA1})
        elif vk == 0x11:
            self._currently_pressed_vks.difference_update({0xA2, 0xA3})
        elif vk == 0x12:
            self._currently_pressed_vks.difference_update({0xA4, 0xA5})

        # AHK handles recording; don't record releases either
        if not self.recording:
            self._on_key_release(key)

    def _pause_hk_listener(self):
        self._hk_suppressed = True

    def _resume_hk_listener(self):
        self._hk_suppressed = False

    def _setup_focus_suppression(self):
        def _on_focus_in(event):
            w = event.widget
            if isinstance(w, (tk.Entry, tk.Text)):
                self._pause_hk_listener()
            else:
                self._resume_hk_listener()

        def _on_focus_out(event):
            w = event.widget
            if isinstance(w, (tk.Entry, tk.Text)):
                self._resume_hk_listener()

        self.root.bind_all("<FocusIn>", _on_focus_in, "+")
        self.root.bind_all("<FocusOut>", _on_focus_out, "+")

    def _panic(self):
        _LOG.warning("PANIC STOP")
        # Bug 14: Add _stop_listeners method
        self._stop_listeners()
        self.recording = False
        self._stop_ev.set()
        self._autoclick_stop_ev.set()
        self.playing = self.looping = self.autoclicking = False
        self.running_all_images = False
        try:
            self._release_held()
        except Exception:
            pass
        if self._blink_after is not None:
            try:
                self.root.after_cancel(self._blink_after)
            except Exception:
                pass
            self._blink_after = None
        self.root.after(0, self._reset_ui)
        self.root.after(0, lambda: self.set_status("⚠ PANIC", _C["rec"], 5000))

    # Bug 14
    def _stop_listeners(self):
        if self._mouse_l:
            try:
                self._mouse_l.stop()
            except Exception:
                pass
            self._mouse_l = None
        if self._kb_l:
            try:
                self._kb_l.stop()
            except Exception:
                pass
            self._kb_l = None

    def toggle_record(self):
        if self.playing or self.looping or getattr(self, "running_all_images", False):
            if getattr(self, "running_all_images", False):
                self._stop_run_all_images()
            else:
                self._stop_playback()
            return
        self._stop_recording() if self.recording else self._start_recording()

    def toggle_autoclick(self):
        # Bug 24: Guard against starting autoclicker during recording/playback
        if self.recording or self.playing or self.looping:
            self.set_status("Macro busy!", _C["rec"], 1500)
            return
        self.autoclicking = not self.autoclicking
        if self.autoclicking:
            self._autoclick_stop_ev.clear()
            self.set_status("⏺ AUTO", _C["go"])
            threading.Thread(target=self._autoclick_loop, daemon=True).start()
        else:
            self._autoclick_stop_ev.set()
            if self.playing or self.looping:
                self.set_status(
                    "▶ Playing" if self.playing and not self.looping else "∞ LOOP",
                    _C["go"] if self.playing and not self.looping else _C["loop"],
                )
            elif self.recording:
                self.set_status("● REC", _C["rec"])
            else:
                self.set_status("Ready", _C["pill"])

    def _autoclick_loop(self):
        while self.autoclicking and not self._autoclick_stop_ev.is_set():
            try:
                btn = str(self.cfg.autoclick_btn).lower()
                _send_input(_mouse_button(btn, False), _mouse_button(btn, True))
            except Exception as e:
                _LOG.warning("Autoclick: %s", e)
            time.sleep(1.0 / max(float(self.cfg.autoclick_cps), 0.1))

    def _start_recording(self):
        if getattr(self, "running_all_images", False):
            self._stop_run_all_images()
            return
        self.events = []
        self.recording = True
        self.c_rec.set_active(True)
        self.root.after(0, self._update_status_row)
        with self._click_lock:
            self._clicked_this_run = set()
        if self.temp_image_det_list:
            with self._img_cache_lock:
                self.image_det_list = [dict(x) for x in self.temp_image_det_list]

        self.c_rec.ico.config(text="⏹")
        self.c_rec.lbl.config(text="Stop")
        self.set_status("⏺ REC", _C["rec"])
        self._log_message("> recording started")
        self._anim_tick()

        try:
            ahk_path = _find_autohotkey()
            script_dir = os.path.dirname(os.path.abspath(__file__))
            ahk_script = os.path.join(script_dir, "TinyKullan.ahk")
            if not os.path.exists(ahk_script):
                raise FileNotFoundError(f"TinyKullan.ahk not found")
            if not os.path.exists(ahk_path):
                raise FileNotFoundError(f"AutoHotkey not found: {ahk_path}")

            import tempfile

            macro_temp = os.path.join(
                tempfile.gettempdir(), f"tkmacro_record_{os.getpid()}.txt"
            )
            stop_temp = macro_temp + ".stop"
            for tp in (macro_temp, stop_temp):
                try:
                    if os.path.exists(tp):
                        os.remove(tp)
                except Exception:
                    pass
            self._record_macro_temp = macro_temp
            self._record_stop_temp = stop_temp

            import subprocess

            self._ahk_proc = subprocess.Popen(
                [ahk_path, ahk_script, "/record", macro_temp],
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
        except FileNotFoundError as e:
            _LOG.error("AHK not found: %s", e)
            self.set_status("AHK not installed - run install.bat", _C["rec"], 4000)
            self.recording = False
            self.c_rec.ico.config(text=self.cfg.ico_record)
            self.c_rec.lbl.config(text="Record")
        except Exception as e:
            _LOG.error("Failed to start AHK recorder: %s", e)
            self.set_status("Record failed", _C["rec"], 3000)
            self.recording = False
            self.c_rec.ico.config(text=self.cfg.ico_record)
            self.c_rec.lbl.config(text="Record")

    def _stop_recording(self):
        if not self.recording:
            return
        if self._blink_after is not None:
            self.root.after_cancel(self._blink_after)
            self._blink_after = None

        if self._ahk_proc is not None:
            stop_temp = getattr(self, "_record_stop_temp", "")
            self.c_rec.ico.config(text="⏳")
            self.set_status("Saving...", _C["loop"], 3000)
            ahk = self._ahk_proc
            self._ahk_proc = None
            macro_temp = getattr(self, "_record_macro_temp", "")

            def _wait_ahk():
                try:
                    with open(stop_temp, "w", encoding="utf-8") as f:
                        f.write("stop")
                    ahk.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        ahk.kill()
                        ahk.wait(timeout=1)
                    except Exception:
                        pass
                except Exception:
                    try:
                        ahk.terminate()
                    except Exception:
                        pass
                self.root.after(0, lambda: self._finish_recording(macro_temp))

            self.recording = False
            threading.Thread(target=_wait_ahk, daemon=True).start()
            return

        self.recording = False
        self._finish_recording(getattr(self, "_record_macro_temp", ""))

    def _finish_recording(self, macro_temp):
        self._release_held()
        if macro_temp and os.path.exists(macro_temp):
            try:
                self.events = _read_csv_macro(macro_temp)
                os.remove(macro_temp)
            except Exception:
                pass

        self.c_rec.set_active(False)
        self.root.after(0, self._update_status_row)
        self.c_rec.ico.config(text=self.cfg.ico_record)
        self.c_rec.lbl.config(text="Record")
        self.root.after(0, self._reset_ui)
        self.set_status(f"Done ({len(self.events)} ev)", _C["go"], 3000)
        self._log_message(f"> recorded {len(self.events)} events")
        threading.Thread(target=self._webhook, args=("record",), daemon=True).start()
        self._auto_save_run()

    def _dt(self):
        now = _ms()
        d = now - self._last_ms
        self._last_ms = now
        return d

    def _cached_bounds(self, x, y):
        """Check if (x,y) falls on the app window, caching rects up to 200ms."""
        now = _ms()
        if now - self._cached_bounds_ts > 200:
            self._cached_bounds_ts = now
            try:
                r1 = wintypes.RECT()
                ok1 = _ct.windll.user32.GetWindowRect(self._hwnd, _ct.byref(r1))
                r2 = wintypes.RECT()
                ok2 = False
                if self._cached_swin_hwnd is not None:
                    ok2 = _ct.windll.user32.GetWindowRect(
                        self._cached_swin_hwnd, _ct.byref(r2)
                    )
                self._cached_rects = (r1 if ok1 else None, r2 if ok2 else None)
            except Exception:
                self._cached_rects = None

        rects = self._cached_rects
        if rects is not None:
            r1, r2 = rects
            if r1 is not None and (
                r1.left - _APP_PAD <= x <= r1.right + _APP_PAD
                and r1.top - _APP_PAD <= y <= r1.bottom + _APP_PAD
            ):
                return True
            if r2 is not None and (
                r2.left - _APP_PAD <= x <= r2.right + _APP_PAD
                and r2.top - _APP_PAD <= y <= r2.bottom + _APP_PAD
            ):
                return True
        return False

    def _on_key_press(self, key, is_auto_repeat=False):
        if is_auto_repeat:
            return
        vk, scan, ext = _key_to_vk(key)
        if vk:
            _KMAP = {
                0x10: "sh",
                0xA0: "sh",
                0xA1: "sh",
                0x11: "ct",
                0xA2: "ct",
                0xA3: "ct",
                0x12: "al",
                0xA4: "al",
                0xA5: "al",
                0x5B: "wn",
                0x5C: "wn",
                0x20: "sp",
                0x0D: "en",
                0x09: "tb",
                0x1B: "es",
                0x08: "bk",
                0x2E: "de",
            }
            txt = _KMAP.get(vk) or (
                chr(vk).lower()
                if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39
                else str(key).replace("'", "")[:2]
            )
            self.root.after(0, self._maybe_update_kv, txt)

    def _on_key_release(self, key):
        pass

    def toggle_play(self):
        if not self._can_start():
            return
        # S-2 fix: lock-protected clicked set reset
        with self._click_lock:
            self._clicked_this_run = set()
        self.playing = True
        self.c_play.set_active(True)
        self.root.after(0, self._update_status_row)
        self._stop_ev.clear()
        self.c_play.ico.config(text="⏹")
        self.c_play.lbl.config(text="Stop")
        self.set_status("▶ Playing", _C["go"])
        self._log_message("> playback started")
        self._anim_tick()

        # Start AHK playback process in background thread
        threading.Thread(
            target=self._ahk_playback_worker, args=(False,), daemon=True
        ).start()

    def toggle_loop(self):
        if not self._can_start():
            return
        # S-2 fix: lock-protected clicked set reset
        with self._click_lock:
            self._clicked_this_run = set()
        self.playing = self.looping = True
        self.c_loop.set_active(True)
        self.root.after(0, self._update_status_row)
        self._stop_ev.clear()
        self.c_loop.ico.config(text="⏹")
        self.c_loop.lbl.config(text="Stop")
        self.set_status("\u221e LOOP", _C["loop"])
        self._loop_warn_active = True
        stop_key = self.cfg.key_stop or "esc"
        self._log_message(f"> {stop_key} = stop")
        self._anim_tick()

        # Start AHK playback process with looping in background thread
        threading.Thread(
            target=self._ahk_playback_worker, args=(True,), daemon=True
        ).start()

    def _can_start(self):
        if self.recording:
            self._stop_recording()
            return False
        if self.playing or self.looping:
            self._stop_playback()
            return False
        if getattr(self, "running_all_images", False):
            self._stop_run_all_images()
            return False
        if not self.events:
            self.set_status("No events!", _C["rec"], 1500)
            return False
        return True

    def _stop_playback(self):
        self._stop_ev.set()
        self._pause_playback = False
        self.playing = self.looping = False

        # Terminate the running AHK process
        if self._ahk_proc is not None:
            try:
                self._ahk_proc.terminate()
            except Exception:
                pass
            self._ahk_proc = None

        # Emergency release: AHK terminate() skips OnExit, so force-release all modifiers
        _EMERGENCY_VKS = (
            0x10,
            0x11,
            0x12,
            0x5B,
            0x5C,  # Shift, Ctrl, Alt, Win L/R
            0xA0,
            0xA1,
            0xA2,
            0xA3,
            0xA4,
            0xA5,  # L/R variants
            0x57,
            0x41,
            0x53,
            0x44,  # WASD
            0x25,
            0x26,
            0x27,
            0x28,  # Arrows
            0x20,
            0x0D,
            0x1B,
            0x09,  # Space, Enter, Esc, Tab
            0x51,
            0x45,
            0x52,
            0x46,  # Q, E, R, F
            0x08,
            0x2E,
            0x14,  # BS, Del, Caps
            0x70,
            0x71,
            0x72,
            0x73,
            0x74,
            0x75,
            0x76,
            0x77,  # F1-F8
            0x21,
            0x22,
            0x23,
            0x24,
            0x2D,
            0x2E,  # PgUp, PgDn, End, Home, Ins, Del
        )
        for vk in _EMERGENCY_VKS:
            try:
                sc = user32.MapVirtualKeyW(vk, 0)
                _send_input(_make_key(vk, sc, True, vk in _EXTENDED_VKS))
            except Exception:
                pass

        self.root.after(0, self._reset_ui)
        self.root.after(0, self._update_status_row)
        self.set_status("Stopped", None, 1500)

    def _toggle_pause(self):
        if self._ahk_proc is not None:
            self.set_status("Pause not supported in AHK mode", _C["rec"], 1500)
            return
        self._pause_playback = not self._pause_playback
        label = "Resume" if self._pause_playback else "Pause"
        self.c_pause.ico.config(text="\u25b6" if self._pause_playback else "\u23f8")
        self.c_pause.lbl.config(text=label)
        self.set_status(label, _C["loop"])

    def _reset_ui(self):
        with self._held_lock:
            self._currently_pressed_vks.clear()
        self.c_rec.set_active(False)
        self.c_play.set_active(False)
        self.c_loop.set_active(False)
        self.root.after(0, self._update_status_row)
        # Reset icon colours from animation
        self.c_rec.ico.config(fg=_C["icon_fg"])
        self.c_play.ico.config(fg=_C["icon_fg"])
        self.c_loop.ico.config(fg=_C["icon_fg"])
        self.c_play.ico.config(text=self.cfg.ico_play)
        self.c_play.lbl.config(text="Play")
        self.c_loop.ico.config(text=self.cfg.ico_loop)
        self.c_loop.lbl.config(text="Loop")
        self.c_rec.ico.config(text=self.cfg.ico_record)
        self.c_rec.lbl.config(text="Record")
        self.c_pause.ico.config(text="\u23f8")
        self.c_pause.lbl.config(text="Pause")
        self._pause_playback = False
        self._loop_warn_active = False

    def _ahk_playback_worker(self, loop):
        t0 = time.perf_counter()
        ahk_path = _find_autohotkey()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ahk_script = os.path.join(script_dir, "TinyKullan.ahk")

        if not os.path.exists(ahk_script) or not os.path.exists(ahk_path):
            self.set_status("AHK not installed", _C["rec"], 4000)
            self.playing = self.looping = False
            self.root.after(0, self._reset_ui)
            return

        import subprocess
        import tempfile

        _cleanup_macro_temp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".txt",
                prefix="tkmacro_",
                delete=False,
                encoding="utf-8",
            ) as tf:
                macro_temp = tf.name
                _cleanup_macro_temp = macro_temp
        except Exception:
            macro_temp = os.path.join(script_dir, f"temp_macro_{os.getpid()}.txt")
            _cleanup_macro_temp = macro_temp

        with self._ev_lock:
            evs_snapshot = list(self.events)
        _write_csv_macro(evs_snapshot, macro_temp)

        speed = max(0.1, min(10.0, self.cfg.speed))
        args = [ahk_path, ahk_script, "/play", macro_temp]
        if speed != 1.0:
            args.extend(["/speed", str(speed)])
        creationflags = 0x08000000 if sys.platform == "win32" else 0

        iteration = [0]
        _LOG.info(
            "AHK PLAY: exe=%s  script=%s",
            os.path.abspath(ahk_path),
            os.path.abspath(ahk_script),
        )

        def _cleanup():
            try:
                if _cleanup_macro_temp and os.path.exists(_cleanup_macro_temp):
                    os.remove(_cleanup_macro_temp)
            except Exception:
                pass

        def _finish(err=None):
            if self._ahk_proc is not None:
                try:
                    self._ahk_proc.terminate()
                except Exception:
                    pass
                self._ahk_proc = None
            _cleanup()
            if getattr(self, "_recovering", False):
                return
            play_ms = int((time.perf_counter() - t0) * 1000)
            self.playing = self.looping = False
            self.root.after(0, self._reset_ui)
            if err:
                self.root.after(0, lambda: self.set_status(err, _C["rec"], 4000))
            elif loop and iteration[0] > 1:
                self.root.after(
                    0,
                    lambda: self.set_status(f"∞ {iteration[0]} loops", _C["go"], 2000),
                )
            else:
                self.root.after(0, lambda: self.set_status("✓ Done", _C["go"], 1500))
            threading.Thread(
                target=self._post_play, args=(play_ms, loop), daemon=True
            ).start()

        def _on_ahk_done():
            self._ahk_proc = None
            iteration[0] += 1
            if self._stop_ev.is_set() or not loop:
                _finish()
                return
            self._log_message(f"> looped {iteration[0]}x")
            self.root.after(
                0,
                lambda: self.set_status(
                    f"\u221e {iteration[0]}  |  esc = stop", _C["loop"]
                ),
            )
            # Send webhook with screenshot+embed after each loop iteration
            if self.cfg.wh_loop:
                threading.Thread(
                    target=self._post_play, args=(0, True, True), daemon=True
                ).start()
            # Schedule next iteration via main loop
            self.root.after(50, _spawn)

        def _spawn():
            if self._stop_ev.is_set():
                _finish()
                return
            try:
                self._ahk_proc = subprocess.Popen(args, creationflags=creationflags)
            except Exception as e:
                _LOG.error("AHK spawn failed: %s", e)
                _finish("AHK spawn failed")
                return
            self.root.after(100, _poll)

        def _poll():
            if self._ahk_proc is None:
                return
            ret = self._ahk_proc.poll()
            if ret is None:
                self.root.after(100, _poll)
            else:
                _on_ahk_done()

        self.root.after(0, _spawn)

    def _calc_activity_score(self, hours, runs):
        """Calculate activity score from runs and hours using idea math.
        Score = (runs x 10) + (hours x 50) + consistency bonus + streak bonus
        Returns dict with full breakdown for dashboard display."""
        runs = max(0, int(runs))
        hours = max(0.0, float(hours))

        run_pts = runs * 10
        hour_pts = hours * 50

        # Consistency bonus: more runs = more consistent = bonus multiplier
        if runs >= 500:
            consistency = 500
        elif runs >= 200:
            consistency = 200
        elif runs >= 100:
            consistency = 100
        elif runs >= 50:
            consistency = 40
        elif runs >= 20:
            consistency = 15
        elif runs >= 5:
            consistency = 5
        else:
            consistency = 0

        # Streak bonus: based on total engagement depth (hours per run)
        if runs >= 1:
            hpr = hours / runs  # hours per run
        else:
            hpr = 0
        if hpr >= 2.0:
            streak = 300
        elif hpr >= 1.0:
            streak = 150
        elif hpr >= 0.5:
            streak = 75
        elif hpr >= 0.1:
            streak = 30
        else:
            streak = 0

        total = int(run_pts + hour_pts + consistency + streak)
        return {
            "total": total,
            "run_pts": int(run_pts),
            "hour_pts": int(hour_pts),
            "consistency": consistency,
            "streak": streak,
        }

    def _get_rank(self, hours, runs=0):
        """Return rank dict with emoji, name, level number, and next-rank info.
        Ranks are based on activity score (runs x 10 + hours x 50 + bonuses)."""
        ranks = self.cfg.dash_rank_names or {}
        emojis = self.cfg.dash_rank_emojis or {}
        score_info = self._calc_activity_score(hours, runs)
        score = score_info["total"]

        TIERS = [
            (50000, "\u2726", "Legend", 5, 50000),
            (10000, "\U0001f3c6", "Master", 4, 50000),
            (2000, "\U0001f451", "Expert", 3, 10000),
            (500, "\U0001f48e", "Pro", 2, 2000),
            (100, "\u26a1", "Apprentice", 1, 500),
            (0, "\U0001f331", "Beginner", 0, 100),
        ]

        for threshold, emoji, name, level, next_threshold in TIERS:
            if score >= threshold:
                display_name = ranks.get(str(threshold), name)
                display_emoji = emojis.get(str(threshold), emoji)
                prev = threshold
                next_t = next_threshold
                if prev == next_t:
                    pct = 100.0
                else:
                    span = max(1, next_t - prev)
                    pct = min(100.0, max(0.0, ((score - prev) / span) * 100.0))
                return {
                    "emoji": display_emoji,
                    "name": display_name,
                    "level": level,
                    "score": score,
                    "score_info": score_info,
                    "prev": prev,
                    "next": next_t,
                    "pct": pct,
                    "display": f"{display_emoji} {display_name}",
                    "threshold": threshold,
                }

        return {
            "emoji": "\U0001f331",
            "name": "Beginner",
            "level": 0,
            "score": 0,
            "score_info": score_info,
            "prev": 0,
            "next": 100,
            "pct": 0,
            "display": "\U0001f331 Beginner",
            "threshold": 0,
        }

    JS_SCRIPT = """<script>
var _ed=false;
var PRESETS=['#1a1a2e','#16213e','#0f3460','#1b1b2f','#2d1b3d','#1a1a1a'];
function toggleEdit(){
_ed=!_ed;var b=document.querySelector(".pen");
if(_ed){
b.innerHTML="💾 Save All";b.style.cssText="background:rgba(74,222,128,.25);border-color:rgba(74,222,128,.5);color:#fff;padding:8px 18px;border-radius:999px;cursor:pointer;font-size:13px;font-weight:700;border:1px solid";
document.querySelectorAll(".ico,.bt,.editable,.rn,.re").forEach(function(e){e.contentEditable="true";e.style.outline="2px dashed rgba(255,209,102,.6)";e.style.borderRadius="4px"});
document.querySelectorAll(".bg-presets,.bg-picker-row").forEach(function(e){e.style.display="flex"});
document.querySelectorAll(".preset-dot").forEach(function(e){e.style.pointerEvents="auto"});
}else{
b.innerHTML="🖊️ Edit Dashboard";b.style.cssText="background:rgba(157,124,255,.2);border-color:rgba(157,124,255,.4);color:#f7edff;padding:8px 18px;border-radius:999px;cursor:pointer;font-size:13px;font-weight:700;border:1px solid";
document.querySelectorAll(".ico,.bt,.editable,.rn,.re").forEach(function(e){e.contentEditable="false";e.style.outline="";e.style.borderRadius=""});
document.querySelectorAll(".bg-presets,.bg-picker-row").forEach(function(e){e.style.display="none"});
document.querySelectorAll(".preset-dot").forEach(function(e){e.style.pointerEvents="none"});
var t={},i={},rn={},re={};
document.querySelectorAll("[data-key]").forEach(function(e){var k=e.getAttribute("data-key");if(e.classList.contains("ico"))i[k]=e.textContent.trim();else if(e.classList.contains("rn"))rn[k]=e.textContent.trim();else if(e.classList.contains("re"))re[k]=e.textContent.trim();else t[k]=e.textContent.trim()});
var bg=document.getElementById("bgColorPicker")?document.getElementById("bgColorPicker").value:document.documentElement.style.getPropertyValue("--bg")||"#1a1a2e";
var title=document.getElementById("dashTitle")?document.getElementById("dashTitle").innerHTML.replace(/<br\\s*\\/?>/gi,"\\n"):"Macro\\nDashboard";
var subtitle=document.getElementById("dashSubtitle")?document.getElementById("dashSubtitle").textContent:"";
b.innerHTML="⏳ Saving...";
fetch("/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({badgeTexts:t,badgeIcons:i,rankNames:rn,rankEmojis:re,bgColor:bg,title:title,subtitle:subtitle})}).then(function(r){b.innerHTML=r.ok?"✅ Saved!":"❌ Error";setTimeout(function(){b.innerHTML="🖊️ Edit Dashboard";b.style.cssText="background:rgba(157,124,255,.2);border-color:rgba(157,124,255,.4);color:#f7edff;padding:8px 18px;border-radius:999px;cursor:pointer;font-size:13px;font-weight:700;border:1px solid"},2000)}).catch(function(){b.innerHTML="❌ Error"});
}}
function applyPreset(color){
document.getElementById("bgColorPicker").value=color;
document.documentElement.style.setProperty("--bg",color);
document.body.style.background="radial-gradient(circle at 20% 15%,"+shadeColor(color,30)+" 0,"+shadeColor(color,8)+" 35%,"+color+" 72%)";
}
function changeBgColor(){
var picker=document.getElementById("bgColorPicker");
if(picker){
document.documentElement.style.setProperty("--bg",picker.value);
document.body.style.background="radial-gradient(circle at 20% 15%,"+shadeColor(picker.value,30)+" 0,"+shadeColor(picker.value,8)+" 35%,"+picker.value+" 72%)";
}}
function shadeColor(color,percent){
var R=parseInt(color.substring(1,3),16);
var G=parseInt(color.substring(3,5),16);
var B=parseInt(color.substring(5,7),16);
R=parseInt(R*(100+percent)/100);
G=parseInt(G*(100+percent)/100);
B=parseInt(B*(100+percent)/100);
R=(R<255)?R:255;G=(G<255)?G:255;B=(B<255)?B:255;
var RR=((R.toString(16).length==1)?"0"+R.toString(16):R.toString(16));
var GG=((G.toString(16).length==1)?"0"+G.toString(16):G.toString(16));
var BB=((B.toString(16).length==1)?"0"+B.toString(16):B.toString(16));
return "#"+RR+GG+BB;
}
document.addEventListener("mouseover",function(e){
if(!_ed)return;
var t=e.target.closest("[data-key],#dashTitle,#dashSubtitle");
if(t&&!t.querySelector(".hover-pen")){
var pen=document.createElement("span");pen.className="hover-pen";pen.innerHTML="&#x1F58A;";pen.style.cssText="position:absolute;right:-20px;top:0;font-size:14px;cursor:pointer;opacity:.7;";
t.style.position="relative";t.appendChild(pen);
}});
document.addEventListener("mouseout",function(e){
if(!_ed)return;
var t=e.target.closest("[data-key],#dashTitle,#dashSubtitle");
if(t){var p=t.querySelector(".hover-pen");if(p)p.remove();}
});
</script>"""

    def _start_stats_server(self):
        cfg = self.cfg
        me = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hours = max(0.0, cfg.stats_total_minutes / 60.0)
                runs = max(0, int(cfg.stats_run_count))
                rank = me._get_rank(hours, runs)
                score_info = rank["score_info"]
                avg = (cfg.stats_total_minutes / runs) if runs else 0
                today = datetime.now().strftime("%B %d, %Y")
                bg = cfg.dash_bg_color or "#1a1a2e"
                title_html = cfg.dash_title.replace("\\n", "<br>")
                subtitle = cfg.dash_subtitle
                safe_emoji = (
                    str(rank["emoji"])
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                safe_name = (
                    str(rank["name"])
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )

                badge_states = [
                    ("b0", rank["level"] >= 0),
                    ("b1", rank["level"] >= 1),
                    ("b2", rank["level"] >= 2),
                    ("b3", rank["level"] >= 3),
                    ("b4", rank["level"] >= 4),
                ]

                htm = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TinyKullan Dashboard</title>
<style>
:root{{--bg:{bg};--panel:rgba(255,255,255,.06);--panel2:rgba(255,255,255,.04);--line:rgba(255,255,255,.12);--txt:#f0f0f0;--muted:#a0a0b8;--acc:#7c8cfc;--hot:#fc6c8c;--gold:#ffc144;--green:#4ade80;--cyan:#22d3ee}}
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;font-family:'Segoe UI',Inter,system-ui,sans-serif;color:var(--txt);background:radial-gradient(circle at 20% 15%,{bg} 0,{bg} 35%,{bg} 72%);overflow-x:hidden;transition:background .5s}}
body::before{{content:"";position:fixed;inset:0;background:linear-gradient(rgba(255,255,255,.02) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.02) 1px,transparent 1px);background-size:48px 48px;mask-image:linear-gradient(to bottom,#000,transparent 88%);pointer-events:none;z-index:0}}
.wrap{{width:min(960px,94vw);margin:40px auto;position:relative;z-index:1}}
.top-bar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px;gap:16px;flex-wrap:wrap}}
.brand{{display:flex;gap:12px;align-items:center}}
.logo{{width:44px;height:44px;border-radius:14px;background:linear-gradient(135deg,var(--acc),var(--hot));display:grid;place-items:center;font-size:20px;color:#fff;box-shadow:0 0 28px rgba(124,140,252,.35)}}
.brand-text{{font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--muted)}}

/* Hero cards */
.hero{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:20px;backdrop-filter:blur(20px);overflow:hidden}}
.card-glow{{box-shadow:0 20px 60px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.06)}}
.main-card{{padding:32px}}
.rank-badge{{display:inline-flex;gap:10px;align-items:center;padding:10px 18px;border-radius:999px;background:rgba(255,193,68,.10);border:1px solid rgba(255,193,68,.30);color:var(--gold);font-weight:800;font-size:14px;letter-spacing:.5px;margin-bottom:20px}}
h1{{font-size:52px;line-height:1.05;margin:0 0 8px;font-weight:900;letter-spacing:-2px;color:var(--txt)}}
.subtitle{{color:var(--muted);font-size:14px;line-height:1.6;max-width:440px}}

/* Stats side card */
.stats-card{{padding:26px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;gap:8px}}
.big-score{{font-size:80px;font-weight:950;letter-spacing:-4px;line-height:1;background:linear-gradient(135deg,var(--acc),var(--cyan),var(--gold));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.big-score-label{{color:var(--muted);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:2px}}

/* Activity Score Breakdown */
.score-section{{margin-bottom:20px}}
.score-section h3{{font-size:12px;text-transform:uppercase;letter-spacing:2px;color:var(--muted);margin:0 0 14px}}
.math-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.math-item{{padding:16px 12px;border-radius:14px;background:var(--panel2);border:1px solid var(--line);text-align:center}}
.math-num{{font-size:26px;font-weight:900;color:var(--txt)}}
.math-lbl{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px}}
.math-formula{{font-size:9px;color:var(--muted);opacity:.6;margin-top:2px}}

/* Stats grid */
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}}
.stat{{padding:22px;border-radius:18px;background:var(--panel2);border:1px solid var(--line)}}
.num{{font-size:30px;font-weight:900;letter-spacing:-1px}}
.lbl{{color:var(--muted);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-top:6px}}

/* Progress */
.progress-card{{padding:26px;margin-bottom:20px}}
.progress-top{{display:flex;justify-content:space-between;gap:16px;color:var(--muted);font-size:13px;margin-bottom:14px}}
.progress-top b{{color:var(--txt)}}
.progress-bar{{height:16px;background:rgba(0,0,0,.30);border-radius:999px;padding:3px;border:1px solid var(--line)}}
.progress-fill{{height:100%;width:{rank["pct"]:.0f}%;border-radius:999px;background:linear-gradient(90deg,var(--acc),var(--hot),var(--gold));box-shadow:0 0 24px rgba(124,140,252,.40);transition:width 1.2s ease}}

/* Badges */
.badges{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}
.badge{{padding:18px 10px;text-align:center;border-radius:16px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--muted);transition:all .3s}}
.badge.on{{background:linear-gradient(135deg,rgba(124,140,252,.22),rgba(252,108,140,.10));color:var(--txt);border-color:rgba(124,140,252,.40)}}
.badge .ico{{font-size:28px;margin-bottom:6px}}
.badge .bt{{font-size:11px;font-weight:700}}

/* Background presets */
.bg-presets{{display:none;gap:10px;margin-top:10px;align-items:center;flex-wrap:wrap}}
.bg-presets span{{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px}}
.preset-dot{{width:26px;height:26px;border-radius:50%;border:2px solid var(--line);cursor:pointer;pointer-events:none;transition:transform .15s,box-shadow .15s}}
.preset-dot:hover{{transform:scale(1.2);box-shadow:0 0 14px rgba(255,255,255,.20)}}
.bg-picker-row{{display:none;margin-top:8px;align-items:center;gap:8px}}
.bg-picker-row label{{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px}}
.bg-picker-row input{{border:1px solid var(--line);border-radius:10px;padding:4px 8px;background:var(--panel2);color:var(--txt);cursor:pointer;height:32px;width:50px}}

.edit-bar{{text-align:right;margin-bottom:14px;width:min(960px,94vw);margin:0 auto 14px}}
.edit-bar button{{transition:all .2s}}
.edit-bar button:hover{{transform:translateY(-1px)}}

.footer{{text-align:center;color:var(--muted);font-size:11px;opacity:.7;margin-top:22px;padding-bottom:30px}}

@media(max-width:750px){{
.hero,.grid,.badges,.math-grid{{grid-template-columns:1fr 1fr}}
h1{{font-size:36px}}
.big-score{{font-size:56px}}
}}
@media(max-width:500px){{
.hero,.grid,.badges,.math-grid{{grid-template-columns:1fr}}
h1{{font-size:30px}}
.big-score{{font-size:44px}}
}}
</style>
</head>
<body>
<main class="wrap">

<div class="top-bar">
<div class="brand">
<div class="logo">⬡</div>
<div class="brand-text">TinyKullan Stats</div>
</div>
<div class="brand-text" style="font-weight:400;letter-spacing:0;text-transform:none;font-size:12px">{today}</div>
</div>

<!-- Hero -->
<section class="hero">
<div class="card card-glow main-card">
<div class="rank-badge"><span class="re" data-key="{rank["threshold"]}">{safe_emoji}</span> <span class="rn" data-key="{rank["threshold"]}">{safe_name}</span></div>
<h1 class="editable" id="dashTitle">{title_html}</h1>
<p class="subtitle editable" id="dashSubtitle">{subtitle}</p>
</div>
<div class="card card-glow stats-card">
<div class="big-score">{rank["score"]}</div>
<div class="big-score-label">Activity Score</div>
</div>
</section>

<!-- Score Breakdown -->
<section class="card card-glow progress-card score-section">
<h3>Score Breakdown (idea math)</h3>
<div class="math-grid">
<div class="math-item">
<div class="math-num">{score_info["run_pts"]}</div>
<div class="math-lbl">Run Points</div>
<div class="math-formula">{runs} runs x 10</div>
</div>
<div class="math-item">
<div class="math-num">{score_info["hour_pts"]}</div>
<div class="math-lbl">Hour Points</div>
<div class="math-formula">{hours:.1f}h x 50</div>
</div>
<div class="math-item">
<div class="math-num">+{score_info["consistency"]}</div>
<div class="math-lbl">Consistency</div>
<div class="math-formula">{runs} runs bonus</div>
</div>
<div class="math-item">
<div class="math-num">+{score_info["streak"]}</div>
<div class="math-lbl">Depth Bonus</div>
<div class="math-formula">{hours / max(1, runs):.1f}h/run</div>
</div>
</div>
</section>

<!-- Stats Grid -->
<section class="grid">
<div class="stat card-glow"><div class="num">{runs}</div><div class="lbl">Total Runs</div></div>
<div class="stat card-glow"><div class="num">{hours:.1f}h</div><div class="lbl">Total Playtime</div></div>
<div class="stat card-glow"><div class="num">{cfg.stats_total_minutes:.0f}m</div><div class="lbl">Minutes Macroed</div></div>
<div class="stat card-glow"><div class="num">{avg:.1f}m</div><div class="lbl">Avg Run Time</div></div>
</section>

<!-- Rank Progress -->
<section class="card card-glow progress-card">
<div class="progress-top"><span>Rank progress: <b>{rank["prev"]}</b> pts → <b>{rank["next"]}</b> pts ({rank["name"]})</span><span><b>{rank["pct"]:.0f}%</b></span></div>
<div class="progress-bar"><div class="progress-fill"></div></div>
<div class="badges" style="margin-top:20px">
<div class="badge {"on" if rank["level"] >= 0 else ""}" data-key="b0"><div class="ico" data-key="b0">{cfg.dash_badge_icons.get("b0", "🌱")}</div><span class="bt" data-key="b0">{cfg.dash_badge_texts.get("b0", "Beginner")}</span></div>
<div class="badge {"on" if rank["level"] >= 1 else ""}" data-key="b1"><div class="ico" data-key="b1">{cfg.dash_badge_icons.get("b1", "⚡")}</div><span class="bt" data-key="b1">{cfg.dash_badge_texts.get("b1", "Apprentice")}</span></div>
<div class="badge {"on" if rank["level"] >= 2 else ""}" data-key="b2"><div class="ico" data-key="b2">{cfg.dash_badge_icons.get("b2", "💎")}</div><span class="bt" data-key="b2">{cfg.dash_badge_texts.get("b2", "Pro")}</span></div>
<div class="badge {"on" if rank["level"] >= 3 else ""}" data-key="b3"><div class="ico" data-key="b3">{cfg.dash_badge_icons.get("b3", "👑")}</div><span class="bt" data-key="b3">{cfg.dash_badge_texts.get("b3", "Expert")}</span></div>
<div class="badge {"on" if rank["level"] >= 4 else ""}" data-key="b4"><div class="ico" data-key="b4">{cfg.dash_badge_icons.get("b4", "🏆")}</div><span class="bt" data-key="b4">{cfg.dash_badge_texts.get("b4", "Master")}</span></div>
</div>
</section>

<div class="footer">TinyKullan v5 • refresh to update stats • runs at <b>127.0.0.1:9270</b></div>

</main>

<div class="edit-bar">
<div class="bg-presets">
<span>Presets:</span>
<button class="preset-dot" style="background:#1a1a2e" onclick="applyPreset('#1a1a2e')" title="Midnight"></button>
<button class="preset-dot" style="background:#16213e" onclick="applyPreset('#16213e')" title="Ocean"></button>
<button class="preset-dot" style="background:#0f3460" onclick="applyPreset('#0f3460')" title="Deep Blue"></button>
<button class="preset-dot" style="background:#1b1b2f" onclick="applyPreset('#1b1b2f')" title="Slate"></button>
<button class="preset-dot" style="background:#2d1b3d" onclick="applyPreset('#2d1b3d')" title="Plum"></button>
<button class="preset-dot" style="background:#1a1a1a" onclick="applyPreset('#1a1a1a')" title="Charcoal"></button>
</div>
<div class="bg-picker-row">
<label>Custom:</label>
<input type="color" id="bgColorPicker" value="{bg}" onchange="changeBgColor()">
</div>
<button class="pen" onclick="toggleEdit()" style="background:rgba(157,124,255,.2);border:1px solid rgba(157,124,255,.4);color:#f7edff;padding:8px 18px;border-radius:999px;cursor:pointer;font-size:13px;font-weight:700;margin-left:auto;display:block">🖊️ Edit Dashboard</button>
</div>

{me.JS_SCRIPT}
</body>
</html>"""
                self.send_response(200)
                self.send_header("Content-type", "text/html;charset=utf-8")
                self.end_headers()
                self.wfile.write(htm.encode("utf-8"))

            def log_message(self, f, *a):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                if length > 0 and self.path == "/save":
                    body = self.rfile.read(length)
                    try:
                        data = json.loads(body.decode())
                        me.cfg.dash_badge_texts = data.get("badgeTexts", {})
                        me.cfg.dash_badge_icons = data.get("badgeIcons", {})
                        me.cfg.dash_rank_names = data.get("rankNames", {})
                        me.cfg.dash_rank_emojis = data.get("rankEmojis", {})
                        if data.get("bgColor"):
                            me.cfg.dash_bg_color = data["bgColor"]
                        if data.get("title"):
                            me.cfg.dash_title = data["title"]
                        if data.get("subtitle"):
                            me.cfg.dash_subtitle = data["subtitle"]
                        me.cfg.save()
                        self.send_response(200)
                    except Exception:
                        self.send_response(400)
                else:
                    self.send_response(404)
                self.end_headers()

        try:
            if getattr(self, "_stats_server", None) is None:
                self._stats_server = http.server.HTTPServer(("127.0.0.1", 9270), H)
                threading.Thread(
                    target=self._stats_server.serve_forever, daemon=True
                ).start()
            self.set_status("Dashboard: http://127.0.0.1:9270", _C["acc"], 5000)
            webbrowser.open("http://127.0.0.1:9270")
        except OSError as e:
            if e.winerror == 10048 or getattr(e, "errno", None) == 98:
                self.set_status("Dashboard: http://127.0.0.1:9270", _C["acc"], 5000)
                webbrowser.open("http://127.0.0.1:9270")
            else:
                _LOG.warning("Stats server OSError: %s", e)
                self.set_status("Dashboard failed", _C["rec"], 2000)
        except Exception as e:
            _LOG.warning("Stats server: %s", e)
            self.set_status("Dashboard failed", _C["rec"], 2000)

    def _open_macro_editor(self):
        # Bug 22: Guard against multiple editor windows
        if hasattr(self, "_ed_win") and self._ed_win and self._ed_win.winfo_exists():
            self._ed_win.lift()
            return
        ed = tk.Toplevel(self.root)
        self._ed_win = ed
        ed.title("Macro Editor")
        ed.configure(bg=SBG)
        ed.geometry("640x460+150+80")
        ed.attributes("-topmost", True)
        try:
            _round_hwnd(_get_hwnd(ed.winfo_id()))
        except Exception:
            pass

        # Undo stack for macro editor actions
        undo_stack = []

        def save_state():
            with self._ev_lock:
                undo_stack.append([dict(ev) for ev in self.events])

        def perform_undo(event=None):
            if undo_stack:
                state = undo_stack.pop()
                with self._ev_lock:
                    self.events.clear()
                    self.events.extend(state)
                self.set_status("Undo successful", _C["go"], 1000)
                _refresh_list()
            else:
                self.set_status("Nothing to undo", _C["rec"], 1000)

        # Header
        hdr = tk.Frame(ed, bg=SSURF, height=32)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="  Macro Editor", bg=SSURF, fg=STEXT, font=("Segoe UI", 9, "bold")
        ).pack(side="left", padx=6)
        cnt_lbl = tk.Label(hdr, text="", bg=SSURF, fg=SMUTED, font=("Segoe UI", 7))
        cnt_lbl.pack(side="left", padx=8)
        close_btn = tk.Label(
            hdr,
            text=" ✕ ",
            bg=SSURF,
            fg=SMUTED,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=4)
        close_btn.bind("<Button-1>", lambda _: _on_ed_close())

        # Bug 22: Clear editor window reference on close
        def _on_ed_close():
            self._ed_win = None
            try:
                ed.destroy()
            except Exception:
                pass

        ed.protocol("WM_DELETE_WINDOW", _on_ed_close)

        # Main body: list + edit panel
        body = tk.Frame(ed, bg=SBG)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # Search filter bar
        _filter_text = [""]  # mutable container for closure
        search_frame = tk.Frame(body, bg=SBG)
        search_frame.pack(fill="x", pady=(0, 4))
        tk.Label(search_frame, text="🔍", bg=SBG, fg=SMUTED, font=("Segoe UI", 8)).pack(
            side="left", padx=(0, 4)
        )
        _search_entry = tk.Entry(
            search_frame,
            bg=SED,
            fg=STEXT,
            insertbackground=SACC,
            relief="flat",
            font=("Consolas", 8),
        )
        _search_entry.pack(side="left", fill="x", expand=True)
        tk.Label(
            search_frame, text="ESC to clear", bg=SBG, fg=SMUTED, font=("Segoe UI", 6)
        ).pack(side="left", padx=(4, 0))
        _search_entry.bind(
            "<KeyRelease>",
            lambda _: (
                _filter_text.__setitem__(0, _search_entry.get().strip().lower()),
                _refresh_list(),
            ),
        )
        ed.bind(
            "<Escape>",
            lambda _: (
                _search_entry.delete(0, "end"),
                _filter_text.__setitem__(0, ""),
                _refresh_list(),
            ),
        )

        list_frame = tk.Frame(body, bg=SBG)
        list_frame.pack(side="left", fill="both", expand=True)

        class VirtualEventList:
            """Canvas-based virtual list — O(visible) not O(total)."""

            ROW_H = 24

            def __init__(self, parent):
                self.outer = tk.Frame(parent, bg=SBG, width=380, height=350)
                self.outer.pack_propagate(False)
                self.outer.pack(side="left", fill="both", expand=True)
                self._sb = tk.Scrollbar(
                    self.outer,
                    orient="vertical",
                    bg=SSURF,
                    troughcolor=SBG,
                    activebackground=SACC,
                    relief="flat",
                    bd=0,
                )
                self._sb.pack(side="right", fill="y")
                self._cv = tk.Canvas(
                    self.outer,
                    bg=SBG,
                    highlightthickness=0,
                    bd=0,
                    yscrollcommand=self._update_scrollbar,
                )
                self._cv.pack(side="left", fill="both", expand=True)
                self._sb.config(command=self._on_sb)
                self.selected_indices = set()
                self.on_select_cb = None
                self._on_reorder_cb = None
                self._items = []  # [(display_text, ev_dict), ...]
                self._top_idx = 0
                self._hovered_idx = -1
                self._drag_idx = None
                self._drag_y = 0.0
                self._width = 380
                self._height = 350
                self._empty_lbl = tk.Label(
                    self._cv,
                    text="No events.\nUse Quick Add to create one.",
                    bg=SBG,
                    fg=SMUTED,
                    font=("Segoe UI", 9),
                    justify="center",
                    anchor="center",
                )
                self._empty_win = self._cv.create_window(
                    190, 120, window=self._empty_lbl, anchor="center"
                )
                self._cv.bind("<Configure>", self._on_configure)
                self._cv.bind("<Button-1>", self._on_click)
                self._cv.bind("<B1-Motion>", self._on_b1_motion)
                self._cv.bind("<ButtonRelease-1>", self._on_b1_release)
                self._cv.bind("<Motion>", self._on_motion)
                self._cv.bind("<Leave>", self._on_leave)
                self._cv.bind("<MouseWheel>", self._on_mousewheel)
                self._cv.bind("<Button-4>", self._on_mousewheel)
                self._cv.bind("<Button-5>", self._on_mousewheel)
                self.outer.bind(
                    "<Enter>",
                    lambda _: self._cv.bind_all("<MouseWheel>", self._on_mousewheel),
                )
                self.outer.bind(
                    "<Leave>", lambda _: self._cv.unbind_all("<MouseWheel>")
                )

            def _update_scrollbar(self, *_):
                total = len(self._items)
                if total == 0:
                    self._sb.set(0.0, 1.0)
                    return
                vis = self._vis_count()
                lo = self._top_idx / total
                self._sb.set(lo, min(1.0, (self._top_idx + vis) / total))

            def _on_sb(self, action, value, unit=None):
                total = len(self._items)
                vis = self._vis_count()
                if action == "moveto":
                    self._top_idx = int(float(value) * total)
                elif action == "scroll":
                    self._top_idx += int(value) * (vis - 1 if unit == "pages" else 1)
                self._clamp_top()
                self._redraw()

            def _on_mousewheel(self, e):
                if hasattr(e, "num") and e.num == 4:
                    delta = -3
                elif hasattr(e, "num") and e.num == 5:
                    delta = 3
                elif hasattr(e, "delta") and e.delta:
                    delta = int(-1 * (e.delta / 120)) * 3
                else:
                    delta = 0
                self._top_idx += delta
                self._clamp_top()
                self._redraw()

            def _vis_count(self):
                return max(1, self._height // self.ROW_H + 1)

            def _clamp_top(self):
                self._top_idx = max(
                    0, min(self._top_idx, max(0, len(self._items) - self._vis_count()))
                )

            def _y_to_idx(self, y):
                return self._top_idx + int(y // self.ROW_H)

            def _on_configure(self, e):
                self._width = e.width
                self._height = e.height
                self._cv.coords(self._empty_win, e.width // 2, e.height // 2)
                self._redraw()

            def _redraw(self):
                self._cv.delete("vrow")
                total = len(self._items)
                if total == 0:
                    self._cv.itemconfigure(self._empty_win, state="normal")
                    self._update_scrollbar()
                    return
                self._cv.itemconfigure(self._empty_win, state="hidden")
                self._clamp_top()
                w = self._width
                for slot in range(self._vis_count()):
                    idx = self._top_idx + slot
                    if idx >= total:
                        break
                    text, _ = self._items[idx]
                    y0 = slot * self.ROW_H
                    y1 = y0 + self.ROW_H - 1
                    is_sel = idx in self.selected_indices
                    is_hov = idx == self._hovered_idx
                    bg, fg, pf = (
                        (SACC, SBG, SBG)
                        if is_sel
                        else (SED, STEXT, SACC)
                        if is_hov
                        else (SSURF, STEXT, SSURF)
                    )
                    self._cv.create_rectangle(
                        0, y0, w, y1, fill=bg, outline="", tags="vrow"
                    )
                    self._cv.create_text(
                        8,
                        y0 + self.ROW_H // 2,
                        text=text,
                        anchor="w",
                        fill=fg,
                        font=("Consolas", 8),
                        width=max(w - 46, 40),
                        tags="vrow",
                    )
                    self._cv.create_text(
                        w - 8,
                        y0 + self.ROW_H // 2,
                        text="✏",
                        anchor="e",
                        fill=pf,
                        font=("Segoe UI", 9),
                        tags="vrow",
                    )
                self._update_scrollbar()

            def _on_motion(self, e):
                idx = self._y_to_idx(e.y)
                if idx != self._hovered_idx:
                    self._hovered_idx = idx
                    self._redraw()

            def _on_leave(self, e):
                if self._hovered_idx != -1:
                    self._hovered_idx = -1
                    self._redraw()

            def _on_click(self, e):
                idx = self._y_to_idx(e.y)
                if not (0 <= idx < len(self._items)):
                    return
                if e.x >= self._width - 30:
                    self._do_pen_click(idx, self._items[idx][1])
                    return
                ctrl = bool(e.state & 0x0004)
                if ctrl:
                    self.select_toggle(idx)
                    self._drag_idx = idx
                    self._drag_y = float(e.y_root)
                    # S-11 fix: save undo state ONCE at drag start, not on every swap
                    save_state()
                else:
                    self.selection_set(idx)
                if self.on_select_cb:
                    self.on_select_cb()

            def _on_b1_motion(self, e):
                if self._drag_idx is None:
                    return
                dy = e.y_root - self._drag_y
                if abs(dy) < self.ROW_H:
                    return
                self._drag_y = float(e.y_root)
                direction = 1 if dy > 0 else -1
                new_idx = self._drag_idx + direction
                if 0 <= new_idx < len(self._items) and self._on_reorder_cb:
                    self._on_reorder_cb(self._drag_idx, new_idx)
                    self._drag_idx = new_idx

            def _on_b1_release(self, e):
                self._drag_idx = None

            def _do_pen_click(self, idx, ev):
                # S-10 fix: guard against playback starting while modal is open
                if (
                    self._master._app_busy()
                    if hasattr(self._master, "_app_busy")
                    else (self._master.playing or self._master.looping)
                ):
                    return
                from tkinter import simpledialog

                top = self.outer.winfo_toplevel()
                try:
                    top.grab_set()
                except Exception:
                    pass
                try:
                    ans = simpledialog.askstring(
                        "Rename Action",
                        "Enter visual name/comment for this action:",
                        initialvalue=ev.get("custom_name", ""),
                        parent=top,
                    )
                finally:
                    try:
                        top.grab_release()
                    except Exception:
                        pass
                if ans is not None:
                    save_state()
                    ev["custom_name"] = ans.strip()
                    _refresh_list()

            def curselection(self):
                return tuple(sorted(self.selected_indices))

            def selection_clear(self, start=0, end="end"):
                self.selected_indices.clear()
                self._redraw()

            def selection_set(self, idx):
                self.selected_indices.clear()
                self.selected_indices.add(idx)
                self._redraw()

            def select_toggle(self, idx):
                if idx in self.selected_indices:
                    self.selected_indices.remove(idx)
                else:
                    self.selected_indices.add(idx)
                self._redraw()

            def see(self, idx):
                vis = self._vis_count()
                if idx < self._top_idx:
                    self._top_idx = max(0, idx - 1)
                elif idx >= self._top_idx + vis - 2:
                    self._top_idx = max(0, idx - vis + 3)
                self._redraw()

            def delete(self, start, end=None):
                self._items.clear()
                if start == 0 and end == "end":
                    self.selected_indices.clear()
                self._top_idx = 0
                self._hovered_idx = -1
                self._redraw()

            def insert(self, _end, text, _i, ev):
                self._items.append((text, ev))

            def finalize(self):
                self._top_idx = 0
                self._redraw()

            def bind(self, event, callback):
                if event == "<<ListboxSelect>>":
                    self.on_select_cb = callback
                else:
                    self._cv.bind(event, callback)

        lb = VirtualEventList(list_frame)

        # Wire ctrl+drag reorder callback: swap actual events and refresh
        # S-11 fix: save_state() is called once at drag start, not on every swap
        def _on_reorder(src_idx, dst_idx):
            indices = _filter_indices[0]
            real_src = (
                indices[src_idx] if indices and src_idx < len(indices) else src_idx
            )
            real_dst = (
                indices[dst_idx] if indices and dst_idx < len(indices) else dst_idx
            )
            with self._ev_lock:
                if 0 <= real_src < len(self.events) and 0 <= real_dst < len(
                    self.events
                ):
                    self.events[real_src], self.events[real_dst] = (
                        self.events[real_dst],
                        self.events[real_src],
                    )
            _refresh_list(select=dst_idx)

        lb._on_reorder_cb = _on_reorder

        panel = tk.Frame(body, bg=SSURF, width=200)
        panel.pack(side="right", fill="y", padx=(6, 0))
        panel.pack_propagate(False)

        edit_title_lbl = tk.Label(
            panel, text="Edit Event", bg=SSURF, fg=STEXT, font=("Segoe UI", 8, "bold")
        )
        edit_title_lbl.pack(fill="x", padx=8, pady=(8, 4))
        hint_lbl = tk.Label(
            panel,
            text="Select an event from the list",
            bg=SSURF,
            fg=SMUTED,
            font=("Segoe UI", 7),
            wraplength=180,
        )
        hint_lbl.pack(fill="x", padx=8, pady=(0, 6))

        fields_frame = tk.Frame(panel, bg=SSURF)
        fields_frame.pack(fill="x", padx=8)

        field_vars = {}
        field_labels = [
            ("Hold (ms)", "d"),
            ("X", "x"),
            ("Y", "y"),
            ("Button", "btn"),
            ("Key", "key"),
            ("Delta", "delta"),
            ("Name", "name"),
            ("Action", "action"),
        ]

        # Mutable container so _show_fields_for can update the name combobox values
        _name_combo = [None]

        # Custom variables to hold coordinate selector state & mouse button toggler
        btn_toggle_var = tk.StringVar(value="left")
        btn_row_ref = [None]
        hold_var = tk.BooleanVar(value=False)
        hold_chk_ref = [None]

        for label_text, key in field_labels:
            row = tk.Frame(fields_frame, bg=SSURF)
            row.pack(fill="x", pady=2)
            lbl_w = tk.Label(
                row,
                text=label_text,
                bg=SSURF,
                fg=SMUTED,
                font=("Segoe UI", 7),
                width=8,
                anchor="w",
            )
            lbl_w.pack(side="left")
            var = tk.StringVar()
            if key == "action":
                # Dropdown: valid image search action types
                ent = ttk.Combobox(
                    row,
                    textvariable=var,
                    values=["click", "none"],
                    state="readonly",
                    font=("Consolas", 8),
                    width=10,
                )
                var.set("click")  # default selection
            elif key == "name":
                # Editable dropdown: values populated dynamically based on event type
                # (image names when editing an Image step, run names for a Run step)
                ent = ttk.Combobox(
                    row,
                    textvariable=var,
                    values=[],
                    state="normal",
                    font=("Consolas", 8),
                    width=12,
                )
                _name_combo[0] = ent
            elif key == "btn":
                # Button field: clickable label that toggles left/right
                btn_row_ref[0] = row

                def _toggle_btn_val(_=None):
                    curr = btn_toggle_var.get()
                    nxt = "right" if curr == "left" else "left"
                    btn_toggle_var.set(nxt)
                    ent.config(text=nxt.upper(), fg=SACC if nxt == "right" else STEXT)

                ent = tk.Label(
                    row,
                    textvariable=btn_toggle_var,
                    bg=SED,
                    fg=STEXT,
                    font=("Segoe UI", 7, "bold"),
                    cursor="hand2",
                    padx=6,
                    pady=2,
                    relief="flat",
                )
                ent.bind("<Button-1>", _toggle_btn_val)
            elif key in ("x", "y"):
                # Coordinates fields get a "sel" picker
                ent = tk.Entry(
                    row,
                    textvariable=var,
                    bg=SED,
                    fg=STEXT,
                    insertbackground=SACC,
                    relief="flat",
                    font=("Consolas", 8),
                    width=6,
                )
                # Auto-apply on focus loss
                ent.bind("<FocusOut>", lambda _e: _apply())
                ent.pack(side="left", fill="x", expand=True)
                if key == "x":
                    # Add a coordinate select button next to X/Y
                    sel_btn = tk.Label(
                        row,
                        text="sel",
                        bg=SACC_D,
                        fg=STEXT,
                        font=("Segoe UI", 7, "bold"),
                        cursor="hand2",
                        padx=4,
                        relief="flat",
                    )
                    sel_btn.pack(side="right", padx=(4, 0))

                    def _start_coord_picker():
                        hint_lbl.config(
                            text="Move mouse and RIGHT-CLICK to select coordinates...",
                            fg=SREC,
                        )
                        sel_btn.config(bg=SREC, text="...")

                        listener_ref = [None]

                        # Floating tooltip window to display coordinate tracker next to cursor
                        tooltip = tk.Toplevel(ed)
                        tooltip.overrideredirect(True)
                        tooltip.attributes("-topmost", True)
                        tooltip.configure(bg="#1a1a1a")
                        tt_lbl = tk.Label(
                            tooltip,
                            text="0, 0",
                            bg="#1a1a1a",
                            fg="#ffffff",
                            font=("Segoe UI", 8, "bold"),
                            padx=4,
                            pady=2,
                        )
                        tt_lbl.pack()

                        def _on_move_picked(x, y):
                            # Position tooltip window slightly offset from the cursor
                            tooltip.geometry(f"+{int(x) + 15}+{int(y) + 15}")
                            tt_lbl.config(text=f"{int(x)}, {int(y)}")

                        def _on_click_picked(x, y, button, pressed):
                            if not pressed and button == _pmouse.Button.right:
                                # Stop listener
                                if listener_ref[0]:
                                    listener_ref[0].stop()
                                # Destroy floating coordinate tooltip
                                ed.after(0, tooltip.destroy)
                                # Update entries safely in main thread with coordinates of the right-click spot
                                ed.after(10, lambda: _apply_picked_coords(x, y))
                                return False

                        def _apply_picked_coords(px, py):
                            field_vars["x"][0].set(str(int(px)))
                            field_vars["y"][0].set(str(int(py)))
                            hint_lbl.config(text="Coordinates saved!", fg=SACC)
                            sel_btn.config(bg=SACC_D, text="sel")
                            # Apply automatically
                            _apply()

                        listener_ref[0] = _pmouse.Listener(
                            on_move=_on_move_picked, on_click=_on_click_picked
                        )
                        listener_ref[0].start()

                    sel_btn.bind("<Button-1>", lambda _: _start_coord_picker())
            else:
                ent = tk.Entry(
                    row,
                    textvariable=var,
                    bg=SED,
                    fg=STEXT,
                    insertbackground=SACC,
                    relief="flat",
                    font=("Consolas", 8),
                    width=12,
                )
                # Auto-apply on focus loss so edits aren't silently discarded
                # when the user clicks Play or another event without pressing Enter.
                ent.bind("<FocusOut>", lambda _e: _apply())
            if key != "x" and key != "y":
                ent.pack(side="left", fill="x", expand=True)
            field_vars[key] = (var, row, lbl_w)

        # Image Source Selector for 'I' events (Current Imgs vs Folder)
        custom_folder_path = [""]
        img_source_var = tk.StringVar(value="current")
        img_source_frame = tk.Frame(fields_frame, bg=SSURF)
        tk.Label(
            img_source_frame,
            text="Source",
            bg=SSURF,
            fg=SMUTED,
            font=("Segoe UI", 7),
            width=8,
            anchor="w",
        ).pack(side="left")

        btn_curr = tk.Label(
            img_source_frame,
            text=" Current ",
            bg=SACC,
            fg=SBG,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
        )
        btn_curr.pack(side="left", padx=(0, 4))

        btn_fold = tk.Label(
            img_source_frame,
            text=" Folder ",
            bg=SBORD,
            fg=SMUTED,
            font=("Segoe UI", 7),
            cursor="hand2",
        )
        btn_fold.pack(side="left")

        btn_change_fold = tk.Label(
            img_source_frame,
            text=" 📁 ",
            bg=SBORD,
            fg=SMUTED,
            font=("Segoe UI", 7),
            cursor="hand2",
        )
        btn_change_fold.pack(side="left", padx=(2, 0))

        no_images_warn_lbl = tk.Label(
            fields_frame,
            text="(please add images to work)",
            bg=SSURF,
            fg=SREC,
            font=("Segoe UI", 7, "italic"),
            anchor="w",
        )

        def _choose_folder():
            path = _pick_directory(parent=ed, title="Select Images Folder")
            if path:
                custom_folder_path[0] = path
                _update_image_source("folder")

        def _update_image_source(src):
            img_source_var.set(src)
            no_images_warn_lbl.pack_forget()
            if src == "current":
                btn_curr.config(bg=SACC, fg=SBG, font=("Segoe UI", 7, "bold"))
                btn_fold.config(bg=SBORD, fg=SMUTED, font=("Segoe UI", 7))
                btn_change_fold.config(bg=SBORD, fg=SMUTED)
                img_names = []
                for _item in self.image_det_list:
                    _n = _item.get("name") or Path(_item.get("path", "")).stem
                    if _n:
                        img_names.append(_n)
                if _name_combo[0] is not None:
                    _name_combo[0].configure(values=img_names)
                if not img_names:
                    no_images_warn_lbl.pack(fill="x", pady=2, after=img_source_frame)
            else:
                if not custom_folder_path[0]:
                    _choose_folder()
                    if not custom_folder_path[0]:
                        img_source_var.set("current")
                        return _update_image_source("current")

                btn_curr.config(bg=SBORD, fg=SMUTED, font=("Segoe UI", 7))
                btn_fold.config(bg=SACC, fg=SBG, font=("Segoe UI", 7, "bold"))
                btn_change_fold.config(bg=SACC, fg=SBG)
                img_files = []
                try:
                    fpath = Path(custom_folder_path[0])
                    if fpath.exists():
                        for p in fpath.glob("*"):
                            if p.is_file() and p.suffix.lower() in (
                                ".png",
                                ".jpg",
                                ".jpeg",
                                ".bmp",
                                ".webp",
                            ):
                                img_files.append(p.name)
                except Exception:
                    pass
                if _name_combo[0] is not None:
                    _name_combo[0].configure(values=sorted(img_files))

        btn_curr.bind("<Button-1>", lambda _: _update_image_source("current"))
        btn_fold.bind("<Button-1>", lambda _: _update_image_source("folder"))
        btn_change_fold.bind("<Button-1>", lambda _: _choose_folder())

        # Helper functions
        # Use module-level _vk_to_name (handles both int VKs and string names)

        def _name_to_vk_local(name):
            s = name.strip().lower()
            names = {
                "backspace": 0x08,
                "tab": 0x09,
                "enter": 0x0D,
                "shift": 0x10,
                "ctrl": 0x11,
                "alt": 0x12,
                "esc": 0x1B,
                "space": 0x20,
                "left": 0x25,
                "up": 0x26,
                "right": 0x27,
                "down": 0x28,
                "delete": 0x2E,
                "win": 0x5B,
            }
            if len(s) == 1 and ("a" <= s <= "z" or "0" <= s <= "9"):
                return ord(s.upper())
            if s.startswith("f") and s[1:].isdigit():
                n = int(s[1:])
                if 1 <= n <= 24:
                    return 0x6F + n
            if s.startswith("0x"):
                try:
                    return int(s, 16)
                except ValueError:
                    pass
            return names.get(s, 0)

        def _format_line(i, ev):
            t = ev.get("t", "?")
            d = int(ev.get("d", 0))
            custom_lbl = f"({ev['custom_name']}) " if ev.get("custom_name") else ""
            if t == "M":
                return f"{i + 1:04d}  {d:>5}ms  {custom_lbl}Move  x={ev.get('x', 0)} y={ev.get('y', 0)}"
            elif t == "C":
                btn = ev.get("btn", "left")
                prefix = "Hold Click" if d > 0 else "Click"
                dur_str = (
                    f" ({d}ms)"
                    if d > 0
                    else " (Down)"
                    if not ev.get("up", False)
                    else " (Up)"
                )
                return f"{i + 1:04d}  {custom_lbl}{prefix} {btn}{dur_str}  x={ev.get('x', 0)} y={ev.get('y', 0)}"
            elif t == "K":
                name = _vk_to_name(ev.get("vk", 0))
                prefix = "Hold Key" if d > 0 else "Key"
                dur_str = (
                    f" ({d}ms)"
                    if d > 0
                    else " (Down)"
                    if not ev.get("up", False)
                    else " (Up)"
                )
                return f"{i + 1:04d}  {custom_lbl}{prefix} {name}{dur_str}"
            elif t in ("W", "WH"):
                axis = "H" if t == "WH" else "V"
                return f"{i + 1:04d}  {d:>5}ms  {custom_lbl}Scroll {axis} delta={ev.get('delta', 0)}"
            elif t == "I":
                return f"{i + 1:04d}  {custom_lbl}Image {ev.get('name') or ev.get('img', '?')}"
            elif t == "B":
                return f"{i + 1:04d}  {custom_lbl}If {ev.get('name') or ev.get('img', '?')} else skip {ev.get('skip', 1)}"
            elif t == "R":
                return f"{i + 1:04d}  {custom_lbl}Run {ev.get('name', '?')}"
            elif t == "D":
                return f"{i + 1:04d}  {d:>5}ms  {custom_lbl}Delay"
            return f"{i + 1:04d}  {d:>5}ms  {custom_lbl}{t} ..."

        _refresh_after_id = [None]
        _filter_indices = [None]  # mutable: snap_indices mapping from last _do_refresh

        def _do_refresh(select=-1):
            _refresh_after_id[0] = None
            lb.delete(0, "end")
            with self._ev_lock:
                snap = list(self.events)
            ft = _filter_text[0]
            if ft:
                filtered = [
                    (i, ev)
                    for i, ev in enumerate(snap)
                    if ft in _format_line(i, ev).lower()
                ]
                snap_indices = [p[0] for p in filtered]
                snap = [p[1] for p in filtered]
            else:
                snap_indices = list(range(len(snap)))
            _filter_indices[0] = snap_indices  # expose for drag-reorder callback
            total = len(snap)
            cnt_lbl.config(
                text=f"{total} events" + (f'  (filter: "{ft}")' if ft else "")
            )
            for j, ev in enumerate(snap):
                lb.insert("end", _format_line(snap_indices[j], ev), j, ev)
            lb.finalize()
            if snap and select >= 0:
                select = min(select, total - 1)
                lb.selection_set(select)
                lb.see(select)
            _update_visibility()
            _on_select()

        def _refresh_list(select=None):
            if _refresh_after_id[0] is not None:
                try:
                    ed.after_cancel(_refresh_after_id[0])
                except Exception:
                    pass
            if select is None:
                sel = lb.curselection()
                select = sel[0] if sel else -1
            _refresh_after_id[0] = ed.after(100, lambda s=select: _do_refresh(s))

        def _toggle_hold_display():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            with self._ev_lock:
                if idx < len(self.events):
                    ev = self.events[idx]
                    t = ev.get("t", "M")
                    if t in ("C", "K"):
                        if hold_var.get():
                            # Show delay field, set default if 0
                            curr_d = field_vars["d"][0].get().strip()
                            if not curr_d or curr_d == "0":
                                field_vars["d"][0].set("100")
                            field_vars["d"][1].pack(fill="x", pady=2)
                        else:
                            # Hide delay field
                            field_vars["d"][1].pack_forget()

        def _show_fields_for(ev):
            """Show/hide fields based on event type and populate values."""
            t = ev.get("t", "M")
            # Hide all first
            for key, (var, row, lbl) in field_vars.items():
                row.pack_forget()
                var.set("")
            # Reset delay field label
            field_vars["d"][2].config(text="Hold (ms)")
            img_source_frame.pack_forget()
            no_images_warn_lbl.pack_forget()

            # Show Hold checkbox for Click and Key actions in top control panel
            if t in ("C", "K"):
                if hold_chk_ref[0] is not None:
                    hold_chk_ref[0].pack(side="left", padx=(6, 0))
                has_hold = ev.get("d", 0) > 0
                hold_var.set(has_hold)
                if has_hold:
                    field_vars["d"][0].set(str(ev.get("d", 0)))
                    field_vars["d"][1].pack(fill="x", pady=2)
                else:
                    field_vars["d"][1].pack_forget()
            else:
                if hold_chk_ref[0] is not None:
                    hold_chk_ref[0].pack_forget()

            # Delay field only for Move, Scroll, Delay actions.
            if t in ("M", "W", "WH", "D"):
                field_vars["d"][0].set(str(ev.get("d", 0)))
                field_vars["d"][1].pack(fill="x", pady=2)

            if t in ("M", "C", "W", "WH"):
                field_vars["x"][0].set(str(ev.get("x", 0)))
                field_vars["x"][1].pack(fill="x", pady=2)
                field_vars["y"][0].set(str(ev.get("y", 0)))
                field_vars["y"][1].pack(fill="x", pady=2)
            if t == "C":
                btn_val = ev.get("btn", "left")
                btn_toggle_var.set(btn_val)
                # Show click button row
                if btn_row_ref[0] is not None:
                    btn_row_ref[0].pack(fill="x", pady=2)
            if t == "K":
                field_vars["key"][0].set(_vk_to_name(ev.get("vk", 0)))
                field_vars["key"][1].pack(fill="x", pady=2)
            if t in ("W", "WH"):
                field_vars["delta"][0].set(str(ev.get("delta", 120)))
                field_vars["delta"][1].pack(fill="x", pady=2)
            if t == "I":
                field_vars["name"][0].set(ev.get("name") or ev.get("img", ""))
                img_source_frame.pack(fill="x", pady=2)
                _update_image_source(img_source_var.get())
                field_vars["name"][1].pack(fill="x", pady=2)
                # Load action into the Combobox; default to "image" if stored value not in list
                stored_action = ev.get("action", "image")
                field_vars["action"][0].set(
                    stored_action if stored_action in ("click", "none") else "click"
                )
                field_vars["action"][1].pack(fill="x", pady=2)
            if t == "B":
                field_vars["name"][0].set(ev.get("name") or ev.get("img", ""))
                img_source_frame.pack(fill="x", pady=2)
                _update_image_source(img_source_var.get())
                field_vars["name"][1].pack(fill="x", pady=2)
                field_vars["d"][0].set(str(ev.get("skip", 1)))
                field_vars["d"][1].pack(fill="x", pady=2)
                field_vars["d"][2].config(text="Skip N")
            if t == "R":
                field_vars["name"][0].set(ev.get("name", ""))
                # Populate the name dropdown with saved macro run names
                if _name_combo[0] is not None:
                    run_names = []
                    try:
                        for _rp in sorted(
                            RUNS_PATH.glob("*.txt"),
                            key=lambda p: p.stat().st_mtime,
                            reverse=True,
                        ):
                            run_names.append(_rp.stem)
                    except Exception:
                        pass
                    _name_combo[0].configure(values=run_names)
                field_vars["name"][1].pack(fill="x", pady=2)

            hint_lbl.config(
                text={
                    "M": "Mouse move to (x, y)",
                    "C": "Mouse click.",
                    "K": "Key press. Type key name (a-z, F1-F12, enter, space...)",
                    "W": "Vertical scroll",
                    "WH": "Horizontal scroll",
                    "I": "Image step. Name can be image target name or image filename.",
                    "B": "If image found → continue, else → skip N events below.",
                    "R": "Run step. Name can be saved run name or filename.",
                    "D": "Wait-only delay step.",
                }.get(t, "")
            )

        def _update_visibility():
            if not self.events:
                edit_title_lbl.pack_forget()
                hint_lbl.pack_forget()
                fields_frame.pack_forget()
                if "top_btn_frame" in globals() or "top_btn_frame" in locals():
                    top_btn_frame.pack_forget()
                foot.pack_forget()
                panel.config(width=170)
            else:
                edit_title_lbl.pack(
                    fill="x", padx=8, pady=(8, 4), before=quick_add_frame
                )
                hint_lbl.pack(fill="x", padx=8, pady=(0, 6), before=quick_add_frame)
                fields_frame.pack(fill="x", padx=8, before=quick_add_frame)
                if "top_btn_frame" in globals() or "top_btn_frame" in locals():
                    top_btn_frame.pack(
                        fill="x", padx=8, pady=(10, 4), before=quick_add_frame
                    )
                foot.pack(side="bottom", fill="x", padx=8, pady=8)
                panel.config(width=200)

        def _on_select(_=None):
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            with self._ev_lock:
                if idx < len(self.events):
                    _show_fields_for(self.events[idx])

        def _apply():
            sel = lb.curselection()
            if not sel:
                self.set_status("Select an event first", _C["rec"], 1000)
                return
            save_state()
            with self._ev_lock:
                for idx in sel:
                    if idx >= len(self.events):
                        continue
                    ev = self.events[idx]
                    t = ev.get("t", "M")
                    # Apply delay if applicable
                    if t in ("M", "W", "WH", "D"):
                        try:
                            ev["d"] = max(0, int(field_vars["d"][0].get()))
                        except ValueError:
                            pass
                    elif t in ("C", "K"):
                        if hold_var.get():
                            try:
                                ev["d"] = max(1, int(field_vars["d"][0].get()))
                            except ValueError:
                                ev["d"] = 100
                            # Remove "up" so replay takes the press-hold-release
                            # path that respects the duration field.
                            ev.pop("up", None)
                        else:
                            ev["d"] = 0
                    # Apply position
                    if t in ("M", "C", "W", "WH"):
                        try:
                            ev["x"] = int(field_vars["x"][0].get())
                        except ValueError:
                            pass
                        try:
                            ev["y"] = int(field_vars["y"][0].get())
                        except ValueError:
                            pass
                    # Apply button
                    if t == "C":
                        btn = btn_toggle_var.get().strip().lower()
                        if btn in ("left", "right", "middle", "x1", "x2"):
                            ev["btn"] = btn
                    # Apply key
                    if t == "K":
                        key_name = field_vars["key"][0].get().strip()
                        if key_name:
                            vk = _name_to_vk_local(key_name)
                            if vk:
                                ev["vk"] = vk
                                if sys.platform == "win32":
                                    ev["scan"] = user32.MapVirtualKeyW(vk, 0)
                                    ev["ext"] = vk in _EXTENDED_VKS
                                else:
                                    ev["scan"] = 0
                                    ev["ext"] = False
                    # Apply delta
                    if t in ("W", "WH"):
                        try:
                            ev["delta"] = int(field_vars["delta"][0].get())
                        except ValueError:
                            pass
                    if t == "I":
                        name = field_vars["name"][0].get().strip()
                        if name:
                            ev["name"] = name
                            ev["img"] = name
                            if (
                                img_source_var.get() == "folder"
                                and custom_folder_path[0]
                            ):
                                src_file = Path(custom_folder_path[0]) / name
                                if src_file.is_file():
                                    try:
                                        import shutil

                                        IMAGES_PATH.mkdir(parents=True, exist_ok=True)
                                        shutil.copy2(src_file, IMAGES_PATH / name)
                                        get_cached_template.cache_clear()
                                    except Exception as e:
                                        _LOG.error(
                                            "Failed to copy image to IMAGES_PATH: %s", e
                                        )
                        # Read action type from the readonly Combobox dropdown
                        action = field_vars["action"][0].get().strip().lower()
                        if action in ("click", "none", "image", "run"):
                            ev["action"] = action
                    if t == "B":
                        name = field_vars["name"][0].get().strip()
                        if name:
                            ev["name"] = name
                            ev["img"] = name
                        try:
                            ev["skip"] = max(1, int(field_vars["d"][0].get()))
                        except ValueError:
                            ev["skip"] = 1
                    if t == "R":
                        name = field_vars["name"][0].get().strip()
                        if name:
                            ev["name"] = name
            self.set_status("Event(s) updated", _C["go"], 1000)
            _refresh_list()

        def _delete():
            sel = lb.curselection()
            if not sel:
                return
            save_state()
            with self._ev_lock:
                for idx in sorted(sel, reverse=True):
                    if idx < len(self.events):
                        self.events.pop(idx)
            self.set_status("Deleted selected action(s)", _C["rec"], 1000)
            _refresh_list(select=-1)

        def _delete_all():
            if tk.messagebox.askyesno(
                "Delete All",
                "Are you sure you want to delete all actions from this macro?\n\n(Tip: Press Ctrl + Z in the editor to Undo if needed.)",
                parent=ed,
            ):
                save_state()
                with self._ev_lock:
                    self.events.clear()
                self.set_status("All actions deleted", _C["rec"], 1000)
                _refresh_list(select=-1)

        def _duplicate():
            sel = lb.curselection()
            if not sel:
                return
            save_state()
            with self._ev_lock:
                # Add duplicate of each selected action right after its current position
                # Traverse in reverse order to keep correct indexing
                for idx in sorted(sel, reverse=True):
                    if idx < len(self.events):
                        self.events.insert(idx + 1, dict(self.events[idx]))
            _refresh_list(select=sel[-1] + 1 if sel else -1)

        def _move_up():
            sel = lb.curselection()
            if not sel or sel[0] == 0:
                return
            save_state()
            idx = sel[0]
            with self._ev_lock:
                self.events[idx - 1], self.events[idx] = (
                    self.events[idx],
                    self.events[idx - 1],
                )
            _refresh_list(select=idx - 1)

        def _move_down():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            save_state()
            with self._ev_lock:
                if idx >= len(self.events) - 1:
                    return
                self.events[idx], self.events[idx + 1] = (
                    self.events[idx + 1],
                    self.events[idx],
                )
            _refresh_list(select=idx + 1)

        def _add_click():
            pt = POINT()
            user32.GetCursorPos(_ct.byref(pt))
            x, y = int(pt.x), int(pt.y)
            save_state()
            with self._ev_lock:
                pos = len(self.events)
                self.events.append({"t": "C", "btn": "left", "x": x, "y": y, "d": 100})
            _refresh_list(select=pos)

        def _add_key():
            save_state()
            with self._ev_lock:
                pos = len(self.events)
                self.events.append(
                    {
                        "t": "K",
                        "vk": 0x44 if sys.platform == "win32" else "d",
                        "scan": user32.MapVirtualKeyW(0x44, 0)
                        if sys.platform == "win32"
                        else 0,
                        "ext": False,
                        "d": 100,  # 100ms key hold duration
                    }
                )
            _refresh_list(select=pos)

        def _add_scroll():
            pt = POINT()
            user32.GetCursorPos(_ct.byref(pt))
            x, y = int(pt.x), int(pt.y)
            save_state()
            with self._ev_lock:
                pos = len(self.events)
                self.events.append({"t": "W", "x": x, "y": y, "delta": 120, "d": 50})
            _refresh_list(select=pos)

        def _add_wait():
            save_state()
            with self._ev_lock:
                pos = len(self.events)
                self.events.append({"t": "D", "d": 1000})
            _refresh_list(select=pos)

        def _add_run():
            name = ""
            try:
                runs = sorted(
                    RUNS_PATH.glob("*.txt"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if runs:
                    name = runs[0].stem
            except Exception:
                pass
            save_state()
            with self._ev_lock:
                pos = len(self.events)
                self.events.append({"t": "R", "name": name})
            _refresh_list(select=pos)

        def _add_image():
            name = ""
            try:
                if self.image_det_list:
                    name = (
                        self.image_det_list[0].get("name")
                        or Path(self.image_det_list[0].get("path", "")).name
                    )
            except Exception:
                pass
            save_state()
            with self._ev_lock:
                pos = len(self.events)
                self.events.append(
                    {"t": "I", "name": name, "img": name, "action": "click"}
                )
            _refresh_list(select=pos)

        def _add_if_image():
            """Add a conditional branch: if image found → continue, else → skip N events."""
            name = ""
            try:
                if self.image_det_list:
                    name = (
                        self.image_det_list[0].get("name")
                        or Path(self.image_det_list[0].get("path", "")).name
                    )
            except Exception:
                pass
            save_state()
            with self._ev_lock:
                pos = len(self.events)
                self.events.append({"t": "B", "name": name, "img": name, "skip": 1})
            _refresh_list(select=pos)

        def _make_btn(parent, text, cmd, bg=SBORD, fg=SMUTED, bold=False):
            f = tk.Frame(parent, bg=bg, cursor="hand2")
            l = tk.Label(
                f,
                text=text,
                bg=bg,
                fg=fg,
                font=("Segoe UI", 7, "bold" if bold else "normal"),
                cursor="hand2",
            )
            l.pack(padx=4, pady=3)
            for w in (f, l):
                w.bind("<Button-1>", lambda _: cmd())
            return f

        # Top Buttons (only visible when events exist)
        top_btn_frame = tk.Frame(panel, bg=SSURF)
        top_btn_frame.pack(fill="x", padx=8, pady=(10, 4))

        _make_btn(top_btn_frame, "Apply", _apply, bg=SACC_D, fg=STEXT, bold=True).pack(
            fill="x", pady=(0, 4)
        )

        row1 = tk.Frame(top_btn_frame, bg=SSURF)
        row1.pack(fill="x", pady=2)
        _make_btn(row1, "▲", _move_up).pack(side="left", padx=(0, 2))
        _make_btn(row1, "▼", _move_down).pack(side="left", padx=(0, 2))
        _make_btn(row1, "Dup", _duplicate).pack(side="left", padx=(0, 2))

        # Hold Checkbutton placed beautifully in the empty space
        hold_chk = tk.Checkbutton(
            row1,
            text="Hold",
            variable=hold_var,
            bg=SSURF,
            fg=SMUTED,
            selectcolor=SSURF,
            activebackground=SSURF,
            activeforeground=STEXT,
            font=("Segoe UI", 7),
            cursor="hand2",
            command=_toggle_hold_display,
        )
        hold_chk.pack(side="left", padx=(6, 0))
        hold_chk_ref[0] = hold_chk

        _make_btn(row1, "Del", _delete, bg=SREC, fg="#fff").pack(side="right")

        _make_btn(top_btn_frame, "Del all", _delete_all, bg=SREC, fg="#fff").pack(
            fill="x", pady=(2, 4)
        )

        # Quick Add Buttons (always visible)
        quick_add_frame = tk.Frame(panel, bg=SSURF)
        quick_add_frame.pack(fill="x", padx=8, pady=(10, 4))

        tk.Label(
            quick_add_frame,
            text="Quick Add:",
            bg=SSURF,
            fg=SMUTED,
            font=("Segoe UI", 7),
        ).pack(fill="x", pady=(8, 2), anchor="w")
        row2 = tk.Frame(quick_add_frame, bg=SSURF)
        row2.pack(fill="x", pady=2)
        _make_btn(row2, "+ Click", _add_click).pack(side="left", padx=(0, 4))
        _make_btn(row2, "+ Key", _add_key).pack(side="left", padx=(0, 4))
        _make_btn(row2, "+ Delay", _add_wait).pack(side="left", padx=(0, 4))
        _make_btn(row2, "+ Scroll", _add_scroll).pack(side="left")
        row3 = tk.Frame(quick_add_frame, bg=SSURF)
        row3.pack(fill="x", pady=2)
        _make_btn(row3, "+ Run", _add_run).pack(side="left", padx=(0, 4))
        _make_btn(row3, "+ Image", _add_image).pack(side="left", padx=(0, 4))
        _make_btn(row3, "+ If", _add_if_image).pack(side="left")

        # Footer
        foot = tk.Frame(panel, bg=SSURF)
        foot.pack(side="bottom", fill="x", padx=8, pady=8)
        _make_btn(
            foot,
            "  Save Macro  ",
            lambda: self.save_events(),
            bg=SACC_D,
            fg=STEXT,
            bold=True,
        ).pack(fill="x")

        # Bindings
        lb.bind("<<ListboxSelect>>", _on_select)
        lb.bind("<Delete>", lambda _: _delete())
        ed.bind("<Return>", lambda _: _apply())
        ed.bind("<Control-s>", lambda _: self.save_events())
        ed.bind("<Control-z>", perform_undo)
        ed.bind("<Control-Z>", perform_undo)

        # NOTE: editor_window.grab_set() and root.wait_window(editor_window) are
        # intentionally NOT called here, so the editor stays open in the background
        # without freezing or blocking the main application window.

        _do_refresh(select=0 if self.events else -1)

    def _resolve_run_path(self, name):
        if not name:
            return None
        raw = Path(str(name).strip())
        candidates = []
        if raw.is_file():
            candidates.append(raw)
        candidates.extend(
            [
                RUNS_PATH / str(name),
                RUNS_PATH / f"{name}.txt",
                RUNS_PATH / f"{name}.json",
            ]
        )
        for path in candidates:
            try:
                if path.is_file():
                    return path
            except Exception:
                pass
        try:
            needle = str(name).strip().lower()
            for path in RUNS_PATH.glob("*"):
                if path.is_file() and path.stem.lower() == needle:
                    return path
        except Exception:
            pass
        return None

    def _resolve_image_path(self, name):
        if not name:
            return ""
        needle = str(name).strip().lower()
        for tgt in getattr(self, "image_det_list", []):
            try:
                tgt_name = str(tgt.get("name", "")).strip().lower()
                tgt_path = str(tgt.get("path", ""))
                p = Path(tgt_path) if tgt_path else None
                if tgt_name == needle or (
                    p and (p.name.lower() == needle or p.stem.lower() == needle)
                ):
                    if p and p.is_file():
                        return str(p)
            except Exception:
                pass
        raw = Path(str(name).strip())
        candidates = []
        if raw.is_file():
            candidates.append(raw)
        candidates.append(IMAGES_PATH / str(name).strip())
        if not raw.suffix:
            for ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
                candidates.append(IMAGES_PATH / f"{name}{ext}")
        for path in candidates:
            try:
                if path.is_file():
                    return str(path)
            except Exception:
                pass
        return ""

    def _replay_inline_events(self, evs, depth=0):
        if depth > 5:
            self.root.after(
                0, lambda: self.set_status("Run nesting too deep", _C["rec"], 1500)
            )
            return
        speed = max(0.1, min(10.0, self.cfg.speed))
        for ev in evs:
            if self._stop_ev.is_set():
                break
            delay = max(ev.get("d", 0), 0) / 1000.0 / speed
            target = time.perf_counter() + delay
            while time.perf_counter() < target:
                if self._stop_ev.is_set():
                    return
                if getattr(self, "_pause_playback", False):
                    time.sleep(0.01)
                    target += 0.01
                    continue
                time.sleep(min(0.01, max(0, target - time.perf_counter())))
            while (
                getattr(self, "_pause_playback", False) and not self._stop_ev.is_set()
            ):
                time.sleep(0.01)
            self._replay(ev, depth + 1, speed)

    def _replay(self, ev, depth=0, speed=1.0):
        t = ev.get("t", "")
        try:
            if t == "M":
                cx, cy = int(ev["x"]), int(ev["y"])

                if ev.get("rel"):
                    try:
                        hwnd = user32.GetForegroundWindow()
                        if hwnd:
                            rect = RECT()
                            if user32.GetWindowRect(hwnd, _ct.byref(rect)):
                                cx += rect.left
                                cy += rect.top
                    except Exception:
                        pass

                # Match AHK: GetCursorPos + SendInput relative move
                pt = POINT()
                user32.GetCursorPos(_ct.byref(pt))
                dx, dy = cx - pt.x, cy - pt.y
                if dx != 0 or dy != 0:
                    _send_input(_mouse_move_rel(dx, dy))

            elif t == "C":
                btn_name = ev.get("btn", "left")
                cx, cy = int(ev.get("x", 0)), int(ev.get("y", 0))

                if ev.get("rel"):
                    try:
                        hwnd = user32.GetForegroundWindow()
                        if hwnd:
                            rect = RECT()
                            if user32.GetWindowRect(hwnd, _ct.byref(rect)):
                                cx += rect.left
                                cy += rect.top
                    except Exception:
                        pass

                # Use absolute positioning — bypasses mouse acceleration that
                # would cause large relative moves to drift.
                _send_input(_mouse_move(cx, cy))
                time.sleep(0.01)

                if "up" in ev:
                    up = ev.get("up", False)
                    _send_input(_mouse_button(btn_name, up))
                    with self._held_lock:
                        if not up:
                            self._held_btns.add(btn_name)
                        else:
                            self._held_btns.discard(btn_name)
                else:
                    # Hand-crafted simplified action: press, hold, release
                    _send_input(_mouse_button(btn_name, False))
                    d = ev.get("d", 0)
                    hold = (max(d / 1000.0, 0.05) if d > 0 else 0.05) / speed
                    time.sleep(hold)
                    _send_input(_mouse_button(btn_name, True))
            elif t == "K":
                vk, scan, ext, up = (
                    ev.get("vk", 0),
                    ev.get("scan", 0),
                    ev.get("ext", False),
                    ev.get("up", False),
                )
                if vk and not scan:
                    scan = user32.MapVirtualKeyW(vk, 0)

                if "up" in ev:
                    _send_input(_make_key(vk, scan, up, ext))
                    with self._held_lock:
                        if not up:
                            self._held_vks.add(vk)
                            self._held_keys[vk] = {
                                "press_time": time.perf_counter(),
                                "last_reinject": time.perf_counter(),
                                "scan": scan,
                                "ext": ext,
                            }
                        else:
                            self._held_vks.discard(vk)
                            self._held_keys.pop(vk, None)
                else:
                    # Hand-crafted simplified action: press, hold, release
                    _send_input(_make_key(vk, scan, False, ext))
                    d = ev.get("d", 0)
                    hold = (d / 1000.0 if d > 0 else 0.05) / speed
                    time.sleep(hold)
                    _send_input(_make_key(vk, scan, True, ext))
            elif t == "W":
                cx, cy = int(ev.get("x", 0)), int(ev.get("y", 0))
                pt = POINT()
                user32.GetCursorPos(_ct.byref(pt))
                dx, dy = cx - pt.x, cy - pt.y
                if dx != 0 or dy != 0:
                    _send_input(_mouse_move_rel(dx, dy))
                _send_input(_mouse_wheel(cx, cy, ev.get("delta", 0)))
            elif t == "WH":
                cx, cy = int(ev.get("x", 0)), int(ev.get("y", 0))
                pt = POINT()
                user32.GetCursorPos(_ct.byref(pt))
                dx, dy = cx - pt.x, cy - pt.y
                if dx != 0 or dy != 0:
                    _send_input(_mouse_move_rel(dx, dy))
                _send_input(_mouse_wheel(cx, cy, ev.get("delta", 0), h=True))
            elif t == "D":
                pass
            elif t == "B":
                # Branch/if-image — treat as found (continue) in fallback replay
                pass
            elif t == "R":
                # Bug 16: Run sub-macro event for Python fallback playback
                name = ev.get("name", "")
                rp = self._resolve_run_path(name)
                if rp:
                    try:
                        with open(rp, encoding="utf-8") as f:
                            first_char = f.read(1)
                            f.seek(0)
                            if first_char == "#":
                                sub_evs = _read_compact_run(rp)
                            else:
                                sub_evs = [e for e in json.load(f) if _valid_ev(e)]
                        self._replay_inline_events(sub_evs, depth + 1)
                    except Exception as e:
                        _LOG.warning("Run step failed: %s", e)
            elif t == "I":
                # Image search event
                img_name = ev.get("name") or ev.get("img", "")
                action = ev.get("action", "click")
                img_path = self._resolve_image_path(img_name)
                if img_path and os.path.exists(img_path):
                    import cv2
                    import numpy as np

                    template = cv2.imread(img_path, cv2.IMREAD_COLOR)
                    if template is not None:
                        try:
                            screen = _grab_screen()
                            screen_np = np.array(screen)
                            screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
                            max_val, match_pt = self._find_best_match(
                                screen_bgr, template
                            )
                            if max_val >= 0.55:
                                match_x, match_y = match_pt
                                if action == "click":
                                    pt = POINT()
                                    try:
                                        user32.GetCursorPos(_ct.byref(pt))
                                        orig_x, orig_y = pt.x, pt.y
                                    except Exception:
                                        orig_x, orig_y = int(match_x), int(match_y)

                                    offsets = [(-5, -5), (5, -5), (0, 5)]
                                    for ox, oy in offsets:
                                        if self._stop_ev.is_set():
                                            break
                                        tx, ty = int(match_x + ox), int(match_y + oy)
                                        pt2 = POINT()
                                        user32.GetCursorPos(_ct.byref(pt2))
                                        dx2, dy2 = tx - pt2.x, ty - pt2.y
                                        if dx2 != 0 or dy2 != 0:
                                            _send_input(_mouse_move_rel(dx2, dy2))
                                        time.sleep(0.05)
                                        # M-3 fix: use _mouse_button (relative) not _mouse_click (absolute)
                                        _send_input(_mouse_button("left", False))
                                        time.sleep(0.06)
                                        _send_input(_mouse_button("left", True))
                                        time.sleep(0.08)
                                    pt3 = POINT()
                                    user32.GetCursorPos(_ct.byref(pt3))
                                    dx3, dy3 = orig_x - pt3.x, orig_y - pt3.y
                                    if dx3 != 0 or dy3 != 0:
                                        _send_input(_mouse_move_rel(dx3, dy3))
                                else:
                                    tx, ty = int(match_x), int(match_y)
                                    pt2 = POINT()
                                    user32.GetCursorPos(_ct.byref(pt2))
                                    dx2, dy2 = tx - pt2.x, ty - pt2.y
                                    if dx2 != 0 or dy2 != 0:
                                        _send_input(_mouse_move_rel(dx2, dy2))
                                    time.sleep(0.2)
                        except Exception as e_inner:
                            _LOG.warning(
                                "Image Search Event Match failure: %s", e_inner
                            )
        except Exception as e:
            _LOG.debug("Replay: %s – %r", e, ev)

    def _release_held(self):
        with self._held_lock:
            held_vks_snap = list(self._held_vks)
            held_btns_snap = list(self._held_btns)
        for vk in held_vks_snap:
            try:
                scan = user32.MapVirtualKeyW(vk, 0) if vk else 0
                _send_input(_make_key(vk, scan, True, vk in _EXTENDED_VKS))
            except Exception:
                _LOG.debug("Release held key vk=%s failed", vk, exc_info=True)
        with self._held_lock:
            self._held_vks.clear()
            self._held_keys.clear()
        for btn_name in held_btns_snap:
            try:
                _send_input(_mouse_button(btn_name, True))
            except Exception:
                _LOG.debug("Release held btn %s failed", btn_name, exc_info=True)
        with self._held_lock:
            self._held_btns.clear()
        # Safety: release all modifier keys
        for vk in (0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5):
            try:
                _send_input(_make_key(vk, 0, True, vk in _EXTENDED_VKS))
            except Exception:
                _LOG.debug("Release modifier vk=%s failed", vk, exc_info=True)

    def save_events(self):
        if self.recording:
            self.set_status("Stop recording first", _C["rec"], 1500)
            return
        if not self.events:
            if RUNS_PATH.exists() and any(RUNS_PATH.glob("*.txt")):
                self._open_run_picker()
            else:
                self.set_status("Nothing!", _C["rec"], 1500)
            return

        # Custom beautifully-styled popup inside the app to enter a run name
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Run")
        dialog.configure(bg=SBG)
        dialog.geometry("260x120")
        dialog.attributes("-topmost", True)
        try:
            _round_hwnd(_get_hwnd(dialog.winfo_id()))
        except Exception:
            pass
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="Enter Run Name:",
            bg=SBG,
            fg=STEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(pady=(12, 6))

        ent_var = tk.StringVar()
        ent = tk.Entry(
            dialog,
            textvariable=ent_var,
            bg=SED,
            fg=STEXT,
            font=("Consolas", 9),
            insertbackground=STEXT,
            relief="flat",
            width=24,
        )
        ent.pack(pady=4)
        ent.focus_set()

        def _confirm():
            name = ent_var.get().strip()
            if name:
                if name.endswith(".txt"):
                    name = name[:-4]
                elif name.endswith(".json"):
                    name = name[:-5]

                RUNS_PATH.mkdir(parents=True, exist_ok=True)
                path = RUNS_PATH / f"{name}.txt"

                try:
                    with self._ev_lock:
                        _write_compact_run(self.events, str(path))
                    self.set_status("💾 Saved Run", _C["go"], 1500)
                    self._log_message(f"> saved as {name}.txt")
                    threading.Thread(
                        target=self._webhook, args=("save",), daemon=True
                    ).start()
                except Exception as e:
                    _LOG.error("Save: %s", e)
                    self.set_status("ERR save", _C["rec"], 2000)
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg=SBG)
        btn_frame.pack(pady=8)

        ok_f = tk.Frame(btn_frame, bg=SACC_D, cursor="hand2")
        ok_l = tk.Label(
            ok_f,
            text="Save",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        ok_l.pack(padx=12, pady=3)
        ok_f.pack(side="left", padx=4)

        cancel_f = tk.Frame(btn_frame, bg=SBORD, cursor="hand2")
        cancel_l = tk.Label(
            cancel_f,
            text="Cancel",
            bg=SBORD,
            fg=SMUTED,
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        cancel_l.pack(padx=12, pady=3)
        cancel_f.pack(side="left", padx=4)

        ok_l.bind("<Button-1>", lambda _: _confirm())
        cancel_l.bind("<Button-1>", lambda _: dialog.destroy())
        ent.bind("<Return>", lambda _: _confirm())

    def _load_events(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                first_char = f.read(1)
                f.seek(0)
                if first_char == "#":
                    self.events = _read_compact_run(path)
                else:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.events = [ev for ev in data if _valid_ev(ev)]
            # Fix old recordings that have d=0 but _ts_perf timestamps
            if (
                self.events
                and all(ev.get("d", 0) == 0 for ev in self.events)
                and self.events[0].get("_ts_perf") is not None
            ):
                prev_ts = self.events[0].get("_ts_perf", 0)
                self.events[0]["d"] = 0
                for ev in self.events[1:]:
                    cur = ev.get("_ts_perf", prev_ts)
                    ev["d"] = max(0, int((cur - prev_ts) * 1000))
                    prev_ts = cur
            if self.events:
                name = Path(path).stem
                self._log_message(f"> loaded {name}")
        except FileNotFoundError:
            self.set_status("Run file not found!", _C["rec"], 3000)
            self.cfg.save_path = ""
            self.cfg.save()
        except Exception as e:
            _LOG.error("Load: %s", e)
            self.set_status("Load failed!", _C["rec"], 3000)

    def _auto_save_run(self):
        if not self.events:
            return
        try:
            RUNS_PATH.mkdir(parents=True, exist_ok=True)
            name = datetime.now().strftime("run_%Y%m%d_%H%M%S.txt")
            path = RUNS_PATH / name
            with self._ev_lock:
                _write_compact_run(self.events, str(path))
            self.cfg.save_path = str(path)
            self.cfg.save()
            self.set_status("\U0001f4be Saved", _C["go"], 2500)
            # Bug 11: Cap auto-saves to the last 50 files
            try:
                all_runs = sorted(
                    RUNS_PATH.glob("run_*.txt"), key=lambda p: p.stat().st_mtime
                )
                for old in all_runs[:-50]:
                    try:
                        old.unlink()
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            _LOG.error("Auto-save run: %s", e)
            self.set_status("\u2717 Save err", _C["rec"], 2000)

    def _open_run_picker(self):
        if not RUNS_PATH.exists():
            self.set_status("No runs", _C["rec"], 1500)
            return

        def _load_favs():
            try:
                if RUN_FAV_PATH.exists():
                    data = json.loads(RUN_FAV_PATH.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        return {str(x) for x in data}
            except Exception as e:
                _LOG.debug("Load run favorites: %s", e)
            return set()

        def _save_favs():
            try:
                RUN_FAV_PATH.parent.mkdir(parents=True, exist_ok=True)
                RUN_FAV_PATH.write_text(json.dumps(sorted(favs)), encoding="utf-8")
            except Exception as e:
                _LOG.debug("Save run favorites: %s", e)

        favs = _load_favs()
        runs = []

        def _refresh_runs():
            nonlocal runs
            all_runs = [p for p in RUNS_PATH.glob("*.txt") if p.is_file()]
            runs = sorted(
                all_runs,
                key=lambda p: (p.name not in favs, -p.stat().st_mtime),
            )

        _refresh_runs()
        if not runs:
            self.set_status("No runs", _C["rec"], 1500)
            return
        W = 360
        win = tk.Toplevel(self.root)
        if sys.platform == "win32":
            win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=SBORD, padx=1, pady=1)
        if sys.platform != "win32":
            win.transient(self.root)
        self.root.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        scw, sch = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        wx = max(0, min(rx, scw - W - 4))
        wy = ry + TH + 1 + BH + 4
        inner = tk.Frame(win, bg=SBG)
        inner.pack(fill="both", expand=True)
        stb = tk.Frame(inner, bg=SSURF, height=32)
        stb.pack(fill="x")
        stb.pack_propagate(False)
        tk.Label(
            stb,
            text="  ✦  Saved Runs",
            bg=SSURF,
            fg=STEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=8)
        stat_lbl = tk.Label(stb, text="", bg=SSURF, fg=SMUTED, font=("Segoe UI", 7))
        stat_lbl.pack(side="left", padx=4)
        xb = tk.Label(
            stb,
            text="\u2715",
            bg=SSURF,
            fg=SMUTED,
            font=("Segoe UI", 9),
            cursor="hand2",
            width=3,
        )
        xb.pack(side="right")
        xb.bind("<Button-1>", lambda _: win.destroy())
        xb.bind("<Enter>", lambda _: xb.config(fg=STEXT, bg=SREC))
        xb.bind("<Leave>", lambda _: xb.config(fg=SMUTED, bg=SSURF))
        sdx, sdy = [0], [0]
        stb.bind(
            "<ButtonPress-1>",
            lambda e: (
                sdx.__setitem__(0, e.x_root - win.winfo_x()),
                sdy.__setitem__(0, e.y_root - win.winfo_y()),
            ),
        )
        stb.bind(
            "<B1-Motion>",
            lambda e: win.geometry(f"+{e.x_root - sdx[0]}+{e.y_root - sdy[0]}"),
        )
        tk.Frame(inner, bg=SBORD, height=1).pack(fill="x")
        lf = tk.Frame(inner, bg=SBG)
        lf.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        visible = min(len(runs), 9)
        lb = tk.Listbox(
            lf,
            bg=SED,
            fg=STEXT,
            selectbackground=SACC,
            selectforeground=SBG,
            font=("Consolas", 8),
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=SEDB,
            activestyle="none",
            height=visible,
        )
        sb = tk.Scrollbar(
            lf,
            orient="vertical",
            command=lb.yview,
            bg=SBORD,
            troughcolor=SSURF,
            activebackground=SACC,
            width=5,
        )
        lb.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)

        # Pen icon for rename-on-hover
        rename_lbl = tk.Label(
            lf,
            text="\u270e",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            padx=5,
            pady=1,
        )
        rename_edit = None
        rename_idx = [-1]
        _last_hover_idx = [-1]
        _hide_after_id = [None]

        tk.Frame(inner, bg=SBORD, height=1).pack(fill="x", padx=8)
        bf = tk.Frame(inner, bg=SBG)
        bf.pack(fill="x", padx=8, pady=7)

        def _run_label(r):
            star = "★" if r.name in favs else "☆"
            try:
                dt_r = datetime.strptime(r.stem, "run_%Y%m%d_%H%M%S")
                label = dt_r.strftime("%b %d  %H:%M:%S")
            except ValueError:
                label = r.stem[:22]
            try:
                size = max(1, r.stat().st_size // 1024)
            except Exception:
                size = 0
            return f" {star}  {label:<18}  {size:>4} KB"

        def _selected_run():
            sel = lb.curselection()
            if not sel or sel[0] >= len(runs):
                return None
            return runs[sel[0]]

        def _redraw(keep=0):
            lb.delete(0, "end")
            for r in runs:
                lb.insert("end", _run_label(r))
            if runs:
                keep = max(0, min(keep, len(runs) - 1))
                lb.selection_set(keep)
                lb.see(keep)
            stat_lbl.config(
                text=f"{len(runs)} runs  •  {len([r for r in runs if r.name in favs])} fav"
            )

        _redraw()

        def _rename_hover(e):
            if rename_edit is not None:
                return
            # Cancel any pending hide from leave
            if _hide_after_id[0] is not None:
                win.after_cancel(_hide_after_id[0])
                _hide_after_id[0] = None
            idx = lb.nearest(e.y)
            if idx < 0 or idx >= len(runs):
                _last_hover_idx[0] = -1
                rename_lbl.place_forget()
                return
            if idx == _last_hover_idx[0]:
                return
            _last_hover_idx[0] = idx
            bbox = lb.bbox(idx)
            if bbox is None:
                rename_lbl.place_forget()
                return
            x, y, w, h = bbox
            rename_lbl.place(x=x + 118, y=y + 1, height=h - 2)
            rename_idx[0] = idx

        def _rename_leave(_e=None):
            if rename_edit is not None:
                return

            # Delay hide so mouse can reach the pen icon
            def _do_hide():
                _hide_after_id[0] = None
                rename_lbl.place_forget()

            if _hide_after_id[0] is not None:
                win.after_cancel(_hide_after_id[0])
            _hide_after_id[0] = win.after(250, _do_hide)

        def _start_rename(_e=None):
            nonlocal rename_edit
            idx = rename_idx[0]
            if idx < 0 or idx >= len(runs):
                return
            rp = runs[idx]
            rename_lbl.place_forget()
            bbox = lb.bbox(idx)
            if bbox is None:
                return
            bx, by, bw, bh = bbox
            rename_edit = tk.Entry(
                lf,
                bg=SED,
                fg=STEXT,
                insertbackground=SACC,
                font=("Consolas", 8),
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=SACC,
            )
            rename_edit.insert(0, rp.stem)
            rename_edit.selection_range(0, "end")
            rename_edit.place(x=bx + 2, y=by + 1, width=bw - 4, height=bh - 2)
            rename_edit.focus_set()

            def _finish_rename(_e=None):
                nonlocal rename_edit
                if rename_edit is None:
                    return
                new_stem = rename_edit.get().strip()
                rename_edit.destroy()
                rename_edit = None
                rename_lbl.place_forget()
                if not new_stem or new_stem == rp.stem:
                    return
                safe = "".join(
                    c for c in new_stem if c.isalnum() or c in " _-."
                ).strip()
                if not safe:
                    self.set_status("Invalid name", _C["rec"], 1500)
                    return
                new_path = rp.parent / (safe + ".txt")
                if new_path.exists() and new_path != rp:
                    self.set_status("Name exists", _C["rec"], 1500)
                    return
                try:
                    rp.rename(new_path)
                    old_name = rp.name
                    if old_name in favs:
                        favs.discard(old_name)
                        favs.add(new_path.name)
                    _save_favs()
                    _refresh_runs()
                    try:
                        new_idx = runs.index(new_path)
                    except ValueError:
                        new_idx = idx
                    _redraw(new_idx)
                    self.set_status("Renamed", _C["go"], 1500)
                except Exception as ex:
                    _LOG.warning("Rename run: %s", ex)
                    self.set_status("Rename failed", _C["rec"], 1500)

            rename_edit.bind("<Return>", _finish_rename)
            rename_edit.bind("<Escape>", _finish_rename)
            rename_edit.bind("<FocusOut>", _finish_rename)

        rename_lbl.bind("<Button-1>", _start_rename)
        rename_lbl.bind("<Enter>", lambda _e: rename_lbl.config(bg=SACC))
        rename_lbl.bind("<Leave>", lambda _e: rename_lbl.config(bg=SACC_D))
        lb.bind("<Motion>", _rename_hover, add="+")
        lf.bind("<Leave>", _rename_leave, add="+")

        def _load():
            rp = _selected_run()
            if rp is None:
                return
            self.cfg.save_path = str(rp)
            self.cfg.save()
            self._load_events(str(rp))
            self.set_status(f"\u25b6 {len(self.events)} ev", _C["go"], 2000)
            win.destroy()

        def _new():
            self.cfg.save_path = ""
            self.events = []
            win.destroy()
            self.set_status("Ready", _C["pill"])

        def _toggle_fav():
            rp = _selected_run()
            if rp is None:
                return
            idx = lb.curselection()[0]
            if rp.name in favs:
                favs.discard(rp.name)
                self.set_status("Unfavorited", _C["pill"], 1200)
            else:
                favs.add(rp.name)
                self.set_status("Favorited", _C["go"], 1200)
            _save_favs()
            _refresh_runs()
            try:
                idx = runs.index(rp)
            except ValueError:
                pass
            _redraw(idx)

        def _delete_one():
            rp = _selected_run()
            if rp is None:
                return
            if not tk.messagebox.askyesno(
                "Delete Run", f"Delete {rp.name}?", parent=win
            ):
                return
            idx = lb.curselection()[0]
            try:
                rp.unlink()
            except Exception as e:
                _LOG.warning("Delete run: %s", e)
                self.set_status("Delete failed", _C["rec"], 1500)
                return
            favs.discard(rp.name)
            _save_favs()
            _refresh_runs()
            if not runs:
                self.cfg.save_path = ""
                win.destroy()
                self.set_status("No runs", _C["rec"], 1500)
                return
            self.set_status("Run deleted", _C["rec"], 1500)
            _redraw(idx)

        def _btn(parent, text, bg, fg, cmd, bold=False):
            f = tk.Frame(parent, bg=bg, cursor="hand2")
            l = tk.Label(
                f,
                text=text,
                bg=bg,
                fg=fg,
                font=("Segoe UI", 7, "bold" if bold else "normal"),
                cursor="hand2",
            )
            l.pack(padx=2, pady=3)
            for w in (f, l):
                w.bind("<Button-1>", lambda _, c=cmd: c())
            return f

        ld_f = tk.Frame(bf, bg=SACC_D, cursor="hand2")
        ld_f.pack(side="left", padx=(0, 4))
        ld_l = tk.Label(
            ld_f,
            text="  Load  ",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
        )
        ld_l.pack(padx=2, pady=2)
        for w in (ld_f, ld_l):
            w.bind("<Button-1>", lambda _: _load())
        _btn(bf, "  Fav  ", SBORD, SMUTED, _toggle_fav).pack(side="left", padx=(0, 4))
        _btn(bf, "  Delete  ", SREC, "#fff", _delete_one, True).pack(
            side="left", padx=(0, 4)
        )
        _btn(bf, "  New  ", SBORD, SMUTED, _new).pack(side="left")

        def _clear_all():
            if not tk.messagebox.askyesno(
                "Clear All Runs", f"Delete all {len(runs)} saved runs?", parent=win
            ):
                return
            for rp in runs:
                try:
                    rp.unlink()
                except Exception:
                    pass
            favs.clear()
            _save_favs()
            self.cfg.save_path = ""
            win.destroy()
            self.set_status("All runs cleared", _C["acc"], 2000)

        _btn(bf, "  Clear All  ", SREC, "#fff", _clear_all, True).pack(side="right")
        lb.bind("<Double-Button-1>", lambda _: _load())
        lb.bind("<Delete>", lambda _: _delete_one())
        lb.bind("<space>", lambda _: _toggle_fav())
        win.update_idletasks()
        H = win.winfo_reqheight()
        if wy + H > sch - 48:
            wy = ry - H - 4
        win.geometry(f"{W}x{H}+{wx}+{wy}")
        try:
            _round_hwnd(_get_hwnd(win.winfo_id()))
        except Exception:
            pass

    def _view_image(self, tgt):
        img_path = tgt.get("path")
        if not img_path or not os.path.exists(img_path):
            self.set_status("Image file not found!", _C["rec"], 2000)
            return

        try:
            pil_img = Image.open(img_path)
        except Exception as e:
            self.set_status("Failed to open image!", _C["rec"], 2000)
            return

        max_w, max_h = 200, 200
        w, h = pil_img.size
        if w > max_w or h > max_h:
            ratio = min(max_w / w, max_h / h)
            w = int(w * ratio)
            h = int(h * ratio)
            pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=SBG, padx=1, pady=1)

        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        pos_x = rx + rw + 10
        pos_y = ry + 80

        win_w = w + 30
        win_h = h + 64
        win.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")

        try:
            _round_hwnd(_get_hwnd(win.winfo_id()))
        except Exception:
            pass

        close_lbl = tk.Label(
            win,
            text="X",
            bg="#8e0a0a",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
            bd=0,
            highlightthickness=0,
            anchor="center",
        )
        close_lbl.place(x=win_w - 22, y=4, width=18, height=18)
        close_lbl.bind("<Button-1>", lambda _: win.destroy())

        win.photo = ImageTk.PhotoImage(pil_img)
        img_lbl = tk.Label(
            win, image=win.photo, bg=SBG, bd=0, highlightthickness=0, cursor="hand2"
        )
        img_lbl.pack(pady=(22, 2), padx=15)
        img_lbl.bind("<Button-1>", lambda _: win.destroy())

        preview_lbl = tk.Label(
            win, text="preview", bg=SBG, fg=SACC, font=("Segoe UI", 12), anchor="center"
        )
        preview_lbl.pack(pady=(2, 6))

        def start_drag(e):
            win.x = e.x
            win.y = e.y

        def drag(e):
            x = win.winfo_x() - win.x + e.x
            y = win.winfo_y() - win.y + e.y
            win.geometry(f"+{x}+{y}")

        win.bind("<Button-1>", start_drag)
        win.bind("<B1-Motion>", drag)
        preview_lbl.bind("<Button-1>", start_drag)
        preview_lbl.bind("<B1-Motion>", drag)

        win.bind("<Escape>", lambda _: win.destroy())
        win.bind("<x>", lambda _: win.destroy())
        win.bind("<X>", lambda _: win.destroy())

    def load_image_detection(self):
        try:
            if IMAGE_DET_JSON.exists():
                with open(IMAGE_DET_JSON, "r", encoding="utf-8") as f:
                    self.image_det_list = json.load(f)
            else:
                self.image_det_list = []
        except Exception as e:
            _LOG.error("Failed to load image detection: %s", e)
            self.image_det_list = []

    def save_image_detection(self):
        try:
            IMAGE_DET_JSON.parent.mkdir(parents=True, exist_ok=True)
            with open(IMAGE_DET_JSON, "w", encoding="utf-8") as f:
                json.dump(self.image_det_list, f, indent=4)
        except Exception as e:
            _LOG.error("Failed to save image detection: %s", e)

    def _image_search_worker(self):
        # BUG-3 fix: outer restart loop — if the inner loop crashes, restart after 2s
        while True:
            try:
                self._image_search_loop()
            except Exception as e:
                _LOG.error("Image search worker crashed, restarting: %s", e)
            time.sleep(2.0)

    def _image_search_loop(self):
        # M-2 fix: persistent mss instance inside try so init failure doesn't kill thread
        try:
            self._persistent_mss = _mss.mss()
        except Exception as e:
            _LOG.error("mss init failed: %s", e)
            self._persistent_mss = None
        # BUG-4 fix: per-image ROI dict instead of single shared tuple
        self._roi_cache = {}
        last_check = 0.0
        last_disc_check = 0.0
        while True:
            try:
                now = time.time()
                # Run image detection during playback, loop, OR recording (if enabled)
                active = self.playing or self.looping
                if getattr(self.cfg, "img_detect_while_recording", False):
                    active = active or self.recording

                # ALWAYS check for disconnect during playback/loop (every 4s)
                if active and getattr(self.cfg, "roblox_enabled", False):
                    with self._recover_lock:
                        disc_interval = 2.0 if self._recovering else 4.0
                    if now - last_disc_check >= disc_interval:
                        last_disc_check = now
                        try:
                            screen = _grab_screen(self._persistent_mss)
                            import cv2
                            import numpy as np

                            screen_np = np.array(screen)
                            del screen
                            screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
                            del screen_np
                            self._handle_roblox_recovery(screen_bgr)
                        except Exception as e:
                            _LOG.error("Disconnect check error: %s", e)

                # Image detection (separate from disconnect check)
                if active and getattr(self.cfg, "img_det_enabled", True):
                    # Threading race fix: read image_det_list under lock
                    with self._img_cache_lock:
                        has_images = bool(self.image_det_list)
                    if not has_images:
                        time.sleep(0.5)
                        continue
                    if now - last_check >= 0.5:
                        last_check = now
                        self._check_images()
                else:
                    time.sleep(2.0)
                    continue
            except Exception as e:
                _LOG.error("Error in image search loop: %s", e)
            time.sleep(0.1)

    def _find_best_match(self, screen_bgr, template_bgr, use_roi=True, roi_key=None):
        import cv2
        import numpy as np

        h, w = template_bgr.shape[:2]
        sh, sw = screen_bgr.shape[:2]

        # BUG-4 fix: per-image ROI dict so images don't clobber each other's cache
        roi_cache = getattr(self, "_roi_cache", {})
        if use_roi and roi_key and roi_key in roi_cache:
            rx, ry, rw, rh = roi_cache[roi_key]
            padding = 250
            x1 = max(0, rx - padding)
            y1 = max(0, ry - padding)
            x2 = min(sw, rx + rw + padding)
            y2 = min(sh, ry + rh + padding)
            roi_area = screen_bgr[y1:y2, x1:x2]
            roi_h, roi_w = roi_area.shape[:2]
            if roi_w >= w and roi_h >= h:
                try:
                    res = cv2.matchTemplate(
                        roi_area, template_bgr, cv2.TM_CCOEFF_NORMED
                    )
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    if max_val >= 0.55:
                        match_x = x1 + max_loc[0] + w // 2
                        match_y = y1 + max_loc[1] + h // 2
                        roi_cache[roi_key] = (match_x - w // 2, match_y - h // 2, w, h)
                        return max_val, (match_x, match_y)
                except Exception:
                    pass
            # ROI miss — clear this image's cache entry and fall through to full scan
            roi_cache.pop(roi_key, None)

        use_screen_scale = 1.0
        if sw > 900 or sh > 900:
            use_screen_scale = 0.5
            scr_search = cv2.resize(
                screen_bgr, (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA
            )
        else:
            scr_search = screen_bgr

        ssh, ssw = scr_search.shape[:2]

        # Finer scales sweep  — fewer scales during playback for speed
        if self.playing or self.looping:
            scales = [0.7, 0.85, 1.0, 1.15, 1.3]
        else:
            scales = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6]

        best_val = -1.0
        best_loc = None
        best_scale = 1.0
        best_tw = w
        best_th = h

        for scale in scales:
            tpl_scale = scale * use_screen_scale
            tw = int(w * tpl_scale)
            th = int(h * tpl_scale)

            if tw > ssw or th > ssh or tw < 10 or th < 10:
                continue

            tpl_scaled = cv2.resize(
                template_bgr,
                (tw, th),
                interpolation=cv2.INTER_AREA if tpl_scale < 1.0 else cv2.INTER_CUBIC,
            )

            try:
                res = cv2.matchTemplate(scr_search, tpl_scaled, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc
                    best_scale = scale
                    best_tw = tw
                    best_th = th
            except Exception:
                pass

        # Refine at original resolution around the match area
        match_x = (
            int((best_loc[0] + best_tw // 2) / use_screen_scale)
            if best_loc is not None
            else 0
        )
        match_y = (
            int((best_loc[1] + best_th // 2) / use_screen_scale)
            if best_loc is not None
            else 0
        )

        if best_val >= 0.50 and use_screen_scale != 1.0 and best_loc is not None:
            try:
                orig_match_x = match_x
                orig_match_y = match_y

                tw_full = int(w * best_scale)
                th_full = int(h * best_scale)

                crop_w = int(tw_full * 2.5)
                crop_h = int(th_full * 2.5)

                x1 = max(0, orig_match_x - crop_w // 2)
                y1 = max(0, orig_match_y - crop_h // 2)
                x2 = min(sw, orig_match_x + crop_w // 2)
                y2 = min(sh, orig_match_y + crop_h // 2)

                screen_crop = screen_bgr[y1:y2, x1:x2]
                tpl_refine = cv2.resize(
                    template_bgr,
                    (tw_full, th_full),
                    interpolation=cv2.INTER_AREA
                    if best_scale < 1.0
                    else cv2.INTER_CUBIC,
                )

                if (
                    screen_crop.shape[0] >= tpl_refine.shape[0]
                    and screen_crop.shape[1] >= tpl_refine.shape[1]
                ):
                    res_refine = cv2.matchTemplate(
                        screen_crop, tpl_refine, cv2.TM_CCOEFF_NORMED
                    )
                    _, refine_val, _, refine_loc = cv2.minMaxLoc(res_refine)

                    if refine_val >= best_val:
                        best_val = refine_val
                        match_x = x1 + refine_loc[0] + tw_full // 2
                        match_y = y1 + refine_loc[1] + th_full // 2
            except Exception:
                pass

        # Now apply color similarity check to the final matched region to avoid false color matches
        if best_loc is not None:
            try:
                tw_full = int(w * best_scale)
                th_full = int(h * best_scale)
                x1 = max(0, match_x - tw_full // 2)
                y1 = max(0, match_y - th_full // 2)
                x2 = min(sw, match_x + tw_full // 2)
                y2 = min(sh, match_y + th_full // 2)

                screen_crop = screen_bgr[y1:y2, x1:x2]
                # M-8 fix: guard against zero-dimension resize at screen edge
                rw = x2 - x1
                rh = y2 - y1
                if rw < 4 or rh < 4:
                    best_val = best_val * 0.25  # heavily penalize edge matches
                else:
                    tpl_refine = cv2.resize(
                        template_bgr,
                        (rw, rh),
                        interpolation=cv2.INTER_AREA
                        if best_scale < 1.0
                        else cv2.INTER_CUBIC,
                    )

                    if screen_crop.shape[0] > 0 and screen_crop.shape[1] > 0:
                        hsv_tpl = cv2.cvtColor(tpl_refine, cv2.COLOR_BGR2HSV)
                        hsv_scr = cv2.cvtColor(screen_crop, cv2.COLOR_BGR2HSV)

                        mean_tpl = cv2.mean(hsv_tpl)[:3]
                        mean_scr = cv2.mean(hsv_scr)[:3]

                        h_tpl, s_tpl, v_tpl = mean_tpl
                        h_scr, s_scr, v_scr = mean_scr

                        # If template color is colorful (Saturation >= 35)
                        if s_tpl >= 35:
                            # Matched area must also be colorful (Saturation >= 20)
                            if s_scr < 20:
                                best_val = best_val * 0.5
                            else:
                                # Compare Hue difference (circular diff on 0-180 scale)
                                hue_diff = min(
                                    abs(h_tpl - h_scr), 180 - abs(h_tpl - h_scr)
                                )
                                if hue_diff > 25:
                                    # Hue mismatch (e.g. green vs red)
                                    best_val = best_val * 0.4
                        else:
                            # Template is grayscale. Matched area should not be highly colorful
                            if s_scr >= 70:
                                best_val = best_val * 0.5
            except Exception:
                pass

            # BUG-4 fix: save ROI per image key for next scan acceleration
            if best_val >= 0.55 and roi_key:
                tw_full = int(w * best_scale)
                th_full = int(h * best_scale)
                roi_cache[roi_key] = (
                    match_x - tw_full // 2,
                    match_y - th_full // 2,
                    tw_full,
                    th_full,
                )

            return best_val, (match_x, match_y)

        return 0.0, (0, 0)

    def _handle_roblox_recovery(self, screen_bgr):
        # ── Re-entrancy guard: only one recovery at a time ──────────────
        with self._recover_lock:
            if self._recovering:
                return

        img_path = getattr(self.cfg, "roblox_disconnect_img", "")
        if not img_path or not os.path.exists(img_path):
            return

        import cv2

        template = get_cached_template(img_path)
        if template is None:
            return

        max_val, match_pt = self._find_best_match(screen_bgr, template)
        if max_val < 0.75:
            return

        # ── Capture playback state BEFORE touching anything ──────────────
        was_looping = self.looping
        was_playing = self.playing
        if not was_playing and not was_looping:
            return  # nothing to recover

        # ── C-2 fix: set recovering before terminate, use lock ─────────
        with self._recover_lock:
            self._recovering = True
        try:
            _LOG.info("Disconnect detected (conf=%.2f) — auto-recovering...", max_val)
            self.root.after(
                0,
                lambda: self.set_status(
                    "🔌 Disconnect — Rejoining...", _C["rec"], 5000
                ),
            )

            # S-7 fix: Terminate AHK BEFORE firing deeplink
            if self._ahk_proc is not None:
                try:
                    self._ahk_proc.terminate()
                except Exception:
                    pass
                self._ahk_proc = None

            # Emergency modifier release
            for vk in (
                0x10,
                0x11,
                0x12,
                0x5B,
                0x5C,
                0xA0,
                0xA1,
                0xA2,
                0xA3,
                0xA4,
                0xA5,
            ):
                try:
                    sc = user32.MapVirtualKeyW(vk, 0)
                    _send_input(_make_key(vk, sc, True, vk in _EXTENDED_VKS))
                except Exception:
                    pass

            # Now fire deeplink (after AHK is stopped)
            link = getattr(self.cfg, "roblox_server_link", "").strip()
            if link:
                import re

                pm = re.search(r"/games/(\d+)", link)
                if pm:
                    deeplink = "roblox://placeId=" + pm.group(1)
                    cm = re.search(r"privateServerLinkCode=([^&]+)", link)
                    if cm:
                        deeplink += "&linkCode=" + cm.group(1)
                    try:
                        os.startfile(deeplink)
                    except Exception as ex:
                        _LOG.error(
                            "os.startfile deeplink failed, trying webbrowser: %s", ex
                        )
                        try:
                            webbrowser.open(deeplink)
                        except Exception as ex2:
                            _LOG.error("Deeplink failed: %s", ex2)

            # S-3 fix: interruptible sleep instead of blocking time.sleep()
            wait_t = float(getattr(self.cfg, "roblox_wait_time", 5.0))
            self.root.after(
                0,
                lambda: self.set_status(
                    f"⏸ Waiting {wait_t:.0f}s for Roblox...",
                    _C["loop"],
                    int(wait_t * 1000),
                ),
            )
            _LOG.info("Waiting %.1fs for Roblox to load...", wait_t)
            for _ in range(int(wait_t * 10)):
                if self._stop_ev.is_set():
                    break
                time.sleep(0.1)

            # Bail if user stopped during wait
            if self._stop_ev.is_set():
                _LOG.info("Recovery aborted: user stopped playback during wait.")
                self.playing = self.looping = False
                self.root.after(0, self._reset_ui)
                return

            # Optional recovery macro
            rec_run_path = getattr(self.cfg, "roblox_recovery_run", "")
            if rec_run_path and os.path.exists(rec_run_path):
                _LOG.info("Running recovery macro: %s", rec_run_path)
                try:
                    with open(rec_run_path, encoding="utf-8") as rf:
                        rec_data = json.load(rf)
                    if isinstance(rec_data, list):
                        rec_evs = [ev for ev in rec_data if _valid_ev(ev)]
                        speed = max(0.1, min(10.0, self.cfg.speed))
                        rec_delays = [
                            max(ev.get("d", 0), 0) / 1000.0 / speed for ev in rec_evs
                        ]
                        self.root.after(
                            0, lambda: self.set_status("⚙️ Event Vol...", _C["go"], 3000)
                        )
                        for delay, ev in zip(rec_delays, rec_evs):
                            if self._stop_ev.is_set():
                                break
                            if delay > 0:
                                time.sleep(delay)
                            self._replay(ev)
                        _LOG.info("Recovery macro completed.")
                except Exception as rec_err:
                    _LOG.error("Failed to play recovery macro: %s", rec_err)

            if self._stop_ev.is_set():
                self.playing = self.looping = False
                self.root.after(0, self._reset_ui)
                return

            # Restart macro
            with self._click_lock:
                self._clicked_this_run = set()
            _LOG.info("Restarting macro (loop=%s)...", was_looping)
            self.root.after(
                0, lambda: self.set_status("✅ Recovery — Restarting", _C["go"], 3000)
            )

            self._stop_ev.clear()
            self.playing = True
            self.looping = was_looping

            # C-2 fix: Give the old AHK thread time to notice _recovering=True
            # and exit cleanly, then clear the flag so the new thread runs
            # normal post-playback cleanup.
            time.sleep(0.1)  # 100ms is enough for wait() to return and guard to fire

            threading.Thread(
                target=self._ahk_playback_worker,
                args=(was_looping,),
                daemon=True,
            ).start()

            # Old thread has exited by now — clear recovering so new thread
            # will do normal cleanup when it finishes.
            with self._recover_lock:
                self._recovering = False

        except Exception:
            # On unexpected error, DO clear _recovering to allow future recovery
            with self._recover_lock:
                self._recovering = False
            raise

    def _check_images(self):
        with self._recover_lock:
            if self._recovering:
                return
        try:
            import cv2
            import numpy as np
        except ImportError:
            _LOG.error("cv2 or numpy is not installed. Image detection skipped.")
            return

        try:
            screen = _grab_screen(getattr(self, "_persistent_mss", None))
            screen_np = np.array(screen)
            del screen
            screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
            del screen_np
        except Exception as e:
            _LOG.error("Failed to capture screenshot for image detection: %s", e)
            return

        if not self.image_det_list:
            return

        targets = [t for t in self.image_det_list if t.get("enabled", True)]
        targets.sort(key=lambda t: t.get("priority", 999))
        if not targets:
            return

        for tgt in targets:
            img_path = tgt.get("path")
            if not img_path:
                continue

            action = tgt.get("action", "click")

            template = get_cached_template(img_path)
            if template is None:
                continue

            max_val, match_pt = self._find_best_match(
                screen_bgr, template, roi_key=img_path
            )
            # S-4 fix: use per-image threshold if configured, else 0.90
            threshold = float(tgt.get("threshold", 0.90))
            # S-6 fix: only unpack coordinates AFTER threshold check passes
            if max_val >= threshold:
                match_x, match_y = match_pt
                name = tgt.get("name", "Image")

                _LOG.info(
                    "Image Detection: Found '%s' (Confidence: %.2f) at (%d, %d). Action: %s",
                    name,
                    max_val,
                    match_x,
                    match_y,
                    action,
                )

                if action == "click":
                    # Simple deduplication — only click each image once per run
                    with self._click_lock:
                        if img_path in getattr(self, "_clicked_this_run", set()):
                            continue
                        self._clicked_this_run.add(img_path)

                    self.root.after(
                        0,
                        lambda n=name: self.set_status(
                            f"🖱 Clicked: {n}", _C["go"], 2000
                        ),
                    )

                    # Save cursor position to restore later
                    pt = POINT()
                    user32.GetCursorPos(_ct.byref(pt))
                    orig_x, orig_y = pt.x, pt.y

                    # Teleport slower — break move into steps
                    dx = int(match_x) - pt.x
                    dy = int(match_y) - pt.y
                    steps = 4
                    for s in range(1, steps + 1):
                        user32.SetCursorPos(
                            pt.x + dx * s // steps, pt.y + dy * s // steps
                        )
                        time.sleep(0.015)

                    time.sleep(0.150)  # settle delay

                    # Three clicks spread around the image — AHK for Roblox compat
                    offsets = [(0, 0), (-4, -4), (4, -3)]
                    self.root.after(
                        0,
                        lambda n=name, mx=match_x, my=match_y: self._log_message(
                            f"> click {n} at {int(mx)},{int(my)}"
                        ),
                    )
                    for ox, oy in offsets:
                        _ahk_imgclick(int(match_x) + ox, int(match_y) + oy)
                        time.sleep(0.080)

                    # Restore cursor
                    user32.SetCursorPos(orig_x, orig_y)

                    break  # screen changed; re-capture next cycle
                else:
                    self.root.after(
                        0,
                        lambda n=name: self.set_status(f"👁 Seen: {n}", _C["go"], 2000),
                    )

    def run_all_images(self):
        if self.recording or self.playing or self.looping:
            self.set_status("Macro busy!", _C["rec"], 1500)
            return
        if getattr(self, "running_all_images", False):
            self._stop_run_all_images()
            return

        if not self.temp_image_det_list:
            self.set_status("No images!", _C["rec"], 1500)
            return

        self.running_all_images = True
        self._stop_ev.clear()
        with self._click_lock:
            self._clicked_this_run = set()
        self.c_rec.ico.config(text="⏹")
        self.c_rec.lbl.config(text="Stop")
        self.set_status("👁 RUN ALL", _C["go"])
        threading.Thread(target=self._run_all_images_worker, daemon=True).start()

    def _stop_run_all_images(self):
        self._stop_ev.set()
        self.running_all_images = False
        self.root.after(0, self._reset_ui)
        self.root.after(0, self._update_status_row)
        self.set_status("Stopped", None, 1500)

    def _run_all_images_worker(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.root.after(
                0, lambda: self.set_status("Missing cv2/numpy!", _C["rec"], 2000)
            )
            self.running_all_images = False
            self.root.after(0, self._reset_ui)
            return

        # Sort the enabled targets by priority from temp_image_det_list
        targets = [t for t in self.temp_image_det_list if t.get("enabled", True)]
        targets.sort(key=lambda t: t.get("priority", 999))

        if not targets:
            self.root.after(
                0, lambda: self.set_status("No enabled images!", _C["rec"], 2000)
            )
            self.running_all_images = False
            self.root.after(0, self._reset_ui)
            return

        try:
            for tgt in targets:
                if self._stop_ev.is_set() or not self.running_all_images:
                    break

                img_path = tgt.get("path")
                if not img_path or not os.path.exists(img_path):
                    continue

                # Take fresh screenshot
                try:
                    screen = _grab_screen()
                    screen_np = np.array(screen)
                    del screen
                    screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
                    del screen_np
                except Exception as e:
                    _LOG.error("Run All: screenshot failed: %s", e)
                    continue

                # Load template
                template = cv2.imread(img_path, cv2.IMREAD_COLOR)
                if template is None:
                    continue

                max_val, match_pt = self._find_best_match(screen_bgr, template)
                if max_val >= 0.55:
                    match_x, match_y = match_pt
                    name = tgt.get("name", "Image")
                    self.root.after(
                        0,
                        lambda n=name: self.set_status(
                            f"🖱 Clicked: {n}", _C["go"], 2000
                        ),
                    )

                    action = tgt.get("action", "click")
                    if action == "click":
                        # Perform the 3-point box click sequence (with return teleport)
                        pt = POINT()
                        user32.GetCursorPos(_ct.byref(pt))
                        orig_x, orig_y = pt.x, pt.y

                        # 3-Point Box/Triangle Click Pattern (5px offsets)
                        offsets = [
                            (-5, -5),  # Top-Left
                            (5, -5),  # Top-Right
                            (0, 5),  # Bottom-Center
                        ]

                        for ox, oy in offsets:
                            if self._stop_ev.is_set() or not self.running_all_images:
                                break
                            target_x = int(match_x + ox)
                            target_y = int(match_y + oy)
                            _ahk_imgclick(target_x, target_y)
                            time.sleep(0.08)

                        pt3 = POINT()
                        user32.GetCursorPos(_ct.byref(pt3))
                        dx3, dy3 = orig_x - pt3.x, orig_y - pt3.y
                        if dx3 != 0 or dy3 != 0:
                            _send_input(_mouse_move_rel(dx3, dy3))
                        # Wait a bit for the click consequence to render visually before scanning next image
                        time.sleep(0.5)
                    else:
                        # Just log seeing it
                        self.root.after(
                            0,
                            lambda n=name: self.set_status(
                                f"👁 Seen: {n}", _C["go"], 2000
                            ),
                        )
                        time.sleep(0.2)

            if not self._stop_ev.is_set() and self.running_all_images:
                self.root.after(
                    0, lambda: self.set_status("Run All Done!", _C["pill"], 3000)
                )

        except Exception as e:
            _LOG.error("Error in run all worker: %s", e)
        finally:
            self.running_all_images = False
            self.root.after(0, self._reset_ui)

    def clear_events(self):
        if self.recording or self.playing or self.looping:
            return
        with self._ev_lock:
            self.events = []
        self.set_status("Cleared", None, 1500)

    def _screenshot(self):
        threading.Thread(target=self._ss_worker, daemon=True).start()

    def _ss_worker(self, suffix=""):
        if not self._ss_lock.acquire(blocking=False):
            return None
        try:
            f = Path(self.cfg.shot_folder)
            f.mkdir(parents=True, exist_ok=True)
            name = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + (suffix or "") + ".png"
            _grab_screen().save(f / name)
            self.root.after(0, lambda: self.set_status("", _C["acc"], 1500))
            return str(f / name)
        except Exception as e:
            _LOG.error("Screenshot: %s", e)
            self.root.after(0, lambda: self.set_status("", _C["rec"], 2000))
            return None
        finally:
            self._ss_lock.release()

    def _webhook(self, event):
        url = self.cfg.webhook_url.strip()
        if not url or not getattr(self.cfg, f"wh_{event}", False):
            return
        # Deduplicate: skip if same event fired within last 2 seconds
        now = time.time()
        last_key = f"_last_wh_{event}"
        if now - getattr(self, last_key, 0) < 2.0:
            return
        setattr(self, last_key, now)

        try:
            titles = {"record": "", "save": ""}
            fields = [
                {"name": "Events", "value": str(len(self.events)), "inline": True},
                {
                    "name": "Runs",
                    "value": str(self.cfg.stats_run_count),
                    "inline": True,
                },
            ]
            embed = {
                "author": {"name": "TinyKullan"},
                "title": titles.get(event, "TinyKullan Notification"),
                "color": 0x9D7CFF,
                "fields": fields,
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"
                ),
            }
            wh = DiscordWebhook(url=url, username="TinyKullan")
            em = DiscordEmbed(
                title=embed.get("title", ""),
                color=embed.get("color", 0x9D7CFF),
                timestamp=embed.get("timestamp"),
            )
            for field in embed.get("fields", []):
                em.add_embed_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", True),
                )
            wh.add_embed(em)
            wh.execute()
        except Exception as e:
            _LOG.warning("Webhook: %s", e)

    def _post_play(self, play_ms, was_loop, skip_stats=False):
        self._run_count += 1
        # S-9 fix: lock-protected stats increment and save
        if not skip_stats:
            with self._stats_lock:
                self.cfg.stats_run_count += 1
                self.cfg.stats_total_minutes += play_ms / 60000.0
            try:
                self.cfg.save()
            except Exception:
                pass
        url = self.cfg.webhook_url.strip()
        if not url or not (
            (was_loop and self.cfg.wh_loop) or (not was_loop and self.cfg.wh_play)
        ):
            return
        shot = self._ss_worker("_playback") if self.cfg.wh_screenshot else None
        title = "Loop Complete" if was_loop else "Play Complete"
        embed = {
            "author": {"name": "TinyKullan action completed"},
            "title": title,
            "color": 0xFF4FD8,
            "fields": [
                {"name": "Events", "value": str(len(self.events)), "inline": True},
                {"name": "Speed", "value": f"{self.cfg.speed}x", "inline": True},
                {
                    "name": "Total Runs",
                    "value": str(self.cfg.stats_run_count),
                    "inline": True,
                },
            ],
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        payload = {"username": "TinyKullan", "embeds": [embed]}
        if self.cfg.mention_id:
            payload["content"] = f"<@{self.cfg.mention_id}>"
        try:
            wh = DiscordWebhook(
                url=url, username="TinyKullan", content=payload.get("content", "")
            )
            em = DiscordEmbed(
                title=embed.get("title", ""),
                color=embed.get("color", 0xFF4FD8),
                timestamp=embed.get("timestamp"),
            )
            for field in embed.get("fields", []):
                em.add_embed_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", True),
                )
            wh.add_embed(em)
            if shot and Path(shot).exists():
                with open(shot, "rb") as fp:
                    wh.add_file(file=fp.read(), filename="screenshot.png")
            wh.execute()
        except Exception as e:
            _LOG.warning("Post-play webhook: %s", e)

    def apply_theme(self):
        old_vals = {
            "SBG": SBG,
            "SSURF": SSURF,
            "SBORD": SBORD,
            "SACC": SACC,
            "SACC_D": SACC_D,
            "STEXT": STEXT,
            "SMUTED": SMUTED,
            "SED": SED,
            "SEDB": SEDB,
        }
        _C.update(_derive(self.cfg.theme))
        _update_sp(self.cfg.theme)
        self.root.configure(bg=_C["bg"])
        self._tb.configure(bg=_C["top"])
        self._ico.configure(bg=_C["top"], fg=_C["title_fg"])
        self._title.configure(bg=_C["top"], fg=_C["title_fg"])
        self._sep.configure(bg=_C["sep"])
        self._pill.configure(bg=_C["pill"])
        self._slbl.configure(bg=_C["pill"], fg=_C["status_fg"])
        for _, col in self._all_cols:
            col.refresh()

        if self._swin is not None:
            try:
                color_map = {
                    old_vals["SBG"]: SBG,
                    old_vals["SSURF"]: SSURF,
                    old_vals["SBORD"]: SBORD,
                    old_vals["SACC"]: SACC,
                    old_vals["SACC_D"]: SACC_D,
                    old_vals["STEXT"]: STEXT,
                    old_vals["SMUTED"]: SMUTED,
                    old_vals["SED"]: SED,
                    old_vals["SEDB"]: SEDB,
                }
                color_map = {k: v for k, v in color_map.items() if k and k != v}
                if color_map:

                    def _upd_w(w):
                        try:
                            cfg = {}
                            for opt in ["bg", "background"]:
                                if w.keys() and opt in w.keys():
                                    curr = w.cget(opt)
                                    if curr in color_map:
                                        cfg[opt] = color_map[curr]
                            for opt in ["fg", "foreground"]:
                                if w.keys() and opt in w.keys():
                                    curr = w.cget(opt)
                                    if curr in color_map:
                                        cfg[opt] = color_map[curr]
                            for opt in [
                                "highlightbackground",
                                "troughcolor",
                                "selectcolor",
                            ]:
                                if w.keys() and opt in w.keys():
                                    curr = w.cget(opt)
                                    if curr in color_map:
                                        cfg[opt] = color_map[curr]
                            if cfg:
                                w.configure(**cfg)
                        except Exception:
                            pass
                        for child in w.winfo_children():
                            _upd_w(child)

                    _upd_w(self._swin)
            except Exception as e:
                _LOG.warning("Failed to dynamically update settings theme: %s", e)

    def _snap_settings_to_main(self, _=None):
        if self._swin is None:
            return
        try:
            self.root.update_idletasks()
            self._swin.update_idletasks()
            sw, sh = self._swin.winfo_width(), self._swin.winfo_height()
            rx, ry = self.root.winfo_x(), self.root.winfo_y()
            rw = self.root.winfo_width()
            scw, sch = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            x = rx + rw + 6
            if x + sw > scw - 4:
                x = max(0, rx - sw - 6)
            y = max(0, min(ry, sch - sh - 48))
            self._swin.geometry(f"+{x}+{y}")
            self._swin.lift()
        except Exception as e:
            _LOG.debug("Snap settings: %s", e)

    def _open_settings(self):
        if self._swin is not None:
            try:
                self._swin.lift()
                return
            except Exception:
                self._swin = None
                self._cached_swin_hwnd = None
                self._cached_rects = None

        SW, SH = 420, 530
        win = tk.Toplevel(self.root)
        win.title("Settings")
        if sys.platform == "win32":
            win.overrideredirect(True)
        win.configure(bg=SBG)
        win.attributes("-topmost", True)
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        scw, sch = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        wx = max(0, min(rx, scw - SW - 4))
        wy = ry + TH + 1 + BH + 4
        if wy + SH > sch - 48:
            wy = ry - SH - 4
        win.geometry(f"{SW}x{SH}+{wx}+{wy}")
        if sys.platform != "win32":
            win.transient(self.root)
            win.focus_force()
        self._swin = win
        self._cached_swin_hwnd = _get_hwnd(win.winfo_id()) if win.winfo_id() else None

        snap = {k: getattr(self.cfg, k) for k in self.cfg.DEFAULTS}
        snap["theme"] = dict(self.cfg.theme)
        self.temp_image_det_list = [dict(x) for x in self.image_det_list]

        def _close(*_):
            for sf in self._scroll_frames:
                sf.destroy()
            self._scroll_frames.clear()
            for k, v in snap.items():
                if k == "theme":
                    self.cfg.theme.clear()
                    self.cfg.theme.update(v)
                else:
                    setattr(self.cfg, k, v)
            self.apply_theme()
            self._apply_tiny()
            self._apply_icons()
            self._resume_hk_listener()
            win.destroy()
            self._swin = None
            self._cached_swin_hwnd = None
            self._cached_rects = None

        ob = tk.Frame(win, bg=SBORD)
        ob.place(x=0, y=0, width=SW, height=SH)
        wp = tk.Frame(ob, bg=SBG)
        wp.place(x=1, y=1, width=SW - 2, height=SH - 2)

        stb = tk.Frame(wp, bg=SSURF, height=26)
        stb.pack(fill="x")
        stb.pack_propagate(False)
        tk.Label(
            stb,
            text="\u2699  Settings",
            bg=SSURF,
            fg=STEXT,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=10)
        xb = tk.Label(
            stb,
            text="\u2715",
            bg=SSURF,
            fg=SMUTED,
            font=("Segoe UI", 9),
            cursor="hand2",
            width=3,
        )
        xb.pack(side="right")
        xb.bind("<Button-1>", _close)
        xb.bind("<Enter>", lambda _: xb.config(fg=STEXT, bg=SREC))
        xb.bind("<Leave>", lambda _: xb.config(fg=SMUTED, bg=SSURF))
        tk.Frame(wp, bg=SBORD, height=1).pack(fill="x")

        sdx, sdy = [0], [0]
        stb.bind(
            "<ButtonPress-1>",
            lambda e: (
                sdx.__setitem__(0, e.x_root - win.winfo_x()),
                sdy.__setitem__(0, e.y_root - win.winfo_y()),
            ),
        )
        stb.bind(
            "<B1-Motion>",
            lambda e: win.geometry(f"+{e.x_root - sdx[0]}+{e.y_root - sdy[0]}"),
        )

        tbar = tk.Frame(wp, bg=SSURF, height=24)
        tbar.pack(fill="x")
        tbar.pack_propagate(False)
        tk.Frame(wp, bg=SBORD, height=1).pack(fill="x")
        tk.Frame(wp, bg=SBORD, height=1).pack(side="bottom", fill="x")

        sbar = tk.Frame(wp, bg=SSURF, height=28)
        sbar.pack(side="bottom", fill="x")
        sbar.pack_propagate(False)
        sstat = tk.Label(sbar, text="", bg=SSURF, fg=SMUTED, font=("Segoe UI", 7))
        sstat.pack(side="left", padx=8)
        sbf = tk.Frame(sbar, bg=SACC_D, cursor="hand2")
        sbf.pack(side="right", padx=6, pady=5)
        sbl = tk.Label(
            sbf,
            text="  SAVE  ",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
        )
        sbl.pack(padx=1, pady=1)

        body = tk.Frame(wp, bg=SBG)
        body.pack(fill="both", expand=True)
        BH2 = SH - 26 - 1 - 24 - 1 - 29
        sf1 = ScrollFrame(body, SBG, SW - 2, BH2)
        sf2 = ScrollFrame(body, SBG, SW - 2, BH2)
        sf3 = ScrollFrame(body, SBG, SW - 2, BH2)
        sf4 = ScrollFrame(body, SBG, SW - 2, BH2)
        sf5 = ScrollFrame(body, SBG, SW - 2, BH2)
        sf6 = ScrollFrame(body, SBG, SW - 2, BH2)
        sf7 = ScrollFrame(body, SBG, SW - 2, BH2)
        self._scroll_frames = [sf1, sf2, sf3, sf4, sf5, sf6, sf7]
        for sf in (sf1, sf2, sf3, sf4, sf5, sf6, sf7):
            sf.outer.place(x=0, y=0, relwidth=1, relheight=1)

        cur, tbtns = [0], []

        def switch(n):
            if cur[0] == n:
                return
            cur[0] = n
            for i, (b, sf) in enumerate(
                zip(tbtns, (sf1, sf4, sf2, sf3, sf5, sf6, sf7))
            ):
                b.config(bg=SBG if i == n else SSURF, fg=STEXT if i == n else SMUTED)
            (sf1, sf4, sf2, sf3, sf5, sf6, sf7)[n].outer.lift()

        for i, lbl in enumerate(
            [
                "  Main  ",
                "  Clicker  ",
                "  Webhook  ",
                "  Theme  ",
                "  Share  ",
                "  Detection  ",
                "  Roblox  ",
            ]
        ):
            b = tk.Label(
                tbar,
                text=lbl,
                bg=SBG if i == 0 else SSURF,
                fg=STEXT if i == 0 else SMUTED,
                font=("Segoe UI", 7, "bold"),
                cursor="hand2",
            )
            b.pack(side="left", ipady=4)
            b.bind("<Button-1>", (lambda n: lambda _: switch(n))(i))
            tbtns.append(b)

        PX = 10

        def _sec(p, t):
            tk.Label(
                p, text=t, bg=SBG, fg=SACC, font=("Segoe UI", 7, "bold"), anchor="w"
            ).pack(fill="x", padx=PX, pady=(10, 1))
            tk.Frame(p, bg=SBORD, height=1).pack(fill="x", padx=PX, pady=(0, 4))

        def _lbl(p, t):
            tk.Label(
                p, text=t, bg=SBG, fg=SMUTED, font=("Segoe UI", 7), anchor="w"
            ).pack(fill="x", padx=PX, pady=(2, 0))

        def _chk(p, text, attr, callback=None):
            var = tk.BooleanVar(value=getattr(self.cfg, attr))
            row = tk.Frame(p, bg=SBG)
            row.pack(fill="x", padx=PX, pady=1)
            dot = tk.Label(row, bg=SBG, font=("Segoe UI", 8))
            dot.pack(side="left", padx=(0, 5))
            tk.Label(
                row,
                text=text,
                bg=SBG,
                fg=STEXT,
                font=("Segoe UI", 8),
                anchor="w",
                cursor="hand2",
            ).pack(side="left")

            def _upd():
                v = var.get()
                setattr(self.cfg, attr, v)
                dot.config(text="\u25c6" if v else "\u25c7", fg=SACC if v else SBORD)
                if callback:
                    callback()

            def _tog(_=None):
                var.set(not var.get())
                _upd()

            _upd()
            for w in row.winfo_children():
                w.bind("<Button-1>", _tog)
            row.bind("<Button-1>", _tog)

        def _path_entry(p, attr, is_file):
            _lbl(
                p,
                {"save_path": "Events (.json)", "shot_folder": "Screenshots"}.get(
                    attr, attr
                ),
            )
            f = tk.Frame(p, bg=SED, highlightbackground=SEDB, highlightthickness=1)
            f.pack(fill="x", padx=PX, pady=(2, 5))
            en = tk.Entry(
                f,
                bg=SED,
                fg=STEXT,
                relief="flat",
                bd=4,
                insertbackground=SACC,
                font=("Segoe UI", 8),
            )
            en.insert(0, getattr(self.cfg, attr))
            en.pack(side="left", fill="x", expand=True)
            en.bind("<FocusOut>", lambda _, a=attr, e=en: setattr(self.cfg, a, e.get()))
            br = tk.Label(
                f,
                text=" \U0001f4c2 ",
                bg=SACC_D,
                fg=STEXT,
                font=("Segoe UI", 8),
                cursor="hand2",
            )
            br.pack(side="right")
            if is_file:
                br.bind(
                    "<Button-1>",
                    lambda _, a=attr, e=en: (
                        e.delete(0, "end"),
                        e.insert(
                            0,
                            _save_file(
                                title="Choose macro file",
                                default_ext=".json",
                                filetypes=[("JSON", "*.json")],
                            ),
                        ),
                        setattr(self.cfg, a, e.get()),
                    ),
                )
            else:
                br.bind(
                    "<Button-1>",
                    lambda _, a=attr, e=en: (
                        e.delete(0, "end"),
                        e.insert(0, _pick_directory(title="Choose folder")),
                        setattr(self.cfg, a, e.get()),
                    ),
                )
            return en

        inn1 = sf1.inner
        _sec(inn1, "HOTKEYS (click \u23fa then press keys)")
        for label, attr in [
            ("Record", "key_record"),
            ("Play", "key_play"),
            ("Loop", "key_loop"),
            ("Save", "key_save"),
            ("Pause", "key_pause"),
            ("Stop", "key_stop"),
        ]:
            _lbl(inn1, label)
            HotkeyEntry(
                inn1, getattr(self.cfg, attr), lambda v, a=attr: setattr(self.cfg, a, v)
            )

        def _upd_speed(v):
            setattr(self.cfg, "speed", float(v))
            snap["speed"] = float(v)
            spd_lbl.config(text=f"Speed: {float(v):.1f}x")

        _sec(inn1, "PLAYBACK SPEED")
        spd_lbl = tk.Label(
            inn1,
            text=f"Speed: {self.cfg.speed:.1f}x",
            bg=SBG,
            fg=SMUTED,
            font=("Segoe UI", 7),
            anchor="w",
        )
        spd_lbl.pack(fill="x", padx=PX, pady=(2, 0))
        speed_var = tk.DoubleVar(value=self.cfg.speed)
        tk.Scale(
            inn1,
            from_=0.1,
            to=10.0,
            resolution=0.1,
            orient="horizontal",
            variable=speed_var,
            bg=SBG,
            fg=STEXT,
            troughcolor=SSURF,
            highlightthickness=0,
            length=200,
            command=_upd_speed,
        ).pack(fill="x", padx=PX, pady=5)

        _sec(inn1, "IMAGE DETECTION")
        _chk(inn1, "Run Image Detection During Playback/Loop", "img_det_enabled")
        _chk(inn1, "Also Detect While Recording", "img_detect_while_recording")

        _sec(inn1, "PATHS")
        path_entries = {
            a: _path_entry(inn1, a, f)
            for a, f in [("save_path", True), ("shot_folder", False)]
        }

        _sec(inn1, "TINY MODE")
        _chk(inn1, "Enable Tiny Mode", "tiny_mode", self._apply_tiny)
        for label, attr in [
            ("Record", "tiny_record"),
            ("Play", "tiny_play"),
            ("Loop", "tiny_loop"),
            ("Save", "tiny_save"),
            ("Pause", "tiny_pause"),
            ("Edit", "tiny_edit"),
        ]:
            _chk(inn1, f"  Show {label}", attr, self._apply_tiny)
        tk.Label(
            inn1,
            text="  Settings is always shown (min 3 buttons enforced)",
            bg=SBG,
            fg=SMUTED,
            font=("Segoe UI", 7, "italic"),
            anchor="w",
        ).pack(fill="x", padx=PX, pady=(2, 4))

        _sec(inn1, "WINDOW")
        _chk(inn1, "Auto Raise on Hover", "auto_focus")
        _chk(
            inn1,
            "Always On Top (Main Window)",
            "always_on_top",
            lambda: self.root.attributes("-topmost", self.cfg.always_on_top),
        )
        _chk(
            inn1,
            "Record Relative To Window",
            "record_relative_to_window",
        )
        _chk(
            inn1,
            "BIG Mode",
            "big_mode",
            callback=self._apply_big,
        )
        tk.Frame(inn1, bg=SBG, height=10).pack()

        inn4 = sf4.inner
        _sec(inn4, "AUTO CLICKER SETTINGS")
        _lbl(inn4, "Hotkey (to start/stop)")
        HotkeyEntry(
            inn4,
            self.cfg.key_autoclick,
            lambda v: setattr(self.cfg, "key_autoclick", v),
        )

        def _upd_cps(v):
            setattr(self.cfg, "autoclick_cps", float(v))
            cps_lbl.config(text=f"Clicks Per Second: {float(v):.1f}")

        _sec(inn4, "CLICK SPEED (CPS)")
        cps_lbl = tk.Label(
            inn4,
            text=f"Clicks Per Second: {self.cfg.autoclick_cps:.1f}",
            bg=SBG,
            fg=SMUTED,
            font=("Segoe UI", 7),
            anchor="w",
        )
        cps_lbl.pack(fill="x", padx=PX, pady=(2, 0))
        cps_var = tk.DoubleVar(value=self.cfg.autoclick_cps)
        tk.Scale(
            inn4,
            from_=1.0,
            to=60.0,
            resolution=1.0,
            orient="horizontal",
            variable=cps_var,
            bg=SBG,
            fg=STEXT,
            troughcolor=SSURF,
            highlightthickness=0,
            length=200,
            command=_upd_cps,
        ).pack(fill="x", padx=PX, pady=5)

        _sec(inn4, "MOUSE BUTTON")
        btn_var = tk.StringVar(value=self.cfg.autoclick_btn)
        row = tk.Frame(inn4, bg=SBG)
        row.pack(fill="x", padx=PX, pady=5)
        for b in ["Left", "Right"]:
            tk.Radiobutton(
                row,
                text=b,
                variable=btn_var,
                value=b,
                bg=SBG,
                fg=STEXT,
                selectcolor=SSURF,
                activebackground=SBG,
                font=("Segoe UI", 8),
                command=lambda: setattr(self.cfg, "autoclick_btn", btn_var.get()),
            ).pack(side="left", padx=(0, 10))
        tk.Frame(inn4, bg=SBG, height=12).pack()

        inn2 = sf2.inner
        _sec(inn2, "DISCORD WEBHOOK")
        _lbl(inn2, "URL")
        ue_f = tk.Frame(inn2, bg=SED, highlightbackground=SEDB, highlightthickness=1)
        ue_f.pack(fill="x", padx=PX, pady=(2, 5))
        ue = tk.Entry(
            ue_f,
            bg=SED,
            fg=STEXT,
            relief="flat",
            bd=4,
            insertbackground=SACC,
            font=("Segoe UI", 8),
        )
        ue.insert(0, self.cfg.webhook_url)
        ue.pack(fill="x")
        ue.bind("<KeyRelease>", lambda _: setattr(self.cfg, "webhook_url", ue.get()))
        tr = tk.Frame(inn2, bg=SBG)
        tr.pack(fill="x", padx=PX, pady=(0, 6))
        whs = tk.Label(tr, text="", bg=SBG, fg=SMUTED, font=("Segoe UI", 7))
        whs.pack(side="left", fill="x", expand=True)
        tf = tk.Frame(tr, bg=SACC_D, cursor="hand2")
        tf.pack(side="right")
        tl = tk.Label(
            tf,
            text=" TEST ",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
        )
        tl.pack(padx=1, pady=1)
        for w in (tf, tl):
            w.bind("<Button-1>", lambda _: self._test_webhook(ue.get(), whs))
        _sec(inn2, "MENTION")
        _lbl(inn2, "User/Role ID")
        me_f = tk.Frame(inn2, bg=SED, highlightbackground=SEDB, highlightthickness=1)
        me_f.pack(fill="x", padx=PX, pady=(2, 5))
        me = tk.Entry(
            me_f,
            bg=SED,
            fg=STEXT,
            relief="flat",
            bd=4,
            insertbackground=SACC,
            font=("Segoe UI", 8),
        )
        me.insert(0, self.cfg.mention_id)
        me.pack(fill="x")
        me.bind("<KeyRelease>", lambda _: setattr(self.cfg, "mention_id", me.get()))
        _sec(inn2, "SEND ON")
        _chk(inn2, "Record stop", "wh_record")
        _chk(inn2, "Play complete", "wh_play")
        _chk(inn2, "Loop complete", "wh_loop")
        _sec(inn2, "CAPTURE")
        _chk(inn2, "Auto-screenshot after playback", "wh_screenshot")
        tk.Frame(inn2, bg=SBG, height=12).pack()

        inn3 = sf3.inner
        _sec(inn3, "BUTTON ICONS")
        ico_entries = {}
        for ico_label, ico_attr in [
            ("Record", "ico_record"),
            ("Play", "ico_play"),
            ("Loop", "ico_loop"),
            ("Save", "ico_save"),
            ("Delete", "ico_delete"),
            ("Settings", "ico_settings"),
        ]:
            row = tk.Frame(inn3, bg=SBG)
            row.pack(fill="x", padx=PX, pady=1)
            tk.Label(
                row,
                text=ico_label,
                bg=SBG,
                fg=SMUTED,
                font=("Segoe UI", 7),
                anchor="w",
                width=8,
            ).pack(side="left")
            ef = tk.Frame(row, bg=SED, highlightbackground=SEDB, highlightthickness=1)
            ef.pack(side="left", padx=(4, 0))
            en = tk.Entry(
                ef,
                bg=SED,
                fg=STEXT,
                relief="flat",
                bd=2,
                insertbackground=SACC,
                font=("Segoe UI Emoji", 12),
                width=4,
                justify="center",
            )
            en.insert(0, getattr(self.cfg, ico_attr))
            en.pack()
            en.bind(
                "<KeyRelease>",
                (lambda a, e: lambda _: setattr(self.cfg, a, e.get().strip() or "?"))(
                    ico_attr, en
                ),
            )
            ico_entries[ico_attr] = en

        def _reset_icons(_=None):
            for a, e in ico_entries.items():
                default = self.cfg.DEFAULTS.get(a, "?")
                setattr(self.cfg, a, default)
                e.delete(0, "end")
                e.insert(0, default)

        rif = tk.Frame(inn3, bg=SBG)
        rif.pack(fill="x", padx=PX, pady=(4, 0))
        rib = tk.Frame(rif, bg=SBORD, cursor="hand2")
        rib.pack(side="left")
        ril = tk.Label(
            rib,
            text="  Reset Icons  ",
            bg=SBORD,
            fg=SMUTED,
            font=("Segoe UI", 7),
            cursor="hand2",
        )
        ril.pack(padx=2, pady=2)
        for w in (rib, ril):
            w.bind("<Button-1>", _reset_icons)
        tk.Label(
            inn3,
            text="Tip: Press  Win + .  to open emoji picker",
            bg=SBG,
            fg=SMUTED,
            font=("Segoe UI", 6, "italic"),
            anchor="w",
        ).pack(fill="x", padx=PX, pady=(3, 0))

        _sec(inn3, "STATS DASHBOARD")
        sf_s = tk.Frame(inn3, bg=SBG)
        sf_s.pack(fill="x", padx=PX, pady=4)
        sbf_s = tk.Frame(sf_s, bg=SACC_D, cursor="hand2")
        sbf_s.pack(side="left")
        sbl_s = tk.Label(
            sbf_s,
            text="  Open Dashboard  ",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
        )
        sbl_s.pack(padx=2, pady=2)
        for w in (sbf_s, sbl_s):
            w.bind("<Button-1>", lambda _: self._start_stats_server())
        tk.Label(
            inn3,
            text="http://127.0.0.1:9270",
            bg=SBG,
            fg=SMUTED,
            font=("Segoe UI", 6, "italic"),
        ).pack(fill="x", padx=PX, pady=(2, 6))
        _lbl(inn3, "Custom 1000h Title")
        ctf = tk.Frame(inn3, bg=SED, highlightbackground=SEDB, highlightthickness=1)
        ctf.pack(fill="x", padx=PX, pady=(2, 5))
        cte = tk.Entry(
            ctf,
            bg=SED,
            fg=STEXT,
            relief="flat",
            bd=4,
            insertbackground=SACC,
            font=("Segoe UI", 8),
        )
        cte.insert(0, self.cfg.stats_custom_title)
        cte.pack(fill="x")
        cte.bind(
            "<KeyRelease>", lambda _: setattr(self.cfg, "stats_custom_title", cte.get())
        )

        _sec(inn3, "THEME COLORS")
        _lbl(inn3, "Pick 3 base colors \u2014 all UI colors derived automatically.")
        tk.Frame(inn3, bg=SBG, height=6).pack()
        swatches = {}

        def _swatch(parent, key, label):
            row = tk.Frame(parent, bg=SBG)
            row.pack(fill="x", padx=PX, pady=5)
            tk.Label(
                row,
                text=label,
                bg=SBG,
                fg=STEXT,
                font=("Segoe UI", 8),
                width=20,
                anchor="w",
            ).pack(side="left")
            sw = tk.Frame(
                row,
                bg=self.cfg.theme.get(key, "#888"),
                width=32,
                height=20,
                cursor="hand2",
                highlightbackground=SBORD,
                highlightthickness=1,
            )
            sw.pack(side="left", padx=6)
            sw.pack_propagate(False)
            cv = tk.Label(
                row,
                text=self.cfg.theme.get(key, ""),
                bg=SBG,
                fg=SMUTED,
                font=("Consolas", 8),
            )
            cv.pack(side="left")

            def _pick(_, k=key, s=sw, c=cv):
                r = colorchooser.askcolor(
                    color=self.cfg.theme.get(k, "#888"), title=f"Pick \u2014 {label}"
                )
                if r and r[1]:
                    self.cfg.theme[k] = r[1]
                    s.config(bg=r[1])
                    c.config(text=r[1])

            sw.bind("<Button-1>", _pick)
            swatches[key] = sw

        for k, l in [
            ("primary", "Primary (Dark)"),
            ("secondary", "Secondary (Light)"),
            ("accent", "Accent (Highlight)"),
        ]:
            _swatch(inn3, k, l)

        tk.Frame(inn3, bg=SBG, height=12).pack()

        inn5 = sf5.inner
        _sec(inn5, "SHARE MACRO")

        macro_info_lbl = tk.Label(
            inn5,
            text=f"Current: {len(self.events)} events",
            bg=SBG,
            fg=STEXT,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        )
        macro_info_lbl.pack(fill="x", padx=PX, pady=(4, 2))

        _lbl(inn5, "Copy macro code to export/share, or paste code here then import.")

        text_frame = tk.Frame(
            inn5, bg=SED, highlightbackground=SEDB, highlightthickness=1
        )
        text_frame.pack(fill="both", expand=True, padx=PX, pady=6)

        share_text = tk.Text(
            text_frame,
            bg=SED,
            fg=STEXT,
            insertbackground=SACC,
            relief="flat",
            font=("Consolas", 8),
            height=4,
            wrap="char",
        )
        share_text.pack(fill="both", expand=True, padx=2, pady=2)

        btn_row = tk.Frame(inn5, bg=SBG)
        btn_row.pack(fill="x", padx=PX, pady=6)

        exp_f = tk.Frame(btn_row, bg=SACC_D, cursor="hand2")
        exp_f.pack(side="left", fill="x", expand=True, padx=(0, 4))
        exp_l = tk.Label(
            exp_f,
            text="Export to Clipboard",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
            anchor="center",
            pady=4,
        )
        exp_l.pack(fill="x")

        imp_f = tk.Frame(btn_row, bg=SACC_D, cursor="hand2")
        imp_f.pack(side="right", fill="x", expand=True, padx=(4, 0))
        imp_l = tk.Label(
            imp_f,
            text="Import Code",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
            anchor="center",
            pady=4,
        )
        imp_l.pack(fill="x")

        def _export_macro():
            try:
                if not self.events:
                    raise ValueError("No events to export")

                # Bundle events, image detection targets, and image binary data
                payload = {
                    "version": 2,
                    "events": self.events,
                    "image_detection": self.image_det_list,
                }

                images_data = {}
                for tgt in self.image_det_list:
                    img_path = tgt.get("path")
                    if img_path and os.path.exists(img_path):
                        try:
                            with open(img_path, "rb") as f:
                                b64 = base64.b64encode(f.read()).decode("utf-8")
                            images_data[Path(img_path).name] = b64
                        except Exception as e:
                            _LOG.warning("Failed to encode image %s: %s", img_path, e)

                payload["images"] = images_data

                json_str = json.dumps(payload)
                b64_str = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

                self.root.clipboard_clear()
                self.root.clipboard_append(b64_str)

                share_text.delete("1.0", "end")
                img_msg = f", {len(images_data)} images" if images_data else ""
                share_text.insert(
                    "1.0",
                    f"Macro successfully exported to clipboard ({len(self.events)} events{img_msg})",
                )

                sstat.config(text="Successfully exported macro", fg=SPLAY)
                macro_info_lbl.config(text=f"Current: {len(self.events)} events")
            except Exception:
                sstat.config(text="Macro Run into issue check the code?!", fg=SREC)

        def _import_macro():
            try:
                raw_str = share_text.get("1.0", "end").strip()
                if not raw_str or raw_str.startswith("Macro successfully"):
                    raw_str = self.root.clipboard_get().strip()
                if not raw_str:
                    raise ValueError("No input")

                try:
                    decoded_bytes = base64.b64decode(raw_str.encode("utf-8"))
                    decoded_str = decoded_bytes.decode("utf-8")
                    payload = json.loads(decoded_str)
                except Exception:
                    payload = json.loads(raw_str)

                # Support backward compatibility
                if isinstance(payload, list):
                    events = payload
                    image_det = []
                    images_data = {}
                elif isinstance(payload, dict):
                    events = payload.get("events", [])
                    image_det = payload.get("image_detection", [])
                    images_data = payload.get("images", {})
                else:
                    raise ValueError("Invalid format")

                if not isinstance(events, list):
                    raise ValueError("Events must be a list")
                for ev in events:
                    if not isinstance(ev, dict) or "t" not in ev:
                        raise ValueError("Invalid event format")

                # Decode and recreate image files on disk
                if images_data:
                    IMAGES_PATH.mkdir(parents=True, exist_ok=True)
                    for name, b64 in images_data.items():
                        dest_path = IMAGES_PATH / name
                        try:
                            with open(dest_path, "wb") as f:
                                f.write(base64.b64decode(b64.encode("utf-8")))
                        except Exception as e:
                            _LOG.error(
                                "Failed to write imported image %s: %s", dest_path, e
                            )

                # Localize image paths in target configs
                updated_image_det = []
                for tgt in image_det:
                    if not isinstance(tgt, dict):
                        continue
                    new_tgt = dict(tgt)
                    if "path" in new_tgt:
                        old_name = Path(new_tgt["path"]).name
                        new_tgt["path"] = str(IMAGES_PATH / old_name)
                    updated_image_det.append(new_tgt)

                self.events = [ev for ev in events if _valid_ev(ev)]
                self.image_det_list = updated_image_det
                self.temp_image_det_list = [dict(x) for x in updated_image_det]

                # Save imported configuration
                self.save_image_detection()

                # Refresh UI
                try:
                    _render_image_list()
                except Exception:
                    pass

                share_text.delete("1.0", "end")
                img_msg = f", {len(images_data)} images" if images_data else ""
                share_text.insert(
                    "1.0",
                    f"Macro successfully loaded: {len(self.events)} events{img_msg}",
                )

                sstat.config(text="Successfully imported macro", fg=SPLAY)
                macro_info_lbl.config(text=f"Current: {len(self.events)} events")
            except Exception:
                sstat.config(text="Macro Run into issue check the code?!", fg=SREC)

        for w in (exp_f, exp_l):
            w.bind("<Button-1>", lambda _: _export_macro())
        for w in (imp_f, imp_l):
            w.bind("<Button-1>", lambda _: _import_macro())

        tk.Frame(inn5, bg=SBG, height=12).pack()

        # TAB 6: DETECTION
        inn6 = sf6.inner
        _sec(inn6, "IMAGE DETECTION")

        _chk(inn6, "Enable image check during playback", "img_det_enabled")

        tk.Frame(inn6, bg=SBG, height=8).pack()

        image_list_frame = tk.Frame(inn6, bg=SBG)
        image_list_frame.pack(fill="x", padx=PX, pady=(4, 8))

        def _render_image_list():
            for child in image_list_frame.winfo_children():
                child.destroy()

            if not self.temp_image_det_list:
                tk.Label(
                    image_list_frame,
                    text="No target images added yet.\nClick the upload button below to select a target PNG.",
                    bg=SBG,
                    fg=SMUTED,
                    font=("Segoe UI", 7),
                    justify="center",
                ).pack(fill="x", pady=20)
                return

            for idx, tgt in enumerate(self.temp_image_det_list):
                row = tk.Frame(image_list_frame, bg=SSURF, padx=6, pady=4)
                row.pack(fill="x", pady=2)

                name_lbl = tk.Label(
                    row,
                    text=tgt.get("name", "Image"),
                    bg=SSURF,
                    fg=STEXT,
                    font=("Segoe UI", 7, "bold"),
                    anchor="w",
                )

                test_lbl = tk.Label(
                    row,
                    text=" Test ",
                    bg=SACC,
                    fg=STEXT,
                    font=("Segoe UI", 7, "bold"),
                    cursor="hand2",
                    padx=2,
                    pady=1,
                )
                test_lbl.pack(side="right", padx=(4, 0))

                view_lbl = tk.Label(
                    row,
                    text=" 🔍 ",
                    bg=SED,
                    fg=STEXT,
                    font=("Segoe UI", 7, "bold"),
                    cursor="hand2",
                    padx=2,
                    pady=1,
                )
                view_lbl.pack(side="right", padx=4)

                chk_lbl = tk.Label(
                    row,
                    text="✦",
                    bg=SSURF,
                    fg=SACC if tgt.get("enabled", True) else SBORD,
                    font=("Segoe UI", 8),
                    cursor="hand2",
                    padx=2,
                )
                chk_lbl.pack(side="right", padx=6)

                def make_enabled_updater(lbl=chk_lbl, t=tgt):
                    def _toggle(e):
                        cur_val = t.get("enabled", True)
                        new_val = not cur_val
                        t["enabled"] = new_val
                        lbl.config(fg=SACC if new_val else SBORD)

                    lbl.bind("<Button-1>", _toggle)

                make_enabled_updater()

                action = tgt.get("action", "click")
                action_text = "Click ☑" if action == "click" else "Nothing ☒"
                action_bg = SACC if action == "click" else SMUTED

                action_lbl = tk.Label(
                    row,
                    text=f"  {action_text}  ",
                    bg=action_bg,
                    fg=STEXT,
                    font=("Segoe UI", 7, "bold"),
                    cursor="hand2",
                    padx=2,
                    pady=1,
                )
                action_lbl.pack(side="right", padx=6)

                def make_action_toggler(lbl=action_lbl, t=tgt):
                    def _toggle(e):
                        if t.get("action", "click") == "click":
                            t["action"] = "nothing"
                            lbl.config(text="  Nothing ☒  ", bg=SMUTED)
                        else:
                            t["action"] = "click"
                            lbl.config(text="  Click ☑  ", bg=SACC)

                    lbl.bind("<Button-1>", _toggle)

                make_action_toggler()

                pri_var = tk.StringVar(value=str(tgt.get("priority", 1)))
                pri_ent = tk.Entry(
                    row,
                    textvariable=pri_var,
                    bg=SED,
                    fg=STEXT,
                    font=("Segoe UI", 7),
                    insertbackground=STEXT,
                    width=3,
                    bd=0,
                    highlightthickness=0,
                    justify="center",
                )
                pri_ent.pack(side="right")

                def make_pri_updater(t=tgt, var=pri_var):
                    def _update(*_):
                        try:
                            t["priority"] = int(var.get())
                        except ValueError:
                            t["priority"] = 1

                    var.trace_add("write", _update)

                make_pri_updater()

                pri_lbl = tk.Label(
                    row, text="Pri:", bg=SSURF, fg=SMUTED, font=("Segoe UI", 7)
                )
                pri_lbl.pack(side="right", padx=(4, 2))

                name_lbl.pack(side="left", fill="x", expand=True)

                def make_viewer(t=tgt):
                    def _view(e):
                        self._view_image(t)

                    view_lbl.bind("<Button-1>", _view)

                make_viewer()

                def make_tester(t=tgt):
                    def _test(e):
                        sstat.config(
                            text=f"Testing match for {t.get('name')}...", fg=SMUTED
                        )

                        def _test_worker():
                            import cv2
                            import numpy as np

                            img_path = t.get("path")
                            if not img_path or not os.path.exists(img_path):
                                self.root.after(
                                    0,
                                    lambda: sstat.config(
                                        text="Image file not found on disk!", fg=SREC
                                    ),
                                )
                                return

                            template = cv2.imread(img_path, cv2.IMREAD_COLOR)
                            if template is None:
                                self.root.after(
                                    0,
                                    lambda: sstat.config(
                                        text="Failed to load image file!", fg=SREC
                                    ),
                                )
                                return

                            h, w = template.shape[:2]

                            start_time = time.perf_counter()
                            search_duration = 3.0
                            poll_interval = 0.150

                            best_val = -1.0
                            best_loc = None

                            while time.perf_counter() - start_time < search_duration:
                                try:
                                    screen = _grab_screen()
                                    screen_np = np.array(screen)
                                    screen_bgr = cv2.cvtColor(
                                        screen_np, cv2.COLOR_RGB2BGR
                                    )

                                    max_val, match_pt = self._find_best_match(
                                        screen_bgr, template
                                    )

                                    if max_val > best_val:
                                        best_val = max_val
                                        best_loc = match_pt

                                    if max_val >= 0.55:
                                        break
                                except Exception:
                                    pass
                                time.sleep(poll_interval)

                            duration = time.perf_counter() - start_time

                            # Safety threshold: Only teleport if confidence is high (>= 0.55) to prevent false positives
                            found = best_val >= 0.55

                            if found:
                                match_x, match_y = best_loc

                                pt = POINT()
                                user32.GetCursorPos(_ct.byref(pt))
                                orig_x, orig_y = pt.x, pt.y

                                action = t.get("action", "click")
                                if action == "click":
                                    # 3-Point Box/Triangle Click Pattern
                                    offsets = [
                                        (-5, -5),  # Top-Left
                                        (5, -5),  # Top-Right
                                        (0, 5),  # Bottom-Center
                                    ]
                                    for ox, oy in offsets:
                                        target_x = int(match_x + ox)
                                        target_y = int(match_y + oy)

                                        # 1. Hover — relative move, no teleport
                                        pt3 = POINT()
                                        user32.GetCursorPos(_ct.byref(pt3))
                                        dx3, dy3 = target_x - pt3.x, target_y - pt3.y
                                        if dx3 != 0 or dy3 != 0:
                                            _send_input(_mouse_move_rel(dx3, dy3))
                                        time.sleep(0.05)

                                        # 2. Press
                                        _send_input(
                                            _mouse_click(
                                                target_x, target_y, "left", False
                                            )
                                        )
                                        time.sleep(0.06)

                                        # 3. Release
                                        _send_input(
                                            _mouse_click(
                                                target_x, target_y, "left", True
                                            )
                                        )
                                        time.sleep(0.08)
                                else:
                                    # Just hover to matched center for 1.0 second (relative move, no teleport)
                                    pt = POINT()
                                    user32.GetCursorPos(_ct.byref(pt))
                                    dx, dy = int(match_x) - pt.x, int(match_y) - pt.y
                                    if dx != 0 or dy != 0:
                                        _send_input(_mouse_move_rel(dx, dy))
                                    time.sleep(1.0)

                                self.root.after(
                                    0,
                                    lambda: sstat.config(
                                        text=f"Found {t.get('name')} in {duration:.2f}s (Conf: {best_val:.2f})",
                                        fg=SPLAY,
                                    ),
                                )

                                url = self.cfg.webhook_url.strip()
                                if url:
                                    try:
                                        payload = {
                                            "username": "TinyKullan Image Detection Test",
                                            "embeds": [
                                                {
                                                    "title": "🎯 Image Detection Test: SUCCESS",
                                                    "color": 0x50C878,
                                                    "fields": [
                                                        {
                                                            "name": "Image Name",
                                                            "value": t.get(
                                                                "name", "Unknown"
                                                            ),
                                                            "inline": True,
                                                        },
                                                        {
                                                            "name": "Latency",
                                                            "value": f"{duration * 1000:.2f} ms",
                                                            "inline": True,
                                                        },
                                                        {
                                                            "name": "Confidence",
                                                            "value": f"{best_val:.4f}",
                                                            "inline": True,
                                                        },
                                                        {
                                                            "name": "Priority",
                                                            "value": str(
                                                                t.get("priority", 1)
                                                            ),
                                                            "inline": True,
                                                        },
                                                        {
                                                            "name": "Action Option",
                                                            "value": t.get(
                                                                "action", "click"
                                                            ),
                                                            "inline": True,
                                                        },
                                                        {
                                                            "name": "Coordinates",
                                                            "value": f"x: {match_x}, y: {match_y}",
                                                            "inline": True,
                                                        },
                                                    ],
                                                    "timestamp": datetime.now(
                                                        timezone.utc
                                                    ).strftime(
                                                        "%Y-%m-%dT%H:%M:%S.000Z"
                                                    ),
                                                }
                                            ],
                                        }
                                        _wh = DiscordWebhook(
                                            url=url,
                                            username="TinyKullan Image Detection Test",
                                        )
                                        _em = DiscordEmbed(
                                            title="\U0001f3af Image Detection Test: SUCCESS",
                                            color=0x50C878,
                                        )
                                        for _f in payload.get("embeds", [{}])[0].get(
                                            "fields", []
                                        ):
                                            _em.add_embed_field(
                                                name=_f["name"],
                                                value=_f["value"],
                                                inline=_f.get("inline", True),
                                            )
                                        _wh.add_embed(_em)
                                        _wh.execute()
                                    except Exception as wh_err:
                                        _LOG.warning(
                                            "Failed to send image detection test webhook: %s",
                                            wh_err,
                                        )

                                pt3 = POINT()
                                user32.GetCursorPos(_ct.byref(pt3))
                                dx3, dy3 = orig_x - pt3.x, orig_y - pt3.y
                                if dx3 != 0 or dy3 != 0:
                                    _send_input(_mouse_move_rel(dx3, dy3))
                            else:
                                self.root.after(
                                    0,
                                    lambda: sstat.config(
                                        text=f"Not found: {t.get('name')} (Best Conf: {best_val:.2f})",
                                        fg=SREC,
                                    ),
                                )

                        threading.Thread(target=_test_worker, daemon=True).start()

                    test_lbl.bind("<Button-1>", _test)

                make_tester()

                del_lbl = tk.Label(
                    row,
                    text=f" {self.cfg.ico_delete} ",
                    bg=SSURF,
                    fg=SREC,
                    font=("Segoe UI", 8),
                    cursor="hand2",
                )
                del_lbl.pack(side="right", padx=(2, 0))

                def make_deleter(t=tgt):
                    def _delete(e):
                        if t in self.temp_image_det_list:
                            self.temp_image_det_list.remove(t)
                        _render_image_list()

                    del_lbl.bind("<Button-1>", _delete)

                make_deleter()

        def _add_image():
            from tkinter import filedialog

            file_paths = filedialog.askopenfilenames(
                title="Select Target Images (multi-select)",
                filetypes=[
                    ("Image Files", "*.png *.jpg *.jpeg *.bmp"),
                    ("All Files", "*.*"),
                ],
            )
            if not file_paths:
                return

            import shutil

            try:
                IMAGES_PATH.mkdir(parents=True, exist_ok=True)
                for file_path in file_paths:
                    src_path = Path(file_path)
                    dest_path = IMAGES_PATH / src_path.name
                    shutil.copy2(src_path, dest_path)
                    get_cached_template.cache_clear()

                    new_tgt = {
                        "path": str(dest_path),
                        "name": src_path.name,
                        "priority": len(self.temp_image_det_list) + 1,
                        "action": "click",
                        "enabled": True,
                    }
                    self.temp_image_det_list.append(new_tgt)
                _render_image_list()
            except Exception as e:
                _LOG.error("Failed to add target images: %s", e)

        btn_container = tk.Frame(inn6, bg=SBG)
        btn_container.pack(fill="x", padx=PX, pady=10)

        upload_btn_f = tk.Frame(btn_container, bg=SACC, cursor="hand2")
        upload_btn_f.pack(side="left", expand=True, padx=4)
        upload_btn_lbl = tk.Label(
            upload_btn_f,
            text="  + Upload Target Image  ",
            bg=SACC,
            fg=STEXT,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
            pady=4,
        )
        upload_btn_lbl.pack(padx=2, pady=2)

        for w in (upload_btn_f, upload_btn_lbl):
            w.bind("<Button-1>", lambda _: _add_image())

        run_all_btn_f = tk.Frame(btn_container, bg=SACC, cursor="hand2")
        run_all_btn_f.pack(side="left", expand=True, padx=4)
        run_all_btn_lbl = tk.Label(
            run_all_btn_f,
            text="  ▶ Run All Images  ",
            bg=SACC,
            fg=STEXT,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
            pady=4,
        )
        run_all_btn_lbl.pack(padx=2, pady=2)

        for w in (run_all_btn_f, run_all_btn_lbl):
            w.bind("<Button-1>", lambda _: self.run_all_images())

        _render_image_list()

        tk.Frame(inn6, bg=SBG, height=12).pack()

        inn7 = sf7.inner
        _sec(inn7, "ROBLOX AUTO RECOVERY")
        _chk(inn7, "Enable Auto Recovery", "roblox_enabled")

        _lbl(inn7, "Disconnect Target Image (.png, .jpg, etc.)")
        roblox_img_f = tk.Frame(
            inn7, bg=SED, highlightbackground=SEDB, highlightthickness=1
        )
        roblox_img_f.pack(fill="x", padx=PX, pady=(2, 5))
        roblox_img_en = tk.Entry(
            roblox_img_f,
            bg=SED,
            fg=STEXT,
            relief="flat",
            bd=4,
            insertbackground=SACC,
            font=("Segoe UI", 8),
        )
        roblox_img_en.insert(0, self.cfg.roblox_disconnect_img)
        roblox_img_en.pack(side="left", fill="x", expand=True)

        roblox_img_btn = tk.Label(
            roblox_img_f,
            text=" \U0001f4c2 ",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        roblox_img_btn.pack(side="right")

        def _choose_roblox_img(e):
            file_path = _pick_file(
                title="Select Disconnect Target Image",
                filetypes=[
                    ("Image Files", "*.png *.jpg *.jpeg *.bmp"),
                    ("All Files", "*.*"),
                ],
            )
            if not file_path:
                return
            import shutil

            try:
                IMAGES_PATH.mkdir(parents=True, exist_ok=True)
                src_path = Path(file_path)
                dest_path = IMAGES_PATH / ("roblox_disconnect_" + src_path.name)
                shutil.copy2(src_path, dest_path)
                roblox_img_en.delete(0, "end")
                roblox_img_en.insert(0, str(dest_path))
                setattr(self.cfg, "roblox_disconnect_img", str(dest_path))
            except Exception as ex:
                _LOG.error("Failed to copy Roblox disconnect image: %s", ex)

        roblox_img_btn.bind("<Button-1>", _choose_roblox_img)

        _lbl(inn7, "Private Server URL / Link")
        roblox_link_f = tk.Frame(
            inn7, bg=SED, highlightbackground=SEDB, highlightthickness=1
        )
        roblox_link_f.pack(fill="x", padx=PX, pady=(2, 5))
        roblox_link_en = tk.Entry(
            roblox_link_f,
            bg=SED,
            fg=STEXT,
            relief="flat",
            bd=4,
            insertbackground=SACC,
            font=("Segoe UI", 8),
        )
        roblox_link_en.insert(0, self.cfg.roblox_server_link)
        roblox_link_en.pack(fill="x")

        roblox_test_btn = tk.Label(
            inn7,
            text="  Test Link  ",
            bg=_C["go"],
            fg=SBG,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
            padx=8,
            pady=4,
        )
        roblox_test_btn.pack(padx=PX, pady=(4, 2))

        def _test_open_link(e):
            link = roblox_link_en.get().strip()
            if not link:
                self.set_status("No link entered!", _C["rec"], 2000)
                return

            run_path = roblox_run_en.get().strip()
            wait_time = roblox_wait_var.get()

            def _test_recovery_worker():
                import re

                pm = re.search(r"/games/(\d+)", link)
                if pm:
                    deeplink = "roblox://placeId=" + pm.group(1)
                    cm = re.search(r"privateServerLinkCode=([^&]+)", link)
                    if cm:
                        deeplink += "&linkCode=" + cm.group(1)
                    try:
                        os.startfile(deeplink)
                        self.root.after(
                            0,
                            lambda: self.set_status(
                                "✓ PS opened, waiting...", _C["go"], 3000
                            ),
                        )
                    except Exception as ex:
                        _LOG.error("Deeplink failed: %s", ex)
                        self.root.after(
                            0,
                            lambda: self.set_status(
                                "✗ Failed to open", _C["rec"], 3000
                            ),
                        )
                        return
                else:
                    self.root.after(
                        0,
                        lambda: self.set_status(
                            "✗ Invalid server link", _C["rec"], 3000
                        ),
                    )
                    return

                # Wait for Roblox to load (interruptible via stop event)
                if wait_time > 0:
                    _LOG.info("Test: waiting %.1fs for Roblox to load...", wait_time)
                    for _ in range(int(wait_time * 10)):
                        if self._stop_ev.is_set():
                            return
                        time.sleep(0.1)

                # Run the recovery macro (disconnect run)
                if run_path and os.path.exists(run_path):
                    try:
                        with open(run_path, encoding="utf-8") as rf:
                            rec_data = json.load(rf)
                        if isinstance(rec_data, list):
                            rec_evs = [ev for ev in rec_data if _valid_ev(ev)]
                            speed = max(0.1, min(10.0, self.cfg.speed))
                            self.root.after(
                                0,
                                lambda: self.set_status(
                                    "⚙️ Running recovery macro...", _C["go"], 2000
                                ),
                            )
                            for ev in rec_evs:
                                if self._stop_ev.is_set():
                                    return
                                delay = max(ev.get("d", 0), 0) / 1000.0 / speed
                                if delay > 0:
                                    time.sleep(delay)
                                if self._stop_ev.is_set():
                                    return
                                self._replay(ev)
                            self.root.after(
                                0,
                                lambda: self.set_status(
                                    "✓ Recovery test complete", _C["go"], 3000
                                ),
                            )
                    except Exception as rec_err:
                        _LOG.error("Test recovery macro failed: %s", rec_err)
                        self.root.after(
                            0,
                            lambda: self.set_status(
                                "✗ Recovery macro failed", _C["rec"], 3000
                            ),
                        )
                else:
                    self.root.after(
                        0,
                        lambda: self.set_status(
                            "✓ Test complete (no recovery run)", _C["go"], 3000
                        ),
                    )

            threading.Thread(target=_test_recovery_worker, daemon=True).start()

        roblox_test_btn.bind("<Button-1>", _test_open_link)

        _lbl(inn7, "Event Vol (Custom recovery macro)")
        roblox_run_f = tk.Frame(
            inn7, bg=SED, highlightbackground=SEDB, highlightthickness=1
        )
        roblox_run_f.pack(fill="x", padx=PX, pady=(2, 5))
        roblox_run_en = tk.Entry(
            roblox_run_f,
            bg=SED,
            fg=STEXT,
            relief="flat",
            bd=4,
            insertbackground=SACC,
            font=("Segoe UI", 8),
        )
        roblox_run_en.insert(0, self.cfg.roblox_recovery_run)
        roblox_run_en.pack(side="left", fill="x", expand=True)

        roblox_run_btn = tk.Label(
            roblox_run_f,
            text=" \U0001f4c2 ",
            bg=SACC_D,
            fg=STEXT,
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        roblox_run_btn.pack(side="right")

        def _choose_roblox_run(e):
            RUNS_PATH.mkdir(parents=True, exist_ok=True)
            file_path = _pick_file(
                title="Select Custom Recovery Macro (Event Vol)",
                initial_dir=str(RUNS_PATH),
                filetypes=[
                    ("Macro Files", "*.txt"),
                    ("All Files", "*.*"),
                ],
            )
            if not file_path:
                return
            roblox_run_en.delete(0, "end")
            roblox_run_en.insert(0, file_path)
            setattr(self.cfg, "roblox_recovery_run", file_path)

        roblox_run_btn.bind("<Button-1>", _choose_roblox_run)

        def _upd_roblox_wait(v):
            setattr(self.cfg, "roblox_wait_time", float(v))
            roblox_wait_lbl.config(text=f"Recovery Delay: {float(v):.1f}s")

        roblox_wait_lbl = tk.Label(
            inn7,
            text=f"Recovery Delay: {self.cfg.roblox_wait_time:.1f}s",
            bg=SBG,
            fg=SMUTED,
            font=("Segoe UI", 7),
            anchor="w",
        )
        roblox_wait_lbl.pack(fill="x", padx=PX, pady=(2, 0))
        roblox_wait_var = tk.DoubleVar(value=self.cfg.roblox_wait_time)
        tk.Scale(
            inn7,
            from_=1.0,
            to=60.0,
            resolution=1.0,
            orient="horizontal",
            variable=roblox_wait_var,
            bg=SBG,
            fg=STEXT,
            troughcolor=SSURF,
            highlightthickness=0,
            length=200,
            command=_upd_roblox_wait,
        ).pack(fill="x", padx=PX, pady=5)

        tk.Frame(inn7, bg=SBG, height=12).pack()

        def _save_all():
            setattr(self.cfg, "roblox_disconnect_img", roblox_img_en.get())
            setattr(self.cfg, "roblox_server_link", roblox_link_en.get())
            setattr(self.cfg, "roblox_recovery_run", roblox_run_en.get())
            for a, e in path_entries.items():
                setattr(self.cfg, a, e.get())
            for a, e in ico_entries.items():
                val = e.get().strip()
                if val:
                    setattr(self.cfg, a, val)
            self._register_hotkeys()
            self.cfg.save()
            self.image_det_list = [dict(x) for x in self.temp_image_det_list]
            self.save_image_detection()
            self.apply_theme()
            self._apply_tiny()
            self._apply_icons()
            _set_alpha(self._hwnd, self._get_alpha())
            snap.clear()
            snap.update({k: getattr(self.cfg, k) for k in self.cfg.DEFAULTS})
            snap["theme"] = dict(self.cfg.theme)
            sstat.config(text="\u2713 saved", fg=SPLAY)
            win.after(2000, lambda: sstat.config(text="", fg=SMUTED))

        for w in (sbf, sbl):
            w.bind("<Button-1>", lambda _: _save_all())

        sf1.outer.lift()
        win.update_idletasks()
        if win.winfo_id():
            _round_hwnd(_get_hwnd(win.winfo_id()))

    def _test_webhook(self, url, slbl):
        if not url.strip():
            slbl.config(text="no url", fg=SREC)
            return
        slbl.config(text="sending…", fg=SMUTED)

        def _do():
            try:
                payload = {
                    "username": "TinyKullan",
                    "embeds": [
                        {
                            "title": "Test",
                            "color": 0x9D7CFF,
                            "description": "Connection confirmed!",
                        }
                    ],
                }
                wh = DiscordWebhook(url=url.strip(), username="TinyKullan")
                em = DiscordEmbed(
                    title="Test", color=0x9D7CFF, description="Connection confirmed!"
                )
                wh.add_embed(em)
                resp = wh.execute()
                msg = (
                    ("sent", SPLAY)
                    if resp.status_code in (200, 204)
                    else (f"{resp.status_code}", SREC)
                )
            except Exception:
                msg = ("error", SREC)
            self.root.after(0, lambda: slbl.config(text=msg[0], fg=msg[1]))

        threading.Thread(target=_do, daemon=True).start()


_VK_MAP = {
    **{f"f{i}": 0x6F + i for i in range(1, 25)},
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "win": 0x5B,
    "tab": 0x09,
    "caps lock": 0x14,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "enter": 0x0D,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "page up": 0x21,
    "page down": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "num lock": 0x90,
    "scroll lock": 0x91,
    "print screen": 0x2C,
    "pause": 0x13,
    "lcontrol": 0xA2,
    "rcontrol": 0xA3,
    "lshift": 0xA0,
    "rshift": 0xA1,
    "lalt": 0xA4,
    "ralt": 0xA5,
    "lwin": 0x5B,
    "rwin": 0x5C,
}
for _c in range(ord("a"), ord("z") + 1):
    _VK_MAP[chr(_c)] = _c - 32
for _c in range(10):
    _VK_MAP[str(_c)] = 0x30 + _c


def _name_to_vk(name):
    return _VK_MAP.get(name.lower().strip())


def _splash(root):
    root.overrideredirect(True)
    root.configure(bg="#1D1128")
    root.attributes("-topmost", True)
    W, H = 200, 68
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
    tk.Frame(root, bg="#4A306D", height=2).pack(fill="x", side="top")
    tk.Label(
        root,
        text="  TinyKullan",
        bg="#1D1128",
        fg="#C3A5E5",
        font=("Segoe UI", 12, "bold"),
    ).pack(pady=(12, 4))
    tk.Label(
        root, text="Starting up…", bg="#1D1128", fg="#4A306D", font=("Segoe UI", 7)
    ).pack()
    tk.Frame(root, bg="#4A306D", height=2).pack(fill="x", side="bottom")
    root.deiconify()
    root.update_idletasks()
    try:
        if root.winfo_id():
            h = _get_hwnd(root.winfo_id())
            _round_hwnd(h)
            s = _ct.windll.user32.GetWindowLongW(h, -20)
            _ct.windll.user32.SetWindowLongW(h, -20, s | 0x80000)
            _ct.windll.user32.SetLayeredWindowAttributes(h, 0, 230, 0x02)
    except Exception:
        pass

    # Let the splash show, then clear widgets and reset window geometry/attributes
    root.after(1200, lambda: _finish_splash(root))
    root.mainloop()


def _finish_splash(root):
    for widget in root.winfo_children():
        widget.destroy()
    root.withdraw()
    root.quit()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            _ct.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                _ct.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    root = tk.Tk()
    root.withdraw()
    _splash(root)
    App(root)
