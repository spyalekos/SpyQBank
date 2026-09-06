---
description: "Flet development rules, deprecations, audio plugins, and API guidelines for SpyQBank"
trigger: always
---

# Κανόνες & Οδηγίες Flet (Flet API Standards)

*Αυτό το αρχείο περιέχει συγκεντρωμένους όλους τους κανόνες, τις καταργήσεις (deprecations) και τις ορθές πρακτικές για το Flet Framework στο παρόν project.*

## 1. ⚠️ ΣΗΜΑΝΤΙΚΕΣ ΚΑΤΑΡΓΗΣΕΙΣ & ΑΛΛΑΓΕΣ (Flet v0.80+ / v2.0+)

*   **ft.ElevatedButton**: Είναι deprecated. Χρησιμοποιούμε αποκλειστικά το **`ft.Button`** για απλή elevated συμπεριφορά. *Σημείωση: Στο `ft.Button` χρησιμοποιούμε την παράμετρο `content` αντί για `text` (π.χ. `ft.Button(content="Κείμενο", ...)`).*
*   **ft.app()**: Είναι deprecated. Χρησιμοποιούμε το **`ft.run(main)`** (όπου η συνάρτηση `main` περνιέται ως positional argument και όχι ως `target=main`).
*   **ft.border.all / symmetric / only**: Έχουν καταργηθεί ως module-level helpers. Χρησιμοποιούμε τις αντίστοιχες μεθόδους κλάσης της `ft.Border` (π.χ. **`ft.Border.all(width, color)`**, **`ft.Border.symmetric(...)`**).
*   **ft.alignment.center**: Χρησιμοποιούμε την κλάση **`ft.Alignment(0, 0)`** για κεντράρισμα.
*   **ft.UserControl**: Έχει καταργηθεί. Για custom components κληρονομούμε απευθείας από κάποιο Flet Control όπως το **`ft.Container`**.

## 2. ⚡ ΑΣΥΓΧΡΟΝΕΣ ΛΕΙΤΟΥΡΓΙΕΣ & THREADING (Async & Thread Executor)

*   **Background Tasks & UI Repainting (CRITICAL)**:
    *   **Πρόβλημα:** Η χρήση «γυμνού» `threading.Thread(target=worker).start()` εκτελείται εκτός του session executor του Flet. Στα Windows, οι κλήσεις `page.update()` ή `control.update()` από τέτοια threads δεν προκαλούν άμεσο redraw στο παράθυρο Flutter μέχρι ο χρήστης να αλλάξει εστίαση (window focus change).
    *   **Λύση:** Χρησιμοποιούμε **ΠΑΝΤΑ** τη μέθοδο **`page.run_thread(worker)`** (ή `page.run_task(coroutine)` για async). Αυτό δεσμεύει το νήμα στον επίσημο executor της σελίδας και εξασφαλίζει άμεση, ζωντανή ανανέωση του UI σε πραγματικό χρόνο.

## 3. 🐛 ΕΠΙΛΥΜΕΝΑ ΣΦΑΛΜΑΤΑ & GOTCHAS (RESOLVED ISSUES)

*   **ReportLab Missing Greek Glyphs / Broken Characters in Generated PDFs**:
    *   **Πρόβλημα:** Οι προεπιλεγμένες γραμματοσειρές της ReportLab (π.χ. `Helvetica`, `Times-Roman`) δεν υποστηρίζουν ελληνικούς χαρακτήρες Unicode, με αποτέλεσμα να παραλείπονται γράμματα ή τονισμένα φωνήεντα στα εξώφυλλα και τα διαχωριστικά κεφαλαίων των παραγόμενων PDF.
    *   **Λύση:** Καταχωρούμε ρητά TrueType Unicode γραμματοσειρές συστήματος (π.χ. `C:/Windows/Fonts/arial.ttf` & `arialbd.ttf` ή `segoeui.ttf`) μέσω `pdfmetrics.registerFont(TTFont('GreekSans', font_path))` και χρησιμοποιούμε αυτές τις γραμματοσειρές σε όλα τα `ParagraphStyle`. Επίσης εφαρμόζουμε `html.escape()` σε τίτλους και ονόματα κεφαλαίων πριν την εισαγωγή σε ReportLab Paragraphs.
*   **Flutter Windows ListView Repaint Bug (LogConsole Pattern)**:
    *   **Πρόβλημα:** Στο Flet desktop στα Windows, όταν προστίθενται νέα controls σε `ft.ListView` (`controls.append`) από background threads, το widget diffing του Flutter engine δεν προκαλεί repaint στο παράθυρο μέχρι ο χρήστης να αλλάξει focus παραθύρου.
    *   **Λύση:** Χρησιμοποιούμε το δοκιμασμένο πρότυπο **`LogConsole`**, δηλαδή ένα ενιαίο `ft.Text` μέσα σε scrollable `ft.Column(scroll=ft.ScrollMode.ALWAYS, auto_scroll=True)`. Η ενημέρωση του `self.log_text.value += f"...\n"` ακολουθούμενη από `self.update()` εξαναγκάζει το Flutter text buffer να σχεδιάσει άμεσα (instant repaint) κάθε γραμμή σε πραγματικό χρόνο.
