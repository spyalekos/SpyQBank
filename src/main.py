"""Main Application entry point for SpyQBank."""

import os
import sys
import re
import time
import random
import asyncio
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
    BORDER_COLOR,
    YELLOW_GREY
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
    page.window.min_width = 1040
    page.window.min_height = 680
    page.window.width = 1480
    page.window.height = 820

    # Set window icon if available
    icon_path = os.path.join(base_dir, "assets", "icon.png")
    if os.path.exists(icon_path):
        page.window.icon = icon_path

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
    is_busy: bool = False
    cancel_requested: bool = False

    # Keyboard event handler (Esc to cancel background tasks)
    def on_keyboard_event(e: ft.KeyboardEvent):
        nonlocal cancel_requested
        if e.key == "Escape":
            if is_busy:
                cancel_requested = True
                log_console.log("🛑 Πατήθηκε Esc: Αίτημα διακοπής της τρέχουσας διεργασίας...", "WARNING")
                show_snackbar("Πατήθηκε Esc - Διακοπή...", is_error=True)

    page.on_keyboard_event = on_keyboard_event

    # UI Components
    log_console = LogConsole(height=120)

    # Progress bar and spinner for background tasks
    progress_bar = ft.ProgressBar(visible=False, color=PRIMARY_LIGHT, bgcolor="#E2E8F0")
    status_spinner = ft.ProgressRing(width=14, height=14, stroke_width=2.5, color=PRIMARY, visible=False)
    status_text = ft.Text("Έτοιμο.", size=12, color=TEXT_MUTED)

    def set_status(msg: str, progress: float | None = None, show_progress: bool | None = None):
        """Update status message, progress bar and active spinner with immediate control repaint on Windows."""
        status_text.value = msg
        if progress is not None:
            progress_bar.value = progress
        if show_progress is not None:
            progress_bar.visible = show_progress
            status_spinner.visible = show_progress
        try:
            status_spinner.update()
            status_text.update()
            progress_bar.update()
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

    # Dropdowns
    type_dropdown = ft.Dropdown(
        label="Τύπος Σχολείου",
        width=260,
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
        width=190,
        content_padding=ft.Padding(10, 0, 10, 0),
        dense=True,
        options=[
            ft.dropdown.Option(key="ALL", text="Όλα τα Θέματα"),
            ft.dropdown.Option(key="2", text="Θέμα 2ο"),
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

    settings_dialog = SettingsDialog(page, on_save_callback=on_settings_saved, storage=storage)

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
                    ft.Text("• 🏫 Επιλογή Μαθήματος: Επιλέξτε Τύπο Σχολείου (ΓΕΛ / ΕΠΑΛ), Τάξη (Γ', Β', Α') και Μάθημα από την πάνω μπάρα για να φορτωθούν τα αντίστοιχα θέματα.", size=16, color=TEXT_MAIN),
                    ft.Text("• 📂 Οργάνωση & Φιλτράρισμα: Φιλτράρισμα ανά Κεφάλαιο, ομαδοποίηση ανά ακέραιο κεφάλαιο, επιλογή Τύπου Θέματος (2ο, 4ο) και γρήγορη αναζήτηση με λέξεις-κλειδιά.", size=16, color=TEXT_MAIN),
                    ft.Text("• 💡 Ζεύγη Θεμάτων & Απαντήσεων: Σε κάθε θέμα εμφανίζεται άμεσα η εκφώνηση και ακριβώς από κάτω η ενδεικτική απάντηση/λύση με κουμπιά προβολής και λήψης.", size=16, color=TEXT_MAIN),
                    ft.Text("• 📑 Εξαγωγή σε PDF: Πατήστε «Παραγωγή ολοκληρωμένου pdf μαθήματος» ή «PDF Κεφαλαίου» για να δημιουργήσετε ενιαίο PDF με όλα τα θέματα και τις απαντήσεις τους στη σειρά.", size=16, color=TEXT_MAIN),
                    ft.Text("• 🎨 Έξυπνη Στοίβαξη & Χρωματισμός: Εκφωνήσεις με μαύρα γράμματα και απαντήσεις με σκούρο μπλε (#0D338C). Στις Ρυθμίσεις (⚙️) ελέγχετε την αφαίρεση κενού χώρου, τις διαχωριστικές σελίδες και τον Πίνακα Περιεχομένων.", size=16, color=TEXT_MAIN),
                    ft.Text("• ⚡ 100% Offline Λειτουργία & Prefetch: Όλα τα δεδομένα και τα PDF αποθηκεύονται τοπικά. Χρησιμοποιήστε τα ειδικά κουμπιά «Prefetch ΓΕΛ», «Prefetch ΕΠΑΛ», «Prefetch Ε.Α.Ε.», «Prefetch ΕΝΕΕΓΥ-Λ» ή «Λήψη PDF Μαθήματος» για πλήρη offline χρήση.", size=16, color=TEXT_MAIN),
                    ft.Text("• ⚙️ Προσαρμοσμένα Στοιχεία: Ορίστε δικό σας τίτλο επικεφαλίδας, κείμενο υποσέλιδου και σελιδοποίηση από το παράθυρο Ρυθμίσεων.", size=16, color=TEXT_MAIN),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, color="#1E40AF", size=24),
                                ft.Column(
                                    controls=[
                                        ft.Text("Οδηγός ορθής & συνειδητής χρήσης (USAGE.md):", weight=ft.FontWeight.BOLD, size=14, color="#1E3A8A"),
                                        ft.Text("Παράκληση προς τους συναδέλφους για ορθολογική λήψη δεδομένων, σεβασμό των σχολικών ωρών και μηδενική σπατάλη χαρτιού.", size=13, color="#1E40AF"),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Button(
                                    content=ft.Text("Άνοιγμα οδηγού ↗", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                    style=ft.ButtonStyle(
                                        bgcolor="#2563EB",
                                        shape=ft.RoundedRectangleBorder(radius=6),
                                        padding=ft.Padding(12, 8, 12, 8)
                                    ),
                                    on_click=lambda e: webbrowser.open("https://github.com/spyalekos/SpyQBank/blob/master/USAGE.md")
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor="#EFF6FF",
                        border=ft.Border.all(1, "#BFDBFE"),
                        border_radius=8,
                        padding=12,
                    ),
                    ft.Divider(height=16, color=BORDER_COLOR),
                    ft.Row(
                        controls=[
                            ft.Text(f"Έκδοση: v{__version__}", size=14, color=TEXT_MUTED, italic=True),
                            ft.Text(" • ", size=14, color=TEXT_MUTED),
                            ft.Text("Δημιουργός: ", size=14, color=TEXT_MUTED, italic=True),
                            ft.TextButton(
                                content=ft.Text("SpyAlekos", size=14, color=PRIMARY, weight=ft.FontWeight.BOLD),
                                style=ft.ButtonStyle(padding=ft.Padding(4, 0, 4, 0)),
                                on_click=lambda e: webbrowser.open("https://alekos.program.gr"),
                                tooltip="https://alekos.program.gr"
                            ),
                        ],
                        spacing=2,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "Όλα τα θέματα προέρχονται και αντλούνται από την πλατφόρμα της Τράπεζας Θεμάτων Διαβαθμισμένης Δυσκολίας που αναπτύχθηκε (MIS5070818-Τράπεζα θεμάτων Διαβαθμισμένης Δυσκολίας για τη Δευτεροβάθμια Εκπαίδευση, Γενικό Λύκειο-ΕΠΑΛ) και είναι διαδικτυακά στο δικτυακό τόπο του Ινστιτούτου Εκπαιδευτικής Πολιτικής (Ι.Ε.Π.) στη διεύθυνση https://www.iep.edu.gr/trapeza-thematon-arxiki-selida/.",
                        size=14,
                        color="#D97706",
                        weight=ft.FontWeight.W_500,
                        italic=True,
                    ),
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
    def _create_prefetch_btn(label: str, bg_color: str, tooltip_txt: str) -> ft.Button:
        return ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CLOUD_DOWNLOAD, size=14, color=ft.Colors.WHITE),
                    ft.Text(label, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                ],
                spacing=3,
                tight=True
            ),
            style=ft.ButtonStyle(
                bgcolor=bg_color,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding(8, 6, 8, 6)
            ),
            tooltip=tooltip_txt,
        )

    prefetch_gel_button = _create_prefetch_btn("Prefetch ΓΕΛ", "#2563EB", "Προφόρτωση όλων των θεμάτων ΓΕΛ (Γενικό Λύκειο)")
    prefetch_epal_button = _create_prefetch_btn("Prefetch ΕΠΑΛ", "#4F46E5", "Προφόρτωση όλων των θεμάτων ΕΠΑΛ (Επαγγελματικό Λύκειο)")
    prefetch_eae_button = _create_prefetch_btn("Prefetch Ε.Α.Ε.", "#7C3AED", "Προφόρτωση όλων των θεμάτων Ειδικής Αγωγής (Λύκεια Ε.Α.Ε.)")
    prefetch_eneegyl_button = _create_prefetch_btn("Prefetch ΕΝΕΕΓΥ-Λ", "#0D9488", "Προφόρτωση όλων των θεμάτων ΕΝ.Ε.Ε.ΓΥ-Λ (Ειδικά Επαγγελματικά Γυμνάσια-Λύκεια)")
    prefetch_buttons = [prefetch_gel_button, prefetch_epal_button, prefetch_eae_button, prefetch_eneegyl_button]
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
                ft.Text("Παραγωγή ολοκληρωμένου pdf μαθήματος", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
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
    cache_subject_pdfs_button = ft.Button(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE, size=15, color="#1E40AF"),
                ft.Text("Λήψη PDF Μαθήματος", size=12, color="#1E40AF", weight=ft.FontWeight.W_600),
            ],
            spacing=4,
            tight=True,
        ),
        style=ft.ButtonStyle(
            bgcolor="#EFF6FF",
            shape=ft.RoundedRectangleBorder(radius=6),
            side=ft.BorderSide(1, "#BFDBFE"),
            padding=ft.Padding(10, 6, 10, 6),
        ),
        tooltip="Λήψη όλων των PDF (Εκφωνήσεων & Απαντήσεων) του επιλεγμένου μαθήματος στην τοπική μνήμη για 100% offline χρήση"
    )

    prefetch_dialog_title = ft.Text("Προφόρτωση για Offline Χρήση", weight=ft.FontWeight.BOLD, size=18)
    prefetch_dialog_desc = ft.Text("Επιλέξτε τον επιθυμητό τρόπο προφόρτωσης:", size=13, color=TEXT_MAIN)
    prefetch_dialog_meta_info = ft.Text(
        "Αποθηκεύει τοπικά τα θέματα, τίτλους και κεφάλαια όλων των μαθημάτων. Επιτρέπει άμεση αναζήτηση, φιλτράρισμα και περιήγηση χωρίς internet.",
        size=11,
        color=TEXT_MUTED
    )
    current_prefetch_target = {"id": 3, "short": "ΕΠΑΛ", "full": "Επαγγελματικό Λύκειο"}

    def _close_prefetch_dialog():
        prefetch_dialog.open = False
        page.update()

    prefetch_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.CLOUD_DOWNLOAD, color=PRIMARY, size=28),
                prefetch_dialog_title,
            ],
            spacing=10
        ),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    prefetch_dialog_desc,
                    ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("⚡ 1. Γρήγορη Προφόρτωση Μεταδεδομένων", weight=ft.FontWeight.BOLD, size=13, color=PRIMARY_DARK),
                                prefetch_dialog_meta_info,
                            ],
                            spacing=2,
                        ),
                        bgcolor="#F8FAFC",
                        border=ft.Border.all(1, "#E2E8F0"),
                        border_radius=6,
                        padding=10,
                    ),
                    ft.Divider(height=6, color=ft.Colors.TRANSPARENT),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("💾 2. Πλήρης Προφόρτωση με Όλα τα PDF (100% Offline)", weight=ft.FontWeight.BOLD, size=13, color="#059669"),
                                ft.Text("Κατεβάζει τόσο τα μεταδεδομένα όσο και ΟΛΑ τα αρχεία PDF εκφωνήσεων & απαντήσεων στην τοπική cache. Επιτρέπει πλήρη προβολή και εξαγωγή συνδυαστικών PDF χωρίς ίχνος internet.", size=11, color=TEXT_MUTED),
                            ],
                            spacing=2,
                        ),
                        bgcolor="#F0FDF4",
                        border=ft.Border.all(1, "#BBF7D0"),
                        border_radius=6,
                        padding=10,
                    ),
                ],
                tight=True,
                spacing=4
            ),
            width=540,
            padding=10
        ),
        actions=[
            ft.Button(
                content=ft.Text("Ακύρωση", color=TEXT_MUTED),
                style=ft.ButtonStyle(
                    bgcolor=YELLOW_GREY,
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.Padding(14, 10, 14, 10)
                ),
                on_click=lambda e: _close_prefetch_dialog()
            ),
            ft.Button(
                content=ft.Text("Μόνο Μεταδεδομένα", color=PRIMARY_DARK, weight=ft.FontWeight.BOLD),
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.Padding(14, 10, 14, 10)
                ),
                on_click=lambda e: _start_prefetch(current_prefetch_target["id"], current_prefetch_target["short"], include_pdfs=False)
            ),
            ft.Button(
                content=ft.Text("Πλήρης Λήψη (+PDFs)", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                style=ft.ButtonStyle(
                    bgcolor="#059669",
                    shape=ft.RoundedRectangleBorder(radius=6),
                    padding=ft.Padding(16, 10, 16, 10)
                ),
                on_click=lambda e: _start_prefetch(current_prefetch_target["id"], current_prefetch_target["short"], include_pdfs=True)
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    is_busy = False

    def set_ui_busy(busy: bool):
        nonlocal is_busy
        is_busy = busy
        # Disable & visually gray out top & selector bar controls
        for p_btn in prefetch_buttons:
            p_btn.disabled = busy
            p_btn.opacity = 0.5 if busy else 1.0

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

        cache_subject_pdfs_button.disabled = busy
        cache_subject_pdfs_button.opacity = 0.5 if busy else 1.0

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
        set_status(f"Επεξεργασία & άνοιγμα PDF #{item.id}...", show_progress=True)

        async def worker():
            kind_label = "Εκφώνηση" if file_type == 1 else "Λύση"
            kind_slug = "assignment" if file_type == 1 else "solution"
            log_console.log(f"Προετοιμασία PDF #{item.id} ({kind_label}) με τίτλους & χρωματισμό...")
            processed_filename = f"IEP_{item.subject_id}_{item.id}_{kind_slug}_view.pdf"
            dest = os.path.join(storage.pdf_cache_dir, processed_filename)
            try:
                final_pdf = await asyncio.to_thread(
                    pdf_builder.build_single_item_report,
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
                set_status("Έτοιμο.", progress=None, show_progress=False)
                set_ui_busy(False)

        page.run_task(worker)

    def handle_download_pdf(item: QuestionItem, file_type: int):
        if is_busy:
            return

        # ⚡ Immediately lock & gray out UI on current UI turn
        set_ui_busy(True)
        set_status(f"Λήψη & μορφοποίηση PDF #{item.id}...", show_progress=True)

        async def worker():
            kind_label = "εκφωνηση" if file_type == 1 else "απαντηση"
            downloads_dir = os.path.abspath("downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            filename = f"IEP_{item.subject_id}_{item.id}_{kind_label}.pdf"
            dest = os.path.join(downloads_dir, filename)

            log_console.log(f"Επεξεργασία & λήψη PDF στο φάκελο downloads: {filename}...")
            try:
                saved_path = await asyncio.to_thread(
                    pdf_builder.build_single_item_report,
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
                set_status("Έτοιμο.", progress=None, show_progress=False)
                set_ui_busy(False)

        page.run_task(worker)

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

        # Update summary banner with offline cache indicator
        total_sub = len(all_items)
        visible_cnt = len(filtered_items)
        sub_name = selected_subject.name if selected_subject else ""
        pdf_stat = storage.get_subject_pdf_status(all_items) if all_items else {}
        total_pdfs = total_sub * 2
        cached_pdfs = (pdf_stat.get("cached_assignments", 0) + pdf_stat.get("cached_solutions", 0)) if pdf_stat else 0

        cache_indicator = ""
        if total_sub > 0:
            if cached_pdfs == total_pdfs and total_pdfs > 0:
                cache_indicator = f"  •  💾 100% έτοιμο offline ({cached_pdfs}/{total_pdfs} PDF)"
            elif cached_pdfs > 0:
                cache_indicator = f"  •  💾 {cached_pdfs}/{total_pdfs} PDF στην Cache"
            else:
                cache_indicator = "  •  🌐 Online (Χωρίς τοπικά PDF)"

        summary_label.value = f"📚 {sub_name}: Εμφανίζονται {visible_cnt} από {total_sub} θέματα{cache_indicator}"
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
        set_status(f"Φόρτωση θεμάτων για: {subject.name}...", show_progress=True)

        async def worker():
            nonlocal all_items, selected_subject
            selected_subject = subject

            log_console.log(f"Φόρτωση θεμάτων: {subject.name} (ID: {subject.id})...")
            await asyncio.sleep(0.01)

            # Try loading cache first if not forced
            cached = await asyncio.to_thread(storage.load_subject_items, subject.school_type_id, subject.class_id, subject.id)
            if cached and not force_refresh:
                all_items = cached
                log_console.log(f"Φορτώθηκαν {len(all_items)} θέματα από την τοπική cache.", "SUCCESS")
            else:
                try:
                    fresh_items = await asyncio.to_thread(
                        api_client.get_subject_items,
                        subject.school_type_id,
                        subject.class_id,
                        subject.id
                    )
                    report = await asyncio.to_thread(
                        storage.detect_changes,
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

            set_status(f"Φορτώθηκαν {len(all_items)} θέματα για: {subject.name}.", show_progress=False)
            set_ui_busy(False)
            update_filtered_list()

        page.run_task(worker)

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

    def handle_open_prefetch(type_id: int, short_name: str, full_name: str):
        if is_busy:
            return
        nonlocal current_prefetch_target
        current_prefetch_target = {"id": type_id, "short": short_name, "full": full_name}

        target_st = next((st for st in school_types if st.id == type_id or short_name.upper() in st.name.upper()), None)
        count_str = ""
        if target_st:
            cnt = sum(len(cl.lessons) for cl in target_st.classes)
            count_str = f"των {cnt} "

        prefetch_dialog_title.value = f"Προφόρτωση {short_name} για Offline Χρήση"
        prefetch_dialog_desc.value = f"Επιλέξτε τον επιθυμητό τρόπο προφόρτωσης {count_str}μαθημάτων {short_name} ({full_name}):"
        prefetch_dialog_meta_info.value = f"Αποθηκεύει τοπικά τα θέματα, τίτλους και κεφάλαια όλων των μαθημάτων {short_name}. Επιτρέπει άμεση αναζήτηση, φιλτράρισμα και περιήγηση χωρίς internet."

        if prefetch_dialog not in page.overlay:
            page.overlay.append(prefetch_dialog)
        prefetch_dialog.open = True
        page.update()

    def _start_prefetch(type_id: int, short_name: str, include_pdfs: bool):
        prefetch_dialog.open = False
        set_ui_busy(True)
        mode_str = "Μεταδεδομένα + Όλα τα PDF" if include_pdfs else "Μεταδεδομένα"
        set_status(f"Έναρξη προφόρτωσης {short_name} ({mode_str})...", progress=0.0, show_progress=True)

        async def worker():
            nonlocal cancel_requested
            cancel_requested = False
            log_console.log(f"=== ΕΝΑΡΞΗ PREFETCH {short_name.upper()} ({mode_str.upper()}) ===")
            target_type = next((st for st in school_types if st.id == type_id or short_name.upper() in st.name.upper()), None)
            if not target_type:
                log_console.log(f"Δεν βρέθηκε ο τύπος σχολείου {short_name} στο δέντρο.", "ERROR")
                show_snackbar(f"Δεν βρέθηκε ο τύπος σχολείου {short_name}.", is_error=True)
                set_status("Έτοιμο.", progress=None, show_progress=False)
                set_ui_busy(False)
                return

            all_lessons: list[tuple[ClassLevel, Subject]] = []
            for cl in sorted(target_type.classes, key=class_sort_key):
                for sub in cl.lessons:
                    all_lessons.append((cl, sub))

            total_subjects = len(all_lessons)
            log_console.log(f"Συνολικά μαθήματα {short_name} προς επεξεργασία: {total_subjects}")
            await asyncio.sleep(0.01)

            downloaded_cnt = 0
            cached_cnt = 0
            error_cnt = 0
            pdf_downloaded_cnt = 0

            for idx, (cl, sub) in enumerate(all_lessons, start=1):
                if cancel_requested:
                    break

                progress_val = idx / total_subjects
                set_status(f"[{idx}/{total_subjects}] {cl.name} - {sub.name}...", progress=progress_val, show_progress=True)
                await asyncio.sleep(0.01)

                # Check if metadata already cached
                cached = await asyncio.to_thread(storage.load_subject_items, target_type.id, cl.id, sub.id)
                current_lesson_items = []
                if cached:
                    cached_cnt += 1
                    current_lesson_items = cached
                    log_console.log(f"[{idx}/{total_subjects}] (Cache) {cl.name} -> {sub.name} ({len(cached)} θέματα)")
                    await asyncio.sleep(0.02)
                else:
                    # Fetch from IEP API with rate-limiting delay
                    delay = random.uniform(1.0, 3.5)
                    await asyncio.sleep(delay)
                    try:
                        fresh_items = await asyncio.to_thread(api_client.get_subject_items, target_type.id, cl.id, sub.id)
                        await asyncio.to_thread(storage.save_subject_items, target_type.id, cl.id, sub.id, fresh_items)
                        downloaded_cnt += 1
                        current_lesson_items = fresh_items
                        log_console.log(f"[{idx}/{total_subjects}] (API) {cl.name} -> {sub.name}: {len(fresh_items)} θέματα", "SUCCESS")
                        await asyncio.sleep(0.01)
                    except Exception as ex:
                        error_cnt += 1
                        log_console.log(f"[{idx}/{total_subjects}] Σφάλμα στο μάθημα {sub.name}: {ex}", "ERROR")
                        await asyncio.sleep(0.01)

                # If include_pdfs is requested, ensure all PDFs are cached
                if include_pdfs and current_lesson_items:
                    total_items = len(current_lesson_items)
                    for p_idx, it in enumerate(current_lesson_items, start=1):
                        if cancel_requested:
                            break

                        p_assign = storage.get_pdf_cache_path(it.id, 1)
                        p_sol = storage.get_pdf_cache_path(it.id, 2)

                        need_assign = not os.path.exists(p_assign) or os.path.getsize(p_assign) == 0
                        need_sol = not os.path.exists(p_sol) or os.path.getsize(p_sol) == 0

                        if need_assign or need_sol:
                            set_status(f"[{idx}/{total_subjects}] {sub.name} [{p_idx}/{total_items}]: Λήψη PDF #{it.id}...", progress=progress_val, show_progress=True)
                            log_console.log(f"[{idx}/{total_subjects}] {sub.name} [{p_idx}/{total_items}]: Λήψη PDF #{it.id}...")
                            await asyncio.sleep(0.01)

                        if need_assign:
                            try:
                                await asyncio.to_thread(api_client.download_file, it.get_assignment_pdf_url(), p_assign)
                                pdf_downloaded_cnt += 1
                                await asyncio.sleep(random.uniform(0.15, 0.35))
                            except Exception as ex_a:
                                log_console.log(f"Σφάλμα λήψης εκφώνησης #{it.id}: {ex_a}", "WARNING")
                                await asyncio.sleep(0.01)

                        if need_sol:
                            try:
                                await asyncio.to_thread(api_client.download_file, it.get_solution_pdf_url(), p_sol)
                                pdf_downloaded_cnt += 1
                                await asyncio.sleep(random.uniform(0.15, 0.35))
                            except Exception as ex_s:
                                log_console.log(f"Σφάλμα λήψης απάντησης #{it.id}: {ex_s}", "WARNING")
                                await asyncio.sleep(0.01)

            pdf_extra = f", {pdf_downloaded_cnt} νέα PDF αποθηκεύτηκαν" if include_pdfs else ""
            if cancel_requested:
                log_console.log(f"🛑 [ΔΙΑΚΟΠΗ ΜΕ ESC] Προφόρτωση {short_name}: Διακόπηκε από το χρήστη. Προφορτώθηκαν: {downloaded_cnt} νέα μαθήματα, {cached_cnt} υπήρχαν στην cache{pdf_extra}, {error_cnt} σφάλματα πριν τη διακοπή.", "WARNING")
                show_snackbar(f"Διακοπή Prefetch {short_name} με Esc ({downloaded_cnt} μαθήματα{pdf_extra}).", is_error=True)
                set_status(f"Διακόπηκε με Esc. Προφορτώθηκαν {downloaded_cnt} μαθήματα.", progress=None, show_progress=False)
            else:
                log_console.log(f"=== ΟΛΟΚΛΗΡΩΣΗ PREFETCH {short_name.upper()} ===", "SUCCESS")
                log_console.log(f"Αποτελέσματα: {downloaded_cnt} μαθήματα λήφθηκαν, {cached_cnt} υπήρχαν στην cache{pdf_extra}, {error_cnt} σφάλματα.", "SUCCESS")
                show_snackbar(f"Ολοκληρώθηκε το Prefetch {short_name} ({downloaded_cnt} νέα μαθήματα{pdf_extra}).")
                set_status(f"Έτοιμο. Η προφόρτωση {short_name} ολοκληρώθηκε.", progress=None, show_progress=False)
            set_ui_busy(False)

        page.run_task(worker)

    def handle_cache_subject_pdfs(e):
        if is_busy:
            return
        if not selected_subject or not all_items:
            show_snackbar("Παρακαλώ επιλέξτε πρώτα μάθημα με διαθέσιμα θέματα.", is_error=True)
            return

        set_ui_busy(True)
        set_status(f"Λήψη αρχείων PDF για: {selected_subject.name}...", progress=0.0, show_progress=True)

        async def worker():
            nonlocal cancel_requested
            cancel_requested = False
            log_console.log(f"Έναρξη λήψης PDF για το μάθημα: {selected_subject.name} ({len(all_items)} θέματα)...")
            total = len(all_items)
            downloaded = 0
            already_cached = 0
            errors = 0

            for idx, it in enumerate(all_items, start=1):
                if cancel_requested:
                    break

                set_status(f"Λήψη PDF [{idx}/{total}]: Θέμα #{it.id}...", progress=idx / total, show_progress=True)
                await asyncio.sleep(0.01)

                p_assign = storage.get_pdf_cache_path(it.id, 1)
                p_sol = storage.get_pdf_cache_path(it.id, 2)

                # Assignment PDF
                if not os.path.exists(p_assign) or os.path.getsize(p_assign) == 0:
                    try:
                        await asyncio.to_thread(api_client.download_file, it.get_assignment_pdf_url(), p_assign)
                        downloaded += 1
                        await asyncio.sleep(random.uniform(0.15, 0.35))
                    except Exception as ex:
                        errors += 1
                        log_console.log(f"Σφάλμα λήψης εκφώνησης #{it.id}: {ex}", "ERROR")
                        await asyncio.sleep(0.01)
                else:
                    already_cached += 1
                    await asyncio.sleep(0.01)

                if cancel_requested:
                    break

                # Solution PDF
                if not os.path.exists(p_sol) or os.path.getsize(p_sol) == 0:
                    try:
                        await asyncio.to_thread(api_client.download_file, it.get_solution_pdf_url(), p_sol)
                        downloaded += 1
                        await asyncio.sleep(random.uniform(0.15, 0.35))
                    except Exception as ex:
                        errors += 1
                        log_console.log(f"Σφάλμα λήψης απάντησης #{it.id}: {ex}", "ERROR")
                        await asyncio.sleep(0.01)
                else:
                    already_cached += 1
                    await asyncio.sleep(0.01)

            if cancel_requested:
                log_console.log(f"🛑 [ΔΙΑΚΟΠΗ ΜΕ ESC] Λήψη PDF: Διακόπηκε από το χρήστη. Αποθηκεύτηκαν {downloaded} νέα, {already_cached} υπήρχαν στην cache, {errors} σφάλματα.", "WARNING")
                show_snackbar(f"Διακοπή λήψης PDF με Esc ({downloaded} νέα αποθηκεύτηκαν).", is_error=True)
                set_status(f"Διακόπηκε με Esc. Αποθηκεύτηκαν {downloaded} νέα PDF.", progress=None, show_progress=False)
            else:
                log_console.log(f"Ολοκληρώθηκε η λήψη PDF: {downloaded} νέα λήφθηκαν, {already_cached} υπήρχαν στην cache, {errors} σφάλματα.", "SUCCESS")
                show_snackbar(f"Ολοκληρώθηκε η αποθήκευση PDF ({downloaded} νέα, {already_cached} cache).")
                set_status("Έτοιμο. Όλα τα PDF του μαθήματος αποθηκεύτηκαν.", progress=None, show_progress=False)
            update_filtered_list()
            set_ui_busy(False)

        page.run_task(worker)

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
        set_status("Έναρξη εξαγωγής PDF...", show_progress=True)

        async def worker():
            cfg = load_config()
            group_by_main = cfg.get("group_by_main_chapter", True)
            target_chapter = selected_chapter if (only_selected_chapter and selected_chapter != "ALL") else None
            items_to_export = [
                it for it in all_items
                if not target_chapter or it.matches_chapter(target_chapter, group_by_main_chapter=group_by_main)
            ]

            if not items_to_export:
                show_snackbar("Δεν βρέθηκαν θέματα για το επιλεγμένο κεφάλαιο.", is_error=True)
                set_status("Έτοιμο.", progress=None, show_progress=False)
                set_ui_busy(False)
                return

            ch_slug = target_chapter[:25].replace("/", "_").replace("\\", "_") if target_chapter else "ALL_CHAPTERS"
            pdf_filename = f"SpyQBank_{selected_subject.id}_{ch_slug}.pdf"
            downloads_dir = os.path.abspath("downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            output_path = os.path.join(downloads_dir, pdf_filename)

            log_console.log(f"Έναρξη δημιουργίας PDF: {pdf_filename} ({len(items_to_export)} θέματα)...", "PDF")
            await asyncio.sleep(0.01)

            def on_pdf_progress(msg: str, progress: float):
                set_status(msg, progress=progress, show_progress=True)
                log_console.log(msg)

            try:
                final_pdf = await asyncio.to_thread(
                    pdf_builder.build_combined_report,
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

        page.run_task(worker)

    # Attach clicks
    prefetch_gel_button.on_click = lambda _: handle_open_prefetch(1, "ΓΕΛ", "Γενικό Λύκειο")
    prefetch_epal_button.on_click = lambda _: handle_open_prefetch(3, "ΕΠΑΛ", "Επαγγελματικό Λύκειο")
    prefetch_eae_button.on_click = lambda _: handle_open_prefetch(6, "Ε.Α.Ε.", "Λύκεια Ειδικής Αγωγής")
    prefetch_eneegyl_button.on_click = lambda _: handle_open_prefetch(7, "ΕΝΕΕΓΥ-Λ", "ΕΝ.Ε.Ε.ΓΥ-Λ")

    sync_button.on_click = handle_sync_check
    export_all_button.on_click = lambda e: handle_export_pdf(e, only_selected_chapter=False)
    settings_button.on_click = lambda _: settings_dialog.show() if not is_busy else None
    help_button.on_click = lambda _: _show_help() if not is_busy else None
    folder_button.on_click = lambda _: (os.startfile(os.path.abspath("downloads")) if sys.platform == "win32" else webbrowser.open(f"file://{os.path.abspath('downloads')}")) if not is_busy else None
    export_chapter_button.on_click = lambda e: handle_export_pdf(e, only_selected_chapter=True)
    cache_subject_pdfs_button.on_click = handle_cache_subject_pdfs


    # --- Initial Data Load ---

    def init_tree():
        async def worker():
            nonlocal school_types
            set_status("Φόρτωση δέντρου μαθημάτων ΙΕΠ...", show_progress=True)
            log_console.log("Φόρτωση δέντρου τύπων σχολείων & μαθημάτων...")
            await asyncio.sleep(0.01)

            cached_tree = await asyncio.to_thread(storage.load_tree)
            if cached_tree:
                school_types = cached_tree
                log_console.log("Φορτώθηκε το δέντρο σχολείων από την τοπική cache.", "SUCCESS")
            else:
                try:
                    school_types = await asyncio.to_thread(api_client.get_school_tree)
                    await asyncio.to_thread(storage.save_tree, school_types)
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

            set_status("Έτοιμο. Επιλέξτε μάθημα.", progress=None, show_progress=False)

        page.run_task(worker)

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
                        prefetch_gel_button,
                        prefetch_epal_button,
                        prefetch_eae_button,
                        prefetch_eneegyl_button,
                        sync_button,
                        export_all_button,
                        settings_button,
                        help_button,
                        folder_button
                    ],
                    spacing=6,
                    wrap=True
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
        content=ft.Row(
            controls=[
                summary_label,
                ft.Container(expand=True),
                cache_subject_pdfs_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
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
                        status_spinner,
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=TEXT_MUTED),
                        status_text,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
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

    # Close PyInstaller splash screen if running
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

    # Start initialization thread
    init_tree()


if __name__ == "__main__":
    ft.run(main)
