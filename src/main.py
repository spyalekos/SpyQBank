"""Main Application entry point for SpyQBank."""

import os
import sys
import re
import time
import random
import webbrowser
import flet as ft

# Ensure root directory and _MEIPASS are in sys.path
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from src.version import APP_NAME, APP_TITLE, __version__
from src.models import SchoolType, ClassLevel, Subject, QuestionItem, extract_main_chapter
from src.iep_api import IepApiClient
from src.storage import StorageManager
from src.pdf_builder import PdfReportBuilder
from src.config import load_config, save_config
from src.ui.theme import (
    PRIMARY,
    PRIMARY_LIGHT,
    PRIMARY_DARK,
    SECONDARY,
    BG_LIGHT,
    TEXT_MAIN,
    TEXT_MUTED,
    BORDER_COLOR
)
from src.ui.log_console import LogConsole
from src.ui.question_card import QuestionCard
from src.ui.settings_dialog import SettingsDialog


def main(page: ft.Page):
    page.title = f"{APP_TITLE} v{__version__}"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0
    page.bgcolor = "#F1F5F9"
    page.window.min_width = 980
    page.window.min_height = 680
    page.window.width = 1180
    page.window.height = 800

    # Services & Managers
    api_client = IepApiClient()
    storage = StorageManager()
    pdf_builder = PdfReportBuilder(api_client, storage)

    # State variables
    school_types: list[SchoolType] = []
    selected_school_type: SchoolType | None = None
    selected_class: ClassLevel | None = None
    selected_subject: Subject | None = None
    all_items: list[QuestionItem] = []
    filtered_items: list[QuestionItem] = []
    selected_chapter: str = "ALL"
    selected_q_type: str = "ALL"
    search_query: str = ""

    # UI Components
    log_console = LogConsole(height=120)

    # Progress bar for background tasks
    progress_bar = ft.ProgressBar(visible=False, color=PRIMARY_LIGHT, bgcolor="#E2E8F0")
    status_text = ft.Text("Έτοιμο.", size=12, color=TEXT_MUTED)

    # Dropdowns
    type_dropdown = ft.Dropdown(
        label="Τύπος Σχολείου",
        width=220,
        content_padding=ft.Padding(10, 0, 10, 0),
        dense=True,
    )
    class_dropdown = ft.Dropdown(
        label="Τάξη",
        width=160,
        content_padding=ft.Padding(10, 0, 10, 0),
        dense=True,
        disabled=True,
    )
    subject_dropdown = ft.Dropdown(
        label="Μάθημα",
        width=480,
        menu_width=600,
        enable_filter=True,
        enable_search=True,
        content_padding=ft.Padding(10, 0, 10, 0),
        dense=True,
        disabled=True,
    )

    # Filter controls
    chapter_dropdown = ft.Dropdown(
        label="Φιλτράρισμα ανά Κεφάλαιο",
        width=380,
        content_padding=ft.Padding(10, 0, 10, 0),
        dense=True,
        disabled=True,
    )
    qtype_dropdown = ft.Dropdown(
        label="Τύπος Θέματος",
        width=150,
        content_padding=ft.Padding(10, 0, 10, 0),
        dense=True,
        options=[
            ft.dropdown.Option(key="ALL", text="Όλα τα Θέματα"),
            ft.dropdown.Option(key="1", text="Θέμα 1ο"),
            ft.dropdown.Option(key="2", text="Θέμα 2ο"),
            ft.dropdown.Option(key="3", text="Θέμα 3ο"),
            ft.dropdown.Option(key="4", text="Θέμα 4ο"),
        ],
        value="ALL",
    )
    search_field = ft.TextField(
        hint_text="Αναζήτηση ID, λέξεις-κλειδιά...",
        prefix_icon=ft.Icons.SEARCH,
        width=250,
        content_padding=ft.Padding(10, 0, 10, 0),
        dense=True,
    )

    # Items container
    items_column = ft.Column(
        scroll=ft.ScrollMode.ALWAYS,
        expand=True,
        spacing=0,
    )

    # Summary text
    summary_label = ft.Text("Επιλέξτε Τύπο Σχολείου, Τάξη και Μάθημα.", size=13, weight=ft.FontWeight.W_500, color=TEXT_MAIN)

    def show_snackbar(message: str, is_error: bool = False):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_800,
            duration=3500
        )
        page.snack_bar.open = True
        page.update()

    def on_settings_saved(new_cfg: dict):
        log_console.log("Οι ρυθμίσεις αποθηκεύτηκαν στο spyqbank.json.", "SUCCESS")
        show_snackbar("Οι ρυθμίσεις αποθηκεύτηκαν επιτυχώς!")
        if all_items:
            populate_chapters_dropdown()
            update_filtered_list()

    settings_dialog = SettingsDialog(page, on_save_callback=on_settings_saved)

    # Help Dialog
    help_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.HELP_OUTLINE, color=PRIMARY, size=32),
                ft.Text(f"Βοήθεια & Οδηγίες Χρήσης - {APP_NAME}", weight=ft.FontWeight.BOLD, size=24),
            ],
            spacing=12
        ),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Βασικές Λειτουργίες της Εφαρμογής:", weight=ft.FontWeight.BOLD, size=18, color=PRIMARY_DARK),
                    ft.Text("• 🏫 Επιλογή Μαθήματος: Επιλέξτε Τύπο Σχολείου (ΓΕΛ / ΕΠΑΛ), Τάξη και Μάθημα από την πάνω μπάρα για να φορτωθούν τα αντίστοιχα θέματα.", size=16, color=TEXT_MAIN),
                    ft.Text("• 📂 Φιλτράρισμα: Χρησιμοποιήστε το φίλτρο Κεφαλαίου, Τύπου Θέματος (1ο, 2ο, 3ο, 4ο) ή την Αναζήτηση με λέξεις-κλειδιά.", size=16, color=TEXT_MAIN),
                    ft.Text("• 💡 Ζεύγη Θεμάτων-Απαντήσεων: Κάθε κάρτα θέματος περιέχει άμεσα κουμπιά προβολής και λήψης της Εκφώνησης και της Λύσης.", size=16, color=TEXT_MAIN),
                    ft.Text("• 📑 Εξαγωγή σε PDF: Πατήστε «Εξαγωγή Όλων σε PDF» ή «PDF Κεφαλαίου» για να δημιουργήσετε ενιαίο PDF με όλα τα θέματα και τις απαντήσεις τους στη σειρά.", size=16, color=TEXT_MAIN),
                    ft.Text("• 🎨 Χρωματισμός & Trimming: Οι εκφωνήσεις εμφανίζονται με μαύρα γράμματα και οι απαντήσεις με σκούρο μπλε. Στις Ρυθμίσεις (⚙️) μπορείτε να ελέγξετε την αφαίρεση κενού χώρου και τις διαχωριστικές σελίδες.", size=16, color=TEXT_MAIN),
                    ft.Text("• ⚡ Offline Cache: Τα μεταδεδομένα και τα αρχεία αποθηκεύονται τοπικά για άμεση offline πρόσβαση.", size=16, color=TEXT_MAIN),
                    ft.Divider(height=16, color=BORDER_COLOR),
                    ft.Text(f"Έκδοση: v{__version__} | Τράπεζα Θεμάτων ΙΕΠ (https://trapeza.iep.edu.gr)", size=14, color=TEXT_MUTED, italic=True),
                ],
                tight=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=760,
            padding=20,
        ),
        actions=[
            ft.Button(
                content=ft.Text("Κλείσιμο", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=16),
                style=ft.ButtonStyle(
                    bgcolor=PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.Padding(24, 14, 24, 14)
                ),
                on_click=lambda e: _close_help()
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _show_help():
        if help_dialog not in page.overlay:
            page.overlay.append(help_dialog)
        help_dialog.open = True
        page.update()

    def _close_help():
        help_dialog.open = False
        page.update()

    # Action Controls references for disabling during operations
    prefetch_epal_button = ft.Button(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.CLOUD_DOWNLOAD, size=16, color=ft.Colors.WHITE),
                ft.Text("Prefetch ΕΠΑΛ", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
            ],
            spacing=4,
            tight=True
        ),
        style=ft.ButtonStyle(
            bgcolor="#4F46E5",
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(12, 8, 12, 8)
        ),
        tooltip="Προφόρτωση όλων των θεμάτων ΕΠΑΛ (με τυχαία καθυστέρηση 1-4s)",
    )
    sync_button = ft.Button(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.REFRESH, size=16, color=ft.Colors.WHITE),
                ft.Text("Έλεγχος Αλλαγών", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
            ],
            spacing=4,
            tight=True
        ),
        style=ft.ButtonStyle(
            bgcolor="#0284C7",
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(12, 8, 12, 8)
        ),
        tooltip="Συγχρονισμός & έλεγχος για νέα/τροποποιημένα θέματα",
    )
    export_all_button = ft.Button(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.PICTURE_AS_PDF, size=16, color=ft.Colors.WHITE),
                ft.Text("Εξαγωγή Όλων σε PDF", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
            ],
            spacing=4,
            tight=True
        ),
        style=ft.ButtonStyle(
            bgcolor="#D97706",
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(12, 8, 12, 8)
        ),
        tooltip="Δημιουργία ενιαίου PDF με όλα τα θέματα και τις λύσεις τους",
    )
    settings_button = ft.IconButton(
        icon=ft.Icons.SETTINGS,
        tooltip="Ρυθμίσεις Επικεφαλίδας & Υποσέλιδου PDF",
        icon_color=ft.Colors.WHITE,
    )
    help_button = ft.IconButton(
        icon=ft.Icons.HELP_OUTLINE,
        tooltip="Οδηγίες & Βοήθεια",
        icon_color=ft.Colors.WHITE,
    )
    folder_button = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN,
        tooltip="Άνοιγμα φακέλου Downloads",
        icon_color=ft.Colors.WHITE,
    )
    export_chapter_button = ft.Button(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.FILE_DOWNLOAD_OUTLINED, size=15, color="#1E40AF"),
                ft.Text("PDF Κεφαλαίου", size=12, color="#1E40AF", weight=ft.FontWeight.BOLD),
            ],
            spacing=4,
            tight=True
        ),
        style=ft.ButtonStyle(
            bgcolor="#DBEAFE",
            shape=ft.RoundedRectangleBorder(radius=6),
            padding=ft.Padding(10, 6, 10, 6)
        ),
        tooltip="Εξαγωγή μόνο του επιλεγμένου κεφαλαίου σε PDF",
    )

    is_busy = False

    def set_ui_busy(busy: bool):
        nonlocal is_busy
        is_busy = busy
        # Disable & visually gray out top & selector bar controls
        prefetch_epal_button.disabled = busy
        prefetch_epal_button.opacity = 0.5 if busy else 1.0

        sync_button.disabled = busy
        sync_button.opacity = 0.5 if busy else 1.0

        export_all_button.disabled = busy
        export_all_button.opacity = 0.5 if busy else 1.0

        settings_button.disabled = busy
        settings_button.opacity = 0.5 if busy else 1.0

        help_button.disabled = busy
        help_button.opacity = 0.5 if busy else 1.0

        folder_button.disabled = busy
        folder_button.opacity = 0.5 if busy else 1.0

        export_chapter_button.disabled = busy
        export_chapter_button.opacity = 0.5 if busy else 1.0

        type_dropdown.disabled = busy
        class_dropdown.disabled = busy or (selected_school_type is None)
        subject_dropdown.disabled = busy or (selected_class is None)
        chapter_dropdown.disabled = busy or (selected_subject is None)
        qtype_dropdown.disabled = busy
        search_field.disabled = busy

        # Visually gray out all item cards
        for card in items_column.controls:
            if hasattr(card, "set_enabled"):
                card.set_enabled(not busy)

        page.update()

    # --- Actions & Handlers ---

    def handle_view_pdf(item: QuestionItem, file_type: int):
        if is_busy:
            return

        # ⚡ Immediately lock & gray out UI on current UI turn
        set_ui_busy(True)
        progress_bar.visible = True
        status_text.value = f"Επεξεργασία & άνοιγμα PDF #{item.id}..."
        page.update()

        def worker():
            kind_label = "Εκφώνηση" if file_type == 1 else "Λύση"
            kind_slug = "assignment" if file_type == 1 else "solution"
            log_console.log(f"Προετοιμασία PDF #{item.id} ({kind_label}) με τίτλους & χρωματισμό...")
            processed_filename = f"IEP_{item.subject_id}_{item.id}_{kind_slug}_view.pdf"
            dest = os.path.join(storage.pdf_cache_dir, processed_filename)
            try:
                final_pdf = pdf_builder.build_single_item_report(
                    item=item,
                    file_type=file_type,
                    output_path=dest
                )
                if os.path.exists(final_pdf):
                    if sys.platform == "win32":
                        os.startfile(final_pdf)
                    else:
                        webbrowser.open(f"file://{os.path.abspath(final_pdf)}")
                    log_console.log(f"Άνοιξε το αρχείο: {os.path.basename(final_pdf)}", "SUCCESS")
                else:
                    url = item.get_assignment_pdf_url() if file_type == 1 else item.get_solution_pdf_url()
                    webbrowser.open(url)
            except Exception as e:
                log_console.log(f"Σφάλμα επεξεργασίας PDF #{item.id}: {e}", "ERROR")
                url = item.get_assignment_pdf_url() if file_type == 1 else item.get_solution_pdf_url()
                webbrowser.open(url)
            finally:
                progress_bar.visible = False
                status_text.value = "Έτοιμο."
                set_ui_busy(False)
                page.update()

        page.run_thread(worker)

    def handle_download_pdf(item: QuestionItem, file_type: int):
        if is_busy:
            return

        # ⚡ Immediately lock & gray out UI on current UI turn
        set_ui_busy(True)
        progress_bar.visible = True
        status_text.value = f"Λήψη & μορφοποίηση PDF #{item.id}..."
        page.update()

        def worker():
            kind_label = "εκφωνηση" if file_type == 1 else "απαντηση"
            downloads_dir = os.path.abspath("downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            filename = f"IEP_{item.subject_id}_{item.id}_{kind_label}.pdf"
            dest = os.path.join(downloads_dir, filename)

            log_console.log(f"Επεξεργασία & λήψη PDF στο φάκελο downloads: {filename}...")
            try:
                saved_path = pdf_builder.build_single_item_report(
                    item=item,
                    file_type=file_type,
                    output_path=dest
                )
                saved_name = os.path.basename(saved_path)
                log_console.log(f"Αποθηκεύτηκε στο: {saved_path}", "SUCCESS")
                show_snackbar(f"Αποθηκεύτηκε: {saved_name}")
            except Exception as e:
                log_console.log(f"Σφάλμα αποθήκευσης: {e}", "ERROR")
                show_snackbar(f"Σφάλμα λήψης: {e}", is_error=True)
            finally:
                progress_bar.visible = False
                status_text.value = "Έτοιμο."
                set_ui_busy(False)
                page.update()

        page.run_thread(worker)

    def _chapter_sort_key(ch_str: str):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", ch_str)]

    def populate_chapters_dropdown():
        nonlocal selected_chapter
        cfg = load_config()
        group_by_main = cfg.get("group_by_main_chapter", True)

        def _item_sort_key(it: QuestionItem):
            primary_ch = it.get_primary_chapter_name(group_by_main_chapter=group_by_main)
            return (_chapter_sort_key(primary_ch), it.question or 99, it.id)

        # Sort items naturally: Chapter ascending -> Question (1, 2, 3, 4) -> ID
        all_items.sort(key=_item_sort_key)

        # Populate chapters dropdown
        unique_chapters = set()
        for it in all_items:
            for m in it.materials:
                if m.name:
                    ch = extract_main_chapter(m.name) if group_by_main else m.name
                    unique_chapters.add(ch)

        sorted_chapters = sorted(list(unique_chapters), key=_chapter_sort_key)
        chapter_dropdown.options = [
            ft.dropdown.Option(key="ALL", text="Όλα τα Κεφάλαια / Ενότητες")
        ] + [
            ft.dropdown.Option(key=ch, text=ch)
            for ch in sorted_chapters
        ]
        if selected_chapter != "ALL" and selected_chapter not in unique_chapters:
            selected_chapter = "ALL"
        chapter_dropdown.value = selected_chapter

    def update_filtered_list():
        nonlocal filtered_items
        res = all_items
        cfg = load_config()
        group_by_main = cfg.get("group_by_main_chapter", True)

        # Filter by Chapter
        if selected_chapter != "ALL":
            res = [
                it for it in res
                if it.matches_chapter(selected_chapter, group_by_main_chapter=group_by_main)
            ]

        # Filter by Question Type (1, 2, 3, 4)
        if selected_q_type != "ALL":
            try:
                q_val = int(selected_q_type)
                res = [it for it in res if it.question == q_val]
            except ValueError:
                pass

        # Filter by Search Query
        if search_query:
            q_lower = search_query.lower()
            res = [
                it for it in res
                if (q_lower in str(it.id) or
                    q_lower in (it.keywords or "").lower() or
                    q_lower in (it.title or "").lower() or
                    any(q_lower in m.name.lower() for m in it.materials))
            ]

        filtered_items = res
        items_column.controls.clear()

        if not filtered_items:
            items_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=TEXT_MUTED),
                            ft.Text("Δεν βρέθηκαν θέματα με τα επιλεγμένα κριτήρια.", size=14, color=TEXT_MUTED),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10
                    ),
                    padding=40,
                    alignment=ft.Alignment(0, 0)
                )
            )
        else:
            for it in filtered_items:
                card = QuestionCard(
                    item=it,
                    on_view_pdf=handle_view_pdf,
                    on_download=handle_download_pdf
                )
                if is_busy:
                    card.set_enabled(False)
                items_column.controls.append(card)

        # Update summary banner
        total_sub = len(all_items)
        visible_cnt = len(filtered_items)
        sub_name = selected_subject.name if selected_subject else ""
        summary_label.value = f"📚 {sub_name}: Εμφανίζονται {visible_cnt} από {total_sub} θέματα (με εκφωνήσεις & απαντήσεις)"
        page.update()

    def on_chapter_changed(e):
        nonlocal selected_chapter
        selected_chapter = chapter_dropdown.value or "ALL"
        update_filtered_list()

    def on_qtype_changed(e):
        nonlocal selected_q_type
        selected_q_type = qtype_dropdown.value or "ALL"
        update_filtered_list()

    def on_search_changed(e):
        nonlocal search_query
        search_query = search_field.value.strip()
        update_filtered_list()

    chapter_dropdown.on_select = on_chapter_changed
    qtype_dropdown.on_select = on_qtype_changed
    search_field.on_change = on_search_changed

    def load_subject_items(subject: Subject, force_refresh: bool = False):
        if is_busy:
            return

        # ⚡ Immediately lock & gray out UI on current UI turn
        set_ui_busy(True)
        progress_bar.visible = True
        status_text.value = f"Φόρτωση θεμάτων για: {subject.name}..."
        page.update()

        def worker():
            nonlocal all_items, selected_subject
            selected_subject = subject

            log_console.log(f"Φόρτωση θεμάτων: {subject.name} (ID: {subject.id})...")

            # Try loading cache first if not forced
            cached = storage.load_subject_items(subject.school_type_id, subject.class_id, subject.id)
            if cached and not force_refresh:
                all_items = cached
                log_console.log(f"Φορτώθηκαν {len(all_items)} θέματα από την τοπική cache.", "SUCCESS")
            else:
                try:
                    fresh_items = api_client.get_subject_items(
                        subject.school_type_id,
                        subject.class_id,
                        subject.id
                    )
                    report = storage.detect_changes(
                        subject.school_type_id,
                        subject.class_id,
                        subject.id,
                        fresh_items
                    )
                    all_items = fresh_items
                    log_console.log(f"Λήφθηκαν {len(all_items)} θέματα από το API. {report.summary}", "SUCCESS")
                    if report.has_changes:
                        show_snackbar(report.summary)
                except Exception as e:
                    log_console.log(f"Σφάλμα ανάκτησης θεμάτων από το API: {e}", "ERROR")
                    if cached:
                        all_items = cached
                        log_console.log("Χρήση παλαιότερων αποθηκευμένων θεμάτων.", "WARNING")
                    else:
                        all_items = []
                        show_snackbar(f"Σφάλμα: {e}", is_error=True)

            populate_chapters_dropdown()

            progress_bar.visible = False
            status_text.value = f"Φορτώθηκαν {len(all_items)} θέματα για: {subject.name}."
            set_ui_busy(False)
            update_filtered_list()

        page.run_thread(worker)

    def class_sort_key(cl: ClassLevel):
        name = cl.name.upper()
        if "Γ" in name:
            return 1
        if "Β" in name:
            return 2
        if "Α" in name:
            return 3
        if "Δ" in name:
            return 4
        return 10

    def on_type_changed(e):
        if is_busy:
            return
        nonlocal selected_school_type, selected_class, selected_subject, all_items
        type_id = int(type_dropdown.value)
        selected_school_type = next((st for st in school_types if st.id == type_id), None)
        selected_class = None
        selected_subject = None
        all_items = []

        if selected_school_type:
            sorted_classes = sorted(selected_school_type.classes, key=class_sort_key)
            class_dropdown.options = [
                ft.dropdown.Option(key=str(cl.id), text=cl.name)
                for cl in sorted_classes
            ]
            class_dropdown.value = None
            class_dropdown.disabled = False

            subject_dropdown.options = []
            subject_dropdown.value = None
            subject_dropdown.disabled = True
            chapter_dropdown.disabled = True
        page.update()

    def on_class_changed(e):
        if is_busy:
            return
        nonlocal selected_class, selected_subject, all_items
        if not selected_school_type or not class_dropdown.value:
            return
        class_id = int(class_dropdown.value)
        selected_class = next((cl for cl in selected_school_type.classes if cl.id == class_id), None)
        selected_subject = None
        all_items = []

        if selected_class:
            sorted_lessons = sorted(selected_class.lessons, key=lambda s: s.name.lower())
            subject_dropdown.options = [
                ft.dropdown.Option(key=str(sub.id), text=sub.name)
                for sub in sorted_lessons
            ]
            subject_dropdown.value = None
            subject_dropdown.disabled = False
            chapter_dropdown.disabled = True
        page.update()

    def on_subject_changed(e):
        if is_busy:
            return
        if not selected_class or not subject_dropdown.value:
            return
        subject_id = int(subject_dropdown.value)
        sub = next((s for s in selected_class.lessons if s.id == subject_id), None)
        if sub:
            load_subject_items(sub)

    type_dropdown.on_select = on_type_changed
    class_dropdown.on_select = on_class_changed
    subject_dropdown.on_select = on_subject_changed

    # --- Sync & Export Handlers ---

    def handle_prefetch_epal(e):
        if is_busy:
            return

        # ⚡ Immediately lock UI synchronously
        set_ui_busy(True)
        progress_bar.visible = True
        progress_bar.value = 0.0
        status_text.value = "Έναρξη προφόρτωσης (prefetch) μαθημάτων ΕΠΑΛ..."
        page.update()

        def worker():
            log_console.log("=== ΕΝΑΡΞΗ PREFETCH ΟΛΩΝ ΤΩΝ ΜΑΘΗΜΑΤΩΝ ΕΠΑΛ ===")
            epal_type = next((st for st in school_types if st.id == 3 or "ΕΠΑΛ" in st.name.upper() or "ΕΠΑ.Λ" in st.name.upper()), None)
            if not epal_type:
                log_console.log("Δεν βρέθηκε ο τύπος σχολείου ΕΠΑΛ στο δέντρο.", "ERROR")
                show_snackbar("Δεν βρέθηκε ο τύπος σχολείου ΕΠΑΛ.", is_error=True)
                progress_bar.visible = False
                status_text.value = "Έτοιμο."
                set_ui_busy(False)
                page.update()
                return

            all_epal_lessons: list[tuple[ClassLevel, Subject]] = []
            for cl in sorted(epal_type.classes, key=class_sort_key):
                for sub in cl.lessons:
                    all_epal_lessons.append((cl, sub))

            total_subjects = len(all_epal_lessons)
            log_console.log(f"Συνολικά μαθήματα ΕΠΑΛ προς επεξεργασία: {total_subjects}")

            downloaded_cnt = 0
            cached_cnt = 0
            error_cnt = 0

            for idx, (cl, sub) in enumerate(all_epal_lessons, start=1):
                progress_val = idx / total_subjects
                progress_bar.value = progress_val
                status_text.value = f"[{idx}/{total_subjects}] {cl.name} - {sub.name}..."
                page.update()

                # Check if already cached
                cached = storage.load_subject_items(epal_type.id, cl.id, sub.id)
                if cached:
                    cached_cnt += 1
                    log_console.log(f"[{idx}/{total_subjects}] (Cache) {cl.name} -> {sub.name} ({len(cached)} θέματα)")
                    page.update()
                    continue

                # Fetch from IEP API with rate-limiting delay
                delay = random.uniform(1.0, 4.0)
                time.sleep(delay)

                try:
                    fresh_items = api_client.get_subject_items(epal_type.id, cl.id, sub.id)
                    storage.save_subject_items(epal_type.id, cl.id, sub.id, fresh_items)
                    downloaded_cnt += 1
                    log_console.log(f"[{idx}/{total_subjects}] (API - {delay:.1f}s delay) {cl.name} -> {sub.name}: {len(fresh_items)} θέματα", "SUCCESS")
                except Exception as ex:
                    error_cnt += 1
                    log_console.log(f"[{idx}/{total_subjects}] Σφάλμα στο μάθημα {sub.name}: {ex}", "ERROR")

                page.update()

            log_console.log(f"=== ΟΛΟΚΛΗΡΩΣΗ PREFETCH ΕΠΑΛ ===", "SUCCESS")
            log_console.log(f"Αποτελέσματα: {downloaded_cnt} λήφθηκαν από API, {cached_cnt} υπήρχαν στην cache, {error_cnt} σφάλματα.", "SUCCESS")
            show_snackbar(f"Ολοκληρώθηκε το Prefetch ΕΠΑΛ ({downloaded_cnt} νέα, {cached_cnt} cache).")

            progress_bar.visible = False
            progress_bar.value = None
            status_text.value = "Έτοιμο. Η προφόρτωση ΕΠΑΛ ολοκληρώθηκε."
            set_ui_busy(False)
            page.update()

        page.run_thread(worker)

    def handle_sync_check(e):
        if is_busy:
            return
        if not selected_subject:
            show_snackbar("Παρακαλώ επιλέξτε πρώτα μάθημα.", is_error=True)
            return
        load_subject_items(selected_subject, force_refresh=True)

    def handle_export_pdf(e, only_selected_chapter: bool = False):
        if is_busy:
            return
        if not selected_subject or not all_items:
            show_snackbar("Δεν υπάρχουν θέματα για εξαγωγή.", is_error=True)
            return

        # ⚡ Immediately lock & gray out all UI controls synchronously
        set_ui_busy(True)
        progress_bar.visible = True
        status_text.value = "Έναρξη εξαγωγής PDF..."
        page.update()

        def worker():
            cfg = load_config()
            group_by_main = cfg.get("group_by_main_chapter", True)
            target_chapter = selected_chapter if (only_selected_chapter and selected_chapter != "ALL") else None
            items_to_export = [
                it for it in all_items
                if not target_chapter or it.matches_chapter(target_chapter, group_by_main_chapter=group_by_main)
            ]

            if not items_to_export:
                show_snackbar("Δεν βρέθηκαν θέματα για το επιλεγμένο κεφάλαιο.", is_error=True)
                progress_bar.visible = False
                set_ui_busy(False)
                page.update()
                return

            ch_slug = target_chapter[:25].replace("/", "_").replace("\\", "_") if target_chapter else "ALL_CHAPTERS"
            pdf_filename = f"SpyQBank_{selected_subject.id}_{ch_slug}.pdf"
            downloads_dir = os.path.abspath("downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            output_path = os.path.join(downloads_dir, pdf_filename)

            log_console.log(f"Έναρξη δημιουργίας PDF: {pdf_filename} ({len(items_to_export)} θέματα)...", "PDF")

            def on_pdf_progress(msg: str, progress: float):
                status_text.value = msg
                log_console.log(msg)
                page.update()

            try:
                final_pdf = pdf_builder.build_combined_report(
                    items=items_to_export,
                    output_path=output_path,
                    subject_name=selected_subject.name,
                    chapter_name=target_chapter,
                    progress_callback=on_pdf_progress
                )
                final_filename = os.path.basename(final_pdf)
                log_console.log(f"Το PDF δημιουργήθηκε επιτυχώς: {final_pdf}", "SUCCESS")
                show_snackbar(f"Το PDF δημιουργήθηκε: {final_filename}")

                # Open the generated PDF
                if sys.platform == "win32":
                    os.startfile(final_pdf)
                else:
                    webbrowser.open(f"file://{os.path.abspath(final_pdf)}")
            except Exception as ex:
                log_console.log(f"Σφάλμα κατά την παραγωγή PDF: {ex}", "ERROR")
                show_snackbar(f"Σφάλμα PDF: {ex}", is_error=True)
            finally:
                progress_bar.visible = False
                status_text.value = "Έτοιμο."
                set_ui_busy(False)
                page.update()

        page.run_thread(worker)

    # Attach clicks
    prefetch_epal_button.on_click = handle_prefetch_epal
    sync_button.on_click = handle_sync_check
    export_all_button.on_click = lambda e: handle_export_pdf(e, only_selected_chapter=False)
    settings_button.on_click = lambda _: settings_dialog.show() if not is_busy else None
    help_button.on_click = lambda _: _show_help() if not is_busy else None
    folder_button.on_click = lambda _: (os.startfile(os.path.abspath("downloads")) if sys.platform == "win32" else webbrowser.open(f"file://{os.path.abspath('downloads')}")) if not is_busy else None
    export_chapter_button.on_click = lambda e: handle_export_pdf(e, only_selected_chapter=True)


    # --- Initial Data Load ---

    def init_tree():
        def worker():
            nonlocal school_types
            progress_bar.visible = True
            status_text.value = "Φόρτωση δέντρου μαθημάτων ΙΕΠ..."
            page.update()
            log_console.log("Φόρτωση δέντρου τύπων σχολείων & μαθημάτων...")

            cached_tree = storage.load_tree()
            if cached_tree:
                school_types = cached_tree
                log_console.log("Φορτώθηκε το δέντρο σχολείων από την τοπική cache.", "SUCCESS")
            else:
                try:
                    school_types = api_client.get_school_tree()
                    storage.save_tree(school_types)
                    log_console.log(f"Λήφθηκαν {len(school_types)} τύποι σχολείων από το API.", "SUCCESS")
                except Exception as e:
                    log_console.log(f"Σφάλμα φόρτωσης δέντρου: {e}", "ERROR")
                    show_snackbar(f"Σφάλμα σύνδεσης με ΙΕΠ: {e}", is_error=True)

            type_dropdown.options = [
                ft.dropdown.Option(key=str(st.id), text=st.name)
                for st in school_types
            ]
            if school_types:
                type_dropdown.value = str(school_types[0].id)
                # Trigger initial select
                on_type_changed(None)

            progress_bar.visible = False
            status_text.value = "Έτοιμο. Επιλέξτε μάθημα."
            page.update()

        page.run_thread(worker)

    # --- Top Navigation Bar ---
    top_header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SCHOOL, size=28, color=PRIMARY_LIGHT),
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(APP_NAME, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                        ft.Container(
                                            content=ft.Text(f"v{__version__}", size=11, weight=ft.FontWeight.BOLD, color="#93C5FD"),
                                            bgcolor="#1E3A8A",
                                            border_radius=4,
                                            padding=ft.Padding(5, 2, 5, 2)
                                        )
                                    ],
                                    spacing=8
                                ),
                                ft.Text("Τράπεζα Θεμάτων ΙΕΠ (Εκφωνήσεις & Απαντήσεις)", size=13, weight=ft.FontWeight.W_500, color="#86EFAC")
                            ],
                            spacing=1,
                            alignment=ft.MainAxisAlignment.CENTER
                        )
                    ],
                    spacing=10
                ),
                ft.Container(expand=True),
                # Action Buttons
                ft.Row(
                    controls=[
                        prefetch_epal_button,
                        sync_button,
                        export_all_button,
                        settings_button,
                        help_button,
                        folder_button
                    ],
                    spacing=8
                )
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        ),
        bgcolor=PRIMARY_DARK,
        padding=ft.Padding(16, 10, 16, 10)
    )

    # --- Selector Bar ---
    selector_card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        type_dropdown,
                        class_dropdown,
                        subject_dropdown,
                    ],
                    spacing=12,
                    wrap=True
                ),
                ft.Divider(height=1, color=BORDER_COLOR),
                ft.Row(
                    controls=[
                        chapter_dropdown,
                        export_chapter_button,
                        qtype_dropdown,
                        search_field,
                    ],
                    spacing=10,
                    wrap=True
                )
            ],
            spacing=10
        ),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, BORDER_COLOR),
        border_radius=8,
        padding=12,
        margin=ft.Margin(12, 10, 12, 6)
    )

    # --- Summary Bar ---
    summary_bar = ft.Container(
        content=summary_label,
        padding=ft.Padding(16, 4, 16, 4),
    )

    # --- Main Layout ---
    main_content = ft.Container(
        content=items_column,
        expand=True,
        padding=ft.Padding(12, 0, 12, 6),
    )

    # --- Bottom Footer & Console ---
    bottom_bar = ft.Container(
        content=ft.Column(
            controls=[
                progress_bar,
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=TEXT_MUTED),
                        status_text,
                        ft.Container(expand=True),
                        ft.Text("https://trapeza.iep.edu.gr", size=11, color=TEXT_MUTED),
                    ],
                    spacing=6
                ),
                log_console
            ],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.only(top=ft.BorderSide(1, BORDER_COLOR)),
        padding=ft.Padding(12, 6, 12, 6),
    )

    page.add(
        top_header,
        selector_card,
        summary_bar,
        main_content,
        bottom_bar
    )

    page.update()

    # Start initialization thread
    init_tree()


if __name__ == "__main__":
    ft.run(main)
