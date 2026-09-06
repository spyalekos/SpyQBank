"""PDF Report Generator and Merger for SpyQBank."""

import os
import io
import html
import logging
from typing import List, Optional, Callable, Dict
from pypdf import PdfWriter, PdfReader

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from src.models import QuestionItem
from src.iep_api import IepApiClient
from src.storage import StorageManager

logger = logging.getLogger("SpyQBank.PdfBuilder")

# Register Unicode / Greek fonts for ReportLab
FONT_REGULAR = "GreekSans"
FONT_BOLD = "GreekSans-Bold"

def _register_greek_fonts():
    """Find and register system fonts supporting Greek characters."""
    candidates_regular = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    candidates_bold = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]

    reg_path = None
    for p in candidates_regular:
        if os.path.exists(p):
            reg_path = p
            break

    bold_path = None
    for p in candidates_bold:
        if os.path.exists(p):
            bold_path = p
            break

    if reg_path:
        try:
            pdfmetrics.registerFont(TTFont(FONT_REGULAR, reg_path))
            logger.info(f"Registered {FONT_REGULAR} from {reg_path}")
        except Exception as e:
            logger.warning(f"Could not register {FONT_REGULAR}: {e}")

    if bold_path:
        try:
            pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
            logger.info(f"Registered {FONT_BOLD} from {bold_path}")
        except Exception as e:
            logger.warning(f"Could not register {FONT_BOLD}: {e}")

# Run font registration
_register_greek_fonts()


class PdfReportBuilder:
    """Builds comprehensive PDF reports pairing questions with their respective solutions."""

    def __init__(self, api_client: IepApiClient, storage: StorageManager):
        self.api = api_client
        self.storage = storage

    def _create_cover_page(self, title: str, subtitle: str, metadata_lines: List[str]) -> io.BytesIO:
        """Create a cover page using ReportLab in memory with Greek font support."""
        packet = io.BytesIO()
        doc = SimpleDocTemplate(
            packet,
            pagesize=A4,
            leftMargin=40,
            rightMargin=40,
            topMargin=50,
            bottomMargin=50
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CoverTitle',
            parent=styles['Normal'],
            fontName=FONT_BOLD if FONT_BOLD in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
            fontSize=22,
            leading=28,
            textColor=colors.HexColor('#1E293B'),
            alignment=1,  # Center
            spaceAfter=15
        )
        subtitle_style = ParagraphStyle(
            'CoverSubtitle',
            parent=styles['Normal'],
            fontName=FONT_REGULAR if FONT_REGULAR in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=14,
            leading=20,
            textColor=colors.HexColor('#2563EB'),
            alignment=1,  # Center
            spaceAfter=25
        )
        meta_style = ParagraphStyle(
            'CoverMeta',
            parent=styles['Normal'],
            fontName=FONT_REGULAR if FONT_REGULAR in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=11,
            leading=16,
            textColor=colors.HexColor('#64748B'),
            alignment=1,
            spaceAfter=8
        )

        story = [
            Spacer(1, 100),
            Paragraph(html.escape(title), title_style),
            Paragraph(html.escape(subtitle), subtitle_style),
            Spacer(1, 40),
        ]

        for line in metadata_lines:
            story.append(Paragraph(html.escape(line), meta_style))

        story.append(Spacer(1, 80))
        story.append(Paragraph("Τράπεζα Θεμάτων Διαβαθμισμένης Δυσκολίας - Ι.Ε.Π.", meta_style))
        story.append(Paragraph("Παραγωγή μέσω SpyQBank", meta_style))

        doc.build(story)
        packet.seek(0)
        return packet

    def _create_chapter_divider(self, chapter_name: str, question_count: int) -> io.BytesIO:
        """Create a divider page for a chapter with Greek font support."""
        packet = io.BytesIO()
        doc = SimpleDocTemplate(
            packet,
            pagesize=A4,
            leftMargin=40,
            rightMargin=40,
            topMargin=150,
            bottomMargin=50
        )
        styles = getSampleStyleSheet()
        ch_style = ParagraphStyle(
            'ChTitle',
            parent=styles['Normal'],
            fontName=FONT_BOLD if FONT_BOLD in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
            fontSize=18,
            leading=24,
            textColor=colors.HexColor('#0F172A'),
            alignment=1,
            spaceAfter=15
        )
        sub_style = ParagraphStyle(
            'ChSub',
            parent=styles['Normal'],
            fontName=FONT_REGULAR if FONT_REGULAR in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#64748B'),
            alignment=1
        )

        story = [
            Paragraph("Κεφάλαιο / Ενότητα:", sub_style),
            Spacer(1, 15),
            Paragraph(html.escape(chapter_name), ch_style),
            Spacer(1, 20),
            Paragraph(f"Σύνολο Θεμάτων: {question_count}", sub_style)
        ]

        doc.build(story)
        packet.seek(0)
        return packet

    def build_combined_report(
        self,
        items: List[QuestionItem],
        output_path: str,
        subject_name: str,
        chapter_name: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> str:
        """
        Merge all items (Question + Solution paired sequentially) into a single PDF.
        """
        writer = PdfWriter()

        # Deduplicate items
        unique_items_map = {it.id: it for it in items}
        unique_items = list(unique_items_map.values())
        unique_items.sort(key=lambda x: (x.question or 99, x.id))
        total_items = len(unique_items)

        if progress_callback:
            progress_callback("Προετοιμασία εξωφύλλου...", 0.05)

        # 1. Add Cover Page
        cover_title = f"Τράπεζα Θεμάτων: {subject_name}"
        cover_sub = chapter_name if chapter_name else "Όλα τα Κεφάλαια"
        meta = [
            f"Συνολικά Θέματα: {total_items}",
            "Περιλαμβάνονται: Εκφωνήσεις & Ενδεικτικές Απαντήσεις",
        ]
        cover_stream = self._create_cover_page(cover_title, cover_sub, meta)
        cover_reader = PdfReader(cover_stream)
        for page in cover_reader.pages:
            writer.add_page(page)

        # 2. Group items by primary chapter
        chapters_map: Dict[str, List[QuestionItem]] = {}
        for it in unique_items:
            primary_ch = it.materials[0].name if it.materials else "Γενικά / Χωρίς Κεφάλαιο"
            if primary_ch not in chapters_map:
                chapters_map[primary_ch] = []
            chapters_map[primary_ch].append(it)

        processed = 0
        for ch_title, ch_items in chapters_map.items():
            if len(chapters_map) > 1 and not chapter_name:
                ch_divider_stream = self._create_chapter_divider(ch_title, len(ch_items))
                div_reader = PdfReader(ch_divider_stream)
                writer.add_page(div_reader.pages[0])
                ch_outline = writer.add_outline_item(
                    title=f"📁 {ch_title}",
                    page_number=len(writer.pages) - 1
                )
            else:
                ch_outline = None

            for it in ch_items:
                processed += 1
                progress = 0.1 + (0.85 * (processed / max(1, total_items)))
                q_label = f"{it.question_label} #{it.id}"
                if progress_callback:
                    progress_callback(f"Επεξεργασία {q_label} ({processed}/{total_items})...", progress)

                # Download / get cached Assignment PDF
                assign_path = self.storage.get_pdf_cache_path(it.id, 1)
                sol_path = self.storage.get_pdf_cache_path(it.id, 2)

                try:
                    self.api.download_file(it.get_assignment_pdf_url(), assign_path)
                except Exception as e:
                    logger.warning(f"Could not download assignment PDF for #{it.id}: {e}")

                try:
                    self.api.download_file(it.get_solution_pdf_url(), sol_path)
                except Exception as e:
                    logger.warning(f"Could not download solution PDF for #{it.id}: {e}")

                # Add Assignment PDF pages
                q_outline = None
                if os.path.exists(assign_path) and os.path.getsize(assign_path) > 0:
                    try:
                        assign_reader = PdfReader(assign_path)
                        first_page = True
                        for page in assign_reader.pages:
                            writer.add_page(page)
                            if first_page:
                                first_page = False
                                page_idx = len(writer.pages) - 1
                                if ch_outline:
                                    q_outline = writer.add_outline_item(
                                        title=f"📄 {q_label} (Εκφώνηση)",
                                        page_number=page_idx,
                                        parent=ch_outline
                                    )
                                else:
                                    q_outline = writer.add_outline_item(
                                        title=f"📄 {q_label} (Εκφώνηση)",
                                        page_number=page_idx
                                    )
                    except Exception as e:
                        logger.error(f"Failed to append assignment PDF #{it.id}: {e}")

                # Add Solution PDF pages directly below
                if os.path.exists(sol_path) and os.path.getsize(sol_path) > 0:
                    try:
                        sol_reader = PdfReader(sol_path)
                        first_page = True
                        for page in sol_reader.pages:
                            writer.add_page(page)
                            if first_page:
                                first_page = False
                                page_idx = len(writer.pages) - 1
                                parent_item = q_outline or ch_outline
                                if parent_item:
                                    writer.add_outline_item(
                                        title=f"💡 {q_label} (Απάντηση)",
                                        page_number=page_idx,
                                        parent=parent_item
                                    )
                                else:
                                    writer.add_outline_item(
                                        title=f"💡 {q_label} (Απάντηση)",
                                        page_number=page_idx
                                    )
                    except Exception as e:
                        logger.error(f"Failed to append solution PDF #{it.id}: {e}")

        if progress_callback:
            progress_callback("Αποθήκευση τελικού αρχείου PDF...", 0.98)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            writer.write(f)

        if progress_callback:
            progress_callback("Ολοκληρώθηκε με επιτυχία!", 1.0)

        return output_path
