"""Settings dialog for SpyQBank."""

import flet as ft
from src.config import load_config, save_config
from src.ui.theme import PRIMARY, TEXT_MAIN, TEXT_MUTED


class SettingsDialog:
    """Dialog for editing custom centered PDF header title and footer text."""

    def __init__(self, page: ft.Page, on_save_callback: callable = None, storage=None):
        self.page = page
        self.on_save_callback = on_save_callback
        self.storage = storage

        self.cfg = load_config()

        self.cache_stats_text = ft.Text("", size=11, color=TEXT_MUTED)

        self.header_field = ft.TextField(
            label="Τίτλος Επικεφαλίδας (Πάνω Αριστερά)",
            hint_text="π.χ. Φροντιστήριο / Εκπαιδευτικός Οργανισμός",
            value=self.cfg.get("custom_header_title", ""),
            autofocus=True,
            width=500,
        )

        self.footer_field = ft.TextField(
            label="Κείμενο Υποσέλιδου (Κάτω Κέντρο)",
            hint_text="π.χ. Επιμέλεια: Καθηγητής ... | Τηλ: 210xxxxxxx",
            value=self.cfg.get("custom_footer_text", ""),
            width=500,
        )

        self.trim_switch = ft.Switch(
            value=self.cfg.get("trim_whitespace", True),
        )

        self.trim_control = ft.Row(
            controls=[
                self.trim_switch,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Αφαίρεση κενού χώρου (Smart Packing & Whitespace Trimming)", size=13, weight=ft.FontWeight.W_500, color=TEXT_MAIN),
                            ft.Text("Συνεχής κάθετη ροή και αφαίρεση περιττών λευκών περιθωρίων/κενών γραμμών στα παραγόμενα PDF.", size=11, color=TEXT_MUTED),
                        ],
                        spacing=1,
                    ),
                    expand=True,
                    on_click=lambda e: self._toggle_trim(),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.chapter_dividers_switch = ft.Switch(
            value=self.cfg.get("include_chapter_covers", True),
        )

        self.chapter_dividers_control = ft.Row(
            controls=[
                self.chapter_dividers_switch,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Σελίδες διαχωρισμού κεφαλαίων (Chapter Dividers)", size=13, weight=ft.FontWeight.W_500, color=TEXT_MAIN),
                            ft.Text("Εμφάνιση ενδιάμεσων διαχωριστικών σελίδων στην αρχή κάθε κεφαλαίου.", size=11, color=TEXT_MUTED),
                        ],
                        spacing=1,
                    ),
                    expand=True,
                    on_click=lambda e: self._toggle_chapter_dividers(),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.group_chapter_switch = ft.Switch(
            value=self.cfg.get("group_by_main_chapter", True),
        )

        self.group_chapter_control = ft.Row(
            controls=[
                self.group_chapter_switch,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Ομαδοποίηση ανά ακέραιο κεφάλαιο (1, 2, 3...)", size=13, weight=ft.FontWeight.W_500, color=TEXT_MAIN),
                            ft.Text("Συγχώνευση όλων των υποενοτήτων (1.1, 1.2, 1.3...) σε ενιαία ακέραια κεφάλαια στο φίλτρο και στο PDF.", size=11, color=TEXT_MUTED),
                        ],
                        spacing=1,
                    ),
                    expand=True,
                    on_click=lambda e: self._toggle_group_chapter(),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.toc_switch = ft.Switch(
            value=self.cfg.get("include_table_of_contents", True),
        )

        self.toc_control = ft.Row(
            controls=[
                self.toc_switch,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("Πίνακας Περιεχομένων στο τέλος (Table of Contents)", size=13, weight=ft.FontWeight.W_500, color=TEXT_MAIN),
                            ft.Text("Προσθήκη αναλυτικού πίνακα περιεχομένων στο τέλος του PDF με σελίδες θεμάτων & απαντήσεων.", size=11, color=TEXT_MUTED),
                        ],
                        spacing=1,
                    ),
                    expand=True,
                    on_click=lambda e: self._toggle_toc(),
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SETTINGS, color=PRIMARY, size=24),
                    ft.Text("Ρυθμίσεις Εξαγωγής PDF", weight=ft.FontWeight.BOLD, size=18),
                ],
                spacing=8
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Ο τίτλος επικεφαλίδας εμφανίζεται με αριστερή στοίχιση στο πάνω μέρος (χωρίς να επικαλύπτει τα κεφάλαια/θέματα δεξιά) και το κείμενο υποσέλιδου στο κάτω μέρος κάθε σελίδας των παραγόμενων PDF (σε όλες τις σελίδες εκτός του εξωφύλλου).",
                            size=12,
                            color=TEXT_MUTED
                        ),
                        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                        self.header_field,
                        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                        self.footer_field,
                        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                        self.trim_control,
                        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                        self.chapter_dividers_control,
                        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                        self.group_chapter_control,
                        ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
                        self.toc_control,
                        ft.Divider(height=8, color=ft.Colors.GREY_200),
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.STORAGE, size=16, color=PRIMARY),
                                    self.cache_stats_text,
                                    ft.Container(expand=True),
                                    ft.TextButton(
                                        content=ft.Text("🗑️ Καθαρισμός PDF", size=11, color=ft.Colors.RED_600),
                                        on_click=self._on_clear_cache
                                    )
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            bgcolor="#F8FAFC",
                            border=ft.Border.all(1, "#E2E8F0"),
                            border_radius=6,
                            padding=ft.Padding(8, 4, 8, 4)
                        ),
                        ft.Text(
                            "Οι ρυθμίσεις αποθηκεύονται αυτόματα στο αρχείο spyqbank.json στον φάκελο της εφαρμογής.",
                            size=11,
                            color=TEXT_MUTED,
                            italic=True
                        )
                    ],
                    tight=True,
                    spacing=6
                ),
                width=520,
                padding=10
            ),
            actions=[
                ft.Button(
                    content=ft.Text("Ακύρωση", color=TEXT_MUTED),
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TRANSPARENT,
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(16, 10, 16, 10)
                    ),
                    on_click=self._on_cancel
                ),
                ft.Button(
                    content=ft.Text("Αποθήκευση", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    style=ft.ButtonStyle(
                        bgcolor="#059669",
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(16, 10, 16, 10)
                    ),
                    on_click=self._on_save
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def _update_cache_stats(self):
        if self.storage:
            try:
                stats = self.storage.get_cache_stats()
                sub_cnt = stats.get("cached_subjects_count", 0)
                pdf_cnt = stats.get("cached_pdfs_count", 0)
                pdf_mb = stats.get("cached_pdfs_mb", 0.0)
                self.cache_stats_text.value = f"Offline Cache: {sub_cnt} μαθήματα | {pdf_cnt} PDF ({pdf_mb} MB)"
            except Exception:
                self.cache_stats_text.value = "Offline Cache: Ενεργή"
        else:
            self.cache_stats_text.value = "Offline Cache: Ενεργή"

    def _on_clear_cache(self, e):
        if self.storage:
            deleted = self.storage.clear_pdf_cache()
            self._update_cache_stats()
            self.page.update()
            if self.page.snack_bar:
                self.page.snack_bar.content = ft.Text(f"Διαγράφηκαν {deleted} προσωρινά αρχεία PDF από την cache.")
                self.page.snack_bar.bgcolor = "#059669"
                self.page.snack_bar.open = True
                self.page.update()

    def show(self):
        # Refresh current config
        self.cfg = load_config()
        self.header_field.value = self.cfg.get("custom_header_title", "")
        self.footer_field.value = self.cfg.get("custom_footer_text", "")
        self.trim_switch.value = self.cfg.get("trim_whitespace", True)
        self.chapter_dividers_switch.value = self.cfg.get("include_chapter_covers", True)
        self.group_chapter_switch.value = self.cfg.get("group_by_main_chapter", True)
        self.toc_switch.value = self.cfg.get("include_table_of_contents", True)
        self._update_cache_stats()
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _toggle_trim(self):
        self.trim_switch.value = not self.trim_switch.value
        self.page.update()

    def _toggle_chapter_dividers(self):
        self.chapter_dividers_switch.value = not self.chapter_dividers_switch.value
        self.page.update()

    def _toggle_group_chapter(self):
        self.group_chapter_switch.value = not self.group_chapter_switch.value
        self.page.update()

    def _toggle_toc(self):
        self.toc_switch.value = not self.toc_switch.value
        self.page.update()

    def _on_cancel(self, e):
        self.dialog.open = False
        self.page.update()

    def _on_save(self, e):
        new_cfg = {
            "custom_header_title": self.header_field.value.strip(),
            "custom_footer_text": self.footer_field.value.strip(),
            "trim_whitespace": bool(self.trim_switch.value),
            "include_chapter_covers": bool(self.chapter_dividers_switch.value),
            "group_by_main_chapter": bool(self.group_chapter_switch.value),
            "include_table_of_contents": bool(self.toc_switch.value),
        }
        save_config(new_cfg)
        self.dialog.open = False
        self.page.update()

        if self.on_save_callback:
            self.on_save_callback(new_cfg)

