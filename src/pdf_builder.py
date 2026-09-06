"""PDF Report Generator and Merger for SpyQBank."""

import os
import io
import re
import html
import random
import logging
from typing import List, Optional, Callable, Dict
from pypdf import PdfWriter, PdfReader, Transformation
from pypdf.generic import DecodedStreamObject, NameObject

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
    Recolor all dark grayscale, near-black, and dark RGB text, fills and strokes to dark navy blue (#0D338C).
    Assignment retains crisp black text, Solution is fully converted to dark navy blue.
    """
    try:
        text = raw_bytes.decode("latin1", errors="ignore")

        # Helper for grayscale 'g' / 'G'
        def replace_grayscale(match):
            val = float(match.group(1))
            # Convert dark colors (e.g. 0.0, 0.133, etc. <= 0.40) to navy blue
            # White (1.0 g) or light highlights remain untouched
            if val <= 0.40:
                op = match.group(2)
                return f"{NAVY_R} {NAVY_G} {NAVY_B} rg" if op == "g" else f"{NAVY_R} {NAVY_G} {NAVY_B} RG"
            return match.group(0)

        # Helper for RGB 'rg' / 'RG'
        def replace_rgb(match):
            r = float(match.group(1))
            g = float(match.group(2))
            b = float(match.group(3))
            op = match.group(4)
            # Convert dark colors (r,g,b all <= 0.45) to navy blue
            if r <= 0.45 and g <= 0.45 and b <= 0.45:
                return f"{NAVY_R} {NAVY_G} {NAVY_B} rg" if op == "rg" else f"{NAVY_R} {NAVY_G} {NAVY_B} RG"
            return match.group(0)

        # 1. Match all grayscale operations (e.g. '0 g', '0.133 g', '0 G')
        text = re.sub(r"(?<![0-9.])([0-9.]+)\s+([gG])(?![a-zA-Z0-9])", replace_grayscale, text)

        # 2. Match all RGB operations (e.g. '0 0 0 rg', '0.137 0.122 0.125 rg', '.058824 .090196 .164706 rg')
        text = re.sub(r"(?<![0-9.])([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([rR][gG])(?![a-zA-Z0-9])", replace_rgb, text)

        # 3. Prepend global default dark navy color state
        prefix = f"{NAVY_R} {NAVY_G} {NAVY_B} rg\n{NAVY_R} {NAVY_G} {NAVY_B} RG\n"
        return (prefix + text).encode("latin1")
    except Exception as e:
        logger.warning(f"Failed to recolor stream: {e}")
        return raw_bytes


def _apply_solution_color(page):
    """
    Apply dark navy blue coloring directly to solution page stream object.
    Consolidates split streams into a single stream before recoloring to preserve
    PDF operator state and prevent missing text across chunk boundaries.
    """
    try:
        contents = page.get("/Contents")
        if contents is not None:
            c_obj = contents.get_object()
            if isinstance(c_obj, list):
                # Multiple stream chunks: combine them first so operator states (BT/ET, cm, etc.)
                # are preserved continuously, avoiding corrupted/missing text.
                all_data = b"\n".join([s.get_object().get_data() for s in c_obj])
                recolored = _recolor_stream_to_dark_blue(all_data)
                new_stream = DecodedStreamObject()
                new_stream.set_data(recolored)
                page[NameObject("/Contents")] = new_stream
            else:
                raw = c_obj.get_data()
                c_obj.set_data(_recolor_stream_to_dark_blue(raw))
    except Exception as e:
        logger.warning(f"Error recoloring solution page: {e}")



def _get_page_content_bounds(page):
    """
    Robustly calculate vertical bounding box (min_y, max_y, height) of content on a PDF page
    by parsing CTM transformations and text/graphic drawing instructions.
    """
    try:
        raw = page.get("/Contents")
        if raw is None:
            h = float(page.mediabox.height)
            return 50.0, h - 50.0, h - 100.0
        c_obj = raw.get_object()
        streams = c_obj if isinstance(c_obj, list) else [c_obj]
        data = b"".join([s.get_object().get_data() for s in streams]).decode("latin1", errors="ignore")

        def mat_mult(m1, m2):
            a = m2[0] * m1[0] + m2[1] * m1[2]
            b = m2[0] * m1[1] + m2[1] * m1[3]
            c = m2[2] * m1[0] + m2[3] * m1[2]
            d = m2[2] * m1[1] + m2[3] * m1[3]
            e = m2[4] * m1[0] + m2[5] * m1[2] + m1[4]
            f = m2[4] * m1[1] + m2[5] * m1[3] + m1[5]
            return [a, b, c, d, e, f]

        def transform_pt(ctm, x, y):
            tx = x * ctm[0] + y * ctm[2] + ctm[4]
            ty = x * ctm[1] + y * ctm[3] + ctm[5]
            return tx, ty

        token_pattern = re.compile(
            r"(?:/[a-zA-Z0-9_\-]+|\[[^\]]*\]|\([^\)]*\)|<[0-9a-fA-F\s]*>|[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?|[a-zA-Z*\'\"]+)"
        )
        tokens = token_pattern.findall(data)

        stack = []
        ctm_stack = [[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]]
        text_matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        line_matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        leading = 14.0

        y_coords = []

        for tok in tokens:
            if tok == "q":
                ctm_stack.append(list(ctm_stack[-1]))
                stack.clear()
            elif tok == "Q":
                if len(ctm_stack) > 1:
                    ctm_stack.pop()
                stack.clear()
            elif tok == "cm":
                if len(stack) >= 6:
                    try:
                        m = [float(stack[-6]), float(stack[-5]), float(stack[-4]), float(stack[-3]), float(stack[-2]), float(stack[-1])]
                        ctm_stack[-1] = mat_mult(ctm_stack[-1], m)
                    except Exception:
                        pass
                stack.clear()
            elif tok == "BT":
                text_matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
                line_matrix = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
                stack.clear()
            elif tok == "TL":
                if stack:
                    try:
                        leading = float(stack[-1])
                    except Exception:
                        pass
                stack.clear()
            elif tok in ("T*", "'"):
                lm = line_matrix
                new_e = lm[4]
                new_f = lm[5] - leading
                line_matrix = [lm[0], lm[1], lm[2], lm[3], new_e, new_f]
                text_matrix = list(line_matrix)
                curr_ctm = ctm_stack[-1]
                eff_matrix = mat_mult(curr_ctm, text_matrix)
                y_coords.append(eff_matrix[5])
                stack.clear()
            elif tok == "Tm":
                if len(stack) >= 6:
                    try:
                        text_matrix = [float(stack[-6]), float(stack[-5]), float(stack[-4]), float(stack[-3]), float(stack[-2]), float(stack[-1])]
                        line_matrix = list(text_matrix)
                        curr_ctm = ctm_stack[-1]
                        eff_matrix = mat_mult(curr_ctm, text_matrix)
                        y_coords.append(eff_matrix[5])
                    except Exception:
                        pass
                stack.clear()
            elif tok in ("Td", "TD"):
                if len(stack) >= 2:
                    try:
                        tx, ty = float(stack[-2]), float(stack[-1])
                        lm = line_matrix
                        new_e = tx * lm[0] + ty * lm[2] + lm[4]
                        new_f = tx * lm[1] + ty * lm[3] + lm[5]
                        line_matrix = [lm[0], lm[1], lm[2], lm[3], new_e, new_f]
                        text_matrix = list(line_matrix)
                        curr_ctm = ctm_stack[-1]
                        eff_matrix = mat_mult(curr_ctm, text_matrix)
                        y_coords.append(eff_matrix[5])
                    except Exception:
                        pass
                stack.clear()
            elif tok == "re":
                if len(stack) >= 4:
                    try:
                        rx, ry, rw, rh = float(stack[-4]), float(stack[-3]), float(stack[-2]), float(stack[-1])
                        # Ignore full page backgrounds or large container frames
                        if not (abs(rw) > 400 and abs(rh) > 300) and abs(rw) < 520 and abs(rh) < 700:
                            curr_ctm = ctm_stack[-1]
                            _, y1 = transform_pt(curr_ctm, rx, ry)
                            _, y2 = transform_pt(curr_ctm, rx + rw, ry + rh)
                            y_coords.extend([min(y1, y2), max(y1, y2)])
                    except Exception:
                        pass
                stack.clear()
            elif tok in ("m", "l"):
                if len(stack) >= 2:
                    try:
                        px, py = float(stack[-2]), float(stack[-1])
                        curr_ctm = ctm_stack[-1]
                        _, ty = transform_pt(curr_ctm, px, py)
                        y_coords.append(ty)
                    except Exception:
                        pass
                stack.clear()
            elif tok == "Do":
                curr_ctm = ctm_stack[-1]
                _, y1 = transform_pt(curr_ctm, 0, 0)
                _, y2 = transform_pt(curr_ctm, 1, 1)
                if abs(y2 - y1) < 700:
                    y_coords.extend([min(y1, y2), max(y1, y2)])
                stack.clear()
            elif tok in ("ET", "c", "v", "y", "h", "B", "B*", "b", "b*", "f", "f*", "s", "S", "n", "W", "W*", "rg", "RG", "g", "G", "k", "K", "cs", "CS", "sc", "SC", "scn", "SCN", "Tf", "Tr", "Ts", "Tw", "Tz", "Tj", "TJ", "d", "gs"):
                stack.clear()
            else:
                stack.append(tok)

        page_h = float(page.mediabox.height)
        if not y_coords:
            return 50.0, page_h - 50.0, page_h - 100.0

        valid_y = [y for y in y_coords if 10.0 <= y <= page_h - 10.0]
        if not valid_y:
            return 50.0, page_h - 50.0, page_h - 100.0

        min_y = max(25.0, min(valid_y) - 10.0)
        max_y = min(page_h - 25.0, max(valid_y) + 12.0)
        return min_y, max_y, (max_y - min_y)
    except Exception as e:
        logger.warning(f"Error calculating content bounds: {e}")
        h = float(page.mediabox.height)
        return 50.0, h - 50.0, h - 100.0


def _trim_whitespace_margins(page):
    """
    Safely trim excessive empty white space around page margins without clipping
    header/footer overlays (cropbox kept at safe bounds: 18pt margins).
    """
    try:
        mb = page.mediabox
        w = float(mb.width)
        h = float(mb.height)
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
        - Top-Left: Custom Title from Settings
        - Top-Right: Question / Chapter Header (# θέματος / Κεφάλαιο)
        - Bottom-Center: Custom Footer Text from Settings
        - Bottom-Right: Page Number (- χχ -)
        """
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))

        font_bold = FONT_BOLD if FONT_BOLD in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
        font_regular = FONT_REGULAR if FONT_REGULAR in pdfmetrics.getRegisteredFontNames() else "Helvetica"

        # 1. Top-Left Header (Custom Title from Settings - Left-aligned)
        if header_center_text:
            c.setFont(font_bold, 9)
            c.setFillColor(colors.HexColor("#334155"))
            c.drawString(35, height - 25, header_center_text)

        # 2. Top-Right Header (# θέματος / Κεφάλαιο)
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

    def _create_inline_badge_overlay(
        self,
        width: float,
        height: float,
        y_pos: float,
        badge_text: str,
        is_solution: bool = False
    ):
        """
        Generate an overlay with an inline badge (#<id>) next to the question/solution title.
        """
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))
        font_bold = FONT_BOLD if FONT_BOLD in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
        c.setFont(font_bold, 9.5)
        if is_solution:
            c.setFillColor(colors.HexColor("#0D338C"))
        else:
            c.setFillColor(colors.HexColor("#1E3A8A"))
        c.drawRightString(width - 35, y_pos, badge_text)
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
            bottomMargin=30
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
        iep_cover_style = ParagraphStyle(
            'CoverIEPNotice',
            parent=styles['Normal'],
            fontName=FONT_REGULAR if FONT_REGULAR in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
            fontSize=7.5,
            leading=11,
            textColor=colors.HexColor('#64748B'),
            alignment=1,  # Center
            spaceBefore=25
        )

        story = [
            Spacer(1, 80),
            Paragraph(html.escape(title), title_style),
            Paragraph(html.escape(subtitle), subtitle_style),
            Spacer(1, 35),
        ]

        for line in metadata_lines:
            story.append(Paragraph(html.escape(line), meta_style))

        story.append(Spacer(1, 60))
        story.append(Paragraph("Τράπεζα Θεμάτων Διαβαθμισμένης Δυσκολίας - Ι.Ε.Π.", meta_style))
        story.append(Paragraph("Παραγωγή μέσω SpyQBank", meta_style))

        iep_full_notice = (
            "Όλα τα θέματα προέρχονται και αντλήθηκαν από την πλατφόρμα της Τράπεζας Θεμάτων Διαβαθμισμένης Δυσκολίας "
            "που αναπτύχθηκε (MIS5070818-Τράπεζα θεμάτων Διαβαθμισμένης Δυσκολίας για τη Δευτεροβάθμια Εκπαίδευση, Γενικό Λύκειο-ΕΠΑΛ) "
            "και είναι διαδικτυακά στο δικτυακό τόπο του Ινστιτούτου Εκπαιδευτικής Πολιτικής (Ι.Ε.Π.) στη διεύθυνση "
            "https://www.iep.edu.gr/trapeza-thematon-arxiki-selida/"
        )
        story.append(Paragraph(iep_full_notice, iep_cover_style))

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
        Merge all items (Question + Solution paired sequentially) into a single PDF.
        When trim_whitespace is enabled:
        - Packs questions & solutions continuously on pages to eliminate whitespace
        - Places the #<id> badge inline next to the question title
        - Breaks pages only when space runs out or on chapter change
        When trim_whitespace is disabled:
        - Keeps standard 1-page-per-slice layout with top-right header badge
        """
        writer = PdfWriter()

        # Load config if not explicitly passed
        cfg = load_config()
        hdr_center = custom_header_title if custom_header_title is not None else cfg.get("custom_header_title", "")
        ftr_center = custom_footer_text if custom_footer_text is not None else cfg.get("custom_footer_text", "")
        should_trim = cfg.get("trim_whitespace", True)
        include_chapter_covers = cfg.get("include_chapter_covers", True)

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

        if should_trim:
            # ==========================================
            # SMART CONTINUOUS PACKING MODE (Trimming ON)
            # ==========================================
            for ch_title, ch_items in chapters_map.items():
                if include_chapter_covers and len(chapters_map) > 1 and not chapter_name:
                    current_page_number += 1
                    ch_divider_stream = self._create_chapter_divider(ch_title, len(ch_items))
                    div_reader = PdfReader(ch_divider_stream)
                    div_page = div_reader.pages[0]
                    added_div_page = writer.add_page(div_page)

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
                    added_div_page.merge_page(overlay)

                    ch_outline = writer.add_outline_item(
                        title=f"{ch_title}",
                        page_number=len(writer.pages) - 1
                    )
                else:
                    ch_outline = None

                # Start a fresh page for the chapter
                current_page_number += 1
                current_packed_page = writer.add_blank_page(width=A4[0], height=A4[1])
                current_y = 790.0
                page_has_content = False

                if ch_outline is None and len(chapters_map) > 1 and not chapter_name:
                    ch_outline = writer.add_outline_item(
                        title=f"{ch_title}",
                        page_number=len(writer.pages) - 1
                    )

                for it in ch_items:
                    processed += 1
                    progress = 0.1 + (0.85 * (processed / max(1, total_items)))
                    q_label = f"{it.question_label} #{it.id}"
                    if progress_callback:
                        progress_callback(f"Επεξεργασία {q_label} ({processed}/{total_items})...", progress)

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

                    slices = []
                    if os.path.exists(assign_path) and os.path.getsize(assign_path) > 0:
                        slices.append((assign_path, False, "Εκφώνηση", "📄"))
                    if os.path.exists(sol_path) and os.path.getsize(sol_path) > 0:
                        slices.append((sol_path, True, "Απάντηση", "💡"))

                    q_outline = None
                    for path, is_sol, kind_str, icon in slices:
                        try:
                            reader = PdfReader(path)
                            first_slice_page = True
                            for page in reader.pages:
                                if is_sol:
                                    _apply_solution_color(page)
                                min_y, max_y, slice_h = _get_page_content_bounds(page)

                                # If slice doesn't fit on current page, finish current page and start a new blank page
                                if page_has_content and (current_y - slice_h < 35.0):
                                    overlay = self._create_header_footer_overlay(
                                        width=A4[0],
                                        height=A4[1],
                                        header_right_text=None,
                                        page_num=current_page_number,
                                        header_center_text=hdr_center,
                                        footer_center_text=ftr_center
                                    )
                                    current_packed_page.merge_page(overlay)

                                    current_page_number += 1
                                    current_packed_page = writer.add_blank_page(width=A4[0], height=A4[1])
                                    current_y = 790.0
                                    page_has_content = False

                                # Position slice onto current packed page
                                dy = current_y - max_y
                                page.add_transformation(Transformation().translate(tx=0, ty=dy))
                                current_packed_page.merge_page(page)

                                # Add inline badge #<id> on first page of slice for space economy
                                if first_slice_page:
                                    badge_overlay = self._create_inline_badge_overlay(
                                        width=A4[0],
                                        height=A4[1],
                                        y_pos=current_y - 2.0,
                                        badge_text=f"#{it.id}",
                                        is_solution=is_sol
                                    )
                                    current_packed_page.merge_page(badge_overlay)

                                    page_idx = len(writer.pages) - 1
                                    if not is_sol:
                                        parent_node = ch_outline
                                        q_outline = writer.add_outline_item(
                                            title=f"{icon} {q_label} ({kind_str})",
                                            page_number=page_idx,
                                            parent=parent_node
                                        )
                                    else:
                                        parent_item = q_outline or ch_outline
                                        if parent_item:
                                            writer.add_outline_item(
                                                title=f"{icon} {q_label} ({kind_str})",
                                                page_number=page_idx,
                                                parent=parent_item
                                            )
                                        else:
                                            writer.add_outline_item(
                                                title=f"{icon} {q_label} ({kind_str})",
                                                page_number=page_idx
                                            )
                                    first_slice_page = False

                                current_y = current_y - slice_h - 16.0
                                page_has_content = True
                        except Exception as e:
                            logger.error(f"Failed to pack {kind_str} #{it.id}: {e}")

                # Finalize last packed page of the chapter
                if page_has_content:
                    overlay = self._create_header_footer_overlay(
                        width=A4[0],
                        height=A4[1],
                        header_right_text=None,
                        page_num=current_page_number,
                        header_center_text=hdr_center,
                        footer_center_text=ftr_center
                    )
                    current_packed_page.merge_page(overlay)

        else:
            # ==========================================
            # CLASSIC 1-PAGE-PER-SLICE MODE (Trimming OFF)
            # ==========================================
            for ch_title, ch_items in chapters_map.items():
                if include_chapter_covers and len(chapters_map) > 1 and not chapter_name:
                    current_page_number += 1
                    ch_divider_stream = self._create_chapter_divider(ch_title, len(ch_items))
                    div_reader = PdfReader(ch_divider_stream)
                    div_page = div_reader.pages[0]
                    added_div_page = writer.add_page(div_page)

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
                    added_div_page.merge_page(overlay)

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
                                added_page = writer.add_page(page)

                                if ch_outline is None and len(chapters_map) > 1 and not chapter_name:
                                    ch_outline = writer.add_outline_item(
                                        title=f"{ch_title}",
                                        page_number=len(writer.pages) - 1
                                    )

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
                                added_page.merge_page(overlay)

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
                                _apply_solution_color(page)
                                added_page = writer.add_page(page)

                                if ch_outline is None and len(chapters_map) > 1 and not chapter_name:
                                    ch_outline = writer.add_outline_item(
                                        title=f"{ch_title}",
                                        page_number=len(writer.pages) - 1
                                    )

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
                                added_page.merge_page(overlay)

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

    def build_single_item_report(
        self,
        item: QuestionItem,
        file_type: int,  # 1 = Assignment, 2 = Solution
        output_path: str,
        custom_header_title: Optional[str] = None,
        custom_footer_text: Optional[str] = None
    ) -> str:
        """
        Download and process a single Question or Solution PDF, applying:
        - Header overlay (# θέματος, custom header)
        - Footer overlay (- χχ -, custom footer)
        - Dark Navy Blue color if it is a Solution (file_type == 2)
        - Safe margin whitespace trimming (if enabled in settings)
        """
        writer = PdfWriter()

        cfg = load_config()
        hdr_center = custom_header_title if custom_header_title is not None else cfg.get("custom_header_title", "")
        ftr_center = custom_footer_text if custom_footer_text is not None else cfg.get("custom_footer_text", "")
        should_trim = cfg.get("trim_whitespace", True)

        is_sol = (file_type == 2)
        kind_label = "Απάντηση" if is_sol else "Εκφώνηση"
        src_path = self.storage.get_pdf_cache_path(item.id, file_type)
        url = item.get_solution_pdf_url() if is_sol else item.get_assignment_pdf_url()

        self.api.download_file(url, src_path)

        if not os.path.exists(src_path) or os.path.getsize(src_path) == 0:
            raise FileNotFoundError(f"Could not download {kind_label} PDF for #{item.id}")

        reader = PdfReader(src_path)
        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            if is_sol:
                _apply_solution_color(page)

            if should_trim:
                min_y, max_y, content_h = _get_page_content_bounds(page)
                mb = page.mediabox
                w = float(mb.width)
                h = float(mb.height)
                bottom_crop = max(15.0, min_y - 20.0)
                page.cropbox.lower_left = (18.0, bottom_crop)
                page.cropbox.upper_right = (w - 18.0, h - 12.0)
            added_page = writer.add_page(page)

            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            header_txt = f"{item.question_label} #{item.id} ({kind_label})"
            overlay = self._create_header_footer_overlay(
                width=w,
                height=h,
                header_right_text=header_txt,
                page_num=page_num,
                header_center_text=hdr_center,
                footer_center_text=ftr_center
            )
            added_page.merge_page(overlay)

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
            with open(final_path, "wb") as f:
                writer.write(f)

        return final_path


