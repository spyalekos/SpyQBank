---
description: "Rules & Guidelines for SpyQBank (IEP Question Bank Manager, Flet UI, PDF Generator, Change Detection)"
trigger: always
---

# SpyQBank Development & Architecture Rules

Αυτό το αρχείο περιέχει τις προδιαγραφές, την αρχιτεκτονική και τους κανόνες του project **SpyQBank** (Τράπεζα Θεμάτων ΙΕΠ).

## 🚀 Σκοπός & Αρχιτεκτονική

1. **SpyQBank Desktop App (Python + Flet)**:
   - Γραφικό περιβάλλον (Flet) για την περιήγηση, οργάνωση, εξαγωγή και διαχείριση θεμάτων από την Τράπεζα Θεμάτων του ΙΕΠ (`https://trapeza.iep.edu.gr/`).
   - Επιλογή Τύπου Σχολείου (ΓΕΛ, ΕΠΑΛ, κ.λπ.), Τάξης (Α', Β', Γ') και Μαθήματος.
   - **Ταξινόμηση ανά Κεφάλαιο / Διδακτική Ενότητα**: Οργάνωση και ομαδοποίηση των θεμάτων ανά κεφάλαιο με βάση τα `material` metadata του ΙΕΠ.
   - **Εμφάνιση Ερωτήσεων & Απαντήσεων (Pairs)**: Κάτω από κάθε θέμα/εκφώνηση εμφανίζεται **υποχρεωτικά** η αντίστοιχη ενδεικτική απάντηση/λύση.
   - **Εξαγωγή Αναφορών PDF**: Δυνατότητα παραγωγής ενιαίου ή ανά κεφάλαιο PDF αρχείου που περιέχει την εκφώνηση και αμέσως μετά τη λύση κάθε θέματος.
   - **Έλεγχος Αλλαγών / Συγχρονισμός (Change Detection)**: Χειροκίνητος ή αυτόματος έλεγχος για νέα ή τροποποιημένα θέματα στο ΙΕΠ, με σύγκριση ημερομηνιών, IDs και hash.

2. **IEP API Integration & Cache Engine (`src/iep_api.py`, `src/storage.py`)**:
   - Base API URL: `https://api.trapeza.registry.digitalschool.gov.gr/v1`
   - School Tree Endpoint: `/public/school/type/tree`
   - Subject Items Endpoint: `/public/school/type/{typeId}/class/{classId}/subject/{subjectId}/items?up_to_last_chapter=false`
   - Direct File Downloads: `https://subjects.draw.iep.edu.gr/{id}-{file_type}?unique_identifier={id}&file_type={file_type}`
     - `1`: Εκφώνηση PDF
     - `2`: Ενδεικτική Απάντηση / Λύση PDF
     - `0`: Εκφώνηση DOCX
     - `4`: Ενδεικτική Απάντηση DOCX
     - `3`: ZIP όλων των αρχείων
   - **Τοπική Αποθήκευση & Cache**: Αποθήκευση JSON metadata και PDF αρχείων τοπικά (π.χ. σε φάκελο `data/` ή `cache/`) για ταχύτατη πρόσβαση και offline λειτουργία.

3. **PDF Generation & Merging Engine (`src/pdf_builder.py`)**:
   - Χρήση `pypdf` ή PyMuPDF (`pymupdf` / `fitz`) ή `reportlab` για συγχώνευση (interleaving) εκφώνησης και απάντησης.
   - Δημιουργία καθαρού σελιδοποιημένου PDF με TOC (Πίνακα Περιεχομένων) ή headers ανά κεφάλαιο.

## 🛠️ Κανόνες Ανάπτυξης & Flet Invariants

1. **Flet Standards**:
   - Χρήση `ft.run(main)` (όχι deprecated `ft.app`).
   - Χρήση `ft.Button(content=...)` (όχι deprecated `ElevatedButton`, ούτε `text` prop).
   - Χρήση `ft.Border.all()`, `ft.Border.symmetric()`.
   - Χρήση `page.snack_bar` με `page.snack_bar.open = True; page.update()`.
   - Χρήση `ft.Alignment(0, 0)`.
   - Τα custom controls κληρονομούν από `ft.Container` ή παρεμφερή (όχι `UserControl`).
2. **Background Tasks & Live Logging**:
   - Όλες οι δικτυακές κλήσεις (λήψη θεμάτων, έλεγχος αλλαγών, downloads, εξαγωγές PDF) εκτελούνται μέσω `page.run_thread(worker)` για να αποτρέπεται το πάγωμα του UI.
   - Χρήση του προτύπου **`LogConsole`** για ζωντανή απεικόνιση της προόδου.
3. **Encoding στα Windows**:
   - Ορίζουμε ρητά `encoding="utf-8"` σε όλα τα file operations.
4. **Dependency Management**:
   - Χρήση αποκλειστικά `uv` (`uv add`, `uv run`).

## 📦 Versioning & Build
1. **Versioning**: Semantic versioning με δεκαδικό rollover (π.χ. 1.0.0, 1.0.1).
2. **PyInstaller**: `uv run pyinstaller SpyQBank.spec --clean` με `console=False`.
