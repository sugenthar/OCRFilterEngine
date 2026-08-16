"""OCR Token and Geometry Data Structures."""

from dataclasses import dataclass, field
import re
from typing import Any, List, Optional


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class OCRToken:
    text: str
    bbox: BoundingBox
    confidence: float
    needs_review: bool = False
    block_num: int = 0
    par_num: int = 0
    line_num: int = 0
    word_num: int = 0
    variant: str = "standard"

    @property
    def x(self) -> int:
        return self.bbox.x

    @property
    def y(self) -> int:
        return self.bbox.y

    @property
    def width(self) -> int:
        return self.bbox.width

    @property
    def height(self) -> int:
        return self.bbox.height

    @property
    def normalized_text(self) -> str:
        return re.sub(r"[^a-zA-Z0-9+*@-]", "", self.text).lower()

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "x": self.bbox.x,
            "y": self.bbox.y,
            "width": self.bbox.width,
            "height": self.bbox.height,
            "confidence": round(self.confidence, 2),
            "needs_review": self.needs_review,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OCRToken":
        bbox = BoundingBox(
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
        )
        return cls(
            text=str(data.get("text", "")),
            bbox=bbox,
            confidence=float(data.get("confidence", 0.0)),
            needs_review=bool(data.get("needs_review", False)),
        )


@dataclass
class OCRRow:
    y: int
    words: List[OCRToken] = field(default_factory=list)
    text: str = ""

    def recompute_text(self) -> None:
        self.words.sort(key=lambda w: w.x)
        self.text = " ".join(w.text for w in self.words).strip()

    def to_dict(self) -> dict:
        return {
            "y": self.y,
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OCRRow":
        words = [OCRToken.from_dict(w) for w in data.get("words", [])]
        row = cls(y=int(data.get("y", 0)), words=words, text=str(data.get("text", "")))
        if not row.text and words:
            row.recompute_text()
        return row


@dataclass
class RawRecord:
    record_number: int
    rows: List[OCRRow] = field(default_factory=list)
    source_text: str = ""

    def recompute_source_text(self) -> None:
        self.source_text = "\n".join(r.text for r in self.rows).strip()

    def all_tokens(self) -> List[OCRToken]:
        return [w for row in self.rows for w in row.words]

    def to_dict(self) -> dict:
        return {
            "record_number": self.record_number,
            "rows": [r.to_dict() for r in self.rows],
            "source_text": self.source_text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RawRecord":
        rows = [OCRRow.from_dict(r) for r in data.get("rows", [])]
        record = cls(
            record_number=int(data.get("record_number", 1)),
            rows=rows,
            source_text=str(data.get("source_text", "")),
        )
        if not record.source_text and rows:
            record.recompute_source_text()
        return record
