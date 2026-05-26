#TinyKullan

<img src="Assets/ScreenShots/banner.png" alt="TinyKullan Banner" width="100%">

# 🎲 TinyKullan

**A universal macro automation tool for Roblox tower defense games**

[![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Kullaners/TinyKullan)
[![License](https://img.shields.io/badge/License-GPL--3.0-green?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Kullaners/TinyKullan?style=for-the-badge&color=yellow)](https://github.com/Kullaners/TinyKullan/stargazers)

*Record. Replay. Share. Grind smarter — not harder.*

</div>

---

## 🧩 What is TinyKullan?

**TinyKullan** is a lightweight yet powerful macro automation tool designed for Roblox tower defense games. It lets you record mouse and keyboard actions, replay them with precision, and share your entire setup with others using a single **Base64 shareable code** — images included.

Whether you're farming waves, automating unit placement, or building the perfect run, TinyKullan keeps it tight and repeatable.

---

## ✨ Features

### 🎮 Core Macro Engine
- **Record & Replay** — Capture every click, keypress, scroll, and mouse movement with frame-perfect timing
- **Loop Mode** — Repeat macros indefinitely for continuous farming runs
- **Speed Control** — Scale playback speed from 0.1× to 10× without re-recording
- **Auto-Clicker** — Built-in configurable auto-clicker (CPS adjustable, left/right button)
- **Pause / Resume** — Full hotkey-driven pause & resume mid-run

### 📦 Share System (Base64 Config)
- **Export to Clipboard** — Encodes your entire macro (events + image detection + images) into a single Base64 string
- **Import from Clipboard** — Paste a code to instantly load someone else's run — files reconstruct automatically
- **Fully Portable** — No file attachments needed; share in Discord, paste bins, or comments

### 🔍 Image Detection Engine
- **Screen Template Matching** — Uses OpenCV to detect on-screen images in real time (powered by `cv2` + `mss`)
- **Trigger Actions on Match** — Run a macro, send a webhook, or take a screenshot when a target image appears
- **Priority System** — Assign priorities to multiple detection targets
- **Live Testing** — Test image detection targets directly from the settings UI

### 🔄 Roblox Auto-Recovery
- **Disconnect Detection** — Detects Roblox disconnects via screen image matching
- **Auto-Rejoin** — Reconnects to your server via Deeplink or Server ID automatically
- **Recovery Run** — Optionally re-launches a specific macro run upon reconnection

### 🔔 Discord Webhook Integration
- **Event Notifications** — Get notified on Record, Play, Loop, Save events
- **Screenshot Attachment** — Automatically attaches a screenshot to webhook messages
- **Mention Support** — Tag a Discord user ID in notifications
- **Test Button** — Test your webhook from the settings panel

### 📊 Macro Dashboard
- **Session Stats** — Total runs, playtime, rank progress
- **Custom Badges** — Add custom emoji badges with labels
- **Fully Themeable** — Custom background color, title, subtitle
- **Exportable Card** — Shareable HTML performance card for your grind stats

### 🎨 UI & Theming
- **Full Color Theming** — Customize primary, secondary, and accent colors with a color picker
- **Tiny Mode** — Compact toolbar with configurable visible buttons
- **Always on Top** — Overlay mode so TinyKullan stays visible over Roblox
- **Adjustable Transparency** — Separate alpha for focused and unfocused states
- **Custom Button Icons** — Change toolbar icons to any emoji
- **System Tray** — Minimize to tray; right-click for quick access

### ⌨️ Hotkey System
| Action | Default Key |
|--------|-------------|
| Record | `F5` |
| Play | `F6` |
| Loop | `F7` |
| Save | `F8` |
| Auto-Click Toggle | `F4` |
| Pause | `F9` |

> All hotkeys are fully rebindable from the Settings panel.

### 🗂️ Run Manager
- **Save & Name Runs** — Save multiple macros with custom names
- **Favorites** — Star your go-to runs for quick access
- **Run Picker UI** — Browse, load, delete, and manage runs in one panel
- **AutoHotkey Export** — Optionally export macros as `.ahk` scripts

---

## 📋 Requirements

- **Windows 10 / 11**
- **Python 3.10+**
- **Dependencies** (auto-installed via `python installer.bat`):

```
pynput
pillow
requests
mss
opencv-python
numpy
discord-webhook
keyboard
```

---

## 🚀 Installation

1. **Download** the latest release zip and extract it
2. Run **`python installer.bat`** to install all dependencies automatically
3. Launch **`TinyKullan.vbs`** to start the app (no console window)

> ℹ️ AutoHotkey (v1 or v2) is optional — required only for `.ahk` macro export

---

## 🔧 Usage

### Recording a Macro
1. Launch TinyKullan and open your Roblox game
2. Press **`F5`** to start recording
3. Play through the actions you want to automate
4. Press **`F5`** again to stop recording
5. Press **`F8`** to save the run

### Playing a Macro
- Press **`F6`** for a single run
- Press **`F7`** to loop indefinitely
- Press **`F9`** to pause/resume at any time

### Sharing a Macro (Base64)
1. Go to **Settings → Import/Export**
2. Click **Export** — your macro is copied to clipboard as a Base64 code
3. Share the code anywhere (Discord, forums, etc.)
4. Recipients paste the code and click **Import** — everything restores automatically

---

## 🗂️ Project Structure

```
TinyKullan/
├── Python/
│   ├── TinyKullan.py       # Main application (~8,000 lines)
│   └── TinyKullan.ahk      # AutoHotkey bridge script
├── configs/
│   └── config.json         # Shareable config templates
├── Saves/
│   ├── TinyKullan.ini      # User settings & hotkeys
│   ├── image_detection.json # Detection target configs
│   ├── run_favorites.json  # Favorited runs
│   └── runs/               # Saved macro run files
├── Assets/
│   └── ScreenShots/        # Auto-captured screenshots
├── TinyKullan.vbs          # Silent launcher (no console)
└── python installer.bat    # Dependency installer
```

---

## 📸 Screenshots

> *Coming soon — add your screenshots to `Assets/ScreenShots/` and link them here*

---

## 📜 License

This project is licensed under the **GNU General Public License v3.0**.
See [LICENSE](LICENSE) for the full text.

---

## 🤝 Contributing

Pull requests are welcome! If you find a bug or have a feature idea, open an issue.

---

<div align="center">

Made with 💜 for the Roblox grinders

**[⭐ Star this repo](https://github.com/Kullaners/TinyKullan)** if TinyKullan saves you time!

</div>
