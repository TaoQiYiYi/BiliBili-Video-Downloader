"""B站视频下载器 —— 樱粉主题 tkinter 窗口 + yt-dlp 下载引擎。"""

import ctypes
import json
import os
import queue
import re
import shutil
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import yt_dlp

try:
    import winreg
except ImportError:  # 非 Windows 系统
    winreg = None

# ---------------- 主题 ----------------
THEMES = {
    "主题1 冰蓝粉": {
        "c1": "#9BE9FF", "c2": "#FFACD2", "c3": "#5B85D2", "c4": "#2C4271",
    },
    "主题2 暖阳青": {
        "c1": "#FFEAB0", "c2": "#FF9FA9", "c3": "#1CB8AB", "c4": "#034B6F",
    },
    "主题3 落霞蓝": {
        "c1": "#FF8E8E", "c2": "#FFBC79", "c3": "#2D616A", "c4": "#00294B",
    },
}
DEFAULT_THEME = "主题1 冰蓝粉"

VERSION = "1.0.1"


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return [int(color[i:i + 2], 16) for i in (0, 2, 4)]


def _rgb_to_hex(rgb):
    return "#%02X%02X%02X" % tuple(
        max(0, min(255, int(round(c)))) for c in rgb)


def _blend_hex(a, b, t):
    ca, cb = _hex_to_rgb(a), _hex_to_rgb(b)
    return _rgb_to_hex([ca[i] + (cb[i] - ca[i]) * t for i in range(3)])


def _gradient_color(colors, pos):
    """取四色渐变在 pos(0~1) 处的颜色。"""
    pos = max(0.0, min(1.0, pos))
    seg = pos * (len(colors) - 1)
    i = min(int(seg), len(colors) - 2)
    return _blend_hex(colors[i], colors[i + 1], seg - i)


def build_palette(theme):
    c1, c2, c3, c4 = theme["c1"], theme["c2"], theme["c3"], theme["c4"]
    return {
        "c1": c1, "c2": c2, "c3": c3, "c4": c4,
        "gradient": [c1, c2, c3, c4],
        "text": c4,
        "text_soft": _blend_hex(c4, "#FFFFFF", 0.38),
        "button": c3,
        "button_text": "#FFFFFF",
        "button_active": _blend_hex(c3, c4, 0.30),
        "button_border": _blend_hex(c3, c4, 0.45),
        "entry": _blend_hex(c1, "#FFFFFF", 0.60),
        "entry_border": _blend_hex(c3, c4, 0.35),
        "card": _blend_hex(c1, c2, 0.40),
        "card_border": _blend_hex(c3, c4, 0.55),
        "progress_fill": c3,
        "progress_track": _blend_hex(c1, "#FFFFFF", 0.55),
        "check": _blend_hex(c2, "#FFFFFF", 0.45),
        "arrow": _blend_hex(c3, c4, 0.10),
        "select": c2,
    }


def _set_dpi_awareness():
    """让窗口在 HiDPI 屏幕上保持清晰。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _find_ffmpeg():
    """按优先级检查：exe/脚本同目录 → 剪映自带 → 常见安装位置 → PATH。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "ffmpeg.exe"),
        r"D:\剪映专业版\JianyingPro\11.1.0.14287\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]
    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    return shutil.which("ffmpeg")


def _default_download_dir():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "downloads")


def _resource_path(name):
    """exe 打包后从临时解包目录取资源，源码运行时从脚本目录取。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


CONFIG_FILE = "config.json"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "B站视频下载器"


def _config_path():
    """配置文件放在用户主目录下的 B站视频下载器 文件夹。"""
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, "B站视频下载器", CONFIG_FILE)


def _old_config_path():
    """旧版本配置路径（程序/exe 同目录），用于自动迁移。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, CONFIG_FILE)


def load_config():
    cfg = {}
    path = _config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass
    # 旧位置（程序/exe 同目录）有配置时自动迁移到新位置
    old = _old_config_path()
    if not os.path.isfile(path) and os.path.isfile(old):
        try:
            shutil.copyfile(old, path)
        except OSError:
            pass
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            cfg = data
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass
    return cfg


def save_config(cfg):
    try:
        path = _config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def _autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable
    return f'"{pythonw}" "{os.path.abspath(__file__)}"'


def set_autostart(enabled):
    """写入/删除 HKCU 启动项（Run 键），无需管理员权限。"""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ,
                                  _autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def is_autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_REG_NAME)
            return True
    except (FileNotFoundError, OSError):
        return False


class BilibiliDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("桃汽依依制作 - B站视频下载器")
        self.geometry("500x500")
        self.resizable(False, False)
        try:
            self.iconbitmap(_resource_path("app.ico"))
        except tk.TclError:
            pass

        self.msg_queue = queue.Queue()
        self.busy = False
        self.ffmpeg = _find_ffmpeg()
        self.format_options = []          # [(显示名, yt-dlp format 选择器)]
        self.quality_avc = {}             # {显示名: 该画质是否存在 H.264}

        self.config = load_config()
        self.default_quality = self.config.get("default_quality") or "自动"
        self.theme_key = self.config.get("theme") or DEFAULT_THEME
        if self.theme_key not in THEMES:
            self.theme_key = DEFAULT_THEME
        self.palette = build_palette(THEMES[self.theme_key])
        self._theme_widgets = []
        self._acrylic_backdrop_set = False
        self.configure(bg=self.palette["c4"])

        self.url_var = tk.StringVar()
        self.save_dir_var = tk.StringVar(
            value=self.config.get("save_dir") or _default_download_dir())
        self.quality_var = tk.StringVar()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._poll_queue()
        self._log(f"版本号：{VERSION}")
        self.after(150, self._redraw_gradient)
        # 毛玻璃必须在窗口首次显示前启用，否则内容会被合成成白屏
        self._apply_acrylic()
        self._window_ready = True

    # ---------------- UI ----------------
    def _font(self, size, bold=False):
        return ("Microsoft YaHei UI", size, "bold" if bold else "normal")

    def _btn(self, parent, text, command, width=None):
        p = self.palette
        btn = tk.Button(
            parent, text=text, command=command,
            bg=p["button"], activebackground=p["button_active"],
            fg=p["button_text"], activeforeground=p["button_text"],
            relief="flat", bd=0, highlightthickness=0,
            font=self._font(10, True), cursor="hand2",
            padx=8, pady=3,
        )
        if width:
            btn.config(width=width)
        self._track_widget(btn, "button")
        return btn

    def _track_widget(self, widget, kind, pos=0.5):
        self._theme_widgets.append((widget, kind, pos))

    def _build_ui(self):
        f = self._font
        p = self.palette

        # 背景渐变画布（毛玻璃内容层，位于所有控件之下）
        self.bg_canvas = tk.Canvas(self, width=500, height=500,
                                   highlightthickness=0, bd=0)
        self.bg_canvas.grid(row=0, column=0, rowspan=10, columnspan=3,
                            sticky="nsew")
        self._redraw_gradient()

        # 标题
        title = tk.Label(self, text="🌸 桃汽依依制作 - B站视频下载器",
                         font=f(15, True))
        title.grid(row=0, column=0, columnspan=3, pady=(10, 4))
        self._track_widget(title, "label", 0.05)

        # 链接输入行
        self.url_entry = tk.Entry(self, textvariable=self.url_var,
                                  relief="flat", font=f(10))
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky="ew",
                            padx=(12, 4))
        self._track_widget(self.url_entry, "entry", 0.18)
        paste_btn = self._btn(self, "粘贴", self.paste_url, 5)
        paste_btn.grid(row=1, column=2, sticky="ew", padx=(0, 12))

        # 解析按钮
        self.parse_btn = self._btn(self, "解析视频", self.fetch_info)
        self.parse_btn.grid(row=2, column=0, columnspan=3, sticky="ew",
                            padx=12, pady=(6, 2))

        # 视频信息卡片
        card = tk.Frame(self, highlightbackground=p["card_border"],
                        highlightthickness=1)
        card.grid(row=3, column=0, columnspan=3, sticky="ew",
                  padx=12, pady=4)
        self._track_widget(card, "card_frame", 0.38)
        self.info_label = tk.Label(
            card, text="输入 B 站视频链接或 BV 号后点击「解析视频」",
            font=f(10, True), anchor="w", justify="left", wraplength=430)
        self.info_label.pack(fill="x", padx=8, pady=(6, 0))
        self._track_widget(self.info_label, "card_label", 0.38)
        self.meta_label = tk.Label(
            card, text="", font=f(9),
            anchor="w", justify="left", wraplength=430)
        self.meta_label.pack(fill="x", padx=8, pady=(0, 6))
        self._track_widget(self.meta_label, "card_meta", 0.38)

        # 画质选择行
        qrow = tk.Frame(self)
        qrow.grid(row=4, column=0, columnspan=3, sticky="ew",
                  padx=12, pady=2)
        self._track_widget(qrow, "frame", 0.52)
        q_label = tk.Label(qrow, text="画质：", font=f(10))
        q_label.pack(side="left")
        self._track_widget(q_label, "label", 0.52)
        self.quality_box = ttk.Combobox(
            qrow, textvariable=self.quality_var, state="readonly",
            style="Pink.TCombobox", font=f(10))
        self.quality_box.pack(side="left", fill="x", expand=True)
        self._track_widget(self.quality_box, "combobox", 0.52)

        # 保存目录行
        srow = tk.Frame(self)
        srow.grid(row=5, column=0, columnspan=3, sticky="ew",
                  padx=12, pady=2)
        self._track_widget(srow, "frame", 0.60)
        s_label = tk.Label(srow, text="保存：", font=f(10))
        s_label.pack(side="left")
        self._track_widget(s_label, "label", 0.60)
        self.dir_entry = tk.Entry(srow, textvariable=self.save_dir_var,
                                  relief="flat", font=f(9))
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._track_widget(self.dir_entry, "entry", 0.60)
        browse_btn = self._btn(srow, "选择", self.choose_dir, 5)
        browse_btn.pack(side="right")
        settings_btn = self._btn(srow, "设置", self.open_settings, 5)
        settings_btn.pack(side="right", padx=(4, 0))

        # 下载按钮
        self.download_btn = self._btn(self, "开始下载", self.start_download)
        self.download_btn.grid(row=6, column=0, columnspan=3, sticky="ew",
                               padx=12, pady=(6, 2))

        # 进度
        self.progress_label = tk.Label(self, text="", font=f(9))
        self.progress_label.grid(row=7, column=0, columnspan=3,
                                 sticky="ew", padx=12, pady=(2, 0))
        self._track_widget(self.progress_label, "label", 0.76)
        self.progress_canvas = tk.Canvas(
            self, height=14, highlightthickness=1, bd=0)
        self.progress_canvas.grid(row=8, column=0, columnspan=3,
                                  sticky="ew", padx=12, pady=(2, 2))
        self._track_widget(self.progress_canvas, "progress_track", 0.82)
        self._bar = self.progress_canvas.create_rectangle(
            0, 0, 0, 14, fill=p["progress_fill"], width=0)
        self._track_widget(self._bar, "progress_bar", 0.82)

        # 日志
        logframe = tk.Frame(self)
        logframe.grid(row=9, column=0, columnspan=3, sticky="nsew",
                      padx=12, pady=(2, 8))
        self._track_widget(logframe, "frame", 0.92)
        self.log = tk.Text(logframe, height=5, relief="flat",
                           font=f(9), wrap="word",
                           state="disabled")
        sb = ttk.Scrollbar(logframe, command=self.log.yview,
                           style="Pink.Vertical.TScrollbar")
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self._track_widget(self.log, "log", 0.92)

        self.columnconfigure(0, weight=1)

        # 应用当前主题（ttk 样式、下拉列表、滚动条等）
        self.apply_theme(self.theme_key)

        if not self.ffmpeg:
            self._log("提示：未检测到 ffmpeg，仅提供免合并画质；"
                      "安装 ffmpeg 后可下载 1080P 及以上。")

    # ---------------- 主题 ----------------
    def _redraw_gradient(self):
        canvas = self.bg_canvas
        canvas.delete("grad")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 50:
            w = 500
        if h < 50:
            h = 500
        colors = self.palette["gradient"]
        for y in range(h):
            canvas.create_line(
                0, y, w, y,
                fill=_gradient_color(colors, y / max(h - 1, 1)),
                tags="grad")
        canvas.tag_lower("grad")

    def _apply_widget_theme(self, widget, kind, pos):
        p = self.palette
        bg = _gradient_color(p["gradient"], pos)
        if kind == "label":
            widget.config(bg=bg, fg=p["text"])
        elif kind == "frame":
            widget.config(bg=bg)
        elif kind == "card_frame":
            widget.config(bg=p["card"], highlightbackground=p["card_border"])
        elif kind == "card_label":
            widget.config(bg=p["card"], fg=p["text"])
        elif kind == "card_meta":
            widget.config(bg=p["card"], fg=p["text_soft"])
        elif kind == "entry":
            widget.config(bg=p["entry"], fg=p["text"],
                          insertbackground=p["text"],
                          highlightthickness=1,
                          highlightbackground=p["entry_border"],
                          highlightcolor=p["entry_border"])
        elif kind == "button":
            widget.config(bg=p["button"], fg=p["button_text"],
                          activebackground=p["button_active"],
                          activeforeground=p["button_text"],
                          highlightthickness=1,
                          highlightbackground=p["button_border"],
                          highlightcolor=p["button_border"])
        elif kind == "combobox":
            pass  # ttk 样式在 apply_theme 中统一更新
        elif kind == "progress_track":
            widget.config(bg=p["progress_track"],
                          highlightbackground=p["entry_border"])
        elif kind == "progress_bar":
            self.progress_canvas.itemconfig(widget, fill=p["progress_fill"])
        elif kind == "log":
            widget.config(bg=p["entry"], fg=p["text"],
                          highlightthickness=1,
                          highlightbackground=p["entry_border"],
                          highlightcolor=p["entry_border"])

    def apply_theme(self, key):
        if key not in THEMES:
            key = DEFAULT_THEME
        self.theme_key = key
        self.palette = build_palette(THEMES[key])
        self.configure(bg=self.palette["c4"])
        self._redraw_gradient()
        for widget, kind, pos in self._theme_widgets:
            try:
                self._apply_widget_theme(widget, kind, pos)
            except tk.TclError:
                pass
        p = self.palette
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Pink.TCombobox",
            fieldbackground=p["entry"], background=p["entry"],
            foreground=p["text"], arrowcolor=p["arrow"],
            bordercolor=p["entry_border"], lightcolor=p["entry_border"],
            darkcolor=p["entry_border"],
            selectbackground=p["select"], selectforeground=p["text"])
        style.configure(
            "Pink.Vertical.TScrollbar",
            background=p["button"], troughcolor=p["progress_track"],
            bordercolor=p["card_border"], arrowcolor=p["text"],
            lightcolor=p["button"], darkcolor=p["button"])
        self.option_clear()
        self.option_add("*TCombobox*Listbox.background", p["entry"])
        self.option_add("*TCombobox*Listbox.foreground", p["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", p["select"])
        self.option_add("*TCombobox*Listbox.selectForeground", p["text"])
        if getattr(self, "_window_ready", False):
            self._apply_acrylic_border()
        self.config["theme"] = key
        save_config(self.config)

    def _apply_acrylic(self):
        """完整启用 Windows 毛玻璃（仅在启动时调用，须在窗口显示前）。"""
        if os.environ.get("BILI_DISABLE_ACRYLIC"):
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            # Windows 11：系统丙烯酸背景（含标题栏与边框），
            # 只在首次启用，避免运行时重复设置破坏合成
            if not self._acrylic_backdrop_set:
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 38, ctypes.byref(ctypes.c_int(3)), 4)
                    self._acrylic_backdrop_set = True
                except Exception:
                    pass
            self._apply_acrylic_border()
        except Exception:
            pass

    def _apply_acrylic_border(self):
        """更新边框与标题栏文字颜色（跟随主题，可随时调用）。"""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            border = int(self.palette["card_border"].lstrip("#"), 16)
            text = int(self.palette["text"].lstrip("#"), 16)
            for attr, value in ((34, border), (36, text)):
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(ctypes.c_uint(value)), 4)
                except Exception:
                    pass
        except Exception:
            pass

    # ---------------- 通用 ----------------
    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_progress(self, pct):
        width = self.progress_canvas.winfo_width()
        if width < 2:
            width = 460
        self.progress_canvas.coords(
            self._bar, 0, 0, width * max(0, min(pct, 100)) / 100, 14)

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.parse_btn.config(state=state)
        self.download_btn.config(state=state)

    def paste_url(self):
        try:
            self.url_var.set(self.clipboard_get().strip())
        except tk.TclError:
            pass

    def choose_dir(self):
        path = filedialog.askdirectory(initialdir=self.save_dir_var.get())
        if path:
            self.save_dir_var.set(path)

    # ---------------- 设置 ----------------
    def _save_settings(self):
        self.config.pop("cookie_enabled", None)
        self.config.pop("browser", None)
        self.config.update({
            "save_dir": self.save_dir_var.get().strip(),
            "default_quality": self.default_quality,
            "theme": self.theme_key,
            "auto_start": is_autostart_enabled(),
        })
        save_config(self.config)

    def on_close(self):
        self._save_settings()
        self.destroy()

    def open_settings(self):
        SettingsDialog(self)

    # ---------------- 解析 ----------------
    @staticmethod
    def _normalize_url(text):
        """支持直接输入 BV 号 / av 号，自动补全为完整链接。"""
        text = (text or "").strip()
        if re.fullmatch(r"BV[0-9A-Za-z]{8,}", text, re.IGNORECASE):
            return f"https://www.bilibili.com/video/{text}"
        if re.fullmatch(r"av\d+", text, re.IGNORECASE):
            return f"https://www.bilibili.com/video/{text.lower()}"
        return text

    def fetch_info(self):
        url = self._normalize_url(self.url_var.get())
        if not url:
            messagebox.showwarning("提示", "请输入 B 站视频链接或 BV 号")
            return
        if self.busy:
            return
        self.url_var.set(url)
        self.set_busy(True)
        self.info_label.config(text="正在解析…")
        self.meta_label.config(text="")
        self.quality_box.set("")
        threading.Thread(
            target=self._fetch_worker,
            args=(url,),
            daemon=True).start()

    def _fetch_worker(self, url):
        base_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": False,
            "socket_timeout": 60,
            "retries": 5,
        }
        try:
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            self.msg_queue.put(("info", info))
        except Exception as exc:
            self.msg_queue.put(("error", f"解析失败：{exc}"))

    @staticmethod
    def _fmt_duration(sec):
        if not sec:
            return "时长未知"
        sec = int(sec)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def _build_quality_options(self, entries):
        heights, combined, has_audio = set(), set(), False
        avc_heights = set()
        for entry in entries:
            for fmt in entry.get("formats") or []:
                vcodec = fmt.get("vcodec", "none")
                acodec = fmt.get("acodec", "none")
                height = fmt.get("height")
                if height:
                    heights.add(height)
                    if vcodec != "none" and acodec != "none":
                        combined.add(height)
                    if vcodec.startswith("avc1") or vcodec.startswith("h264"):
                        avc_heights.add(height)
                if vcodec == "none" and acodec != "none":
                    has_audio = True

        max_h = max(heights) if heights else 0
        options = []
        avc_map = {}
        avc_any = bool(avc_heights)
        if self.ffmpeg:
            auto_label = f"自动（最高 {max_h}P）"
            options.append((
                auto_label,
                "bv*[vcodec^=avc1]+ba/b[ext=mp4]/bv*+ba/b"))
            avc_map[auto_label] = avc_any
        else:
            auto_label = "自动（免合并画质）"
            options.append((auto_label, "b[ext=mp4]/b"))
            avc_map[auto_label] = avc_any
        for h in sorted(heights, reverse=True):
            if self.ffmpeg or h in combined:
                label = f"{h}P"
                if self.ffmpeg:
                    # 优先 H.264，没有时才回退到 HEVC/AV1
                    selector = (
                        f"bv*[height<={h}][vcodec^=avc1]+ba"
                        f"/b[height<={h}][vcodec^=avc1]"
                        f"/bv*[height<={h}]+ba/b[height<={h}]")
                else:
                    selector = (
                        f"b[height<={h}][vcodec^=avc1]"
                        f"/b[height<={h}]/b")
                options.append((label, selector))
                avc_map[label] = h in avc_heights
        if has_audio:
            label = "仅音频"
            options.append((label, "ba"))
            avc_map[label] = True
        self.quality_avc = avc_map
        return options

    def _show_info(self, info):
        if "entries" in info:
            entries = [e for e in info.get("entries") or [] if e]
            title = info.get("title") or "多 P 视频"
            part = f" · 共 {len(entries)} P"
        else:
            entries = [info]
            title = info.get("title") or "未知标题"
            part = ""

        if not entries:
            self.info_label.config(text="未能获取到视频信息")
            return

        options = self._build_quality_options(entries)
        self.format_options = options
        labels = [name for name, _ in options]
        self.quality_box.config(values=labels)
        self.quality_var.set(
            self.default_quality if self.default_quality in labels
            else labels[0])

        author = entries[0].get("uploader") or "未知作者"
        duration = self._fmt_duration(entries[0].get("duration"))
        max_h = max((f.get("height") or 0) for f in entries[0].get("formats") or [])
        quality = f"最高 {max_h}P" if max_h else "画质未知"
        short_title = title if len(title) <= 64 else title[:64] + "…"

        self.info_label.config(text=short_title)
        self.meta_label.config(
            text=f"{author} · {duration} · {quality}{part}")
        self._log(f"解析成功：{title}")

    # ---------------- 下载 ----------------
    def start_download(self):
        url = self._normalize_url(self.url_var.get())
        if not url:
            messagebox.showwarning("提示", "请输入 B 站视频链接或 BV 号")
            return
        if not self.format_options:
            messagebox.showwarning("提示", "请先解析视频")
            return
        if self.busy:
            return

        label = self.quality_var.get() or self.format_options[0][0]
        selector = dict(self.format_options).get(label,
                                                 self.format_options[0][1])
        if not self.quality_avc.get(label, True):
            self._log("注意：该画质没有 H.264 编码（B 站可能只有 HEVC/AV1），"
                      "Windows 媒体播放器可能无法播放，建议用 VLC/PotPlayer"
                      "或安装 HEVC 解码器。")
        save_dir = self.save_dir_var.get().strip() or "downloads"
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("错误", f"无法创建保存目录：{exc}")
            return

        ffmpeg = self.ffmpeg
        self._save_settings()

        self.set_busy(True)
        self._set_progress(0)
        self.progress_label.config(text="")
        self._log(f"开始下载：{label} → {save_dir}")
        threading.Thread(
            target=self._download_worker,
            args=(url, selector, save_dir, ffmpeg),
            daemon=True).start()

    def _download_worker(self, url, selector, save_dir, ffmpeg):
        base_opts = {
            "outtmpl": os.path.join(
                save_dir, "%(title)s [%(id)s].%(ext)s"),
            "format": selector,
            "socket_timeout": 60,
            "retries": 10,
            "fragment_retries": 15,
            "retry_sleep_functions": {
                "http": lambda n: min(2 * n, 20),
                "fragment": lambda n: min(3 * n, 30),
            },
            "merge_output_format": "mp4",
            "remuxvideo": "mp4",
            "postprocessor_args": {
                "merger": ["-movflags", "+faststart"],
                "videoremuxer": ["-movflags", "+faststart"],
            },
            "noplaylist": False,
            "quiet": True,
            "no_warnings": True,
            "concurrent_fragment_downloads": 4,
            "progress_hooks": [self._progress_hook],
        }
        if ffmpeg:
            base_opts["ffmpeg_location"] = ffmpeg
        if selector == "ba" and ffmpeg:
            base_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        max_attempts = 3
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                # 每次重试都会重新解析，拿到全新的 CDN 链接，
                # 可避开偶发超时的慢节点
                with yt_dlp.YoutubeDL(base_opts) as ydl:
                    ydl.download([url])
                self.msg_queue.put(("done", save_dir))
                return
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    self.msg_queue.put((
                        "progress",
                        {"status": "retrying", "attempt": attempt,
                         "message": str(exc)},
                    ))
                    time.sleep(4)
        self.msg_queue.put((
            "error",
            f"下载失败（已自动重试 {max_attempts - 1} 次）：{last_error}"))

    def _progress_hook(self, data):
        self.msg_queue.put(("progress", data))

    # ---------------- 队列轮询 ----------------
    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "info":
                    self._show_info(payload)
                    self.set_busy(False)
                elif kind == "error":
                    self.set_busy(False)
                    self.progress_label.config(text="")
                    self._log(payload)
                    messagebox.showerror("出错了", payload)
                elif kind == "progress":
                    self._handle_progress(payload)
                elif kind == "done":
                    self.set_busy(False)
                    self._set_progress(100)
                    self.progress_label.config(text="下载完成")
                    self._log(f"下载完成，文件保存在：{payload}")
                    messagebox.showinfo(
                        "完成", f"下载完成！\n保存位置：{payload}")
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _handle_progress(self, data):
        status = data.get("status")
        if status == "downloading":
            total = (data.get("total_bytes")
                     or data.get("total_bytes_estimate") or 0)
            downloaded = data.get("downloaded_bytes") or 0
            pct = downloaded / total * 100 if total else 0
            self._set_progress(pct)
            speed = data.get("_speed_str") or ""
            eta = data.get("_eta_str") or ""
            self.progress_label.config(
                text=f"下载中 {pct:.1f}% · {speed}"
                     + (f" · 剩余 {eta}" if eta else ""))
        elif status == "finished":
            self._set_progress(100)
            self.progress_label.config(text="下载完成，正在合并/转换…")
        elif status == "retrying":
            self.progress_label.config(
                text=f"下载出错（第 {data.get('attempt', 1)} 次），"
                     f"4 秒后自动换源重试…")
            self._log(f"下载出错：{data.get('message', '')}")


class SettingsDialog(tk.Toplevel):
    QUALITY_CHOICES = ["自动", "1080P", "720P", "480P", "360P", "仅音频"]

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("设置")
        self.geometry("400x330")
        self.resizable(False, False)
        self.configure(bg=_gradient_color(app.palette["gradient"], 0.5))
        self.transient(app)
        self.grab_set()

        f = app._font
        p = app.palette
        self._d_widgets = []

        def drow():
            row = tk.Frame(self)
            row.pack(fill="x", padx=16, pady=6)
            self._d_widgets.append(row)
            return row

        def dlabel(parent, text, size=10):
            lb = tk.Label(parent, text=text, font=f(size))
            lb.pack(side="left")
            self._d_widgets.append(lb)
            return lb

        # 更换主题
        row0 = drow()
        dlabel(row0, "更换主题：")
        self.theme_var = tk.StringVar(value=app.theme_key)
        self.theme_box = ttk.Combobox(
            row0, textvariable=self.theme_var, values=list(THEMES),
            state="readonly", style="Pink.TCombobox",
            font=f(9), width=20)
        self.theme_box.pack(side="left", fill="x", expand=True)
        self.theme_box.bind("<<ComboboxSelected>>", self._on_theme_change)

        # 默认画质
        row1 = drow()
        dlabel(row1, "默认画质：")
        self.quality_var = tk.StringVar(value=app.default_quality)
        ttk.Combobox(
            row1, textvariable=self.quality_var,
            values=self.QUALITY_CHOICES, state="readonly",
            style="Pink.TCombobox", font=f(10),
            width=24).pack(side="left", fill="x", expand=True)

        # 开机自启动
        row2 = drow()
        self.auto_var = tk.BooleanVar(value=is_autostart_enabled())
        self.auto_check = tk.Checkbutton(
            row2, text="开机自启动（登录 Windows 后自动运行）",
            variable=self.auto_var, font=f(9), bd=0, highlightthickness=0)
        self.auto_check.pack(side="left")
        self._d_widgets.append(self.auto_check)

        # 保存目录提示
        self.hint_label = tk.Label(
            self, text="保存目录在主窗口设置，默认画质在此设置，\n"
                       "都会在下载或退出时自动保存。",
            font=f(9), justify="left",
            anchor="w", wraplength=360, padx=10, pady=8,
            highlightthickness=1)
        self.hint_label.pack(fill="x", padx=16, pady=10)
        self._d_widgets.append(self.hint_label)

        # 按钮
        btns = tk.Frame(self)
        btns.pack(fill="x", padx=16, pady=(4, 14))
        self._d_widgets.append(btns)
        save_btn = app._btn(btns, "保存", self._on_save)
        cancel_btn = app._btn(btns, "取消", self.destroy)
        save_btn.pack(side="right", padx=(6, 0))
        cancel_btn.pack(side="right")

        self._theme_self()

    def _theme_self(self):
        p = self.app.palette
        bg = _gradient_color(p["gradient"], 0.5)
        self.configure(bg=bg)
        for w in self._d_widgets:
            try:
                if isinstance(w, tk.Checkbutton):
                    w.config(bg=bg, activebackground=bg,
                             fg=p["text"], activeforeground=p["text"],
                             selectcolor=p["check"])
                elif isinstance(w, tk.Label):
                    w.config(bg=bg, fg=p["text"])
                elif isinstance(w, tk.Frame):
                    w.config(bg=bg)
            except tk.TclError:
                pass
        self.hint_label.config(bg=p["card"], fg=p["text"],
                               highlightbackground=p["card_border"])

    def _on_theme_change(self, event=None):
        self.app.apply_theme(self.theme_var.get())
        self._theme_self()

    def _on_save(self):
        quality = self.quality_var.get()
        auto = self.auto_var.get()
        self.app.default_quality = quality
        self.app.config["default_quality"] = quality
        self.app.config["theme"] = self.app.theme_key
        ok = set_autostart(auto)
        self.app._save_settings()
        if not ok:
            messagebox.showwarning(
                "提示", "开机自启动设置失败，可能没有写入权限")
        else:
            self.app._log(
                f"设置已保存：默认画质 {quality}，"
                f"开机自启动 {'开' if auto else '关'}")
        self.destroy()


def main():
    _set_dpi_awareness()
    app = BilibiliDownloader()
    app.mainloop()


if __name__ == "__main__":
    main()
