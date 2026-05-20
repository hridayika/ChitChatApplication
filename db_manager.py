"""
Lumina Notes — Data Manager
Handles all CRUD operations via Pandas, persisting to a local CSV file.
"""

import os
import uuid
import pandas as pd
import json
import shutil
from datetime import datetime
from pathlib import Path


DB_COLUMNS = ["note_id", "title", "content", "tags", "created_at", "last_modified"]
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
CONFIG_FILE = ".chitchats_config.json"


class NotesDatabase:
    """
    Acts as the data layer for Lumina Notes.
    Loads/saves a CSV file and exposes typed CRUD + search methods.
    """

    def __init__(self, filepath: str = "notes_db.csv") -> None:
        self.filepath = filepath
        self.df: pd.DataFrame = self._load()

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _load(self) -> pd.DataFrame:
        """Load CSV into DataFrame, or bootstrap an empty one."""
        if os.path.exists(self.filepath):
            try:
                df = pd.read_csv(self.filepath, dtype=str)
                # Ensure all expected columns exist (forward-compat)
                for col in DB_COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
                return df[DB_COLUMNS].fillna("")
            except Exception:
                # Corrupted file — start fresh
                pass
        return pd.DataFrame(columns=DB_COLUMNS)

    def _now(self) -> str:
        return datetime.now().strftime(DATETIME_FMT)

    def _save(self) -> None:
        """Commit in-memory DataFrame to disk atomically with auto-backup."""
        tmp = self.filepath + ".tmp"
        self.df.to_csv(tmp, index=False)
        
        # Auto-backup before overwriting
        if os.path.exists(self.filepath):
            backup_dir = ".backups"
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"notes_db_{timestamp}.csv")
            shutil.copy2(self.filepath, backup_path)
            # Clean old backups (keep last 10)
            backups = sorted(Path(backup_dir).glob("notes_db_*.csv"))
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    old_backup.unlink()
        
        os.replace(tmp, self.filepath)          # atomic on POSIX & Windows

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def add_note(self, title: str = "Untitled Note", content: str = "",
                 tags: str = "") -> str:
        """Append a new note; return its note_id."""
        note_id = str(uuid.uuid4())
        now = self._now()
        new_row = pd.DataFrame([{
            "note_id":       note_id,
            "title":         title,
            "content":       content,
            "tags":          tags,
            "created_at":    now,
            "last_modified": now,
        }])
        self.df = pd.concat([new_row, self.df], ignore_index=True)
        self._save()
        return note_id

    def update_note(self, note_id: str, title: str, content: str,
                    tags: str = "") -> bool:
        """Update title / content / tags for an existing note."""
        mask = self.df["note_id"] == note_id
        if not mask.any():
            return False
        self.df.loc[mask, "title"]         = title
        self.df.loc[mask, "content"]       = content
        self.df.loc[mask, "tags"]          = tags
        self.df.loc[mask, "last_modified"] = self._now()
        self._save()
        return True

    def delete_note(self, note_id: str) -> bool:
        """Remove a note by ID."""
        before = len(self.df)
        self.df = self.df[self.df["note_id"] != note_id].reset_index(drop=True)
        if len(self.df) < before:
            self._save()
            return True
        return False

    def get_note(self, note_id: str) -> pd.Series | None:
        """Return a single note row or None."""
        row = self.df[self.df["note_id"] == note_id]
        return row.iloc[0] if not row.empty else None

    def get_all_notes(self) -> pd.DataFrame:
        """Return all notes sorted newest-modified first."""
        if self.df.empty:
            return self.df
        df = self.df.copy()
        df["last_modified"] = pd.to_datetime(df["last_modified"], errors="coerce")
        return df.sort_values("last_modified", ascending=False,
                              na_position="last").reset_index(drop=True)

    def search_notes(self, query: str) -> pd.DataFrame:
        """
        Vectorised case-insensitive substring search across title,
        content, and tags columns.
        """
        if not query.strip() or self.df.empty:
            return self.get_all_notes()

        q = query.strip()
        mask = (
            self.df["title"].str.contains(q, case=False, na=False)
            | self.df["content"].str.contains(q, case=False, na=False)
            | self.df["tags"].str.contains(q, case=False, na=False)
        )
        result = self.df[mask].copy()
        if result.empty:
            return result
        result["last_modified"] = pd.to_datetime(result["last_modified"],
                                                 errors="coerce")
        return result.sort_values("last_modified", ascending=False,
                                  na_position="last").reset_index(drop=True)

    def note_count(self) -> int:
        return len(self.df)
    
    def save_last_note_id(self, note_id: str | None) -> None:
        """Save last opened note ID to config file for restoration on startup."""
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
            except Exception:
                pass
        config["last_note_id"] = note_id
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    
    def load_last_note_id(self) -> str | None:
        """Load last opened note ID from config file."""
        if not os.path.exists(CONFIG_FILE):
            return None
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                note_id = config.get("last_note_id")
                # Verify note still exists
                if note_id and self.get_note(note_id) is not None:
                    return note_id
        except Exception:
            pass
        return None
