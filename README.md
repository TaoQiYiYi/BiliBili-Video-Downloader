# 桃汽依依制作 - B站视频下载器

> B站视频下载器 v1.0.1 —— 带毛玻璃效果与三套渐变主题的 B 站视频下载工具，基于 `yt-dlp` 构建，开箱即用，无需安装 Python。

## ✨ 功能特性

- 📥 **输入 BV 号即可下载**：直接填 BV 号（也支持 av 号 / 完整链接），不用再复制一长串链接
- 🎨 **三套四色渐变主题**：冰蓝粉 / 暖阳青 / 落霞蓝，设置中一键切换，按钮、输入框、卡片、进度条等所有元素同步换肤，选择自动保存
- 🪟 **Windows 11 毛玻璃窗口**：Acrylic 效果覆盖含标题栏与边框，内容层接近不透明
- ⚡ **无需登录下载 1080P**（大部分视频；4K / 大会员专享除外）
- 🎞️ 画质选择：自动 / 1080P / 720P / 480P / 360P / 仅音频（有 ffmpeg 时输出 mp3）
- 📑 多 P 视频整体下载
- 🧾 解析后显示标题、UP 主、时长、最高画质、P 数
- ▶️ 优先 H.264 编码并统一输出 mp4，Windows 媒体播放器直接可播
- 🔁 网络超时自动重试：每次重试重新获取 CDN 链接避开慢节点，支持断点续传
- 📊 实时进度条与下载日志
- ⚙️ 设置持久化：保存目录、默认画质、主题、开机自启动自动保存到`%USERPROFILE%\B站视频下载器\config.json`
- 🚀 开机自启动（HKCU 注册表 Run 键，无需管理员权限）
- 📦 单文件 exe，免安装双击即用

## 📸 界面预览

![界面预览](theme_preview_exe.png)

## 🚀 快速开始

### 直接使用

从 Releases 页面下载 `B站视频下载器.exe`，双击运行即可，无需安装 Python。

### 源码运行

```bash
pip install -r requirements.txt
python main.py
```

## 🛠️ 技术栈

- Python 3.14 + tkinter（界面）
- yt-dlp（下载引擎）
- Windows DWM API（毛玻璃效果）
- PyInstaller（打包）

## 📦 打包为 exe

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "B站视频下载器" `
  --icon app.ico --add-data "app.ico;." --collect-all yt_dlp main.py
```

## ❓ 常见问题

**Q：为什么某些视频没有 4K / 高码率 1080P？**

这些画质需要登录账号，未登录状态下只能获取公开画质（大部分视频的 1080P 免费）。

**Q：下载的视频 Windows 媒体播放器打不开？**

B 站部分高画质只有 HEVC(H.265) / AV1 编码，Windows 媒体播放器不支持。下载器会优先选择 H.264；若某视频某画质只有 HEVC/AV1，程序会在日志中提示，此时可用 VLC / PotPlayer 播放，或在 Microsoft Store 安装 HEVC 扩展。

**Q：为什么界面没有毛玻璃效果？**

毛玻璃基于 Windows 11 的 Acrylic 背景，Windows 10 会自动降级为主题色窗口。

**Q：ffmpeg 有什么用？**

高清画质（1080P+）需要 ffmpeg 合并音视频流。程序会自动检测系统 ffmpeg（含常见安装位置）；未检测到时自动只提供免合并画质。ffmpeg 下载：[gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/)，或执行 `winget install Gyan.FFmpeg`。

## ⚠️ 免责声明

本工具仅供个人学习与技术交流使用。请遵守 B 站用户协议及相关法律法规，尊重 UP 主版权，请勿将下载内容用于商业用途或二次传播。
