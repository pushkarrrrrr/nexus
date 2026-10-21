# NEXUS Standalone macOS Application — Distribution & Installation Guide

This document provides complete instructions for installing, running, and distributing the **NEXUS Agentic AI Operating System** as a native, self-contained macOS application (`.dmg` / `.app`).

---

## 1. Overview & Architecture

NEXUS for macOS is built as a **two-tier standalone native bundle**:
1. **Frontend HUD Surface**: A high-performance Tauri 2.0 Rust desktop process displaying the summonable liquid-glass floating capsule.
2. **Embedded Core Engine Sidecar**: A standalone compiled native Mach-O binary (`nexus-engine-aarch64-apple-darwin`) containing FastAPI, Uvicorn, SQLAlchemy, SQLite WAL mode, and all autonomous agent capabilities.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        NEXUS Ambient.app                               │
│                                                                        │
│  Contents/MacOS/                                                       │
│  ├── nexus-ambient  (Tauri 2.0 Rust HUD Process, PID 1)                │
│  │     │                                                               │
│  │     └── [EngineSupervisor]                                          │
│  │           Spawns & cleanly terminates (SIGTERM on quit)             │
│  │                                                                     │
│  └── nexus-engine   (Compiled Python Engine, PID 2)                    │
│        ├── Uvicorn Async Server on http://127.0.0.1:8000               │
│        ├── Sub-15ms Fast-Path Intent Router & Gemini Semantic Fallback │
│        ├── Active Screen Reasoner & macOS Perception Engine            │
│        └── SQLite Database (WAL Mode)                                  │
│              └── Path: ~/Library/Application Support/NEXUS/nexus.db    │
└────────────────────────────────────────────────────────────────────────┘
```

> [!NOTE]
> **Zero Dependencies**: End users do **NOT** need to install Python, Node.js, Git, or Docker. Everything required to run NEXUS is 100% self-contained in the application bundle.

---

## 2. System Requirements

- **Operating System**: macOS 12.0 (Monterey), macOS 13.0 (Ventura), macOS 14.0 (Sonoma), or macOS 15.0 (Sequoia).
- **Architecture**: Apple Silicon (M1, M2, M3, M4 family, `aarch64-apple-darwin`).
- **Disk Space**: ~250 MB free space.

---

## 3. Step-by-Step Installation

### Step 1: Locate the DMG Installer
The production installer is located at:
```text
apps/ambient/src-tauri/target/release/bundle/dmg/NEXUS Ambient_0.1.0_aarch64.dmg
```
*SHA256 Checksum:* `fbc0ab4e03a7b52c3dabcd38d4b8a6524b3c83f8b9de783d450a0ced7c10a660`  
*File Size:* `~90.64 MiB`

### Step 2: Mount the Disk Image
Double-click the `NEXUS Ambient_0.1.0_aarch64.dmg` file in Finder. A window will open displaying:
- `NEXUS Ambient.app`
- A shortcut arrow pointing to the `Applications` folder

### Step 3: Drag & Drop to Install
Drag the `NEXUS Ambient` icon and drop it directly onto the `Applications` folder shortcut.

### Step 4: Eject the Installer
In Finder, click the **Eject** (⏏) icon next to `NEXUS Ambient` in the sidebar.

---

## 4. First-Time Launch & macOS Gatekeeper

Because the installer is compiled locally without an enterprise Apple Developer ID signing certificate ($99/year Apple subscription), macOS Gatekeeper protects your system by flagging unsigned downloaded applications.

### Option A: GUI Bypass (Recommended)
1. Open your **Applications** folder in Finder (`/Applications`).
2. **Right-click** (or `Control-click`) on `NEXUS Ambient.app`.
3. Click **Open** from the context menu.
4. macOS will show a prompt: *"macOS cannot verify the developer of NEXUS Ambient. Are you sure you want to open it?"*
5. Click **Open**.
6. *This is only required once.* On all subsequent launches, NEXUS will open directly with a single click or keyboard shortcut.

### Option B: Terminal 1-Liner (For Developers)
If you prefer removing the macOS quarantine flag via terminal:
```bash
xattr -cr /Applications/"NEXUS Ambient.app"
```

---

## 5. macOS System Permissions Setup

NEXUS interacts with your macOS desktop to perceive context, read active windows, control keystrokes, and listen to voice commands. Grant the following permissions in **System Settings**:

### 1. Accessibility (Mandatory for OS Control)
- **Why needed**: Allows NEXUS to read frontmost application names, window titles, simulate keystrokes (e.g. `Cmd+C` selection), and execute automated clicks.
- **How to enable**:
  1. Open **System Settings** > **Privacy & Security** > **Accessibility**.
  2. Click `+` or toggle the switch next to **NEXUS Ambient**.

### 2. Screen Recording (Mandatory for Screen Perception)
- **Why needed**: Allows the Active Screen Reasoner to take contextual screenshots and analyze visual layouts.
- **How to enable**:
  1. Open **System Settings** > **Privacy & Security** > **Screen Recording**.
  2. Toggle the switch next to **NEXUS Ambient**.

### 3. Microphone (Optional for Voice Input)
- **Why needed**: Allows the floating voice orb to process ambient spoken commands.
- **How to enable**: Click the microphone orb inside the HUD; macOS will display a prompt asking for microphone access. Click **Allow**.

---

## 6. Daily Usage & Controls

### Summoning the Ambient HUD
- **Global Keyboard Shortcut**: Press `Cmd + Shift + Space` anywhere in macOS to summon or dismiss the HUD.
- **Menu Bar Icon**: Click the `✦ NEXUS` icon in the macOS menu bar at any time to toggle visibility.

### User Data & Storage
All personal memories, documents, tasks, and settings are stored locally in:
```text
~/Library/Application Support/NEXUS/nexus.db
```
- Operates in high-concurrency **SQLite WAL (Write-Ahead Logging)** mode.
- To reset or backup your data, simply copy or remove this folder.

### Clean App Termination
To completely quit NEXUS and all background processes:
1. Click the `✦ NEXUS` icon in the top menu bar.
2. Select **Quit NEXUS** (or press `Cmd + Q` when focused).
3. The supervisor automatically sends `SIGTERM` to the engine sidecar and releases port `8000`.

---

## 7. Diagnostics & Health Verification

While the app is running, you can verify backend engine connectivity from any terminal:
```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
```

Expected output:
```json
{
    "status": "ok",
    "version": "0.1.0",
    "environment": "production",
    "database": "healthy",
    "database_healthy": true,
    "timestamp": "2026-10-21T19:04:24.217937+00:00"
}
```

---

## 8. Re-building from Source

To compile new updates and regenerate the `.dmg` installer:
```bash
# 1. Compile backend engine sidecar
./scripts/build_engine_sidecar.sh

# 2. Package production .app bundle and .dmg installer
./scripts/build_macos_dmg.sh
```
Output files will be generated in `apps/ambient/src-tauri/target/release/bundle/`.
