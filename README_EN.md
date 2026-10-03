# Ria — a local AI desktop companion for Windows

[🇺🇦 Українська](README.md) · 🇬🇧 English

**Ria** is an anime-style assistant that lives on your desktop. Press **Ctrl+Alt+X** and she pops up with a speech bubble and an input field. You talk to her in Ukrainian or Russian. She opens programs and websites, creates files and code, and her pose changes depending on what she is doing: waiting, thinking or speaking.

All the "smart" work runs **locally on your PC** through [Ollama](https://ollama.com): no API keys, no subscriptions, and your messages are not sent to the cloud.

> This project was built with **Claude** (Anthropic): the code and documentation were written by the AI assistant in a conversation with the author, who came up with the idea, tested it and refined the result.

---

## Features

- **Hotkey summon.** Ctrl+Alt+X shows and hides Ria. The window is borderless, always on top, and can be dragged anywhere with the mouse.
- **Ukrainian and Russian conversation** in a comic-style speech bubble. You can select and copy the reply text (Ctrl+C or right-click).
- **Personality.** Ria talks like an elegant, warm and slightly playful assistant who gladly does what you ask. The personality is just text in the code, so it is easy to change.
- **Poses.** Separate images for "waiting", "thinking" and "speaking" (two alternating frames for speaking).
- **Opening programs and websites** from a list that you control. Ria can add new programs to the list when you ask, but only after you confirm it in a dialog.
- **Files and code.** She creates, reads and lists files in a dedicated `workspace` folder. She can run a `.py` file, but only after your confirmation.

## Requirements

| | |
|---|---|
| OS | Windows 10 or 11 |
| Python | **3.10 or newer** (tkinter comes with Python) |
| Ollama | [ollama.com/download](https://ollama.com/download) |
| Disk | about 3 GB for the model |
| Hardware | a GPU with 4+ GB VRAM is recommended; developed and tested on a GTX 1660 (6 GB). It also runs on CPU, only slower |

## Installation

**1. Install Python** from [python.org/downloads](https://www.python.org/downloads/). During setup, **make sure to tick "Add python.exe to PATH"**. Check in PowerShell: `python --version` (3.10+).

**2. Install Ollama** from [ollama.com/download](https://ollama.com/download) and start it (its icon appears in the system tray).

**3. Download the model** in PowerShell:

```
ollama pull qwen3:4b-instruct
```

That is roughly 2.5 GB. Use the `-instruct` version: it answers right away. The plain `qwen3:4b` "thinks" for a long time first, so Ria would take 8-10 seconds to answer.

**4. Download this repository:** **Code → Download ZIP**, then unzip it anywhere (for example `C:\Ria`). Or with git:

```
git clone https://github.com/Glok333/Ria-AI.git
cd Ria-AI
```

**5. Install the libraries.** In PowerShell go to the project folder (`cd C:\Ria`) and run:

```
pip install -r requirements.txt
```

If `pip` is not found, run `python -m pip install -r requirements.txt`.

## Running

Make sure Ollama is running (tray icon), then:

```
python ria.py
```

or double-click `start.bat`. Ria appears with a greeting. Press **Ctrl+Alt+X** to hide or show her.

> The first reply after launch may take longer because the model is loading into memory. After that it is fast.

## Usage

**Controls**

| Action | How |
|---|---|
| Show / hide | Ctrl+Alt+X (or Esc in the input field to hide) |
| Send a message | Enter |
| Move the window | drag the character, the edges of the bubble or the empty area next to the input field |
| Select text in the bubble | with the mouse (double-click: word, triple-click: line), Ctrl+A selects everything |
| Copy | Ctrl+C or right-click → "Copy selection / Copy all" (the menu labels are in Ukrainian) |
| Scroll a long reply | mouse wheel over the text |

**Example requests** (in Ukrainian or Russian)

- "Відкрий блокнот" (open Notepad)
- "Відкрий youtube.com" (open youtube.com)
- "Створи файл hello.py, який вітає мене по імені" (create a hello.py file that greets me by name)
- "Запусти hello.py" (run hello.py; asks for confirmation)
- "Що ти вмієш відкривати?" (what can you open?)
- "Додай Steam до списку програм" (add Steam to the program list; finds the shortcut and shows a confirmation dialog)
- "Прибери Steam зі списку" (remove Steam from the list)

## Configuration

Everything is configured at the top of `ria.py`, in the settings block (`НАЛАШТУВАННЯ`):

| What | Where |
|---|---|
| Chat model | `CHAT_MODEL`. Any Ollama model with tool support works (look for the *tools* label on its library page). Models with a "thinking" mode answer more slowly |
| Separate coding model | `CODE_MODEL`, for example `"qwen2.5-coder:7b"` (remember to pull it). An empty string disables it |
| Hotkey | `HOTKEY` |
| Programs | the `APPS` dictionary; programs added through chat are saved in `apps.json` |
| Personality | `SYSTEM_PROMPT` (written in Ukrainian) |
| Images | `ria_idle.png`, `ria_thinking.png`, `ria_speaking.png`, `ria_speaking2.png` next to the script (all the **same size**, PNG with a transparent background works best). If they are missing, `ria.png` is used, and if that is missing too, a placeholder (•ᴗ•) is shown |

The `workspace` folder and the `apps.json` file are created automatically next to the script.

## Safety

- Everything runs locally. The only network request the program makes is to your own Ollama (`localhost`). The browser opens only when you ask Ria to open a website.
- Ria can open **only programs from the `APPS` list**. A new program can be added only after you confirm it in a dialog (`.exe`, `.lnk` and `.url` are accepted).
- Files are created and read **only inside the `workspace` folder**; she cannot step outside it.
- Running `.py` files requires confirmation and is limited to 30 seconds. The code still runs with your user permissions, so read it in the confirmation dialog before clicking "Yes".
- The `keyboard` library hooks global keyboard events in order to catch the hotkey. The program only reacts to Ctrl+Alt+X and records nothing; you can verify this in `ria.py` (the `run` method). Some antivirus tools may be wary of libraries of this type.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Ollama не запущений" (Ollama is not running) | Start Ollama from the Start menu; its icon should appear in the tray |
| `pip` / `python` not found | Reinstall Python with "Add python.exe to PATH" ticked, or use `py -m pip ...` and `py ria.py` |
| `ollama pull` cannot find the model | Check the current model name at [ollama.com/library](https://ollama.com/library) and set it in `CHAT_MODEL` |
| Replies are very slow | Run `ollama ps` and check that PROCESSOR says GPU, and that you use an `-instruct` model rather than a "thinking" one |
| English "reasoning" text shows up in the bubble | You are using a model with a thinking mode; switch to `qwen3:4b-instruct` |
| Ctrl+Alt+X does nothing | Some fullscreen games capture hotkeys. Try windowed mode, or choose another combination in `HOTKEY` |
| Very small models mix up the tools | Repeat the request more precisely, or try a larger model |

## Limitations

- Windows only (it uses `os.startfile` and Windows window transparency).
- A 4B model is small: it can make mistakes, mix up tools, and writes complex code poorly.
- **No vision yet**: she cannot see your screen or control the mouse and keyboard.
- The poses are head tilts of a single picture, not real animation. Proper animation would need a Live2D model (planned).

## Credits and disclaimer

- The code and documentation were created with the help of [Claude](https://claude.ai) by Anthropic.
- Ria's personality is inspired by the character Rias Gremory from the anime *High School DxD*. This is an unofficial fan project and is not affiliated with the rights holders of the series; all rights to the character belong to them.
- Character images, if you add them to your copy of the project, must belong to you or be used with permission.
