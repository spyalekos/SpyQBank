"""PDF Report Generator and Merger for SpyQBank."""

import os
import io
import re
import html
import random
import logging
from typing import List, Optional, Callable, Dict
from pypdf import PdfWriter, PdfReader
from pypdf.generic import DecodedStreamObject

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from src.models import QuestionItem
from src.iep_api import IepApiClient
from src.storage import StorageManager
from src.config import load_config

logger = logging.getLogger("SpyQBank.PdfBuilder")

# Register Unicode / Greek fonts for ReportLab
FONT_REGULAR = "GreekSans"
FONT_BOLD = "GreekSans-Bold"

# Dark Blue color for Solution text / lines (RGB values in 0.0 - 1.0 range)
# #0F2D6B or #0D338C (Rich Dark Navy Blue)
NAVY_R = "0.06"
NAVY_G = "0.20"
NAVY_B = "0.58"


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


def _recolor_stream_to_dark_blue(raw_bytes: bytes) -> bytes:
    """
    Recolor black / dark grayscale text, fills and strokes to dark navy blue (#0D338C).
    Assignment retains crisp black text, Solution is converted to dark navy blue.
    """
    try:
        text = raw_bytes.decode("latin1", errors="ignore")
        # 1. Replace standalone '0 g' (grayscale fill black) with navy RGB fill
        text = re.sub(r"(?<![0-9.])0(\.0+)?\s+g(?![a-zA-Z0-9])", f"{NAVY_R} {NAVY_G} {NAVY_B} rg", text)
        # 2. Replace standalone '0 G' (grayscale stroke black) with navy RGB stroke
        text = re.sub(r"(?<![0-9.])0(\.0+)?\s+G(?![a-zA-Z0-9])", f"{NAVY_R} {NAVY_G} {NAVY_B} RG", text)
        # 3. Replace '0 0 0 rg' (RGB fill black)
        text = re.sub(r"(?<![0-9.])0(\.0+)?\s+0(\.0+)?\s+0(\.0+)?\s+rg(?![a-zA-Z0-9])", f"{NAVY_R} {NAVY_G} {NAVY_B} rg", text)
        # 4. Replace '0 0 0 RG' (RGB stroke black)
        text = re.sub(r"(?<![0-9.])0(\.0+)?\s+0(\.0+)?\s+0(\.0+)?\s+RG(?![a-zA-Z0-9])", f"{NAVY_R} {NAVY_G} {NAVY_B} RG", text)
        # 5. Prepend global default dark navy color state
        prefix = f"{NAVY_R} {NAVY_G} {NAVY_B} rg\n{NAVY_R} {NAVY_G} {NAVY_B} RG\n"
        return (prefix + text).encode("latin1")
    except Exception as e:
        logger.warning(f"Failed to recolor stream: {e}")
        return raw_bytes


def _apply_solution_color(page):
    """
    Apply dark navy blue coloring directly to solution page stream object.
    """
    try:
        contents = page.get("/Contents")
        if contents is not None:
            c_obj = contents.get_object()
            if isinstance(c_obj, list):
                for single_stream in c_obj:
                    stream_obj = single_stream.get_object()
                    raw = stream_obj.get_data()
                    stream_obj.set_data(_recolor_stream_to_dark_blue(raw))
            else:
                raw = c_obj.get_data()
                c_obj.set_data(_recolor_stream_to_dark_blue(raw))
    except Exception as e:
        logger.warning(f"Error recoloring solution page: {e}")


def _trim_whitespace_margins(page):
    """
    Safely trim excessive empty white space around page margins without clipping
    header/footer overlays (cropbox kept at safe bounds: 18pt margins).
    """
    try:
        mb = page.mediabox
        w = float(mb.width)
        h = float(mb.height)
        # 18pt (~0.25 in) margin ensures headers (at h - 25) and footers (at y=20)
        # stay perfectly visible and clear while trimming peripheral white borders
        left_crop = 18.0
        right_crop = w - 18.0
        bottom_crop = 12.0
        top_crop = h - 12.0
        if right_crop > left_crop + 50 and top_crop > bottom_crop + 50:
            page.cropbox.lower_left = (left_crop, bottom_crop)
            page.cropbox.upper_right = (right_crop, top_crop)
    except Exception as e:
        logger.warning(f"Error cropping page margins: {e}")


class PdfReportBuilder:
    """Builds comprehensive PDF reports pairing questions with their respective solutions."""

    def __init__(self, api_client: IepApiClient, storage: StorageManager):
        self.api = api_client
        self.storage = storage

    def _create_header_footer_overlay(
        self,
        width: float,
        height: float,
        header_right_text: Optional[str],
        page_num: Optional[int],
        header_center_text: Optional[str] = None,
        footer_center_text: Optional[str] = None
    ):
        """
        Generate a transparent overlay page with:
        - Top-Center: Custom Title from Settings
        - Top-Right: Question Header (# θέματος)
        - Bottom-Center: Custom Footer Text from Settings
        - Bottom-Right: Page Number (- χχ -)
        """
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))

        font_bold = FONT_BOLD if FONT_BOLD in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
        font_regular = FONT_REGULAR if FONT_REGULAR in pdfmetrics.getRegisteredFontNames() else "Helvetica"

        # 1. Top-Center Header (Custom Title from Settings)
        if header_center_text:
            c.setFont(font_bold, 9)
            c.setFillColor(colors.HexColor("#334155"))
            c.drawCentredString(width / 2.0, height - 25, header_center_text)

        # 2. Top-Right Header (# θέματος)
        if header_right_text:
            c.setFont(font_bold, 9)
            c.setFillColor(colors.HexColor("#1E3A8A"))
            c.drawRightString(width - 35, height - 25, header_right_text)

        # 3. Bottom-Center Footer (Custom Footer from Settings)
        if footer_center_text:
            c.setFont(font_regular, 8.5)
            c.setFillColor(colors.HexColor("#475569"))
            c.drawCentredString(width / 2.0, 20, footer_center_text)

        # 4. Bottom-Right Page Number (- χχ -)
        if page_num is not None:
            c.setFont(font_regular, 9)
            c.setFillColor(colors.HexColor("#64748B"))
            c.drawRightString(width - 35, 20, f"- {page_num} -")

        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]

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
        progress_callback: Optional[Callable[[str, float], None]] = None,
        custom_header_title: Optional[str] = None,
        custom_footer_text: Optional[str] = None
    ) -> str:
        """
        Merge all items (Question + Solution paired sequentially) into a single PDF,
        with:
        - Black font for Assignments (Εκφωνήσεις)
        - Dark Blue font for Solutions (Απαντήσεις)
        - White space trimming / margin cropping
        - Custom centered header title, top-right question header, centered footer text,
          and bottom-right pagination (- χχ -).
        Includes automatic fallback with a 3-digit random number if the target file is locked.
        """
        writer = PdfWriter()

        # Load config if not explicitly passed
        cfg = load_config()
        hdr_center = custom_header_title if custom_header_title is not None else cfg.get("custom_header_title", "")
        ftr_center = custom_footer_text if custom_footer_text is not None else cfg.get("custom_footer_text", "")

        # Deduplicate items
        unique_items_map = {it.id: it for it in items}
        unique_items = list(unique_items_map.values())
        unique_items.sort(key=lambda x: (x.question or 99, x.id))
        total_items = len(unique_items)

        if progress_callback:
            progress_callback("Προετοιμασία εξωφύλλου...", 0.05)

        # 1. Add Cover Page (no page number, no header/footer overlay)
        cover_title = f"Τράπεζα Θεμάτων: {subject_name}"
        cover_sub = chapter_name if chapter_name else "Όλα τα Κεφάλαια"
        meta = [
            f"Συνολικά Θέματα: {total_items}",
            "Περιλαμβάνονται: Εκφωνήσεις (Μαύρο) & Ενδεικτικές Απαντήσεις (Μπλε)",
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

        current_page_number = 0
        processed = 0

        for ch_title, ch_items in chapters_map.items():
            if len(chapters_map) > 1 and not chapter_name:
                current_page_number += 1
                ch_divider_stream = self._create_chapter_divider(ch_title, len(ch_items))
                div_reader = PdfReader(ch_divider_stream)
                div_page = div_reader.pages[0]

                # Overlay on chapter divider
                w = float(div_page.mediabox.width)
                h = float(div_page.mediabox.height)
                overlay = self._create_header_footer_overlay(
                    width=w,
                    height=h,
                    header_right_text=f"Κεφάλαιο: {ch_title}",
                    page_num=current_page_number,
                    header_center_text=hdr_center,
                    footer_center_text=ftr_center
                )
                div_page.merge_page(overlay)

                writer.add_page(div_page)
                ch_outline = writer.add_outline_item(
                    title=f"{ch_title}",
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

                # Add Assignment PDF pages (Black text) with Header & Footer overlay
                q_outline = None
                if os.path.exists(assign_path) and os.path.getsize(assign_path) > 0:
                    try:
                        assign_reader = PdfReader(assign_path)
                        first_page = True
                        for page in assign_reader.pages:
                            current_page_number += 1
                            w = float(page.mediabox.width)
                            h = float(page.mediabox.height)
                            header_txt = f"{it.question_label} #{it.id} (Εκφώνηση)"
                            overlay = self._create_header_footer_overlay(
                                width=w,
                                height=h,
                                header_right_text=header_txt,
                                page_num=current_page_number,
                                header_center_text=hdr_center,
                                footer_center_text=ftr_center
                            )
                            page.merge_page(overlay)
                            _trim_whitespace_margins(page)

                            writer.add_page(page)
                            if first_page:
                                first_page = False
                                page_idx = len(writer.pages) - 1
                                parent_node = ch_outline
                                q_outline = writer.add_outline_item(
                                    title=f"📄 {q_label} (Εκφώνηση)",
                                    page_number=page_idx,
                                    parent=parent_node
                                )
                    except Exception as e:
                        logger.error(f"Failed to append assignment PDF #{it.id}: {e}")

                # Add Solution PDF pages directly below (Recolored to Dark Blue) with Header & Footer overlay
                if os.path.exists(sol_path) and os.path.getsize(sol_path) > 0:
                    try:
                        sol_reader = PdfReader(sol_path)
                        first_page = True
                        for page in sol_reader.pages:
                            current_page_number += 1
                            # 1. Apply dark blue recoloring to solution stream
                            _apply_solution_color(page)

                            # 2. Merge Header/Footer overlay
                            w = float(page.mediabox.width)
                            h = float(page.mediabox.height)
                            header_txt = f"{it.question_label} #{it.id} (Απάντηση)"
                            overlay = self._create_header_footer_overlay(
                                width=w,
                                height=h,
                                header_right_text=header_txt,
                                page_num=current_page_number,
                                header_center_text=hdr_center,
                                footer_center_text=ftr_center
                            )
                            page.merge_page(overlay)
                            _trim_whitespace_margins(page)

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
        final_path = output_path
        try:
            with open(final_path, "wb") as f:
                writer.write(f)
        except PermissionError:
            base, ext = os.path.splitext(output_path)
            rand_suffix = random.randint(100, 999)
            final_path = f"{base}_{rand_suffix}{ext}"
            logger.warning(f"File locked ({output_path}), saving with random suffix to: {final_path}")
            if progress_callback:
                progress_callback(f"Το αρχείο ήταν ανοιχτό. Αποθήκευση ως: {os.path.basename(final_path)}", 0.99)
            with open(final_path, "wb") as f:
                writer.write(f)

        if progress_callback:
            progress_callback("Ολοκληρώθηκε με επιτυχία!", 1.0)

        return final_path

