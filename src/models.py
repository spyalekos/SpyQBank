"""Data models for SpyQBank."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


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
    question: Optional[int] = None  # 1, 2, 3, 4 -> Θέμα 1ο, 2ο, 3ο, 4ο
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
