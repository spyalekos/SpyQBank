import os
import sys
import json
import shutil
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from src.models import SchoolType, QuestionItem

logger = logging.getLogger("SpyQBank.Storage")


def get_default_data_dir() -> str:
    """Determine the default writable data directory, with PyInstaller bootstrap support."""
    # When running as a frozen PyInstaller application
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        local_data = os.path.join(exe_dir, "data")
        # If bundled data exists in MEIPASS and local_data doesn't exist yet, bootstrap it
        meipass_data = os.path.join(getattr(sys, "_MEIPASS", ""), "data")
        if os.path.exists(meipass_data) and not os.path.exists(local_data):
            try:
                shutil.copytree(meipass_data, local_data)
            except Exception as ex:
                logger.warning(f"Could not copy bundled data to {local_data}: {ex}")
        if os.path.exists(local_data):
            return local_data
    return os.path.abspath("data")


DATA_DIR = get_default_data_dir()


@dataclass
class ChangeReport:
    school_type_id: int
    class_id: int
    subject_id: int
    checked_at: str
    new_items: List[QuestionItem] = field(default_factory=list)
    updated_items: List[Tuple[QuestionItem, QuestionItem]] = field(default_factory=list)  # (old, new)
    removed_items: List[QuestionItem] = field(default_factory=list)
    total_count: int = 0
    previous_count: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.new_items or self.updated_items or self.removed_items)

    @property
    def summary(self) -> str:
        if not self.has_changes:
            return f"Δεν βρέθηκαν αλλαγές ({self.total_count} θέματα)."
        parts = []
        if self.new_items:
            parts.append(f"+{len(self.new_items)} νέα")
        if self.updated_items:
            parts.append(f"{len(self.updated_items)} τροποποιημένα")
        if self.removed_items:
            parts.append(f"-{len(self.removed_items)} αφαιρεθέντα")
        return f"Αλλαγές: {', '.join(parts)} (Σύνολο: {self.total_count})"


class StorageManager:
    """Manages persistent caching, file storage, and change detection."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or get_default_data_dir()
        self.cache_dir = os.path.join(self.base_dir, "cache")
        self.pdf_cache_dir = os.path.join(self.base_dir, "pdf_cache")
        self.tree_file = os.path.join(self.base_dir, "school_tree.json")
        self.history_file = os.path.join(self.base_dir, "change_history.json")
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.pdf_cache_dir, exist_ok=True)

    def _get_subject_cache_path(self, school_type_id: int, class_id: int, subject_id: int) -> str:
        return os.path.join(self.cache_dir, f"subject_{school_type_id}_{class_id}_{subject_id}.json")

    def save_tree(self, tree: List[SchoolType]) -> None:
        """Save the school tree to disk."""
        data = {
            "saved_at": datetime.now().isoformat(),
            "school_types": [
                {
                    "id": st.id,
                    "name": st.name,
                    "classes": [
                        {
                            "id": cl.id,
                            "name": cl.name,
                            "lessons": [
                                {"id": l.id, "name": l.name}
                                for l in cl.lessons
                            ]
                        }
                        for cl in st.classes
                    ]
                }
                for st in tree
            ]
        }
        with open(self.tree_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_tree(self) -> Optional[List[SchoolType]]:
        """Load the school tree from disk if available."""
        if not os.path.exists(self.tree_file):
            return None
        try:
            with open(self.tree_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [
                SchoolType.from_dict(st)
                for st in data.get("school_types", [])
            ]
        except Exception as e:
            logger.error(f"Failed to load cached tree: {e}")
            return None

    def load_subject_items(self, school_type_id: int, class_id: int, subject_id: int) -> Optional[List[QuestionItem]]:
        """Load cached items for a subject."""
        path = self._get_subject_cache_path(school_type_id, class_id, subject_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = [
                QuestionItem.from_dict(it, subject_id=subject_id)
                for it in data.get("items", [])
            ]
            items.sort(key=lambda x: (x.question or 99, x.id))
            return items
        except Exception as e:
            logger.error(f"Failed to load cached items from {path}: {e}")
            return None

    def save_subject_items(
        self,
        school_type_id: int,
        class_id: int,
        subject_id: int,
        items: List[QuestionItem]
    ) -> None:
        """Save subject items to cache."""
        path = self._get_subject_cache_path(school_type_id, class_id, subject_id)
        data = {
            "school_type_id": school_type_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "updated_at": datetime.now().isoformat(),
            "count": len(items),
            "items": [
                {
                    "id": it.id,
                    "subjectId": it.subject_id,
                    "question": it.question,
                    "title": it.title,
                    "date": it.date,
                    "durationMin": it.duration_min,
                    "difficulty": it.difficulty,
                    "keywords": it.keywords,
                    "remarks": it.remarks,
                    "organization": it.organization,
                    "material": [
                        {"id": m.id, "name": m.name, "shortname": m.shortname, "vieworder": m.vieworder}
                        for m in it.materials
                    ],
                    "resources": [
                        {"kind": r.kind, "format": r.format, "fileName": r.fileName}
                        for r in it.resources
                    ]
                }
                for it in items
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def detect_changes(
        self,
        school_type_id: int,
        class_id: int,
        subject_id: int,
        fresh_items: List[QuestionItem]
    ) -> ChangeReport:
        """Compare fresh items with cached items and report differences."""
        cached_items = self.load_subject_items(school_type_id, class_id, subject_id) or []
        cached_map = {it.id: it for it in cached_items}
        fresh_map = {it.id: it for it in fresh_items}

        new_items = []
        updated_items = []
        removed_items = []

        for it_id, fresh_it in fresh_map.items():
            if it_id not in cached_map:
                new_items.append(fresh_it)
            else:
                old_it = cached_map[it_id]
                # Check for changes in date, question number, or materials
                if (old_it.date != fresh_it.date or
                    old_it.question != fresh_it.question or
                    len(old_it.resources) != len(fresh_it.resources) or
                    len(old_it.materials) != len(fresh_it.materials)):
                    updated_items.append((old_it, fresh_it))

        for it_id, old_it in cached_map.items():
            if it_id not in fresh_map:
                removed_items.append(old_it)

        report = ChangeReport(
            school_type_id=school_type_id,
            class_id=class_id,
            subject_id=subject_id,
            checked_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            new_items=new_items,
            updated_items=updated_items,
            removed_items=removed_items,
            total_count=len(fresh_items),
            previous_count=len(cached_items)
        )

        # Save the fresh items
        self.save_subject_items(school_type_id, class_id, subject_id, fresh_items)

        # Record history if changes occurred
        if report.has_changes:
            self._append_change_history(report)

        return report

    def _append_change_history(self, report: ChangeReport) -> None:
        """Append change report to change history file."""
        history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        entry = {
            "checked_at": report.checked_at,
            "school_type_id": report.school_type_id,
            "class_id": report.class_id,
            "subject_id": report.subject_id,
            "new_count": len(report.new_items),
            "new_ids": [it.id for it in report.new_items],
            "updated_count": len(report.updated_items),
            "updated_ids": [new_it.id for _, new_it in report.updated_items],
            "removed_count": len(report.removed_items),
            "removed_ids": [it.id for it in report.removed_items],
            "total_count": report.total_count
        }
        history.insert(0, entry)
        # Keep last 100 history records
        history = history[:100]
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def get_pdf_cache_path(self, item_id: int, file_type: int) -> str:
        """Get local cache path for question or solution PDF."""
        suffix = "assignment" if file_type == 1 else "solution" if file_type == 2 else f"file_{file_type}"
        return os.path.join(self.pdf_cache_dir, f"{item_id}_{suffix}.pdf")

    def is_subject_cached(self, school_type_id: int, class_id: int, subject_id: int) -> bool:
        """Check if a subject's metadata is cached locally."""
        path = self._get_subject_cache_path(school_type_id, class_id, subject_id)
        return os.path.exists(path) and os.path.getsize(path) > 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """Compute statistics about local metadata and PDF cache."""
        subject_files = [f for f in os.listdir(self.cache_dir) if f.startswith("subject_") and f.endswith(".json")]
        total_questions = 0
        for f in subject_files:
            try:
                with open(os.path.join(self.cache_dir, f), "r", encoding="utf-8") as fp:
                    d = json.load(fp)
                    total_questions += len(d.get("items", []))
            except Exception:
                pass

        pdf_files = [f for f in os.listdir(self.pdf_cache_dir) if f.endswith(".pdf")]
        total_pdf_bytes = sum(os.path.getsize(os.path.join(self.pdf_cache_dir, f)) for f in pdf_files)
        total_pdf_mb = round(total_pdf_bytes / (1024 * 1024), 1)

        tree_cached = os.path.exists(self.tree_file) and os.path.getsize(self.tree_file) > 0

        return {
            "cached_subjects_count": len(subject_files),
            "cached_questions_count": total_questions,
            "cached_pdfs_count": len(pdf_files),
            "cached_pdfs_mb": total_pdf_mb,
            "tree_cached": tree_cached,
        }

    def get_subject_pdf_status(self, items: List[QuestionItem]) -> Dict[str, Any]:
        """Check how many PDFs for the given items are cached locally based on actual IEP availability."""
        total = len(items)
        expected_assign = sum(1 for it in items if it.has_assignment_pdf)
        expected_sol = sum(1 for it in items if it.has_solution_pdf)
        total_expected_pdfs = expected_assign + expected_sol

        cached_assign = 0
        cached_sol = 0
        for it in items:
            if it.has_assignment_pdf:
                p_assign = self.get_pdf_cache_path(it.id, 1)
                if os.path.exists(p_assign) and os.path.getsize(p_assign) > 0:
                    cached_assign += 1
            if it.has_solution_pdf:
                p_sol = self.get_pdf_cache_path(it.id, 2)
                if os.path.exists(p_sol) and os.path.getsize(p_sol) > 0:
                    cached_sol += 1

        cached_total = cached_assign + cached_sol
        is_fully = (cached_total == total_expected_pdfs) if total_expected_pdfs > 0 else (total > 0)
        return {
            "total_items": total,
            "expected_assignments": expected_assign,
            "expected_solutions": expected_sol,
            "total_expected_pdfs": total_expected_pdfs,
            "cached_assignments": cached_assign,
            "cached_solutions": cached_sol,
            "cached_total": cached_total,
            "is_fully_cached": is_fully
        }

    def clear_pdf_cache(self) -> int:
        """Clear all cached PDF files to free disk space."""
        count = 0
        for f in os.listdir(self.pdf_cache_dir):
            if f.endswith(".pdf"):
                try:
                    os.remove(os.path.join(self.pdf_cache_dir, f))
                    count += 1
                except Exception as e:
                    logger.warning(f"Could not remove cached PDF {f}: {e}")
        return count

