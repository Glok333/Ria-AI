# Ria — a local AI desktop companion for Windows

[🇺🇦 Українська](README.md) · 🇬🇧 English

**Ria** is an anime-style assistant that lives on your desktop. Press **Ctrl+Alt+X** and she pops up with a speech bubble and an input field; you type or speak to her in Ukrainian, Russian or English. She opens programs and websites, controls your PC, sees your screen, writes code, and her pose changes depending on what she is doing: waiting, thinking or speaking.

All the "smart" work runs **locally on your PC** through [Ollama](https://ollama.com): no API keys, no subscriptions, and your messages are not sent to the cloud.

> This project was built with **Claude** (Anthropic): the code and documentation were written by the AI assistant in a conversation with the author, who came up with the idea, tested it and refined the result.

---

## Quick start (for most people)

1. Open [**Releases**](https://github.com/Glok333/Ria-AI/releases/latest) and download **`Ria-Setup.exe`**.
2. Run it. At the top right pick the language: **Українська / English / Русский**.
3. Choose where to install (drive D by default if you have one) and which models you want: **chat** (required), **code** and **vision** (optional, just untick them), voice and the Whisper model size.
4. Press **Install** and wait. The wizard installs Ollama if it is missing, downloads the chosen models, creates shortcuts and starts Ria.

No administrator rights needed. After that press **Ctrl+Alt+X**.

> **Windows / antivirus warning.** `Ria-Setup.exe` and `Ria.exe` are not signed with a paid code-signing certificate, so SmartScreen may say "Windows protected your PC". Click **More info → Run anyway**. Antivirus tools are also sometimes wary of PyInstaller-built programs that listen for a hotkey (see "Safety"). The code is open, and you can build everything yourself (see "Building").

### What the installer does

- **Three languages** with buttons at the top (Українська, English, Русский); the default comes from Windows and becomes Ria's interface language too.
- **Install location** for the program and a separate **models folder** (models are big, so the default is `D:\Ollama\models` when drive D exists). It shows the space needed and available, and will not start if there is not enough.
- **Model checkboxes**: chat, code, vision. Each can be switched off (for example, no coding model), swapped for another one from the list, or set to your own name from [ollama.com/library](https://ollama.com/library). Every entry shows its size and a label: recommended, light, strong.
- **GPU hint**: it detects an NVIDIA card and tells you whether the chosen models are likely to fit.
- **Voice**: on or off, and the Whisper model size (downloaded on first use).
- **Settings up front**: hotkey, PC access mode (full / ask / off), game mode, theme, desktop and Start menu shortcuts, autostart with Windows.
- **Progress** with percentages, a log and some Ria quips. If a model fails to download, the wizard carries on and at the end tells you which command to run later.
- **Updates**: if Ria is already installed in that folder, only the program is updated. Your memory, plans, `settings.json`, `commands.json` and so on are kept.
- **Uninstall**: an `Uninstall Ria.bat` appears in the folder (plus an entry in "Apps & features"). It asks whether to delete your data. It never touches Ollama or the downloaded models.
- **Silent install** with no window: `Ria-Setup.exe /S --dir D:\Ria --models-dir D:\Ollama\models --chat qwen3:4b-instruct --vision qwen3-vl:4b-instruct --lang en`. `--code` and `--no-ollama` are available too.

## Features

- **Hotkey summon.** Ctrl+Alt+X shows and hides Ria. The window is borderless, always on top, and draggable.
- **Three languages** for conversation and interface (Ukrainian, Russian, English) in a comic-style speech bubble. Reply text can be selected and copied.
- **Personality.** Ria talks like an elegant, warm and slightly playful assistant. The personality is just text in the code, so it is easy to change.
- **Poses.** Separate images for "waiting", "thinking" and "speaking".
- **Voice.** Local speech recognition (faster-whisper): press **Ctrl+Alt+V** ("press to talk, press again to finish") or use the optional wake word "Ria…". Your request is accepted immediately, and while she is answering she ignores stray sounds instead of collecting them.
- **Full PC access** (`ACCESS_MODE`): run PowerShell/cmd commands; list, search, create, copy, move and delete files (deleting goes to the Recycle Bin); download files; open programs and sites; list and kill processes; system info; clipboard; typing and key presses; media keys; power (shutdown, sleep). Dangerous actions need confirmation.
- **Vision.** Ria sees your screen and images through a vision model: "what is on my screen?", "read this error", "take a screenshot". Screenshots are stored on disk and **cleaned automatically** (by age and total size).
- **Game mode.** Press Ctrl+Alt+X in a game and the cursor is already in Ria's input field: type your message, and after Enter or Esc focus returns to the game. After she answers the window hides by itself.
- **Custom code-word commands.** Say "code 1" and Ria runs a set of actions without the AI model: key presses, launching a program, killing a process, typing text, hide/show and so on. The editor is in **Settings → Custom commands (code words)…**. "Hide" and "show yourself" work too.
- **Files and code.** She creates, reads and edits files; code can be written by a separate model (optional).
- **Tool selection** per request (a small model gets confused less) and **honesty**: gray text under each reply shows which tools were really called.
- **Speed.** Short actions skip the second model call; models can stay loaded (`KEEP_ALIVE`); on 6 GB of VRAM Ria swaps chat/code/vision models herself.
- **Resizable** (Ctrl + mouse wheel), **themes** (light, dark and your own), **model choice** in the menu (chat, code, vision) and an optional **API key** for a cloud model.
- **Memory.** Short-term (recent conversation) and long-term (facts and rules you ask her to remember).
- **Plans and reminders** with date and time.

## Requirements

| | |
|---|---|
| OS | Windows 10 or 11 |
| Disk | chat model ≈ 2.5 GB; + code ≈ 4.7 GB; + vision ≈ 3.3 GB; Whisper small ≈ 0.5 GB; the program ≈ 1 GB |
| Hardware | an NVIDIA GPU with 6+ GB is recommended; developed on a GTX 1660 (6 GB). It also runs on CPU, only slower |
| Running from source | Python 3.10+ (only if you run `ria.py` without the installer) |

## Manual installation (from source)

If you would rather not use `Ria-Setup.exe`:

**1.** Install [Python 3.10+](https://www.python.org/downloads/) with "Add python.exe to PATH" ticked, and [Ollama](https://ollama.com/download).

**2.** Pull the models (everything except chat is optional):

```
ollama pull qwen3:4b-instruct
ollama pull qwen2.5-coder:7b
ollama pull qwen3-vl:4b-instruct
```

Use the `-instruct` versions: they answer right away instead of "thinking" for a long time.

**3.** Download the repository (**Code → Download ZIP** or `git clone https://github.com/Glok333/Ria-AI.git`), open the folder in PowerShell and run `pip install -r requirements.txt`.

**4.** Run `python ria.py` or `start.bat`.

### Models on drive D

By default Ollama stores models on drive C (`%USERPROFILE%\.ollama\models`). To move them to D: Win+R → `sysdm.cpl` → Advanced → Environment Variables → add a user variable `OLLAMA_MODELS` = `D:\Ollama\models`, quit Ollama from the tray and start it again. The installer does this for you. If Ria starts Ollama herself, set the folder with `OLLAMA_MODELS_DIR` in `settings.json`. The menu **Settings → Model** (guide included) opens `models.html` with step-by-step instructions.

## Usage

| Action | How |
|---|---|
| Show / hide | Ctrl+Alt+X (or Esc in the input field) |
| Speak | Ctrl+Alt+V, talk, press Ctrl+Alt+V again |
| Send | Enter |
| Move the window | drag the character, the bubble edges or the empty area near the input |
| Copy | Ctrl+C or right-click |
| Resize | Ctrl + mouse wheel (or Ctrl +, Ctrl -, Ctrl+0) |
| Settings | right-click the text → "Settings" (language, theme, chat/code/vision model, voice, custom commands) |
| Diagnostics | right-click → "Diagnostics" (Ollama, models, tools, voice) |
| Quit | right-click → "Quit" |

**Example requests** (Ukrainian, Russian or English)

- "Open Notepad", "Open youtube.com"
- "What is on my screen?", "Read this error message"
- "Find .pdf files bigger than 50 MB on drive D"
- "Create a Photos folder on the desktop and move all jpg files from Downloads there"
- "How much free space do my drives have?", "Which programs use the most memory?"
- "Download <link> to drive D", "Delete this file"
- "Create snake.py with a snake game" (if the coding model is enabled)
- "Remember that I like coffee", "Be stricter with me"
- "Add 'call mom' to tomorrow's plans at 9:30", "What do I have today?"
- "Hide" / "Show yourself", "Code 1" (your own command)

### Code words

**Settings → Custom commands (code words)…** opens an editor: type what you will say ("code 1, код 1"), add steps (keys, launch, kill process, text, pause, hide…) and what Ria replies. You can test-run the steps. Commands are stored in `commands.json` (example: `commands.example.json`) and work immediately, without the AI.

### Game mode

It works when Ria is summoned by the hotkey from another window (a game). The cursor is already in the input field and the game stays in the background. After Enter or Esc, focus returns to the game. Turn it off with `GAME_MODE: false`; the automatic hide delay is `GAME_AUTOHIDE_SEC`. Borderless-window games work better than exclusive fullscreen.

## Configuration

Everything lives in `settings.json` next to the program (example: `settings.example.json`). The installer creates it; most items can also be changed from the menu. Missing keys fall back to the defaults in `ria.py`.

| Key | What it does |
|---|---|
| `CHAT_MODEL` | chat model (must support tools; `-instruct` preferred) |
| `CODE_MODEL` | coding model; an empty string disables it |
| `VISION_MODEL`, `VISION_MAX_SIDE` | vision model and the longest side of a screenshot |
| `HOTKEY`, `VOICE_HOTKEY` | show and voice hotkeys |
| `ACCESS_MODE` | `full` (full access, dangerous actions confirmed), `ask` (confirm every command), `off` (`workspace` folder only) |
| `CONFIRM_DANGEROUS` | confirm dangerous actions (deletion, shutdown, system commands) |
| `GAME_MODE`, `GAME_AUTOHIDE_SEC` | game mode and auto-hide after a reply (0 disables) |
| `SCREENSHOT_KEEP_DAYS`, `SCREENSHOT_MAX_MB` | how many days and megabytes of screenshots to keep |
| `DOWNLOAD_DIR` | where downloads go (empty: a `downloads` folder on drive D or next to the program) |
| `OLLAMA_MODELS_DIR` | where models are stored when Ria starts Ollama herself |
| `KEEP_ALIVE`, `PRELOAD_MODEL`, `NUM_CTX`, `FAST_TOOL_REPLY` | speed: how long to keep a model loaded, preload at startup, context size, reply to simple actions without a second call |
| `HISTORY_KEEP` | how many messages to remember between launches (0 disables) |
| `VOICE_ENABLED`, `WAKE_ENABLED`, `WAKE_WORDS` | voice, always-listening wake word and the words themselves |
| `STT_MODEL`, `STT_LANG`, `STT_DEVICE`, `MIC_DEVICE`, `VOICE_THRESHOLD` | recognition model (`tiny`…`medium`), language, CPU/GPU, microphone and sensitivity |
| `DAY_START`, `NIGHT_START` | day and night boundaries for greetings |

In `ria.py` itself (the `НАЛАШТУВАННЯ` block): `SYSTEM_PROMPT` (personality), the `APPS` dictionary (programs; ones added through chat live in `apps.json`) and the images `ria_idle.png`, `ria_thinking.png`, `ria_speaking.png`, `ria_speaking2.png` (same size, transparent PNG works best; otherwise `ria.png` or a placeholder is used).

## Language and themes

**Settings** → language (Українська, English, Русский) and theme (light, dark, custom). Your choice is stored in `ui.json`. **Your own theme:** copy `themes.example.json` to `themes.json` and change the `#rrggbb` colors; the theme appears in the menu after a restart.

## Memory and plans

Everything is stored **locally**, in a `memory` folder next to the program:

| File | Contents |
|---|---|
| `memory/history.json` | short-term memory: recent messages |
| `memory/long_term.json` | long-term memory: facts and rules (up to 40 entries) |
| `memory/tasks.json` | plans and reminders |

Files Ria creates live in `workspace` (menu → "Open workspace folder"). You can open or delete any of these files with Notepad. Reminders fire only while Ria is running; missed ones appear at the next launch.

## Building

For developers. Python 3.10+ is required.

| What | How |
|---|---|
| The program only | `build_exe.bat` builds `dist\Ria\Ria.exe` (an `onedir` folder; do not move the exe away from it). Your data (`memory`, `workspace`, `settings.json`, ...) survives rebuilds. All caches go to `_cache` on the same drive |
| The installer | `build_setup.bat` builds the program, packs it into `Ria-app.zip` (+ `.sha256`) and creates `Ria-Setup.exe`. The `embed` argument puts the archive inside the installer (one file, but large) |
| Publishing | create a GitHub Release and attach `Ria-Setup.exe`, `Ria-app.zip` and `Ria-app.zip.sha256`. By default the installer downloads the archive from `releases/latest/download/` (or uses a `Ria-app.zip` placed next to it) |

Startup errors go to `ria_error.log`; tool activity goes to `ria_debug.log`.

## Safety

- Everything runs locally. The network is used for your own Ollama (`localhost`), and when you ask Ria to download something or open a website. The installer separately downloads Ollama, models and the program archive.
- **Ria can have full access to your PC** (`ACCESS_MODE=full`). That is powerful, so: dangerous actions (deletion, shutdown, system commands) are confirmed in a dialog; deleted files go to the Recycle Bin; the model decides which tools to call, so read confirmation dialogs. For more caution set `ask` (confirms every command) or `off` (the `workspace` folder only) in `settings.json`.
- A small local model can make mistakes. Keep backups of anything you cannot afford to lose.
- The `keyboard` library hooks global keyboard events to catch hotkeys. The program reacts only to its own combinations and records nothing (see `ria.py`). The microphone is used only with the voice hotkey or, if you enable it, the wake word; audio is neither saved nor sent anywhere.
- Screenshots and images are processed by a local model and stay on your disk.

## Troubleshooting

| Problem | Fix |
|---|---|
| SmartScreen blocks `Ria-Setup.exe` | "More info → Run anyway": the exe is unsigned. You can add Ria's folder to your antivirus exclusions |
| "Ollama is not running" | Start Ollama from the Start menu (tray icon) |
| A model failed in the wizard | Run `ollama pull <name>` in PowerShell; current names are at [ollama.com/library](https://ollama.com/library); the wizard also accepts your own |
| Ria says "done" but nothing happened | Right-click → **Diagnostics**; more detail in `ria_debug.log` |
| Slow replies | `ollama ps`: PROCESSOR should say GPU; use an `-instruct` model; on 6 GB VRAM keep one big model at a time |
| Voice recognition is slow | Set `STT_MODEL` to `base` or `tiny`; keep `STT_DEVICE` on `auto`; do not enable `WAKE_ENABLED` in a noisy room |
| Ctrl+Alt+X does nothing in a game | Exclusive fullscreen captures keys; try windowed or borderless mode, or another combination in `HOTKEY` |
| Ria cannot see the screen | Make sure a vision model is installed (menu → Settings → Vision model) and there is free memory |
| Very small models mix up tools | Repeat the request more precisely or try a larger model |

## Limitations

- Windows only.
- A 4B model is small: it can make mistakes, mix up tools, and writes complex code poorly.
- Reminders only work while Ria is running.
- Vision understands a screenshot but does not click on it with the mouse: control goes through keys, commands and programs.
- The poses are head tilts of a single picture, not real animation (Live2D is planned).

## Credits and disclaimer

- The code and documentation were created with the help of [Claude](https://claude.ai) by Anthropic.
- Ria's personality is inspired by Rias Gremory from the anime *High School DxD*. This is an unofficial fan project, not affiliated with the rights holders of the series; all rights to the character belong to them.
- Character images, if you add them to your copy, must belong to you or be used with permission.
