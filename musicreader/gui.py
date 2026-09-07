"""Small Tk desktop interface for Windows users."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .extractor import LyricExtractor


class MusicReaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MusicReader — Sheet Music Lyrics")
        self.root.geometry("820x620")
        self.source = tk.StringVar()
        self.verse_count = tk.StringVar(value="Auto")
        self.status = tk.StringVar(value="Choose a sheet-music image or PDF.")
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Sheet music").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(frame, textvariable=self.source).grid(
            row=1, column=0, sticky=tk.EW, padx=(0, 8)
        )
        ttk.Button(frame, text="Browse…", command=self._browse).grid(row=1, column=1)

        options = ttk.Frame(frame)
        options.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(12, 12))
        ttk.Label(options, text="Verses:").pack(side=tk.LEFT)
        ttk.Combobox(
            options,
            textvariable=self.verse_count,
            values=["Auto", "1", "2", "3", "4", "5", "6", "7", "8"],
            width=6,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(6, 14))
        self.extract_button = ttk.Button(
            options, text="Extract lyrics", command=self._start
        )
        self.extract_button.pack(side=tk.LEFT)
        ttk.Button(options, text="Save text…", command=self._save).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        self.output = tk.Text(frame, wrap=tk.WORD, font=("Segoe UI", 11), undo=True)
        self.output.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.output.yview)
        scrollbar.grid(row=3, column=2, sticky=tk.NS)
        self.output.configure(yscrollcommand=scrollbar.set)

        ttk.Label(frame, textvariable=self.status).grid(
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(10, 0)
        )
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

    def _browse(self) -> None:
        filename = filedialog.askopenfilename(
            title="Choose sheet music",
            filetypes=[
                ("Sheet music", "*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            self.source.set(filename)

    def _set_status(self, text: str) -> None:
        self.root.after(0, self.status.set, text)

    def _start(self) -> None:
        path = Path(self.source.get().strip())
        if not path.is_file():
            messagebox.showerror("MusicReader", "Choose an existing image or PDF.")
            return
        count = None if self.verse_count.get() == "Auto" else int(self.verse_count.get())
        self.extract_button.configure(state=tk.DISABLED)
        self.output.delete("1.0", tk.END)
        threading.Thread(
            target=self._extract, args=(path, count), daemon=True
        ).start()

    def _extract(self, path: Path, count: int | None) -> None:
        try:
            result = LyricExtractor(verses=count, progress=self._set_status).extract(path)
        except Exception as error:
            self.root.after(0, self._failed, str(error))
            return
        self.root.after(0, self._complete, result.text, result.warnings)

    def _failed(self, error: str) -> None:
        self.extract_button.configure(state=tk.NORMAL)
        self.status.set("Extraction failed.")
        messagebox.showerror("MusicReader", error)

    def _complete(self, text: str, warnings: list[str]) -> None:
        self.extract_button.configure(state=tk.NORMAL)
        self.output.insert("1.0", text)
        self.status.set(
            "Finished."
            if not warnings
            else f"Finished with {len(warnings)} warning(s)."
        )
        if warnings:
            messagebox.showwarning("MusicReader", "\n\n".join(warnings))

    def _save(self) -> None:
        text = self.output.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("MusicReader", "There are no extracted lyrics to save.")
            return
        filename = filedialog.asksaveasfilename(
            title="Save lyrics",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if filename:
            Path(filename).write_text(text + "\n", encoding="utf-8")
            self.status.set(f"Saved {Path(filename).name}.")


def run_gui() -> None:
    root = tk.Tk()
    MusicReaderApp(root)
    root.mainloop()
