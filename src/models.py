import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


def extract_main_chapter(name: str) -> str:
    """
    Extract the main integer chapter name from an IEP material/chapter string.
    Examples:
      '2.1 ΟΙ ΠΡΑΞΕΙΣ' -> 'Κεφάλαιο 2'
      '2.1.3 Μύκητες' -> 'Κεφάλαιο 2'
      '3.01. Είδη τριγώνων' -> 'Κεφάλαιο 3'
      '1.1.8 Η έννοια...' -> 'Κεφάλαιο 1'
      '1.2.β. Η βασιλεία...' -> 'Κεφάλαιο 1'
      'Δ.Ε. 10 - ΠΛΑΤΩΝ...' -> 'Διδακτική Ενότητα 10'
      'Διδακτική Ενότητα 2: ...' -> 'Διδακτική Ενότητα 2'
      'Βιβλίο 3ο, § 70' -> 'Βιβλίο 3ο'
      '1. Η ακμή της...' -> 'Κεφάλαιο 1'
      'Κεφάλαιο 4 - ...' -> 'Κεφάλαιο 4'
      '-' or '' -> 'Γενικά / Χωρίς Κεφάλαιο'
    """
    if not name or name.strip() in ("-", "", "None"):
        return "Γενικά / Χωρίς Κεφάλαιο"

    s = name.strip()

    # 1. Check for Book / Βιβλίο (e.g. 'Βιβλίο 3ο', 'Βιβλίο 1')
    m_book = re.search(r"\b(Βιβλίο\s+\d+[ο|α|η|ος]?)\b", s, re.IGNORECASE)
    if m_book:
        return m_book.group(1).capitalize()

    # 2. Check for Didactic Unit / Δ.Ε. / Διδακτική Ενότητα (e.g. 'Δ.Ε. 10', 'Διδακτική Ενότητα 3')
    m_de = re.search(r"\b(?:Δ\.?\s*Ε\.?|Διδακτική\s+Ενότητα)\s*(\d+)", s, re.IGNORECASE)
    if m_de:
        return f"Διδακτική Ενότητα {m_de.group(1)}"

    # 3. Check for explicit 'Κεφάλαιο X' / 'ΚΕΦΑΛΑΙΟ X'
    m_kef = re.search(r"\bΚεφάλαι[ο|α|ου]\s*(\d+)", s, re.IGNORECASE)
    if m_kef:
        return f"Κεφάλαιο {int(m_kef.group(1))}"

    # 4. Check for leading dotted numbers: e.g. '2.1', '2.1.3', '3.01', '1.2.β', '1. '
    m_num = re.match(r"^(\d+)(?:\.|\s|$)", s)
    if m_num:
        num = int(m_num.group(1))
        return f"Κεφάλαιο {num}"

    # 5. Check for any leading integer
    m_first_int = re.match(r"^(\d+)", s)
    if m_first_int:
        return f"Κεφάλαιο {int(m_first_int.group(1))}"

    # Fallback: keep original if no integer chapter could be extracted
    return s


@dataclass
class ResourceFile:
    kind: str  # e.g. 'Εκφώνηση', 'Ενδεικτική Απάντηση'
    format: str  # e.g. 'pdf', 'doc', 'docx'
    fileName: str = ""


@dataclass
class MaterialChapter:
    id: int
    name: str
    shortname: Optional[str] = None
    vieworder: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MaterialChapter":
        return cls(
            id=data.get("id", 0),
            name=data.get("name", "").strip(),
            shortname=data.get("shortname"),
            vieworder=data.get("vieworder", 0) or 0
        )


@dataclass
class QuestionItem:
    id: int
    subject_id: int
    question: Optional[int] = None  # 2, 4 -> Θέμα 2ο, 4ο
    title: Optional[str] = None
    date: str = ""
    duration_min: Optional[int] = None
    difficulty: int = -1
    keywords: str = ""
    remarks: str = ""
    organization: str = ""
    materials: List[MaterialChapter] = field(default_factory=list)
    resources: List[ResourceFile] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], subject_id: int = 0) -> "QuestionItem":
        materials = [MaterialChapter.from_dict(m) for m in data.get("material", [])]
        resources = [
            ResourceFile(
                kind=r.get("kind", ""),
                format=r.get("format", ""),
                fileName=r.get("fileName", "")
            )
            for r in data.get("resources", [])
        ]
        return cls(
            id=data.get("id", 0),
            subject_id=subject_id or data.get("subjectId", 0),
            question=data.get("question"),
            title=data.get("title"),
            date=data.get("date", "") or "",
            duration_min=data.get("durationMin"),
            difficulty=data.get("difficulty", -1),
            keywords=data.get("keywords") or "",
            remarks=data.get("remarks") or "",
            organization=data.get("organization") or "",
            materials=materials,
            resources=resources
        )

    @property
    def question_label(self) -> str:
        if self.question is not None:
            return f"Θέμα {self.question}ο"
        return "Θέμα"

    def get_primary_chapter_name(self, group_by_main_chapter: bool = False) -> str:
        """Return the primary chapter name, optionally grouped by main integer chapter."""
        if not self.materials or not self.materials[0].name:
            return "Γενικά / Χωρίς Κεφάλαιο"
        raw_name = self.materials[0].name
        if group_by_main_chapter:
            return extract_main_chapter(raw_name)
        return raw_name

    def matches_chapter(self, target_chapter: str, group_by_main_chapter: bool = False) -> bool:
        """Check if item belongs to the target chapter."""
        if not target_chapter or target_chapter == "ALL":
            return True
        if not self.materials:
            return target_chapter == "Γενικά / Χωρίς Κεφάλαιο"
        for m in self.materials:
            ch = extract_main_chapter(m.name) if group_by_main_chapter else m.name
            if ch == target_chapter:
                return True
        return False

    @property
    def has_assignment_pdf(self) -> bool:
        return any(
            "εκφώνηση" in r.kind.lower() and r.format.lower() == "pdf"
            for r in self.resources
        )

    @property
    def has_solution_pdf(self) -> bool:
        return any(
            ("απάντηση" in r.kind.lower() or "λύση" in r.kind.lower()) and r.format.lower() == "pdf"
            for r in self.resources
        )

    @property
    def has_assignment_doc(self) -> bool:
        return any(
            "εκφώνηση" in r.kind.lower() and ("doc" in r.format.lower())
            for r in self.resources
        )

    @property
    def has_solution_doc(self) -> bool:
        return any(
            ("απάντηση" in r.kind.lower() or "λύση" in r.kind.lower()) and ("doc" in r.format.lower())
            for r in self.resources
        )

    def get_assignment_pdf_url(self) -> str:
        return f"https://subjects.draw.iep.edu.gr/{self.id}-1?unique_identifier={self.id}&file_type=1"

    def get_solution_pdf_url(self) -> str:
        return f"https://subjects.draw.iep.edu.gr/{self.id}-2?unique_identifier={self.id}&file_type=2"

    def get_assignment_doc_url(self) -> str:
        return f"https://subjects.draw.iep.edu.gr/{self.id}-0?unique_identifier={self.id}&file_type=0"

    def get_solution_doc_url(self) -> str:
        return f"https://subjects.draw.iep.edu.gr/{self.id}-4?unique_identifier={self.id}&file_type=4"

    def get_zip_url(self) -> str:
        return f"https://subjects.draw.iep.edu.gr/{self.id}-3?unique_identifier={self.id}&file_type=3"


@dataclass
class Subject:
    id: int
    name: str
    class_id: int
    school_type_id: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any], class_id: int = 0, school_type_id: int = 0) -> "Subject":
        return cls(
            id=data.get("id", 0),
            name=data.get("name", "").strip(),
            class_id=class_id,
            school_type_id=school_type_id
        )


@dataclass
class ClassLevel:
    id: int
    name: str
    school_type_id: int
    lessons: List[Subject] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], school_type_id: int = 0) -> "ClassLevel":
        cid = data.get("id", 0)
        lessons = [
            Subject.from_dict(l, class_id=cid, school_type_id=school_type_id)
            for l in data.get("lessons", [])
        ]
        return cls(
            id=cid,
            name=data.get("name", "").strip(),
            school_type_id=school_type_id,
            lessons=lessons
        )


@dataclass
class SchoolType:
    id: int
    name: str
    classes: List[ClassLevel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchoolType":
        stid = data.get("id", 0)
        classes = [
            ClassLevel.from_dict(c, school_type_id=stid)
            for c in data.get("classes", [])
        ]
        return cls(
            id=stid,
            name=data.get("name", "").strip(),
            classes=classes
        )
