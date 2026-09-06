---
description: "Flet development rules, deprecations, audio plugins, and API guidelines for SpyQBank"
trigger: always
---

# Κανόνες & Οδηγίες Flet (Flet API Standards)

*Αυτό το αρχείο περιέχει συγκεντρωμένους όλους τους κανόνες, τις καταργήσεις (deprecations) και τις ορθές πρακτικές για το Flet Framework.*

## 1. ⚠️ ΣΗΜΑΝΤΙΚΕΣ ΚΑΤΑΡΓΗΣΕΙΣ & ΑΛΛΑΓΕΣ (Flet v0.80+ / v2.0+)

*   **ft.ElevatedButton / ft.TextButton / ft.Button**: Είναι deprecated η χρήση της παραμέτρου `text`. Χρησιμοποιούμε **ΑΠΟΚΛΕΙΣΤΙΚΑ** την παράμετρο **`content=ft.Text("Κείμενο")`** (ή `content=ft.Row(...)`) σε όλους τους τύπους κουμπιών (`Button`, `TextButton`, `FilledButton`, `ElevatedButton`, `OutlinedButton`).
*   **ft.app()**: Είναι deprecated. Χρησιμοποιούμε το **`ft.run(main)`** (όπου η συνάρτηση `main` περνιέται ως positional argument και όχι ως `target=main`).
*   **ft.border.all / symmetric / only**: Έχουν καταργηθεί ως module-level helpers. Χρησιμοποιούμε τις αντίστοιχες μεθόδους κλάσης της `ft.Border` (π.χ. **`ft.Border.all(width, color)`**, **`ft.Border.symmetric(...)`**).
*   **ft.alignment.center**: Χρησιμοποιούμε την κλάση **`ft.Alignment(0, 0)`** για κεντράρισμα.
*   **ft.UserControl**: Έχει καταργηθεί. Για custom components κληρονομούμε απευθείας από κάποιο Flet Control όπως το **`ft.Container`**.

## 2. ⚡ ΑΣΥΓΧΡΟΝΕΣ ΛΕΙΤΟΥΡΓΙΕΣ & THREADING (Async & Thread Executor)

*   **Background Tasks & UI Repainting (CRITICAL)**:
    *   **Πρόβλημα:** Η χρήση «γυμνού» `threading.Thread(target=worker).start()` εκτελείται εκτός του session executor του Flet. Στα Windows, οι κλήσεις `page.update()` ή `control.update()` από τέτοια threads δεν προκαλούν άμεσο redraw στο παράθυρο Flutter μέχρι ο χρήστης να αλλάξει εστίαση (window focus change).
    *   **Λύση:** Χρησιμοποιούμε **ΠΑΝΤΑ** τη μέθοδο **`page.run_thread(worker)`** (ή `page.run_task(coroutine)` για async). Αυτό δεσμεύει το νήμα στον επίσημο executor της σελίδας και εξασφαλίζει άμεση, ζωντανή ανανέωση του UI σε πραγματικό χρόνο.

## 3. 🐛 ΕΠΙΛΥΜΕΝΑ ΣΦΑΛΜΑΤΑ & GOTCHAS (RESOLVED ISSUES)

*   **TypeError: TextButton.__init__() (ή Button.__init__()) got an unexpected keyword argument 'text'**:
    *   **Πρόβλημα:** Στο Flet v0.80+, οι κλάσεις κουμπιών (`ft.Button`, `ft.TextButton`, `ft.FilledButton`, `ft.ElevatedButton`, `ft.OutlinedButton`) δεν διαθέτουν πλέον την παράμετρο `text` στον κατασκευαστή τους. Η κλήση π.χ. `ft.TextButton(text="Ακύρωση", ...)` προκαλεί runtime εξαίρεση `TypeError`.
    *   **Λύση:** Χρησιμοποιούμε **ΠΑΝΤΑ** την παράμετρο `content` περνώντας ένα `ft.Text` control:
        ```python
        # ΣΩΣΤΟ:
        ft.TextButton(content=ft.Text("Ακύρωση"), on_click=handler)
        ft.Button(content=ft.Text("Αποθήκευση", color=ft.Colors.WHITE), on_click=handler)
        
        # ΛΑΘΟΣ (CRASH):
        ft.TextButton(text="Ακύρωση", on_click=handler)
        ft.Button(text="Αποθήκευση", on_click=handler)
        ```

*   **ReportLab Missing Greek Glyphs / Broken Characters in Generated PDFs**:
    *   **Πρόβλημα:** Οι προεπιλεγμένες γραμματοσειρές της ReportLab (π.χ. `Helvetica`, `Times-Roman`) δεν υποστηρίζουν ελληνικούς χαρακτήρες Unicode, με αποτέλεσμα να παραλείπονται γράμματα ή τονισμένα φωνήεντα στα εξώφυλλα και τα διαχωριστικά κεφαλαίων των παραγόμενων PDF.
    *   **Λύση:** Καταχωρούμε ρητά TrueType Unicode γραμματοσειρές συστήματος (π.χ. `C:/Windows/Fonts/arial.ttf` & `arialbd.ttf` ή `segoeui.ttf`) μέσω `pdfmetrics.registerFont(TTFont('GreekSans', font_path))` και χρησιμοποιούμε αυτές τις γραμματοσειρές σε όλα τα `ParagraphStyle`. Επίσης εφαρμόζουμε `html.escape()` σε τίτλους και ονόματα κεφαλαίων πριν την εισαγωγή σε ReportLab Paragraphs.

*   **Flutter Windows ListView Repaint Bug (LogConsole Pattern)**:
    *   **Πρόβλημα:** Στο Flet desktop στα Windows, όταν προστίθενται νέα controls σε `ft.ListView` (`controls.append`) από background threads, το widget diffing του Flutter engine δεν προκαλεί repaint στο παράθυρο μέχρι ο χρήστης να αλλάξει focus παραθύρου.
    *   **Λύση:** Χρησιμοποιούμε το δοκιμασμένο πρότυπο **`LogConsole`**, δηλαδή ένα ενιαίο `ft.Text` μέσα σε scrollable `ft.Column(scroll=ft.ScrollMode.ALWAYS, auto_scroll=True)`. Η ενημέρωση του `self.log_text.value += f"...\n"` ακολουθούμενη από `self.update()` εξαναγκάζει το Flutter text buffer να σχεδιάσει άμεσα (instant repaint) κάθε γραμμή σε πραγματικό χρόνο.

*   **pypdf DeprecationWarning: Calling `PageObject.replace_contents()` for pages not assigned to a writer**:
    *   **Πρόβλημα:** Στη βιβλιοθήκη `pypdf` (v5+), η κλήση `page.merge_page(overlay)` σε ένα αντικείμενο σελίδας που προέρχεται απευθείας από `PdfReader` και δεν έχει ακόμη προστεθεί σε κάποιο `PdfWriter` παράγει προειδοποίηση αποδοκιμασίας (`DeprecationWarning: Calling PageObject.replace_contents() for pages not assigned to a writer is deprecated and will be removed in pypdf 7.0.0. Attach the page to the writer first or use PdfWriter(clone_from=...) directly.`).
    *   **Λύση:** Προσθέτουμε πρώτα τη σελίδα στον `PdfWriter` μέσω `added_page = writer.add_page(page)` και στη συνέχεια καλούμε τη συγχώνευση πάνω στην προσαρτημένη σελίδα (`added_page.merge_page(overlay)`). Έτσι η σελίδα συνδέεται άμεσα με το PDF document context του writer και η διαδικασία εκτελείται αξιόπιστα χωρίς warnings.

*   **Flet Dropdown Search & Filtering**:
    *   **Ορθή Χρήση:** Για dropdowns με μεγάλο πλήθος επιλογών (π.χ. λίστα μαθημάτων), χρησιμοποιούμε `enable_filter=True` και `enable_search=True` μαζί με επαρκές `menu_width` (π.χ. `menu_width=600`, `width=480`), επιτρέποντας στον χρήστη να πληκτρολογεί και να φιλτράρει άμεσα τις επιλογές.


