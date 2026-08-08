import ctypes
import os
import struct

import main


def save_bmp_from_dib(buf, w, h, path, header):
    with open(path, "wb") as fh:
        fh.write(b"BM")
        fh.write(struct.pack("<I", 54 + len(buf)))
        fh.write(struct.pack("<HH", 0, 0))
        fh.write(struct.pack("<I", 54))
        fh.write(header)
        fh.write(buf)


def capture_screen_rect(app, path):
    """从屏幕 DC 直接抓取窗口矩形区域（= 用户实际看到的画面）。"""
    from ctypes import wintypes

    hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top

    hdc_screen = ctypes.windll.user32.GetDC(None)
    hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    ctypes.windll.gdi32.SelectObject(hdc_mem, hbmp)
    ctypes.windll.gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen,
                               rect.left, rect.top, 0x00CC0020)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    buf = (ctypes.c_ubyte * (w * h * 4))()
    ctypes.windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf,
                                  ctypes.byref(bmi), 0)
    header = bytes(ctypes.string_at(ctypes.byref(bmi), 40))
    save_bmp_from_dib(bytes(buf), w, h, path, header)
    print("SCREEN CAPTURE SAVED", path, w, "x", h)
    return w, h, bytes(buf), rect.left, rect.top


def sample(pixels, w, h, cx, cy, label):
    off = (cy * w + cx) * 4
    b, g, r = pixels[off], pixels[off + 1], pixels[off + 2]
    print(label, "(%d,%d)" % (cx, cy), "#%02X%02X%02X" % (r, g, b))


def run(glass):
    if not glass:
        os.environ["BILI_DISABLE_ACRYLIC"] = "1"
    else:
        os.environ.pop("BILI_DISABLE_ACRYLIC", None)
    main._set_dpi_awareness()
    app = main.BilibiliDownloader()

    def snap():
        wx, wy = app.winfo_rootx(), app.winfo_rooty()
        w, h, px, rl, rt = capture_screen_rect(app, "screen_%s.bmp" % glass)
        ox = wx - rl
        oy = wy - rt
        for cx, cy, label in (
                (250, 30, "title"),
                (250, 72, "url_entry"),
                (250, 115, "parse_btn"),
                (250, 175, "card"),
                (250, 315, "download_btn"),
                (250, 440, "log"),
                (5, 250, "left_edge")):
            sample(px, w, h, ox + cx, oy + cy, label)
        app.destroy()

    app.after(1200, snap)
    app.mainloop()


def run_early_glass():
    """在窗口创建后、显示前立即启用丙烯酸。"""
    os.environ["BILI_DISABLE_ACRYLIC"] = "1"  # 阻止 after(300) 的默认调用
    main._set_dpi_awareness()
    app = main.BilibiliDownloader()
    hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd, 38, ctypes.byref(ctypes.c_int(3)), 4)
    # 模拟 _apply_acrylic 里的边框色 + 标题文字色
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd, 34, ctypes.byref(ctypes.c_uint(0x4B6EB0)), 4)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(
        hwnd, 36, ctypes.byref(ctypes.c_uint(0x2C4271)), 4)

    def snap():
        wx, wy = app.winfo_rootx(), app.winfo_rooty()
        w, h, px, rl, rt = capture_screen_rect(
            app, "screen_early.bmp")
        ox = wx - rl
        oy = wy - rt
        for cx, cy, label in (
                (250, 115, "parse_btn"),
                (250, 175, "card"),
                (250, 315, "download_btn")):
            sample(px, w, h, ox + cx, oy + cy, label)
        app.destroy()

    app.after(1200, snap)
    app.mainloop()


if __name__ == "__main__":
    run(True)
