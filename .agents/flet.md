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

*   **Flet Modal Dialogs (`AlertDialog`) & `page.overlay` Management**:
    *   **Πρόβλημα:** Στο Flet v0.80+, τα modals (`ft.AlertDialog`) δεν ανοίγουν αξιόπιστα ή προκαλούν σφάλματα εάν δεν προστεθούν στο `page.overlay` ή εάν προστίθενται πολλαπλές φορές σε κάθε κλικ.
    *   **Λύση:** Κατά το άνοιγμα ενός διαλόγου (π.χ. `SettingsDialog.show()` ή `HelpDialog`), ελέγχουμε αν υπάρχει ήδη στο `page.overlay` και το προσθέτουμε μόνο μία φορά:
        ```python
        if self.dialog not in self.page.overlay:
            self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()
        ```
    *   **Text Wrapping & Layout στα Dialogs:** Σε διαλόγους με ρυθμίσεις (π.χ. διακόπτες `ft.Switch` με επεξηγήσεις), τοποθετούμε τα κείμενα μέσα σε `ft.Container(content=ft.Column([...]), expand=True)` εντός `ft.Row` ώστε το κείμενο να αναδιπλώνεται αυτόματα (auto-wrap) και να μην υπερχειλίζει ποτέ εκτός του διαλόγου.

*   **Συγχρονισμένο UI Busy Lock & Visual Graying**:
    *   **Πρότυπο:** Όταν ξεκινά μία βαριά ή ασύγχρονη διεργασία (π.χ. λήψη θεμάτων, μαζική εξαγωγή PDF, συγχρονισμός), καλούμε **άμεσα και συγχρονισμένα** τη συνάρτηση `set_ui_busy(True)` (μείωση `opacity = 0.50`, απενεργοποίηση όλων των buttons και dropdowns) και `page.update()` **πριν** την εκκίνηση του `page.run_thread(worker)`.
    *   Η επαναφορά (`set_ui_busy(False)`) τοποθετείται πάντοτε σε μπλοκ `finally:` μέσα στον worker ώστε το UI να ξεκλειδώνει 100% ακόμη και σε περίπτωση εξαίρεσης.

*   **Full-Width Responsive Containers & Bottom Bar**:
    *   **Πρότυπο:** Για να εκτείνονται τα κάτω panels, η κονσόλα logs (`LogConsole`) και οι μπάρες ενεργειών σε ολόκληρο το πλάτος του παραθύρου χωρίς να συρρικνώνονται κατά την αυξομείωση μεγέθους παραθύρου, χρησιμοποιούμε:
        ```python
        ft.Column(
            controls=[...],
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True
        )
        ```
        και στο Container: `alignment=ft.Alignment(-1, -1)`.

*   **ReportLab Custom Flowables (`Flowable`) & Fine Dot Leaders**:
    *   **Ορθή Πρακτική:** Για δυναμικά στοιχεία όπως ο Πίνακας Περιεχομένων με διακεκομμένες τελείες σύνδεσης (dot leaders), κληρονομούμε από το `reportlab.platypus.Flowable` υλοποιώντας τις μεθόδους `wrap(availWidth, availHeight)` και `draw()`.
    *   Στο `draw()`, χρησιμοποιούμε `self.canv.stringWidth()` για ακριβή μέτρηση ελληνικών γραμματοσειρών, `self.canv.setDash(1, 2.5)` για πολύ λεπτές διανυσματικές τελείες, και αποφεύγουμε πλήρως τα emojis στο Canvas ώστε να μην προκαλούνται Unicode / missing glyph errors.

*   **PDF Stream Recoloring & Custom Colorspaces (Word Export Gotcha)**:
    *   **Πρόβλημα:** Στα PDF που εξάγονται από Word (όπως πολλά έγγραφα του ΙΕΠ), χρησιμοποιείται custom colorspace declaration (π.χ. `/Cs1 cs`) πριν από `0 0 0 sc`. Αν μετατραπεί το `sc` σε `rg` χωρίς να αλλάξει το colorspace declaration, αυστηροί PDF renderers (Adobe Acrobat, Chrome PDF) αγνοούν το `rg` και διατηρούν το κείμενο μαύρο.
    *   **Λύση:** Πριν τη μετατροπή των χρωματικών τελεστών, κανονικοποιούμε όλα τα custom colorspace declarations (`/CsX cs` -> `/DeviceRGB cs` και `/CsX CS` -> `/DeviceRGB CS`), διασφαλίζοντας ότι όλα τα κείμενα χρωματίζονται 100% στο επιθυμητό σκούρο μπλε (`#0D338C`).

*   **PDF Whitespace Trimming & Bounding Box Calculation (Word Export / Phantom Spaces)**:
    *   **Πρόβλημα:** Σε PDF του ΙΕΠ που εξάγονται από Word, υπάρχουν αόρατοι χαρακτήρες κενού (`( )`, `[( )]`, CID font space code `<0003>`), διακοσμητικές γραμμές ή full-page background rectangles στα άκρα της σελίδας (`y=38` και `y=796`). Αυτό διόγκωνε τεχνητά το ύψος περιεχομένου (`slice_h = max_y - min_y`) στα ~780pt (ολόκληρη σελίδα), αποτρέποντας τη συνεχή στοίβαξη (smart packing) και αφήνοντας τεράστιο κενό χώρο στο κάτω μέρος.
    *   **Λύση:** 
        1. Υλοποιήθηκε έλεγχος `_is_empty_or_whitespace_pdf_text` που αγνοεί text operators που περιέχουν αποκλειστικά κενά, kerning shifts ή `<0003>`.
        2. Φιλτράρονται πλήρως τα full-page background rectangles (`rw >= page_w - 50` και `rh >= page_h - 100`) και γραμμές περιθωρίων (`y < 25` ή `y > page_h - 25`).
        3. Κατά τη συνεχή στοίβαξη (`merge_page`), ρυθμίζεται αυστηρά το `page.cropbox` στα πραγματικά όρια `[min_y - 2, max_y + 2]`, διασφαλίζοντας ότι το Form XObject είναι κλειδωμένο στο ορατό τμήμα και δεν υπερκαλύπτει άλλα στοιχεία.




