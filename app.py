"""
ChitChats — Main Application
CustomTkinter-powered note-taking app backed by a Pandas CSV data layer.
"""

import customtkinter as ctk
from db_manager import NotesDatabase

# ── Palette ──────────────────────────────────────────────────────────────────
BG_DARK        = "#0F1419"   # window / editor background (darker)
SIDEBAR_BG     = "#1A1F2E"   # sidebar panel (improved contrast)
SIDEBAR_HOVER  = "#2A3F5F"   # note-button hover (softer)
ACCENT         = "#0084FF"   # primary button fill (vibrant blue)
ACCENT_HOVER   = "#0065CC"   # primary button hover (darker blue)
ITEM_ACTIVE_BG = "#1F3A5F"   # currently selected note (subtle highlight)
TEXT_PRIMARY   = "#F5F5F5"   # primary text (brighter white)
TEXT_SECONDARY = "#B0B0C0"
TEXT_MUTED     = "#707080"
ENTRY_BG       = "#1A1F2E"   # input fields (consistent with sidebar)
BORDER_COLOR   = "#2A3040"
DANGER_COLOR   = "#FF4444"   # error/delete (improved red)


# ── Colour theme helpers ──────────────────────────────────────────────────────
def make_font(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


# ─────────────────────────────────────────────────────────────────────────────
class NoteListItem(ctk.CTkFrame):
    """A single row in the sidebar note list."""

    def __init__(self, parent, note_id: str, title: str, modified: str,
                 on_select, on_delete, **kwargs):
        super().__init__(parent, fg_color="transparent", corner_radius=6, **kwargs)

        self.note_id   = note_id
        self.on_select = on_select
        self.on_delete = on_delete
        self._active   = False

        self.grid_columnconfigure(0, weight=1)

        # Clickable title label
        self.title_btn = ctk.CTkButton(
            self,
            text=title if title.strip() else "Untitled Note",
            anchor="w",
            font=make_font(12, "normal"),
            fg_color="transparent",
            text_color=TEXT_PRIMARY,
            hover_color=SIDEBAR_HOVER,
            corner_radius=4,
            command=lambda: on_select(note_id),
        )
        self.title_btn.grid(row=0, column=0, sticky="ew", padx=(6, 4), pady=(3, 1))

        # Timestamp + delete row
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="ew", padx=6, pady=(1, 3))
        bottom.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bottom,
            text=modified[:10] if modified else "",
            font=make_font(9),
            text_color=TEXT_MUTED,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.del_btn = ctk.CTkButton(
            bottom,
            text="✕",
            width=22,
            height=18,
            font=make_font(9),
            fg_color="transparent",
            text_color=TEXT_MUTED,
            hover_color=DANGER_COLOR,
            corner_radius=3,
            command=lambda: on_delete(note_id),
        )
        self.del_btn.grid(row=0, column=1, sticky="e")

    def set_active(self, active: bool) -> None:
        self._active = active
        colour = ITEM_ACTIVE_BG if active else "transparent"
        self.configure(fg_color=colour)
        self.title_btn.configure(fg_color=colour)


# ─────────────────────────────────────────────────────────────────────────────
class NotesApp(ctk.CTk):
    """Root application window."""

    # ── constants ─────────────────────────────────────────────────────────────
    AUTOSAVE_MS   = 2_000   # auto-save after 2 s of inactivity
    SEARCH_DEBOUNCE = 300   # ms to wait before firing a search

    def __init__(self) -> None:
        super().__init__()

        # ── Appearance ─────────────────────────────────────────────────────
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=BG_DARK)

        # ── State ──────────────────────────────────────────────────────────
        self.db               = NotesDatabase()
        self.current_note_id: str | None = None
        self._autosave_job:   str | None = None
        self._search_job:     str | None = None
        self._note_items:     list[NoteListItem] = []

        # ── Window ─────────────────────────────────────────────────────────
        self.title("ChitChats")
        self.geometry("1100x680")
        self.minsize(750, 480)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_editor()
        self._refresh_list()
        self._set_editor_enabled(False)

        # ── Bindings ───────────────────────────────────────────────────────
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # ── Auto-restore last opened note ──────────────────────────────────
        self.after(100, self._restore_last_note)

    # ══════════════════════════════════════════════════════════════════════════
    #  BUILD — SIDEBAR
    # ══════════════════════════════════════════════════════════════════════════
    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(
            self, width=280, corner_radius=0,
            fg_color=SIDEBAR_BG, border_width=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(3, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # — Header —
        header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 12))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="✦  ChitChats",
            font=make_font(20, "bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.count_label = ctk.CTkLabel(
            header,
            text="0 notes",
            font=make_font(10),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.count_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        # — Search —
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)

        search_frame = ctk.CTkFrame(self.sidebar, fg_color=ENTRY_BG,
                                    corner_radius=6, border_width=1,
                                    border_color=BORDER_COLOR)
        search_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        search_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame, text="⌕", font=make_font(14),
                     text_color=TEXT_SECONDARY, width=32).grid(row=0, column=0, padx=(8, 0))

        self.search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="Search notes…",
            font=make_font(12),
            fg_color="transparent",
            border_width=0,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED,
        )
        self.search_entry.grid(row=0, column=1, sticky="ew",
                               padx=(4, 8), pady=7)

        # — New Note button —
        self.new_note_btn = ctk.CTkButton(
            self.sidebar,
            text="＋  New Note",
            font=make_font(12, "bold"),
            height=36,
            corner_radius=6,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            command=self._create_new_note,
        )
        self.new_note_btn.grid(row=2, column=0, sticky="ew",
                               padx=12, pady=(0, 10))

        # — Note list —
        self.note_list = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=TEXT_SECONDARY,
        )
        self.note_list.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.note_list.grid_columnconfigure(0, weight=1)

        # — Footer —
        self.status_label = ctk.CTkLabel(
            self.sidebar,
            text="",
            font=make_font(10),
            text_color=TEXT_MUTED,
        )
        self.status_label.grid(row=4, column=0, pady=(0, 12), padx=12)

    # ══════════════════════════════════════════════════════════════════════════
    #  BUILD — EDITOR
    # ══════════════════════════════════════════════════════════════════════════
    def _build_editor(self) -> None:
        self.editor_frame = ctk.CTkFrame(
            self, fg_color=BG_DARK, corner_radius=0,
        )
        self.editor_frame.grid(row=0, column=1, sticky="nsew")
        self.editor_frame.grid_rowconfigure(2, weight=1)
        self.editor_frame.grid_columnconfigure(0, weight=1)

        # — Top toolbar row —
        toolbar = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=36, pady=(24, 12))
        toolbar.grid_columnconfigure(0, weight=1)

        self.tags_entry = ctk.CTkEntry(
            toolbar,
            placeholder_text="Tags (comma-separated)",
            font=make_font(11),
            fg_color=ENTRY_BG,
            border_color=BORDER_COLOR,
            text_color=TEXT_SECONDARY,
            placeholder_text_color=TEXT_MUTED,
            height=32,
            corner_radius=6,
        )
        self.tags_entry.grid(row=0, column=0, sticky="ew")

        self.save_indicator = ctk.CTkLabel(
            toolbar,
            text="",
            font=make_font(10),
            text_color=TEXT_SECONDARY,
        )
        self.save_indicator.grid(row=0, column=1, padx=(16, 0))

        # — White curved note box container —
        self.note_box = ctk.CTkFrame(
            self.editor_frame,
            fg_color="#FFFFFF",
            corner_radius=12,
            border_width=0,
        )
        self.note_box.grid(row=1, column=0, sticky="nsew",
                          padx=28, pady=(12, 24))
        self.note_box.grid_rowconfigure(1, weight=1)
        self.note_box.grid_columnconfigure(0, weight=1)

        # — Title inside the white box —
        self.title_entry = ctk.CTkEntry(
            self.note_box,
            placeholder_text="Note title…",
            font=make_font(24, "bold"),
            fg_color="transparent",
            border_width=0,
            text_color="#1A1A2E",
            placeholder_text_color="#1834C2",
        )
        self.title_entry.grid(row=0, column=0, sticky="ew",
                              padx=20, pady=(16, 0))
        self.title_entry.bind("<KeyRelease>", self._on_content_changed)

        # — Separator inside white box —
        ctk.CTkFrame(self.note_box, height=1,
                     fg_color="#E8E8E8").grid(
            row=0, column=0, sticky="ew", padx=20, pady=(68, 8),
            ipady=0,
        )

        # — Content inside white box —
        self.content_text = ctk.CTkTextbox(
            self.note_box,
            font=make_font(13),
            wrap="word",
            fg_color="transparent",
            border_width=0,
            text_color="#2A2A2A",
            scrollbar_button_color="#B40000",
            scrollbar_button_hover_color="#FF0000",
        )
        self.content_text.grid(row=1, column=0, sticky="nsew",
                               padx=20, pady=(0, 0))
        self.content_text.bind("<KeyRelease>", self._on_content_changed)

        # — Empty-state overlay —
        self.empty_label = ctk.CTkLabel(
            self.editor_frame,
            text="Select a note or create a new one\n\n✦  ChitChats",
            font=make_font(18),
            text_color=TEXT_MUTED,
            justify="center",
        )
        self.empty_label.grid(row=1, column=0, sticky="nsew", padx=28, pady=(12, 24))

    # ══════════════════════════════════════════════════════════════════════════
    #  STATE MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════
    def _set_editor_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.title_entry.configure(state=state)
        self.content_text.configure(state=state)
        self.tags_entry.configure(state=state)
        if enabled:
            self.note_box.grid()
            self.empty_label.grid_remove()
        else:
            self.note_box.grid_remove()
            self.empty_label.grid()

    def _load_note_into_editor(self, note_id: str) -> None:
        """Populate editor widgets from DB."""
        note = self.db.get_note(note_id)
        if note is None:
            return

        self._set_editor_enabled(True)

        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, note["title"])

        self.content_text.delete("1.0", "end")
        self.content_text.insert("1.0", note["content"])

        self.tags_entry.delete(0, "end")
        self.tags_entry.insert(0, note.get("tags", ""))

    def _clear_editor(self) -> None:
        self.title_entry.delete(0, "end")
        self.content_text.delete("1.0", "end")
        self.tags_entry.delete(0, "end")
        self.save_indicator.configure(text="")
        self.current_note_id = None
        self._set_editor_enabled(False)
        self._deselect_all_items()

    # ══════════════════════════════════════════════════════════════════════════
    #  LIST MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════════
    def _refresh_list(self, query: str = "") -> None:
        """Rebuild sidebar list from DB (optionally filtered)."""
        # Destroy old widgets
        for w in self.note_list.winfo_children():
            w.destroy()
        self._note_items.clear()

        notes_df = (
            self.db.search_notes(query) if query
            else self.db.get_all_notes()
        )

        total = self.db.note_count()
        found = len(notes_df)
        if query:
            self.count_label.configure(
                text=f"{found} of {total} note{'s' if total != 1 else ''}"
            )
        else:
            self.count_label.configure(
                text=f"{total} note{'s' if total != 1 else ''}"
            )

        if notes_df.empty:
            lbl = ctk.CTkLabel(
                self.note_list,
                text="No notes found." if query else "No notes yet.",
                font=make_font(12),
                text_color=TEXT_MUTED,
            )
            lbl.pack(pady=20)
            return

        for _, row in notes_df.iterrows():
            modified = str(row.get("last_modified", ""))
            item = NoteListItem(
                self.note_list,
                note_id=row["note_id"],
                title=row["title"],
                modified=modified,
                on_select=self._select_note,
                on_delete=self._delete_note,
            )
            item.pack(fill="x", pady=2)
            self._note_items.append(item)

        self._highlight_active()

    def _deselect_all_items(self) -> None:
        for item in self._note_items:
            item.set_active(False)

    def _highlight_active(self) -> None:
        for item in self._note_items:
            item.set_active(item.note_id == self.current_note_id)

    # ══════════════════════════════════════════════════════════════════════════
    #  ACTIONS
    # ══════════════════════════════════════════════════════════════════════════
    def _create_new_note(self) -> None:
        """Insert a blank note, select it immediately."""
        self._flush_autosave()  # persist any pending edits first
        note_id = self.db.add_note(title="Untitled Note", content="")
        self.current_note_id = note_id
        self._refresh_list(self.search_var.get())
        self._load_note_into_editor(note_id)
        self.title_entry.focus_set()
        # Bind special handler to auto-replace title with content
        self.title_entry.bind("<KeyRelease>", self._on_title_changed)

    def _select_note(self, note_id: str) -> None:
        if note_id == self.current_note_id:
            return
        self._flush_autosave()  # save current before switching
        self.current_note_id = note_id
        self._load_note_into_editor(note_id)
        self._highlight_active()
        self.save_indicator.configure(text="")
        self.db.save_last_note_id(note_id)  # Auto-save selection

    def _delete_note(self, note_id: str) -> None:
        self.db.delete_note(note_id)
        if self.current_note_id == note_id:
            self._clear_editor()
        self._refresh_list(self.search_var.get())
        self._set_status("Note deleted.")

    def _save_current_note(self) -> None:
        """Persist the currently open note to DB."""
        if not self.current_note_id:
            return
        title   = self.title_entry.get().strip() or "Untitled Note"
        content = self.content_text.get("1.0", "end-1c").strip()  # Auto-trim whitespace
        tags    = self.tags_entry.get().strip()
        
        ok = self.db.update_note(self.current_note_id, title, content, tags)
        if ok:
            self.save_indicator.configure(text="✓ Saved")
            self.after(2_000, lambda: self.save_indicator.configure(text=""))
            # Refresh list to reflect updated title / timestamp
            self._refresh_list(self.search_var.get())
            # Auto-save the session (which note is currently open)
            self.db.save_last_note_id(self.current_note_id)

    # ══════════════════════════════════════════════════════════════════════════
    #  AUTO-SAVE  (debounced)
    # ══════════════════════════════════════════════════════════════════════════
    def _on_title_changed(self, _event=None) -> None:
        """Handle title edits with smart placeholder replacement."""
        current_title = self.title_entry.get()
        # If user is editing the default placeholder, trigger auto-save
        if current_title and current_title != "Untitled Note":
            self._on_content_changed(_event)
    
    def _on_content_changed(self, _event=None) -> None:
        """Schedule an auto-save after AUTOSAVE_MS ms of no further changes."""
        self.save_indicator.configure(text="…")
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
        self._autosave_job = self.after(self.AUTOSAVE_MS, self._flush_autosave)

    def _flush_autosave(self) -> None:
        """Actually run the save (cancel any pending job first)."""
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
            self._autosave_job = None
        self._save_current_note()

    # ══════════════════════════════════════════════════════════════════════════
    #  SEARCH  (debounced)
    # ══════════════════════════════════════════════════════════════════════════
    def _on_search_change(self, *_) -> None:
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(
            self.SEARCH_DEBOUNCE,
            lambda: self._refresh_list(self.search_var.get()),
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  UTILITY
    # ══════════════════════════════════════════════════════════════════════════
    def _restore_last_note(self) -> None:
        """Auto-restore the last viewed note from previous session."""
        last_note_id = self.db.load_last_note_id()
        if last_note_id:
            self.current_note_id = last_note_id
            self._load_note_into_editor(last_note_id)
            self._highlight_active()
    
    def _set_status(self, msg: str, duration_ms: int = 2_500) -> None:
        self.status_label.configure(text=msg)
        self.after(duration_ms, lambda: self.status_label.configure(text=""))

    def _on_close(self) -> None:
        """Flush unsaved edits before quitting."""
        self._flush_autosave()
        self.db.save_last_note_id(self.current_note_id)  # Save current note for next session
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = NotesApp()
    app.mainloop()
