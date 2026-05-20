# ✦ ChitChats

A lightweight, high-performance note-taking desktop application built with Python, CustomTkinter, and Pandas.

---

## Features

| Feature | Details |
|---|---|
| **Single-click creation** | Hit "＋ New Note" — a blank note appears instantly, cursor ready |
| **Auto-save** | Edits are persisted 2 seconds after you stop typing — no Save button needed |
| **Real-time search** | Filters across title, content, and tags as you type |
| **Tags** | Add comma-separated tags per note; fully searchable |
| **Delete** | ✕ button on each note row; confirms and removes from disk |
| **Dark theme** | Deep blue-grey palette, high-contrast accent colours |
| **CSV persistence** | `notes_db.csv` — portable, human-readable, version-control friendly |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the app

```bash
python app.py
```

> **Python 3.10+** is required (uses `X | Y` type-union syntax).

---

## Project Structure

```
lumina_notes/
├── app.py            # CustomTkinter UI — all widgets, events, callbacks
├── db_manager.py     # Pandas data layer — CRUD + search
├── requirements.txt
├── README.md
└── notes_db.csv      # auto-created on first run
```

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                     app.py  (UI)                     │
│                                                      │
│   Sidebar                  Editor Workspace          │
│  ┌──────────────┐         ┌──────────────────────┐  │
│  │ Search bar   │         │ Tags entry           │  │
│  │ + New Note   │◄──────► │ Title entry          │  │
│  │ Note list    │ select  │ Content textbox      │  │
│  └──────────────┘         └──────────┬───────────┘  │
│                                      │ KeyRelease    │
│                              debounced auto-save     │
└──────────────────────────────────────┼───────────────┘
                                       │
                           ┌───────────▼───────────┐
                           │   db_manager.py        │
                           │   NotesDatabase        │
                           │   (Pandas DataFrame)   │
                           └───────────┬────────────┘
                                       │ atomic write
                                  notes_db.csv
```

### Auto-save flow
1. User types → `<KeyRelease>` fires `_on_content_changed`
2. Any pending save job is cancelled; a new 2 s timer starts
3. After 2 s of inactivity → `_flush_autosave` → `db.update_note` → CSV

### Search flow
1. User types in search box → `StringVar` trace fires
2. 300 ms debounce → `db.search_notes(query)` (Pandas vectorised `str.contains`)
3. Sidebar list rebuilt with filtered results

---

## Customisation

| Setting | Location | Variable |
|---|---|---|
| Auto-save delay | `app.py` | `AUTOSAVE_MS` |
| Search debounce | `app.py` | `SEARCH_DEBOUNCE` |
| Accent colour | `app.py` | `ACCENT`, `ACCENT_HOVER` |
| DB file path | `db_manager.py` | `NotesDatabase(filepath=…)` |
