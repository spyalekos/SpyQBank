"""Question & Answer Card UI Component for SpyQBank."""

import os
import webbrowser
import flet as ft

from src.models import QuestionItem
from src.ui.theme import (
    get_question_color,
    BORDER_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    PRIMARY_LIGHT,
    SECONDARY
)


class QuestionCard(ft.Container):
    """Card representing a single question and its paired solution."""

    def __init__(
        self,
        item: QuestionItem,
        on_view_pdf: callable,
        on_download: callable
    ):
        self.item = item
        self.on_view_pdf = on_view_pdf
        self.on_download = on_download

        q_num = item.question or 0
        q_color = get_question_color(q_num)

        # 1. Header Badges
        header_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(
                        item.question_label,
                        weight=ft.FontWeight.BOLD,
                        size=12,
                        color=ft.Colors.WHITE
                    ),
                    bgcolor=q_color,
                    border_radius=6,
                    padding=ft.Padding(8, 3, 8, 3)
                ),
                ft.Container(
                    content=ft.Text(
                        f"#{item.id}",
                        weight=ft.FontWeight.W_600,
                        size=12,
                        color=ft.Colors.BLUE_GREY_800
                    ),
                    bgcolor=ft.Colors.BLUE_GREY_100,
                    border_radius=6,
                    padding=ft.Padding(8, 3, 8, 3)
                ),
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CALENDAR_MONTH, size=14, color=TEXT_MUTED),
                        ft.Text(item.date or "-", size=12, color=TEXT_MUTED),
                    ],
                    spacing=4
                ),
                ft.Container(expand=True),
                # ZIP download button
                ft.IconButton(
                    icon=ft.Icons.FOLDER_ZIP_OUTLINED,
                    tooltip="Λήψη όλων των αρχείων (ZIP)",
                    icon_color=TEXT_MUTED,
                    icon_size=18,
                    on_click=lambda _: self._open_url(item.get_zip_url())
                )
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        # 2. Material / Chapters Tags
        material_chips = []
        if item.materials:
            for m in item.materials:
                material_chips.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.BOOKMARK_BORDER, size=13, color="#1E40AF"),
                                ft.Text(m.name, size=11, weight=ft.FontWeight.W_500, color="#1E40AF"),
                            ],
                            spacing=3,
                            tight=True
                        ),
                        bgcolor="#EFF6FF",
                        border=ft.Border.all(1, "#DBEAFE"),
                        border_radius=6,
                        padding=ft.Padding(6, 3, 6, 3)
                    )
                )
        else:
            material_chips.append(
                ft.Text("Χωρίς συγκεκριμένο κεφάλαιο", size=11, color=TEXT_MUTED, italic=True)
            )

        materials_row = ft.Row(
            controls=material_chips,
            wrap=True,
            spacing=6,
            run_spacing=6
        )

        # 3. Keywords / Remarks if any
        extra_controls = []
        if item.keywords:
            extra_controls.append(
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TAG, size=13, color=TEXT_MUTED),
                        ft.Text(f"Λέξεις-κλειδιά: {item.keywords}", size=11, color=TEXT_MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=4
                )
            )

        # 4. Action Section: Question & Solution Pairs (Βασικότερο Όλων)
        qa_section = ft.Container(
            content=ft.Row(
                controls=[
                    # 📄 ΕΚΦΩΝΗΣΗ (Question)
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=16, color="#1E3A8A"),
                                        ft.Text("Εκφώνηση Θέματος", size=13, weight=ft.FontWeight.BOLD, color="#1E3A8A"),
                                    ],
                                    spacing=4
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Button(
                                            content=ft.Row(
                                                controls=[
                                                    ft.Icon(ft.Icons.PICTURE_AS_PDF, size=15, color=ft.Colors.WHITE),
                                                    ft.Text("Προβολή PDF", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                                                ],
                                                spacing=4,
                                                tight=True
                                            ),
                                            style=ft.ButtonStyle(
                                                bgcolor="#2563EB",
                                                padding=ft.Padding(12, 6, 12, 6),
                                                shape=ft.RoundedRectangleBorder(radius=6)
                                            ),
                                            on_click=lambda _: self.on_view_pdf(self.item, 1)
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DOWNLOAD,
                                            tooltip="Αποθήκευση PDF Εκφώνησης",
                                            icon_size=18,
                                            icon_color="#2563EB",
                                            on_click=lambda _: self.on_download(self.item, 1)
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.TEXT_SNIPPET_OUTLINED,
                                            tooltip="Λήψη Word (.docx/.doc)",
                                            icon_size=18,
                                            icon_color=TEXT_MUTED,
                                            on_click=lambda _: self._open_url(self.item.get_assignment_doc_url())
                                        ) if item.has_assignment_doc else ft.Container()
                                    ],
                                    spacing=4
                                )
                            ],
                            spacing=6
                        ),
                        bgcolor="#F8FAFC",
                        border=ft.Border.all(1, "#E2E8F0"),
                        border_radius=8,
                        padding=10,
                        expand=True
                    ),

                    # 💡 ΕΝΔΕΙΚΤΙΚΗ ΑΠΑΝΤΗΣΗ / ΛΥΣΗ (Solution)
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, size=16, color="#065F46"),
                                        ft.Text("Ενδεικτική Απάντηση / Λύση", size=13, weight=ft.FontWeight.BOLD, color="#065F46"),
                                    ],
                                    spacing=4
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Button(
                                            content=ft.Row(
                                                controls=[
                                                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=15, color=ft.Colors.WHITE),
                                                    ft.Text("Προβολή Λύσης", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                                                ],
                                                spacing=4,
                                                tight=True
                                            ),
                                            style=ft.ButtonStyle(
                                                bgcolor="#059669",
                                                padding=ft.Padding(12, 6, 12, 6),
                                                shape=ft.RoundedRectangleBorder(radius=6)
                                            ),
                                            on_click=lambda _: self.on_view_pdf(self.item, 2)
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DOWNLOAD,
                                            tooltip="Αποθήκευση PDF Λύσης",
                                            icon_size=18,
                                            icon_color="#059669",
                                            on_click=lambda _: self.on_download(self.item, 2)
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.TEXT_SNIPPET_OUTLINED,
                                            tooltip="Λήψη Word (.docx/.doc) Λύσης",
                                            icon_size=18,
                                            icon_color=TEXT_MUTED,
                                            on_click=lambda _: self._open_url(self.item.get_solution_doc_url())
                                        ) if item.has_solution_doc else ft.Container()
                                    ],
                                    spacing=4
                                )
                            ],
                            spacing=6
                        ),
                        bgcolor="#F0FDF4",
                        border=ft.Border.all(1, "#DCFCE7"),
                        border_radius=8,
                        padding=10,
                        expand=True
                    )
                ],
                spacing=10
            )
        )

        content_column = ft.Column(
            controls=[
                header_row,
                materials_row,
                *extra_controls,
                qa_section
            ],
            spacing=8
        )

        super().__init__(
            content=content_column,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, BORDER_COLOR),
            border_radius=10,
            padding=12,
            margin=ft.Margin(0, 0, 0, 8),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=3,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 1)
            )
        )

    def _open_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass
