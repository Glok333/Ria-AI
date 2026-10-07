"""
Патч для Ria: Ctrl+C/V/A/X у полі введення + оптимізація
Вставити цей код в ria.py, де відповідно до коментарів
"""

# У методі Ria.__init__ де створюється self.entry, додай binding:

ENTRY_BINDINGS = """
        self.entry.bind("<Return>", self.on_submit)
        self.entry.bind("<Control-Return>", self.on_submit)
        self.entry.bind("<Escape>", lambda e: self.root.withdraw())
        
        # CLIPBOARD SUPPORT
        self.entry.bind("<Control-v>", self._paste_entry)
        self.entry.bind("<Control-V>", self._paste_entry)
        self.entry.bind("<Control-a>", self._select_entry_all)
        self.entry.bind("<Control-A>", self._select_entry_all)
        self.entry.bind("<Control-c>", self._copy_entry_selection)
        self.entry.bind("<Control-C>", self._copy_entry_selection)
        self.entry.bind("<Control-x>", self._cut_entry_selection)
        self.entry.bind("<Control-X>", self._cut_entry_selection)
"""

# Додай ці методи в клас Ria:

CLIPBOARD_METHODS = """
    def _copy_entry_selection(self, _event=None):
        \"\"\"Ctrl+C у полі вводу\"\"\"
        try:
            text = self.entry.get("sel.first", "sel.last")
        except tk.TclError:
            text = ""
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        return "break"

    def _cut_entry_selection(self, _event=None):
        \"\"\"Ctrl+X у полі вводу\"\"\"
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
        \"\"\"Ctrl+V у полі вводу\"\"\"
        try:
            text = self.root.clipboard_get()
            self.entry.insert("insert", text)
        except tk.TclError:
            pass
        return "break"

    def _select_entry_all(self, _event=None):
        \"\"\"Ctrl+A у полі вводу\"\"\"
        self.entry.tag_add("sel", "1.0", "end")
        self.entry.mark_set("insert", "end")
        return "break"
"""

# Заміни SYSTEM_PROMPT на цей:

SYSTEM_PROMPT = (
    "Ти — Ріас Гремори, демонічна дівчина, яка живе на робочому столі користувача. "
    "Ти — його локальний помічник, ти працюєш виключно через локальну Ollama, без хмарних сервісів і без API-ключів. "
    "\n\n"
    "Твоя манера поведінки: впевнена, розумна, з легким шармом, але завжди ввічлива й поважна до користувача. "
    "Можеш додати ледь помітний гумор, але без нахабства. Звертаєшся з повагою, але не надмірно скромна. "
    "\n\n"
    "Адаптивність за складністю запиту: "
    "— Для простих повсякденних текстових запитів (переклади, шутки, якщо питання) відповідай максимально швидко, коротко, без зайвого обдумування. "
    "— Для складних запитів (програмування, дебаг, логіка, математика, технічні задачі, аналіз) приділяй більше уваги якості, точності, перевірці відповіді. "
    "Не витрачай ресурси на прості запити, але не жертвуй якістю складних відповідей заради швидкості. "
    "\n\n"
    "Тримайся української мови за замовчуванням, але можеш спілкуватися й російською, якщо користувач просить."
)
