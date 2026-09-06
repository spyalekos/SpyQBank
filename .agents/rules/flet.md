---
description: "Flet development rules, deprecations, audio plugins, and API guidelines for Spyken"
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
*   Πολλές ενσωματωμένες μέθοδοι (όπως το `page.window.center()`, `audio.play()`, κ.λπ.) είναι πλέον **coroutine functions**.
*   Όταν καλούνται μέσα από σύγχρονη συνάρτηση `main(page: ft.Page)`, εκτελούνται μέσω της μεθόδου:
    ```python
    page.run_task(page.window.center)
    ```
*   Σε ασύγχρονα contexts, καλούνται με `await`:
    ```python
    await page.window.center_async()
    ```


## 3. 🔊 AUDIO STRATEGY (flet-audio)

*   Τα Audio controls **δεν ανήκουν** στο κεντρικό πακέτο `flet`. Εισάγονται από το **`flet_audio`**:
    ```python
    from flet_audio import Audio
    ```
*   Τα plugins δηλώνονται στο `pyproject.toml` κάτω από το `[tool.flet.plugins]`:
    ```toml
    [tool.flet.plugins]
    flet_audio = "Audio"
    ```
*   **Event Names**: Τα events είναι σε ενικό αριθμό: `on_position_change` (ΟΧΙ `on_position_changed`) και `on_state_change`.
*   **Event Properties**: Στους handlers, τα δεδομένα βρίσκονται στα attributes: `e.position` (ms), `e.state` (enum/string), `e.duration` (ms).
*   Οι μέθοδοι `.play()`, `.pause()`, `.resume()`, `.seek()` είναι ασύγχρονες (coroutine functions).

## 4. 🧩 ΠΡΩΤΟΚΟΛΛΟ MOUNTING (Services vs Overlay)

*   **Service-Only Plugins**: Plugins που λειτουργούν ως background services (όπως το `Audio` και το `PermissionHandler`) **ΔΕΝ ΠΡΕΠΕΙ** να προστίθενται στο `page.overlay` (προκαλεί σφάλμα "Unknown control").
*   **Σωστή Τοποθέτηση**: Προστίθενται αποκλειστικά στο `page.services`:
    ```python
    page.services.append(audio_player)
    ```
*   **Απαγόρευση Καθαρισμού**: Απαγορεύεται η χρήση του `page.services.clear()` διότι αποσυνδέει τα plugins από το Flutter runtime.
*   **Όνομα Control (`_c`)**: Διατηρούμε το default PascalCase που παρέχει η βιβλιοθήκη.

## 5. 🖼️ NATIVE SPLASH SCREEN (PyInstaller Splash)

*   Για να αποφευχθεί η καθυστέρηση φόρτωσης (loading delay) των βιβλιοθηκών της Python/Flet, **ΔΕΝ** υλοποιούμε splash screen μέσω του κώδικα Flet.
*   **Πρότυπο Υλοποίησης**: Χρησιμοποιούμε την εγγενή λειτουργία **`Splash`** του PyInstaller.
*   **Στο spec αρχείο (`Spyken.spec`)**:
    *   Εισάγουμε την κλάση: `from PyInstaller.building.api import Splash`
    *   Ορίζουμε το αντικείμενο `splash`:
        ```python
        splash = Splash(
            'assets/spyken_splash.jpg',
            binaries=a.binaries,
            datas=a.datas,
            text_pos=None,
            text_size=12,
            minify_script=True,
            always_on_top=True,
        )
        ```
    *   Προσθέτουμε τα `splash` και `splash.binaries` στο αντικείμενο `EXE(...)`:
        ```python
        exe = EXE(
            pyz,
            a.scripts,
            splash,
            splash.binaries,
            a.binaries,
            a.datas,
            ...
        )
        ```
*   **Στον Python κώδικα (`main.py`)**:
    *   Κλείνουμε το splash screen μόλις το UI φορτωθεί πλήρως (μετά το `page.update()` στο τέλος της `main`), χρησιμοποιώντας:
        ```python
        try:
            import pyi_splash
            pyi_splash.close()
        except ImportError:
            pass
        ```

## 6. 🐛 ΕΠΙΛΥΜΕΝΑ ΣΦΑΛΜΑΤΑ & GOTCHAS (RESOLVED ISSUES)

*   **TypeError: Button.__init__() got an unexpected keyword argument 'text'**:
    *   **Πρόβλημα:** Στο Flet v0.80+, η κλάση `ft.Button` (καθώς και οι υποκλάσεις της όπως η `ft.FilledButton`, `ft.ElevatedButton` κ.λπ.) δεν δέχεται την παράμετρο `text`.
    *   **Λύση:** Χρησιμοποιούμε την παράμετρο `content` (π.χ. `ft.Button(content="Κείμενο", ...)`).
*   **AttributeError: 'super' object has no attribute '__getattr__' (BLUE_GREY_950)**:
    *   **Πρόβλημα:** Οι παλέτες χρωμάτων του Flet (Material Design) όπως η `ft.Colors.BLUE_GREY` φτάνουν μέχρι το shade `900`. Η χρήση μη υπαρκτών αποχρώσεων όπως `BLUE_GREY_950` προκαλεί `AttributeError`.
    *   **Λύση:** Για πολύ σκούρες αποχρώσεις (π.χ. shade 950), χρησιμοποιούμε ρητά hex color string (π.χ. `bgcolor="#0e131f"`).
*   **TypeError: Dropdown.__init__() got an unexpected keyword argument 'on_change'**:
    *   **Πρόβλημα:** Στο Flet v0.80+, η κλάση `ft.Dropdown` δεν δέχεται την παράμετρο `on_change` στον κατασκευαστή της.
    *   **Λύση:** Χρησιμοποιούμε την παράμετρο `on_select` (π.χ. `ft.Dropdown(on_select=handler, ...)`).
*   **AttributeError: 'Page' object has no attribute 'open' (Flet SnackBar Version Mismatch)**:
    *   **Πρόβλημα:** Η χρήση της νεότερης μεθόδου `page.open(SnackBar)` προκαλεί σφάλμα `AttributeError` σε περιβάλλοντα με παλαιότερες εκδόσεις του Flet (π.χ. `< 0.22`).
    *   **Λύση:** Χρησιμοποιούμε την καθολικά συμβατή σύνταξη αναθέτοντας το SnackBar στο `page.snack_bar` και ορίζοντας το attribute `open` σε `True`, ακολουθούμενο από `page.update()`:
        ```python
        page.snack_bar = ft.SnackBar(content=ft.Text("Μήνυμα"), bgcolor=ft.Colors.BLUE_600)
        page.snack_bar.open = True
        page.update()
        ```
*   **AttributeError: EDIT_DOCUMENT_ROUNDED (Non-existent Icon Variant)**:
    *   **Πρόβλημα:** Το `ft.Icons.EDIT_DOCUMENT_ROUNDED` δεν υπάρχει στη βιβλιοθήκη Material Icons του Flet, προκαλώντας `AttributeError`.
    *   **Λύση:** Χρησιμοποιούμε το `ft.Icons.EDIT_NOTE` ή το `ft.Icons.EDIT`.
*   **AttributeError: module 'flet' has no attribute 'ImageFit'**:
    *   **Πρόβλημα:** Στο Flet το enum για την προσαρμογή εικόνων είναι το `ft.BoxFit` (π.χ. `fit=ft.BoxFit.COVER` ή `fit="cover"`) και όχι `ft.ImageFit`.
    *   **Λύση:** Χρησιμοποιούμε αποκλειστικά το `ft.BoxFit.COVER` (ή `"cover"`).
*   **Flutter Windows ListView Repaint Bug (LogConsole Pattern)**:
    *   **Πρόβλημα:** Στο Flet desktop στα Windows, όταν προστίθενται νέα controls σε `ft.ListView` (`controls.append`) από background threads, το widget diffing του Flutter engine δεν προκαλεί repaint στο παράθυρο μέχρι ο χρήστης να αλλάξει focus παραθύρου.
    *   **Λύση:** Χρησιμοποιούμε το δοκιμασμένο πρότυπο **`LogConsole`** (όπως στο Spypress), δηλαδή ένα ενιαίο `ft.Text` μέσα σε scrollable `ft.Column(scroll=ft.ScrollMode.ALWAYS, auto_scroll=True)`. Η ενημέρωση του `self.log_text.value += f"...\n"` ακολουθούμενη από `self.update()` εξαναγκάζει το Flutter text buffer να σχεδιάσει άμεσα (instant repaint) κάθε γραμμή σε πραγματικό χρόνο.




