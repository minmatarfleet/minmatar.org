from typing import List

from pydantic import BaseModel


class DiffLineResponse(BaseModel):
    kind: str
    text: str


class FieldDiffResponse(BaseModel):
    field: str
    label: str
    lines: List[DiffLineResponse]


class ChangeRequestResponse(BaseModel):
    """A doctrine or fitting change request with its diff against live data."""

    kind: str
    id: int
    target_id: int
    target_name: str
    status: str
    tier: str
    change_kind: str
    submitted_by: str | None
    submitted_at: str
    reviewed_by: str | None
    reviewed_at: str | None
    review_note: str
    can_review: bool
    can_cancel: bool
    diffs: List[FieldDiffResponse]


class ChangePreviewResponse(BaseModel):
    """Diff of a proposed edit. `request` is set once it was submitted."""

    diffs: List[FieldDiffResponse]
    request: ChangeRequestResponse | None = None
    applied: bool = False


class FittingChangeRequest(BaseModel):
    eft_format: str
    description: str
    tags: List[str]
    preview: bool = False


class DoctrineCompositionRequest(BaseModel):
    primary: List[int] = []
    secondary: List[int] = []
    support: List[int] = []
    utility: List[int] = []


class DoctrineChangeRequestBody(BaseModel):
    name: str
    type: str
    description: str
    composition: DoctrineCompositionRequest
    preview: bool = False


class ReviewRequest(BaseModel):
    action: str
    review_note: str = ""
