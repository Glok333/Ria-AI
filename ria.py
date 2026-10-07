r"""
Ріас — локальний ІІ-компаньйон (тестова версія, без зору)

Ctrl+Alt+X  — показати / сховати
Enter       — відправити
Esc         — сховати

Потрібно:
    pip install requests keyboard pillow
    ollama pull qwen3:4b-instruct    # мозок (чат + виклик інструментів), без «роздумів»
    ollama pull qwen2.5-coder:7b     # необов'язково: пише код у файли (CODE_MODEL)
Картинки персонажа лежать поруч зі скриптом: ria_idle.png (очікує), ria_thinking.png (думає),
ria_speaking.png + ria_speaking2.png (говорить, кадри чергуються). Усі одного розміру.
Якщо якоїсь немає — береться ria_idle.png або ria.png.
Усі файли, які створює Ріас, лежать у папці  workspace  поруч зі скриптом
Програми, які Ріас додала до свого списку за твоїм проханням, зберігаються у файлі  apps.json  поруч зі скриптом
"""
import inspect
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox

import keyboard
import requests
from PIL import Image, ImageTk

# ---------------- НАЛАШТУВАННЯ ----------------
OLLAMA_URL = "http://localhost:11434/api/chat"
CHAT_MODEL = "qwen3:4b-instruct"
CODE_MODEL = "qwen2.5-coder:7b"
HOTKEY = "ctrl+alt+x"
KEEP_ALIVE = "30m"
PRELOAD_MODEL = True
MODEL_SWITCH = True
DEBUG_LOG = True
SHOW_ACTIONS = True
HISTORY_KEEP = 50
OLLAMA_MODELS_DIR = ""

BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CHAR_IMAGE = BASE_DIR / "ria.png"

def _load_settings():
    try:
        data = json.loads((BASE_DIR / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    g = globals()
    if not isinstance(data, dict):
        return
    for key in ("CHAT_MODEL", "CODE_MODEL", "HOTKEY", "OLLAMA_MODELS_DIR", "KEEP_ALIVE"):
        if isinstance(data.get(key), str):
            g[key] = data[key]
    for key in ("PRELOAD_MODEL", "SHOW_ACTIONS", "DEBUG_LOG", "MODEL_SWITCH"):
        if isinstance(data.get(key), bool):
            g[key] = data[key]
    if isinstance(data.get("HISTORY_KEEP"), int) and not isinstance(data.get("HISTORY_KEEP"), bool):
        g["HISTORY_KEEP"] = max(0, data["HISTORY_KEEP"])

_load_settings()

WORKSPACE = (BASE_DIR / "workspace").resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = MEMORY_DIR / "history.json"
LONG_FILE = MEMORY_DIR / "long_term.json"
TASKS_FILE = MEMORY_DIR / "tasks.json"
_data_lock = threading.Lock()

APPS = {
    "блокнот": "notepad.exe",
    "калькулятор": "calc.exe",
    "провідник": "explorer.exe",
    "диспетчер задач": "taskmgr.exe",
    "paint": "mspaint.exe",
}
APPS_FILE = WORKSPACE.parent / "apps.json"
CUSTOM_APPS: dict[str, str] = {}

def _load_custom_apps():
    try:
        data = json.loads(APPS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, str):
                    CUSTOM_APPS[k.strip().lower()] = v
    except (OSError, ValueError):
        pass
    APPS.update(CUSTOM_APPS)

def _save_custom_apps():
    APPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    APPS_FILE.write_text(json.dumps(CUSTOM_APPS, ensure_ascii=False, indent=2), encoding="utf-8")

_load_custom_apps()

def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

WEEKDAYS = ["понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя"]

def now_prompt() -> str:
    n = datetime.now()
    return f"Зараз {n:%Y-%m-%d %H:%M}, {WEEKDAYS[n.weekday()]}. "

def _find(items: list, ref: str):
    ref = str(ref).strip().lstrip("№#").strip()
    if ref.isdigit():
        for i in items:
            if i.get("id") == int(ref):
                return i, ""
        return None, f"Запису №{ref} немає."
    low = ref.lower()
    matches = [i for i in items if low and low in str(i.get("text", "")).lower()]
    if len(matches) == 1:
        return matches[0], ""
    if not matches:
        return None, f"Не знайшла «{ref}»."
    return None, "Підходить кілька, уточни номер: " + "; ".join(f"№{i['id']} {i['text']}" for i in matches[:5])

MAX_MEMORY_ITEMS = 40
MEMORY_KINDS = {"fact": "факт", "style": "правило поведінки"}
_STYLE_HINT = re.compile(r"\b(будь|будьте|звертайся|говори|відповідай|поводься|пиши|обращайся|говори|отвечай|веди себя)\b", re.I)

def _load_long() -> list:
    d = _read_json(LONG_FILE, [])
    return d if isinstance(d, list) else []

def remember(text: str, kind: str = "") -> str:
    text = " ".join(str(text).split())[:200]
    if not text:
        return "Нема що запам'ятовувати."
    kind = str(kind).strip().lower()
    if kind not in MEMORY_KINDS:
        kind = "style" if _STYLE_HINT.search(text) else "fact"
    with _data_lock:
        items = _load_long()
        if any(str(i.get("text", "")).lower() == text.lower() for i in items):
            return "Це вже є в довгій пам'яті."
        if len(items) >= MAX_MEMORY_ITEMS:
            return f"Довга пам'ять заповнена ({MAX_MEMORY_ITEMS}). Попроси забути щось зайве."
        nid = max((i.get("id", 0) for i in items), default=0) + 1
        items.append({"id": nid, "kind": kind, "text": text, "added": date.today().isoformat()})
        _write_json(LONG_FILE, items)
    return f"Запам'ятала ({MEMORY_KINDS[kind]}): {text}"

def forget(what: str) -> str:
    with _data_lock:
        items = _load_long()
        item, err = _find(items, what)
        if not item:
            return err
        items.remove(item)
        _write_json(LONG_FILE, items)
    return f"Забула: {item['text']}"

def show_memory() -> str:
    items = _load_long()
    if not items:
        return "Довга пам'ять порожня."
    return "\n".join(f"№{i['id']} [{MEMORY_KINDS.get(i.get('kind'), 'факт')}] {i['text']}" for i in items)

def memory_prompt() -> str:
    items = _load_long()
    rules = [str(i["text"]) for i in items if i.get("kind") == "style"]
    facts = [str(i["text"]) for i in items if i.get("kind") != "style"]
    out = []
    if rules:
        out.append("Правила від користувача (виконуй їх, вони важливіші за твій звичайний стиль): " + "; ".join(rules) + ".")
    if facts:
        out.append("Що ти пам'ятаєш про користувача: " + "; ".join(facts) + ".")
    return " ".join(out)

def _load_tasks() -> list:
    d = _read_json(TASKS_FILE, [])
    return d if isinstance(d, list) else []

def _parse_day(s: str) -> str | None:
    s = (s or "").strip().lower()
    today = date.today()
    if s in ("today", "сьогодні", "сегодня"):
        return today.isoformat()
    if s in ("tomorrow", "завтра"):
        return (today + timedelta(days=1)).isoformat()
    if s in ("післязавтра", "послезавтра"):
        return (today + timedelta(days=2)).isoformat()
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        return None

def _parse_time(s: str) -> str | None:
    m = re.fullmatch(r"(\d{1,2})[:.](\d{2})", (s or "").strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None

def add_task(text: str, day: str = "", at: str = "") -> str:
    text = " ".join(str(text).split())[:200]
    if not text:
        return "Порожній план."
    t = ""
    if str(at).strip():
        t = _parse_time(str(at))
        if t is None:
            return "Не зрозуміла час. Потрібен формат ГГ:ХХ, наприклад 18:30."
    d = ""
    if str(day).strip():
        d = _parse_day(str(day))
        if d is None:
            return "Не зрозуміла дату. Скажи «сьогодні», «завтра» або РРРР-ММ-ДД."
    elif t:
        d = date.today().isoformat()
    notified, note = False, ""
    if d and t and datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M") < datetime.now() - timedelta(minutes=1):
        notified, note = True, " (цей час уже минув, нагадування не буде)"
    with _data_lock:
        items = _load_tasks()
        nid = max((i.get("id", 0) for i in items), default=0) + 1
        items.append({"id": nid, "text": text, "date": d, "time": t, "done": False, "notified": notified})
        _write_json(TASKS_FILE, items)
    when = (d + (" " + t if t else "")) if d else "без дати"
    return f"Додано план №{nid}: {text} ({when}){note}"

def list_tasks(day: str = "today") -> str:
    key = (str(day) or "today").strip().lower()
    items = _load_tasks()
    today = date.today().isoformat()
    show_dates = False
    if key in ("all", "усі", "всі", "все"):
        sel, title, show_dates = [i for i in items if not i.get("done")], "Усі невиконані плани", True
    else:
        d = _parse_day(key)
        if d is None:
            return "Не зрозуміла дату. Скажи «сьогодні», «завтра», РРРР-ММ-ДД або all."
        if d == today:
            sel = [i for i in items if i.get("date") == today or (not i.get("done") and (not i.get("date") or i["date"] < today))]
            title = "Плани на сьогодні"
        else:
            sel, title = [i for i in items if i.get("date") == d], f"Плани на {d}"
    if not sel:
        return f"{title}: порожньо."
    sel.sort(key=lambda i: (i.get("date") or "9999-99-99", i.get("time") or "99:99", i.get("id", 0)))
    lines = []
    for i in sel:
        line = f"№{i['id']} " + (f"{i['time']} — " if i.get("time") else "") + str(i.get("text", ""))
        if i.get("done"):
            line += " ✓"
        elif i.get("date") and i["date"] < today:
            line += f" (прострочено, {i['date']})"
        elif not i.get("date"):
            line += " (без дати)"
        elif show_dates:
            line += f" [{i['date']}]"
        lines.append(line)
    return f"{title}:\n" + "\n".join(lines)

def complete_task(task: str) -> str:
    with _data_lock:
        items = _load_tasks()
        item, err = _find(items, task)
        if not item:
            return err
        item["done"] = True
        _write_json(TASKS_FILE, items)
    return f"Позначила виконаним: {item['text']}"

def remove_task(task: str) -> str:
    with _data_lock:
        items = _load_tasks()
        item, err = _find(items, task)
        if not item:
            return err
        items.remove(item)
        _write_json(TASKS_FILE, items)
    return f"Видалила план: {item['text']}"

def due_reminders() -> list[str]:
    now = datetime.now()
    out = []
    with _data_lock:
        items = _load_tasks()
        changed = False
        for t in items:
            if t.get("done") or t.get("notified") or not t.get("time") or not t.get("date"):
                continue
            try:
                due = datetime.strptime(f"{t['date']} {t['time']}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            if due <= now:
                t["notified"], changed = True, True
                out.append((f"{t['time']}" if due.date() == now.date() else f"{t['date']} {t['time']}") + f" — {t['text']}")
        if changed:
            _write_json(TASKS_FILE, items)
    return out

SYSTEM_PROMPT = (
SYSTEM_PROMPT = (
    "Ти — Ріас Гремори, благородна демонічна дівчина з аніме «Старша школа DXD». "
    "Ти — локальний помічник користувача на робочому столі, працюєш виключно через Ollama, "
    "без зовнішніх API-ключів і без хмарних сервісів. "
    "\n\n"
    "Твоя манера поведінки: "
    "• впевнена, розумна, з легким шармом, але завжди ввічлива і поважна; "
    "• не груба, але має характер аристократки; "
    "• можеш іноді додати ледь помітний гумор, але без нахабства; "
    "• звертаєшся до користувача з повагою, але без надмірної скромності; "
    "• якщо запит простий — відповідай швидко і коротко; "
    "• якщо складний — приділяй більше уваги якості, точності та перевірці. "
    "\n\n"
    "Для простих повсякденних текстових запитів відповідай максимально швидко, коротко і без зайвого обдумування. "
    "Для складних запитів — програмування, дебаг, логіка, математика, технічні задачі — приділяй більше уваги точності, перевірці і якості. "
    "Не вигадуй «систему мислення» чи складний роутер моделей. Просто адаптуй глибину відповіді до складності запиту. "
    "Завжди залишайся локальною, коректною і розумною."
)
)
TOOL_RULES = {
    "apps": "Програми відкривай через open_app, сайти через open_url. ",
    "files": "Файли й код створюй у робочій папці: create_file або generate_code_file. ",
    "memory": "Довга пам'ять: remember, forget, show_memory. ",
    "tasks": "Плани: add_task, list_tasks, complete_task, remove_task. ",
}
TOOL_TAIL = "Коли просять щось зробити — викликай відповідний інструмент, а не описуй дію словами. " \
            "Після дії коротко скажи, що саме зроблено. Не вигадуй результатів."
TOOL_GROUPS = {
    "apps": ("open_app", "list_apps", "find_app", "add_app", "remove_app", "open_url"),
    "files": ("create_file", "read_file", "list_files", "open_file", "open_workspace", "run_python", "generate_code_file"),
    "memory": ("remember", "forget", "show_memory"),
    "tasks": ("add_task", "list_tasks", "complete_task", "remove_task"),
}
GROUP_RX = {
    "apps": re.compile(r"відкр|запуск|запусти|програм|браузер|youtube|http|www\.|\.com|\.ua|\.org|steam|блокнот|калькулятор|список|open|launch|browser|apps", re.I),
    "files": re.compile(r"файл|створи|створ|напиш|код|скрипт|html|\.py|\.txt|python|робоч|збережи|прочитай|create|write|code|script|folder|workspace", re.I),
    "memory": re.compile(r"запам|пам.ят|забудь|будь|будьте|звертайся|поводься|remember|forget|memory|веди себя", re.I),
    "tasks": re.compile(r"план|нагад|задач|мої справи|сьогодні|завтра|remind|task|today|tomorrow", re.I),
}

def select_groups(user_text: str, prev_reply: str = "") -> list[str]:
    text = user_text.lower()
    if len(text) < 25 and prev_reply:
        text += " " + prev_reply.lower()
    groups = [g for g, rx in GROUP_RX.items() if rx.search(text)]
    return groups

def _tool(name, desc, props, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
                "required": required,
            },
        },
    }

def build_tools(only: set | None = None) -> list[dict]:
    tools = [
        _tool("open_app", "Відкрити програму зі списку дозволених: " + ", ".join(APPS), {"name": "Назва програми"}, ["name"]),
        _tool("list_apps", "Показати список програм, які можна відкривати", {}, []),
        _tool("find_app", "Знайти програму на ПК за назвою", {"query": "Назва програми"}, ["query"]),
        _tool("add_app", "Додати програму до списку дозволених", {"name": "Коротка назва", "path": "Повний шлях до .exe, .lnk або .url"}, ["name", "path"]),
        _tool("remove_app", "Прибрати програму зі списку", {"name": "Назва програми"}, ["name"]),
        _tool("open_url", "Відкрити сайт у браузері", {"url": "Адреса https://..."}, ["url"]),
        _tool("create_file", "Створити або перезаписати файл у робочій папці", {"path": "Відносний шлях", "content": "Повний вміст файлу"}, ["path", "content"]),
        _tool("read_file", "Прочитати файл із робочої папки", {"path": "Відносний шлях"}, ["path"]),
        _tool("list_files", "Показати файли в робочій папці", {}, []),
        _tool("open_file", "Відкрити файл у програмі за замовчуванням", {"path": "Відносний шлях до файлу"}, ["path"]),
        _tool("open_workspace", "Відкрити робочу папку", {}, []),
        _tool("run_python", "Запустити .py файл", {"path": "Відносний шлях до .py"}, ["path"]),
        _tool("remember", "Запам'ятати правило або факт", {"text": "Що запам'ятати", "kind": "style або fact"}, ["text"]),
        _tool("forget", "Забути запис із довгої пам'яті", {"what": "Номер або текст"}, ["what"]),
        _tool("show_memory", "Показати довгу пам'ять", {}, []),
        _tool("add_task", "Додати план або нагадування", {"text": "Що треба зробити", "day": "сьогодні, завтра або YYYY-MM-DD", "at": "Час HH:MM"}, ["text"]),
        _tool("list_tasks", "Показати плани на день або всі", {"day": "сьогодні, завтра, YYYY-MM-DD або all"}, []),
        _tool("complete_task", "Позначити план виконаним", {"task": "Номер або частина тексту"}, ["task"]),
        _tool("remove_task", "Видалити план", {"task": "Номер або частина тексту"}, ["task"]),
    ]
    if CODE_MODEL:
        tools.append(_tool("generate_code_file", "Написати код файлу спеціальною моделлю для коду", {"path": "Відносний шлях", "task": "Докладний опис"}, ["path", "task"]))
    if only is not None:
        tools = [t for t in tools if t["function"]["name"] in only]
    return tools

confirm_fn = lambda text: False  # noqa: E731

def _safe(rel: str) -> Path:
    p = (WORKSPACE / rel).resolve()
    if not p.is_relative_to(WORKSPACE):
        raise ValueError("Шлях виходить за межі робочої папки")
    return p

def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        s = s.rstrip()
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()

def _resolve_app(name: str) -> str | None:
    key = name.strip().lower()
    if key in APPS:
        return key
    matches = [k for k in APPS if key and (key in k or k in key)]
    return matches[0] if len(matches) == 1 else None

def open_app(name: str) -> str:
    key = _resolve_app(name)
    if not key:
        return f"'{name}' немає в списку дозволених. Доступні: {', '.join(APPS)}"
    os.startfile(APPS[key])
    return f"Запущено: {key}"

def list_apps() -> str:
    return ", ".join(APPS)

def find_app(query: str) -> str:
    q = query.strip().lower()
    if not q:
        return "Вкажи, що шукати."
    roots = []
    if os.environ.get("ProgramData"):
        roots.append(Path(os.environ["ProgramData"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if os.environ.get("APPDATA"):
        roots.append(Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    roots += [Path.home() / "Desktop", Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"]
    found, seen = [], set()
    for root in roots:
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if f.suffix.lower() not in {".lnk", ".exe", ".url"} or q not in f.stem.lower():
                continue
            if re.search(r"uninstall|видал|удал", f.stem, re.I) or str(f).lower() in seen:
                continue
            seen.add(str(f).lower())
            found.append(f"{f.stem} → {f}")
            if len(found) >= 8:
                break
        if len(found) >= 8:
            break
    if not found:
        return "Нічого не знайшла. Попроси користувача дати повний шлях до .exe або ярлика."
    return "\n".join(found)

def add_app(name: str, path: str) -> str:
    key = name.strip().lower()
    if not key:
        return "Потрібна назва програми."
    p = Path(path.strip().strip('"'))
    if not p.is_file() or p.suffix.lower() not in {".exe", ".lnk", ".url"}:
        return "Файл не знайдено, або це не .exe / .lnk / .url."
    replaced = key in APPS
    if not confirm_fn(f"Додати програму {key} -> {p}?"):
        return "Користувач відмовився."
    CUSTOM_APPS[key] = str(p)
    APPS[key] = str(p)
    _save_custom_apps()
    return f"Додано до списку: {key}"

def remove_app(name: str) -> str:
    key = name.strip().lower()
    if key in CUSTOM_APPS:
        del CUSTOM_APPS[key]
        APPS.pop(key, None)
        _save_custom_apps()
        return f"Прибрано зі списку: {key}"
    if key in APPS:
        return "Це вбудована програма, її можна прибрати тільки в коді."
    return f"'{name}' немає в списку."

def open_url(url: str) -> str:
    if not url.lower().startswith(("http://", "https://")):
        return "Дозволені тільки адреси http/https."
    webbrowser.open(url)
    return f"Відкрито: {url}"

def create_file(path: str, content: str) -> str:
    p = _safe(path)
    existed = p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"{'Оновлено' if existed else 'Створено'}: {p.relative_to(WORKSPACE)} ({len(content)} символів)"

def read_file(path: str) -> str:
    p = _safe(path)
    if not p.is_file():
        return "Такого файлу немає."
    return p.read_text(encoding="utf-8", errors="replace")[:4000]

def list_files() -> str:
    files = [str(f.relative_to(WORKSPACE)) for f in WORKSPACE.rglob("*") if f.is_file()]
    return "\n".join(files[:100]) or "Робоча папка порожня."

BLOCKED_OPEN = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse",
                ".wsf", ".wsh", ".hta", ".reg", ".lnk", ".url", ".jar", ".py", ".pyw", ".dll", ".sys"}

def open_file(path: str) -> str:
    p = _safe(path)
    if not p.is_file():
        return "Такого файлу немає в робочій папці."
    if p.suffix.lower() in BLOCKED_OPEN:
        return "Програми й скрипти я напряму не відкриваю (для .py є run_python)."
    os.startfile(p)
    return f"Відкрито: {p.name}"

def open_workspace() -> str:
    os.startfile(WORKSPACE)
    return f"Відкрито папку {WORKSPACE}"

def _python_cmd() -> str | None:
    if not getattr(sys, "frozen", False):
        return sys.executable
    return shutil.which("python") or shutil.which("py")

def run_python(path: str) -> str:
    p = _safe(path)
    if p.suffix != ".py" or not p.is_file():
        return "Це не існуючий .py файл."
    py = _python_cmd()
    if not py:
        return "Щоб запускати .py файли, потрібен встановлений Python."
    preview = p.read_text(encoding="utf-8", errors="replace")[:500]
    if not confirm_fn(f"Запустити {p.name}?\n\n{preview}"):
        return "Користувач відмовився запускати."
    try:
        r = subprocess.run([py, str(p)], cwd=WORKSPACE, capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                           text=True, timeout=30, encoding="utf-8", errors="replace")
        out = (r.stdout + r.stderr).strip()
        return (out[:2000] or "(без виводу)") + f"\n[код завершення {r.returncode}]"
    except subprocess.TimeoutExpired:
        return "Перервано: працює довше 30 секунд."

def _ollama_unload(model: str):
    if not model:
        return
    try:
        requests.post(OLLAMA_BASE + "/api/generate", json={"model": model, "keep_alive": 0, "stream": False}, timeout=120)
    except requests.RequestException:
        pass

def _prepare_model(model: str):
    if not model or not MODEL_SWITCH:
        return
    others = {CHAT_MODEL, CODE_MODEL}
    others.discard(model)
    for other in others:
        if other:
            _ollama_unload(other)

def _model_is_installed(model: str) -> tuple[bool, list[str]]:
    if not model:
        return False, []
    try:
        data = requests.get(OLLAMA_BASE + "/api/tags", timeout=5).json()
        installed = [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]
        have = model in installed or f"{model}:latest" in installed
        return have, installed
    except (requests.RequestException, ValueError):
        return False, []

def generate_code_file(path: str, task: str) -> str:
    p = _safe(path)
    if not CODE_MODEL:
        return "Окрема модель для коду вимкнена (CODE_MODEL порожній)."
    installed, names = _model_is_installed(CODE_MODEL)
    if not installed:
        available = ", ".join(names) or "нічого"
        return f"Модель коду «{CODE_MODEL}» не знайдена в Ollama. Встанови її командою: ollama pull {CODE_MODEL}. Є: {available}"
    prompt = f"Файл: {p.name}\nЗавдання: {task}"
    if p.is_file():
        old = p.read_text(encoding="utf-8", errors="replace")[:20000]
        prompt = (f"Файл: {p.name}\nЗавдання: {task}\n\nПоточний вміст файлу:\n{old}\n\n"
                  "Внеси зміни за завданням і поверни ВЕСЬ оновлений файл. "
                  "Перед фінальною відповіддю перевір синтаксис, логіку, імпорти та очевидні помилки. ")
    else:
        prompt += "\n\nНапиши завершений робочий файл. Перед відповіддю перевір синтаксис, логіку, імпорти та очевидні помилки."
    _prepare_model(CODE_MODEL)
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": CODE_MODEL,
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0.2, "num_ctx": 8192},
            "messages": [{"role": "system", "content": "Ти досвідчений програміст. Відповідай ТІЛЬКИ повним кодом файлу, без пояснень."}, {"role": "user", "content": prompt}],
        }, timeout=900)
        r.raise_for_status()
        data = r.json()
        code = _strip_fences(clean_reply(data["message"]["content"]))
        if not code:
            return "Модель коду повернула порожню відповідь."
        return create_file(path, code)
    except requests.RequestException as e:
        return f"Помилка моделі коду «{CODE_MODEL}»: {e}"
    finally:
        if MODEL_SWITCH:
            _ollama_unload(CODE_MODEL)

TOOL_FUNCS = {
    "open_app": open_app, "list_apps": list_apps, "find_app": find_app, "add_app": add_app,
    "remove_app": remove_app, "open_url": open_url, "create_file": create_file,
    "read_file": read_file, "list_files": list_files, "open_workspace": open_workspace,
    "run_python": run_python, "generate_code_file": generate_code_file, "open_file": open_file,
    "remember": remember, "forget": forget, "show_memory": show_memory, "add_task": add_task,
    "list_tasks": list_tasks, "complete_task": complete_task, "remove_task": remove_task,
}

ARG_ALIASES = {"filename": "path", "file_name": "path", "file": "path", "filepath": "path", "file_path": "path",
               "code": "content", "html": "content", "body": "content", "data": "content", "text": "content",
               "app": "name", "program": "name", "application": "name",
               "link": "url", "site": "url", "address": "url", "description": "task", "prompt": "task"}

def run_tool(name: str, args: dict) -> str:
    fn = TOOL_FUNCS.get(name)
    if not fn:
        return f"Невідомий інструмент: {name}"
    try:
        if isinstance(args, str):
            args = json.loads(args)
        args = dict(args or {})
        accepted = inspect.signature(fn).parameters
        for k in list(args):
            alias = ARG_ALIASES.get(k)
            if k not in accepted and alias in accepted and alias not in args:
                args[alias] = args.pop(k)
        return fn(**{k: v for k, v in args.items() if k in accepted})
    except Exception as e:
        return f"Помилка інструмента {name}: {e}"

history: list[dict] = []
HISTORY_SEND = 14

def _load_history():
    if HISTORY_KEEP <= 0:
        return
    data = _read_json(HISTORY_FILE, [])
    if isinstance(data, list):
        history.extend({"role": m["role"], "content": m["content"]} for m in data
                        if isinstance(m, dict) and m.get("role") in ("user", "assistant")
                        and isinstance(m.get("content"), str))
        del history[:-HISTORY_KEEP]

def _save_history():
    if len(history) > 60:
        del history[:-60]
    if HISTORY_KEEP > 0:
        with _data_lock:
            _write_json(HISTORY_FILE, history[-HISTORY_KEEP:])

def clear_history():
    history.clear()
    with _data_lock:
        _write_json(HISTORY_FILE, [])

def _drop_message(msg: dict):
    for i in range(len(history) - 1, -1, -1):
        if history[i] is msg:
            del history[i]
            return

_load_history()

def clean_reply(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"<tool_call>.*?(</tool_call>|$)", "", text, flags=re.S)
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()

_TOOL_TEXT = re.compile(r"<tool_call>\s*(\{.*?\})\s*(?:</tool_call>|$)", re.S)

def parse_text_tool_calls(text: str) -> list:
    out = []
    for m in _TOOL_TEXT.finditer(text or ""):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("name") in TOOL_FUNCS:
            out.append({"function": {"name": d["name"], "arguments": d.get("arguments") or d.get("parameters") or {}}})
    if not out:
        raw = (text or "").strip()
        if raw.startswith("{") and raw.endswith("}"):
            try:
                d = json.loads(raw)
            except ValueError:
                d = None
            if isinstance(d, dict) and d.get("name") in TOOL_FUNCS:
                out.append({"function": {"name": d["name"], "arguments": d.get("arguments") or d.get("parameters") or {}}})
    return out

DEBUG_FILE = BASE_DIR / "ria_debug.log"
_log_lock = threading.Lock()

def dlog(msg: str):
    if not DEBUG_LOG:
        return
    try:
        with _log_lock:
            if DEBUG_FILE.exists() and DEBUG_FILE.stat().st_size > 300_000:
                DEBUG_FILE.write_text(DEBUG_FILE.read_text(encoding="utf-8", errors="replace")[-150_000:], encoding="utf-8")
            with DEBUG_FILE.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except OSError:
        pass

def _clip(text, n: int = 700) -> str:
    text = str(text)
    return text if len(text) <= n else text[:n] + "…"

def build_system_prompt(groups: list | None = None) -> str:
    lang_hint = f"Мова інтерфейсу користувача: {LANG_PROMPT_NAMES.get(LANG, 'українська')}; якщо мова його повідомлення незрозуміла — відповідай українською або російською природно."
    rules = " ".join(TOOL_RULES[g] for g in (groups or []) if g in TOOL_RULES)
    tail = TOOL_TAIL if groups else ""
    return " ".join(p for p in (SYSTEM_PROMPT, rules, tail, lang_hint, now_prompt(), memory_prompt()) if p)

ACTION_REQUEST = re.compile(r"відкр|запуст|створ|напиш|зроби|збережи|додай|нагад|запам|забудь|прибери|познач|хочу|потрібн|треба|open|launch|run|create|write|make|save|add|remind|remember|forget|remove|need|want", re.I)
CLAIMS_DONE = re.compile(r"(створила|створив|створено|зробила|зробив|зроблено|відкрила|відкрив|відкрито|запустила|запустив|запущено|додала|додав|додано|записала|записано|зберегла|зберіг|збережено|запам'ятала|запам'ятав|видалила|видалено|прибрала|прибрано|готово|created|opened|launched|saved|added|removed|done|finished)", re.I)

AI_GENERATION_STOP = threading.Event()

def clear_stop_generation():
    AI_GENERATION_STOP.clear()

def stop_generation():
    AI_GENERATION_STOP.set()

def ask(user_text: str, actions: list | None = None, stop_event: threading.Event | None = None) -> str:
    actions = actions if actions is not None else []
    stop_event = stop_event or AI_GENERATION_STOP

    if stop_event.is_set():
        return "Скасовано."

    prev_reply = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), "")
    user_msg = {"role": "user", "content": user_text}
    history.append(user_msg)

    groups = select_groups(user_text, prev_reply)
    names = {n for g in groups for n in TOOL_GROUPS[g]}
    tools = build_tools(names) if groups else []

    recent = [{"role": m["role"], "content": _clip(m["content"])} for m in history[-HISTORY_SEND:-1]] + [user_msg]
    msgs = [{"role": "system", "content": build_system_prompt(groups)}] + recent
    dlog(f"USER {_clip(user_text, 200)!r} | groups={groups} tools={[t['function']['name'] for t in tools]}")

    used_tools = nudged = False

    try:
        for _ in range(6):
            if stop_event.is_set():
                _drop_message(user_msg)
                return "Відповідь перервано користувачем."

            msgs[0]["content"] = build_system_prompt(groups)
            _prepare_model(CHAT_MODEL)

            if tools:
                body = {
                    "model": CHAT_MODEL,
                    "messages": msgs,
                    "stream": False,
                    "keep_alive": KEEP_ALIVE,
                    "options": {
                        "temperature": 0.3 if tools else 0.7,
                        "top_p": 0.8,
                        "top_k": 20,
                        "num_ctx": 8192,
                    },
                    "tools": tools,
                }
                r = requests.post(OLLAMA_URL, json=body, timeout=600)
                r.raise_for_status()
                data = r.json()
                m = data["message"]
                calls = m.get("tool_calls")
                if not calls and tools:
                    calls = parse_text_tool_calls(m.get("content") or "")
                    if calls:
                        m = {"role": "assistant", "content": "", "tool_calls": calls}
                        dlog("tool call recovered from plain text")

                msgs.append(m)
                dlog(f"LLM prompt_tokens={data.get('prompt_eval_count')} out_tokens={data.get('eval_count')} "
                     f"tool_calls={[c['function']['name'] for c in calls] if calls else None} "
                     f"text={_clip(m.get('content') or '', 160)!r}")

                if not calls:
                    text = clean_reply(m.get("content") or "") or "…"
                    if (tools and not used_tools and ACTION_REQUEST.search(user_text)
                            and CLAIMS_DONE.search(text) and not text.rstrip().endswith("?")):
                        dlog("GUARD: claimed done without a tool call" + (" (second time)" if nudged else ""))
                        if not nudged:
                            nudged = True
                            msgs.append({"role": "user", "content": "[службове] Ти не викликала жодного інструмента, тож нічого не зроблено. Виклич потрібний інструмент зараз, потім відповідай."})
                            continue
                        text = t("err_no_action")
                    history.append({"role": "assistant", "content": text})
                    _save_history()
                    return text

                for c in calls:
                    fn = c["function"]["name"]
                    args = c["function"].get("arguments") or {}
                    result = run_tool(fn, args)
                    used_tools = True
                    one_line = " ".join(str(result).split())
                    actions.append(f"{fn} → {one_line[:70]}{'…' if len(one_line) > 70 else ''}")
                    dlog(f"TOOL {fn}({_clip(json.dumps(args, ensure_ascii=False) if not isinstance(args, str) else args, 200)}) "
                         f"-> {_clip(one_line, 200)!r}")
                    msgs.append({"role": "tool", "tool_name": fn, "content": result})
            else:
                body = {
                    "model": CHAT_MODEL,
                    "messages": msgs,
                    "stream": True,
                    "keep_alive": KEEP_ALIVE,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.8,
                        "top_k": 20,
                        "num_ctx": 8192,
                    },
                }
                r = requests.post(OLLAMA_URL, json=body, timeout=600, stream=True)
                chunks = []
                for line in r.iter_lines(decode_unicode=True):
                    if stop_event.is_set():
                        break
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    content = (obj.get("message") or {}).get("content") or ""
                    if content:
                        chunks.append(content)

                text = clean_reply("".join(chunks)) or "…"
                history.append({"role": "assistant", "content": text})
                _save_history()
                return text

        _drop_message(user_msg)
        return t("err_steps")

    except requests.ConnectionError:
        _drop_message(user_msg)
        dlog("ERROR Ollama connection")
        return t("err_ollama")
    except Exception as e:
        _drop_message(user_msg)
        dlog(f"ERROR {e!r}")
        return t("err_generic", e=e)

def diagnose() -> str:
    lines = []
    try:
        requests.get(OLLAMA_BASE, timeout=3)
        lines.append("OK    Ollama відповідає")
    except requests.RequestException as e:
        lines.append(f"FAIL  Ollama не відповідає ({e.__class__.__name__})")
        return "\n".join(lines)
    try:
        installed = [m.get("name", "") for m in requests.get(OLLAMA_BASE + "/api/tags", timeout=5).json().get("models", [])]
        have = CHAT_MODEL in installed or f"{CHAT_MODEL}:latest" in installed
        lines.append(("OK    " if have else "FAIL  ") + f"модель {CHAT_MODEL}" + ("" if have else f" не встановлена. Є: {', '.join(installed) or 'нічого'}"))
    except Exception as e:
        lines.append(f"FAIL  список моделей: {e}")
    return "\n".join(lines)

OLLAMA_BASE = OLLAMA_URL.rsplit("/api/", 1)[0]
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_ollama_proc = None

def _ollama_api_ready(timeout: float = 1.5) -> bool:
    try:
        r = requests.get(OLLAMA_BASE + "/api/tags", timeout=timeout)
        return r.ok
    except requests.RequestException:
        return False

def ensure_ollama():
    global _ollama_proc
    if _ollama_api_ready():
        return
    exe = shutil.which("ollama")
    if not exe and os.environ.get("LOCALAPPDATA"):
        cand = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe"
        exe = str(cand) if cand.exists() else None
    if not exe:
        return
    env = dict(os.environ)
    if OLLAMA_MODELS_DIR:
        env["OLLAMA_MODELS"] = OLLAMA_MODELS_DIR
    try:
        _ollama_proc = subprocess.Popen([exe, "serve"], env=env, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW)
    except OSError:
        pass

def startup_tasks():
    ensure_ollama()
    if not PRELOAD_MODEL:
        return
    for _ in range(40):
        if _ollama_api_ready():
            break
        time.sleep(1)
    else:
        return
    try:
        requests.post(OLLAMA_BASE + "/api/generate", json={"model": CHAT_MODEL, "keep_alive": KEEP_ALIVE}, timeout=300)
    except requests.RequestException:
        pass

LANG_ORDER = ("uk", "en", "ru")
LANG_PROMPT_NAMES = {"uk": "українська", "en": "англійська", "ru": "російська"}
STRINGS = {
    "uk": {
        "lang_name": "Українська",
        "greet": "Привіт! Я Ріас. {hotkey} — покликати або сховати. Мене можна тягати мишкою, а Ctrl + колесо мишки змінює розмір.",
        "thinking": "…думаю…",
        "m_copy_sel": "Копіювати виділене", "m_copy_all": "Копіювати все",
        "m_bigger": "Збільшити  (Ctrl + колесо)", "m_smaller": "Зменшити", "m_normal": "Звичайний розмір  (Ctrl+0)",
        "m_settings": "Налаштування", "m_language": "Мова / Language / Язык", "m_theme": "Тема",
        "m_forget": "Забути розмову (коротка пам'ять)",
        "m_quit": "Вийти", "m_quit_ollama": "Вийти і вимкнути Ollama",
        "theme_light": "Світла", "theme_dark": "Темна",
        "chat_forgotten": "Добре, розмову забула. Довга пам'ять і плани на місці.",
        "reminder": "Нагадую:",
        "err_steps": "Забагато кроків, не вийшло завершити.",
        "err_no_action": "Не вийшло: я не змогла викликати потрібний інструмент, тож нічого не зроблено.",
        "m_workspace": "Відкрити робочу папку", "m_diag": "Діагностика (перевірка інструментів)",
        "diag_running": "Перевіряю Ollama, модель та інструменти…", "diag_title": "Діагностика:",
        "err_ollama": "Ollama не запущений. Запусти його і спробуй ще раз.",
        "err_generic": "Помилка: {e}",
        "confirm_add_app": "Додати програму у список дозволених?\n\nНазва: {name}\nШлях: {path}",
        "confirm_replace_app": "Замінити програму у списку дозволених?\n\nНазва: {name}\nШлях: {path}",
        "confirm_run": "Запустити {name}?\n\n{preview}",
    },
    "en": {
        "lang_name": "English",
        "greet": "Hi! I'm Ria. {hotkey} shows or hides me. You can drag me with the mouse, and Ctrl + mouse wheel changes my size.",
        "thinking": "…thinking…",
        "m_copy_sel": "Copy selection", "m_copy_all": "Copy all",
        "m_bigger": "Bigger  (Ctrl + wheel)", "m_smaller": "Smaller", "m_normal": "Normal size  (Ctrl+0)",
        "m_settings": "Settings", "m_language": "Мова / Language / Язык", "m_theme": "Theme",
        "m_forget": "Forget the conversation (short-term memory)",
        "m_quit": "Quit", "m_quit_ollama": "Quit and stop Ollama",
        "theme_light": "Light", "theme_dark": "Dark",
        "chat_forgotten": "Okay, I forgot our conversation. Long-term memory and plans are untouched.",
        "reminder": "Reminder:",
        "err_steps": "Too many steps, I couldn't finish.",
        "err_no_action": "That didn't work: I couldn't call the right tool, so nothing was done.",
        "m_workspace": "Open workspace folder", "m_diag": "Diagnostics (check the tools)",
        "diag_running": "Checking Ollama, the model and the tools…", "diag_title": "Diagnostics:",
        "err_ollama": "Ollama isn't running. Start it and try again.",
        "err_generic": "Error: {e}",
        "confirm_add_app": "Add this program to the allowed list?\n\nName: {name}\nPath: {path}",
        "confirm_replace_app": "Replace this program in the allowed list?\n\nName: {name}\nPath: {path}",
        "confirm_run": "Run {name}?\n\n{preview}",
    },
    "ru": {
        "lang_name": "Русский",
        "greet": "Привет! Я Риас. {hotkey} — позвать или спрятать. Меня можно таскать мышкой, а Ctrl + колесо мыши меняет размер.",
        "thinking": "…думаю…",
        "m_copy_sel": "Копировать выделенное", "m_copy_all": "Копировать всё",
        "m_bigger": "Увеличить  (Ctrl + колесо)", "m_smaller": "Уменьшить", "m_normal": "Обычный размер  (Ctrl+0)",
        "m_settings": "Настройки", "m_language": "Мова / Language / Язык", "m_theme": "Тема",
        "m_forget": "Забыть разговор (краткая память)",
        "m_quit": "Выйти", "m_quit_ollama": "Выйти и выключить Ollama",
        "theme_light": "Светлая", "theme_dark": "Тёмная",
        "chat_forgotten": "Хорошо, разговор забыла. Долгая память и планы на месте.",
        "reminder": "Напоминаю:",
        "err_steps": "Слишком много шагов, не получилось завершить.",
        "err_no_action": "Не вышло: я не смогла вызвать нужный инструмент, так что ничего не сделано.",
        "m_workspace": "Открыть рабочую папку", "m_diag": "Диагностика (проверка инструментов)",
        "diag_running": "Проверяю Ollama, модель и инструменты…", "diag_title": "Диагностика:",
        "err_ollama": "Ollama не запущен. Запусти его и попробуй ещё раз.",
        "err_generic": "Ошибка: {e}",
        "confirm_add_app": "Добавить программу в список разрешённых?\n\nНазвание: {name}\nПуть: {path}",
        "confirm_replace_app": "Заменить программу в списке разрешённых?\n\nНазвание: {name}\nПуть: {path}",
        "confirm_run": "Запустить {name}?\n\n{preview}",
    },
}

UI_FILE = BASE_DIR / "ui.json"
_ui = _read_json(UI_FILE, {})
if not isinstance(_ui, dict):
    _ui = {}

def _detect_lang() -> str:
    try:
        import ctypes
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return {0x22: "uk", 0x19: "ru"}.get(primary, "en")
    except Exception:
        return "en"

LANG = _ui["lang"] if _ui.get("lang") in STRINGS else _detect_lang()

def t(key: str, **kw) -> str:
    text = STRINGS.get(LANG, STRINGS["en"]).get(key) or STRINGS["en"].get(key) or key
    return text.format(**kw) if kw else text

def _save_ui(**changes):
    cur = _read_json(UI_FILE, {})
    if not isinstance(cur, dict):
        cur = {}
    cur.update(changes)
    _write_json(UI_FILE, cur)

def _hotkey_label() -> str:
    return "+".join(part.strip().capitalize() for part in HOTKEY.split("+"))

THEME_KEYS = ("bg", "fg", "outline", "sel_bg", "sel_fg", "sel_inactive", "entry_bg", "entry_fg")
THEMES = {
    "light": {"bg": "#ffffff", "fg": "#000000", "outline": "#000000", "sel_bg": "#9ec5ff", "sel_fg": "#000000",
               "sel_inactive": "#cfe2ff", "entry_bg": "#ffffff", "entry_fg": "#000000"},
    "dark": {"bg": "#1f1f23", "fg": "#f2f2f2", "outline": "#9a9aa6", "sel_bg": "#3b6fb6", "sel_fg": "#ffffff",
              "sel_inactive": "#2d4f80", "entry_bg": "#2a2a30", "entry_fg": "#f2f2f2"},
}
THEME_LABELS: dict[str, str] = {}

def _load_custom_themes():
    data = _read_json(BASE_DIR / "themes.json", {})
    if not isinstance(data, dict):
        return
    for name, spec in data.items():
        if isinstance(name, str) and isinstance(spec, dict) and name not in ("light", "dark"):
            THEMES[name] = {k: spec[k] for k in THEME_KEYS if isinstance(spec.get(k), str)}
            if isinstance(spec.get("label"), str):
                THEME_LABELS[name] = spec["label"]

_load_custom_themes()

def theme_label(name: str) -> str:
    return THEME_LABELS.get(name) or (t("theme_" + name) if name in ("light", "dark") else name)

BASE_W = 640
BASE_FONT = 13
MIN_SCALE, MAX_SCALE = 0.4, 2.0
TRANSPARENT = "#ff00ff"
STATES = ("idle", "thinking", "speaking", "speaking2")

def state_path(name: str) -> Path:
    return BASE_DIR / f"ria_{name}.png"

class Ria:
    def __init__(self):
        global confirm_fn
        self.q: queue.Queue = queue.Queue()
        self.last_reply = ""
        self._cur_main = ""
        self._cur_footer = ""
        self._drag = (0, 0)
        self._speak_job = None
        self._speak_until = 0.0
        self._scale_job = None
        self._pending_scale = None
        self.state = "idle"
        self.generating = False

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        self.root.attributes("-transparentcolor", TRANSPARENT)

        self.sw, self.sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.base_char_h = min(520, int(self.sh * 0.45))
        ui = _read_json(UI_FILE, {})
        ui = ui if isinstance(ui, dict) else {}
        self.scale = ui["scale"] if isinstance(ui.get("scale"), (int, float)) else 1.0
        self.theme_name = ui.get("theme") if ui.get("theme") in THEMES else "light"
        self.theme = self._resolve_theme(self.theme_name)
        self._compute_dims()
        self.bfont = tkfont.Font(family="Segoe UI", size=self._font_size(BASE_FONT))
        self.bubble_h = max(110, int(160 * self.scale))

        bar = tk.Frame(self.root, bg=TRANSPARENT)
        bar.pack(side="bottom", fill="x", padx=20, pady=8)
        th = self.theme

        self.entry = tk.Text(bar, height=3, wrap="word", font=("Segoe UI", self._font_size(12)),
                             bg=th["entry_bg"], fg=th["entry_fg"], insertbackground=th["entry_fg"],
                             relief="flat", bd=0, highlightthickness=2, highlightbackground=th["outline"],
                             highlightcolor=th["outline"], undo=True)
        self.entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.entry.bind("<Return>", self.on_submit)
        self.entry.bind("<Control-Return>", self.on_submit)
        self.entry.bind("<Escape>", lambda e: self.root.withdraw())
        self.entry.bind("<Control-v>", self._paste_entry)
        self.entry.bind("<Control-V>", self._paste_entry)
        self.entry.bind("<Control-a>", self._select_entry_all)
        self.entry.bind("<Control-A>", self._select_entry_all)
        self.entry.bind("<Control-c>", self._copy_entry_selection)
        self.entry.bind("<Control-C>", self._copy_entry_selection)
        self.entry.bind("<Control-x>", self._cut_entry_selection)
        self.entry.bind("<Control-X>", self._cut_entry_selection)
        self.entry.bind("<Shift-Insert>", self._paste_entry)

        self.stop_btn = tk.Button(bar, text="Stop", command=self.stop_generation, bg="#7f1d1d", fg="white",
                                  relief="flat", padx=12, pady=4, bd=0)
        self.stop_btn.pack(side="right", padx=(8, 0))
        self.stop_btn.configure(state="disabled")

        self.entry_menu = tk.Menu(self.root, tearoff=0)
        self.entry_menu.add_command(label="Вставити", command=self._paste_entry)
        self.entry_menu.add_command(label="Виділити все", command=self._select_entry_all)
        self.entry.bind("<Button-3>", self._popup_entry_menu)

        self.canvas = tk.Canvas(self.root, width=self.w, height=self.bubble_h, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack(side="top")
        self.char = tk.Label(self.root, bg=TRANSPARENT)
        self.char.pack(side="top")
        self._load_character()

        self.txt = tk.Text(self.canvas, wrap="word", bg=th["bg"], fg=th["fg"], relief="flat", bd=0,
                           highlightthickness=0, padx=0, pady=0, font=self.bfont, cursor="xterm",
                           state="disabled", exportselection=False,
                           selectbackground=th["sel_bg"], selectforeground=th["sel_fg"],
                           inactiveselectbackground=th["sel_inactive"])
        self.txt.bind("<Button-1>", lambda e: (self.root.focus_force(), self.txt.focus_set()))
        self.txt.bind("<Control-a>", self._select_all)
        self.txt.bind("<Control-c>", lambda e: (self.copy_selection(), "break")[1])
        self.txt.bind("<Button-3>", self._popup_menu)
        self.canvas.bind("<Button-3>", self._popup_menu)

        self.menu = tk.Menu(self.root, tearoff=0)
        self._submenus: list = []
        self._build_menu()

        for w in (self.canvas, self.char, bar):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
        for w in (self.canvas, self.char, bar, self.txt, self.entry):
            w.bind("<Control-MouseWheel>", self._wheel_scale)
        for seq in ("<Control-equal>", "<Control-plus>", "<Control-KP_Add>"):
            self.root.bind(seq, lambda e: self._step_scale(1.15))
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.root.bind(seq, lambda e: self._step_scale(1 / 1.15))
        self.root.bind("<Control-Key-0>", lambda e: self.set_scale(1.0))

        self.root.update_idletasks()
        total = self.root.winfo_reqheight()
        self.x, self.y = self.sw - self.w - 20, self.sh - total - 60
        self.root.geometry(f"+{self.x}+{self.y}")

        confirm_fn = self.confirm
        self.say(t("greet", hotkey=_hotkey_label()))

    def _copy_entry_selection(self, _event=None):
        try:
            text = self.entry.get("sel.first", "sel.last")
        except tk.TclError:
            text = ""
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        return "break"

    def _cut_entry_selection(self, _event=None):
        try:
            text = self.entry.get("sel.first", "sel.last")
            if text:
                self.entry.delete("sel.first", "sel.last")
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
        except tk.TclError:
            pass
        return "break"

    def _paste_entry(self, _event=None):
        try:
            value = self.root.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            self.entry.insert("insert", value)
        except tk.TclError:
            pass
        return "break"

    def _select_entry_all(self, _event=None):
        self.entry.tag_add("sel", "1.0", "end")
        self.entry.mark_set("insert", "end")
        return "break"

    def _popup_entry_menu(self, event):
        try:
            self.entry_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.entry_menu.grab_release()

    def _edit_label(self, key: str) -> str:
        labels = {"paste": {"uk": "Вставити", "ru": "Вставить", "en": "Paste"},
                  "select_all": {"uk": "Виділити все", "ru": "Выделить всё", "en": "Select all"}}
        return labels.get(key, {}).get(LANG, key)

    def _build_menu(self):
        m = self.menu
        m.delete(0, "end")
        for sub in self._submenus:
            sub.destroy()
        self._submenus = []
        m.add_command(label=t("m_copy_sel"), command=self.copy_selection)
        m.add_command(label=t("m_copy_all"), command=self.copy_all)
        m.add_separator()
        m.add_command(label=t("m_bigger"), command=lambda: self._step_scale(1.15))
        m.add_command(label=t("m_smaller"), command=lambda: self._step_scale(1 / 1.15))
        m.add_command(label=t("m_normal"), command=lambda: self.set_scale(1.0))
        m.add_separator()

        settings = tk.Menu(m, tearoff=0)
        langs = tk.Menu(settings, tearoff=0)
        themes = tk.Menu(settings, tearoff=0)
        self._submenus += [settings, langs, themes]
        self.lang_var = tk.StringVar(value=LANG)
        self.theme_var = tk.StringVar(value=self.theme_name)
        for code in LANG_ORDER:
            langs.add_radiobutton(label=STRINGS[code]["lang_name"], variable=self.lang_var, value=code,
                                  command=lambda c=code: self.set_language(c))
        for name in THEMES:
            themes.add_radiobutton(label=theme_label(name), variable=self.theme_var, value=name,
                                   command=lambda n=name: self.set_theme(n))
        settings.add_cascade(label=t("m_language"), menu=langs)
        settings.add_cascade(label=t("m_theme"), menu=themes)
        m.add_cascade(label=t("m_settings"), menu=settings)
        m.add_command(label=t("m_workspace"), command=lambda: threading.Thread(target=open_workspace, daemon=True).start())
        m.add_command(label=t("m_diag"), command=self.run_diagnostics)
        m.add_command(label=t("m_forget"), command=self.forget_chat)
        m.add_separator()
        m.add_command(label=t("m_quit"), command=self.quit_app)
        m.add_command(label=t("m_quit_ollama"), command=lambda: self.quit_app(stop_ollama=True))

    def set_language(self, code: str):
        global LANG
        if code not in STRINGS:
            return
        LANG = code
        self._build_menu()
        self.entry_menu.entryconfigure(0, label=self._edit_label("paste"))
        self.entry_menu.entryconfigure(1, label=self._edit_label("select_all"))
        _save_ui(lang=code)

    def _resolve_theme(self, name: str) -> dict:
        base, spec, out = THEMES["light"], THEMES.get(name, THEMES["light"]), {}
        for k in THEME_KEYS:
            v = spec.get(k, base[k])
            try:
                self.root.winfo_rgb(v)
            except tk.TclError:
                v = base[k]
            out[k] = v
        return out

    def set_theme(self, name: str):
        if name not in THEMES:
            return
        self.theme_name, self.theme = name, self._resolve_theme(name)
        th = self.theme
        self.txt.configure(bg=th["bg"], fg=th["fg"], selectbackground=th["sel_bg"],
                           selectforeground=th["sel_fg"], inactiveselectbackground=th["sel_inactive"])
        self.entry.configure(bg=th["entry_bg"], fg=th["entry_fg"], insertbackground=th["entry_fg"],
                             highlightbackground=th["outline"], highlightcolor=th["outline"])
        self.theme_var.set(name)
        self.say(self._cur_main, footer=self._cur_footer)
        _save_ui(theme=name)

    def _max_scale(self) -> float:
        return min(MAX_SCALE, (self.sh * 0.7) / self.base_char_h)

    def _font_size(self, base: int) -> int:
        return max(8, round(base * self.scale))

    def _compute_dims(self):
        self.scale = max(MIN_SCALE, min(float(self.scale), self._max_scale()))
        self.w = int(BASE_W * self.scale)
        self.char_h = int(self.base_char_h * self.scale)
        self.max_bubble_h = max(150, int(self.sh * 0.88) - self.char_h - int(90 * self.scale))

    def _step_scale(self, factor: float):
        base = self._pending_scale if self._pending_scale else self.scale
        self._pending_scale = max(MIN_SCALE, min(self._max_scale(), base * factor))
        if self._scale_job is not None:
            self.root.after_cancel(self._scale_job)
        self._scale_job = self.root.after(70, self._apply_pending_scale)

    def _wheel_scale(self, e):
        self._step_scale(1.1 if e.delta > 0 else 1 / 1.1)
        return "break"

    def _apply_pending_scale(self):
        self._scale_job = None
        s, self._pending_scale = self._pending_scale, None
        if s:
            self.set_scale(s)

    def set_scale(self, s: float):
        self.root.update_idletasks()
        old_total = self.root.winfo_reqheight()
        cx, bottom = self.x + self.w // 2, self.y + old_total
        self.scale = s
        self._compute_dims()
        self.bfont.configure(size=self._font_size(BASE_FONT))
        self.entry.configure(font=("Segoe UI", self._font_size(12)))
        self.canvas.configure(width=self.w)
        self._load_character()
        self.say(self._cur_main, footer=self._cur_footer)
        self.root.update_idletasks()
        new_total = self.root.winfo_reqheight()
        self.x = max(0, min(cx - self.w // 2, max(0, self.sw - self.w)))
        self.y = max(0, bottom - new_total)
        self.root.geometry(f"+{self.x}+{self.y}")
        _save_ui(scale=round(self.scale, 3))

    def _load_character(self):
        self.photos: dict[str, ImageTk.PhotoImage] = {}
        cache: dict[Path, ImageTk.PhotoImage] = {}

        def load(path: Path):
            if path not in cache:
                img = Image.open(path).convert("RGBA")
                ratio = min(self.w / img.width, self.char_h / img.height)
                img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)
                img.putalpha(img.getchannel("A").point(lambda v: 255 if v > 127 else 0))
                cache[path] = ImageTk.PhotoImage(img)
            return cache[path]

        fallback = [state_path("idle"), CHAR_IMAGE]
        for st in STATES:
            candidates = [state_path(st)] + ([state_path("speaking")] if st == "speaking2" else []) + fallback
            for path in candidates:
                if path.exists():
                    self.photos[st] = load(path)
                    break
        self._photo_cache = cache
        if self.photos:
            self.set_state(self.state)
        else:
            self.char.configure(text="(•ᴗ•)", font=("Segoe UI", max(24, int(80 * self.scale))), fg="white", bg="#444444")

    def set_state(self, state: str):
        self.state = state
        if state in self.photos:
            self.char.configure(image=self.photos[state])

    def start_speaking(self, text: str):
        self._stop_speaking()
        self._speak_until = time.time() + min(8.0, max(1.5, len(text) * 0.04))
        self._speak_tick(False)

    def _speak_tick(self, alt: bool):
        if time.time() >= self._speak_until:
            self._speak_job = None
            self.set_state("idle")
            return
        self.set_state("speaking2" if alt else "speaking")
        self._speak_job = self.root.after(280, lambda: self._speak_tick(not alt))

    def _stop_speaking(self):
        if self._speak_job is not None:
            self.root.after_cancel(self._speak_job)
            self._speak_job = None

    def _start_drag(self, e):
        self._drag = (e.x_root - self.x, e.y_root - self.y)

    def _on_drag(self, e):
        self.x, self.y = e.x_root - self._drag[0], e.y_root - self._drag[1]
        self.root.geometry(f"+{self.x}+{self.y}")

    def _resize_bubble(self, new_h: int):
        if new_h == self.bubble_h:
            return
        self.root.update_idletasks()
        old_total = self.root.winfo_reqheight()
        bottom = self.y + old_total
        self.bubble_h = new_h
        self.canvas.configure(height=new_h)
        self.root.update_idletasks()
        new_total = self.root.winfo_reqheight()
        self.y = bottom - new_total
        self.root.geometry(f"+{self.x}+{self.y}")

    def round_rect(self, x1, y1, x2, y2, r=18):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.canvas.create_polygon(pts, smooth=True, fill=self.theme["bg"], outline=self.theme["outline"], width=3)

    def say(self, text: str, reply: bool = False, footer: str = ""):
        if reply:
            self.last_reply = text
        c, txt = self.canvas, self.txt
        c.delete("all")
        text = text if len(text) <= 4000 else text[:4000] + "…"
        self._cur_main, self._cur_footer = text, footer
        if footer:
            text = text + "\n\n" + footer
        u = max(0.6, self.scale)
        pad, top, tail, half = int(16 * u), 6, int(24 * u), int(16 * u)
        max_w = self.w - 2 * pad - int(40 * u)
        longest = max((self.bfont.measure(line) for line in text.split("\n")), default=0)
        tw = min(max_w, max(int(140 * u), longest + 14))
        lh = self.bfont.metrics("linespace")

        txt.configure(state="normal")
        txt.delete("1.0", "end")
        txt.insert("1.0", text)
        if footer:
            txt.tag_add("foot", f"end-1c - {len(footer)}c", "end-1c")
            txt.tag_configure("foot", foreground="#8a8a95")
        txt.configure(state="disabled")

        cx = self.w // 2
        win = c.create_window(cx, top + pad, window=txt, anchor="n", width=tw, height=lh)
        self.root.update_idletasks()
        res = txt.count("1.0", "end-1c", "displaylines")
        lines = res[0] if res else 1
        max_th = max(lh * 3, self.max_bubble_h - top - 2 * pad - tail - 8)
        th = min(lines * lh + 4, max_th)
        c.itemconfigure(win, height=th)
        txt.yview_moveto(0)

        bx1, by1, bx2, by2 = cx - tw // 2 - pad, top, cx + tw // 2 + pad, top + th + 2 * pad
        c.create_polygon(cx - half, by2 - 6, cx + half, by2 - 6, cx, by2 + tail,
                         fill=self.theme["bg"], outline=self.theme["outline"], width=3)
        self.round_rect(bx1, by1, bx2, by2, r=int(18 * u))
        self._resize_bubble(max(int(110 * u), min(by2 + tail + 6, self.max_bubble_h)))

    def _select_all(self, _e=None):
        self.txt.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _popup_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _to_clipboard(self, text: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def copy_selection(self):
        try:
            sel = self.txt.get("sel.first", "sel.last")
        except tk.TclError:
            sel = ""
        if sel:
            self._to_clipboard(sel)

    def copy_all(self):
        self._to_clipboard(self.last_reply or self.txt.get("1.0", "end-1c"))

    def stop_generation(self):
        if not self.generating:
            return
        stop_generation()
        self.stop_btn.configure(state="disabled")

    def run_diagnostics(self):
        self._stop_speaking()
        self.set_state("thinking")
        self.say(t("diag_running"))
        threading.Thread(target=lambda: self.q.put(("say", (t("diag_title") + "\n" + diagnose(), []))), daemon=True).start()

    def forget_chat(self):
        clear_history()
        self._stop_speaking()
        self.set_state("idle")
        self.say(t("chat_forgotten"), reply=True)

    def _check_reminders(self):
        try:
            due = due_reminders()
        except Exception:
            due = []
        if due:
            if self.root.state() == "withdrawn":
                self.root.deiconify(); self.root.lift()
            msg = t("reminder") + "\n" + "\n".join("• " + d for d in due)
            self._stop_speaking(); self.say(msg, reply=True); self.start_speaking(msg)
        self.root.after(15000, self._check_reminders)

    def quit_app(self, stop_ollama: bool = False):
        if stop_ollama:
            for name in ("ollama app.exe", "ollama.exe"):
                subprocess.run(["taskkill", "/f", "/im", name], capture_output=True, creationflags=_NO_WINDOW)
        elif _ollama_proc is not None:
            _ollama_proc.terminate()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.root.destroy()

    def confirm(self, text: str) -> bool:
        done, box = threading.Event(), {"ok": False}
        self.q.put(("confirm", (text, done, box)))
        done.wait()
        return box["ok"]

    def on_submit(self, _event=None):
        if self.generating:
            return

        text = self.entry.get("1.0", "end-1c").strip()
        if not text:
            return

        self.entry.delete("1.0", "end")
        self._stop_speaking()
        self.set_state("thinking")
        self.generating = True
        self.stop_btn.configure(state="normal")
        self.say(t("thinking"))

        def work():
            clear_stop_generation()
            acts: list = []
            try:
                reply = ask(text, acts, stop_event=AI_GENERATION_STOP)
            except Exception as exc:
                reply = f"Помилка: {exc}"
            finally:
                self.q.put(("say", (reply, acts)))
                self.q.put(("generation_done", None))

        threading.Thread(target=work, daemon=True).start()

    def toggle(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify(); self.root.lift(); self.root.focus_force(); self.entry.focus_set()
        else:
            self.root.withdraw()

    def poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "toggle":
                    self.toggle()
                elif kind == "say":
                    reply, acts = payload
                    footer = "\n".join("▸ " + a for a in acts[:4]) if SHOW_ACTIONS and acts else ""
                    self.say(reply, reply=True, footer=footer)
                    self.start_speaking(reply)
                elif kind == "confirm":
                    text, done, box = payload
                    self.root.deiconify(); box["ok"] = messagebox.askyesno("Ріас", text, parent=self.root); done.set()
                elif kind == "generation_done":
                    self.generating = False
                    self.stop_btn.configure(state="disabled")
                    self.set_state("idle")
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def run(self):
        keyboard.add_hotkey(HOTKEY, lambda: self.q.put(("toggle", None)))
        threading.Thread(target=startup_tasks, daemon=True).start()
        self.root.after(100, self.poll)
        self.root.after(5000, self._check_reminders)
        self.root.mainloop()

if __name__ == "__main__":
    try:
        Ria().run()
    except Exception:
        import traceback
        (BASE_DIR / "ria_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise