"""Schemas for the one-round fleet invite feedback form."""

from typing import List

from pydantic import BaseModel, Field


class Choice(BaseModel):
    key: str
    label: str


class Question(BaseModel):
    key: str
    # A label of 45 characters or fewer, for the Discord form.
    short: str = ""
    prompt: str
    help: str = ""
    kind: str
    badge: str = ""
    choices: List[Choice] = []
    exclusive: str = ""
    max: int = 1


class Answers(BaseModel):
    felt: str = ""
    sitting_out: str = ""
    why: str = ""
    why_text: str = ""
    keep: str = ""
    comment: str = ""


class InviteRow(BaseModel):
    fleet_id: int
    when: str
    title: str
    answer: str
    answer_label: str


class FormResponse(BaseModel):
    state: str
    heading: str = ""
    body: str = ""
    detail: str = ""
    intro: str = ""
    list_heading: str = ""
    invites: List[InviteRow] = []
    pending_invites: List[InviteRow] = []
    questions: List[Question] = []
    answers: Answers = Field(default_factory=Answers)
    comment_heading: str = ""
    comment_placeholder: str = ""
    errors: List[str] = []


class SubmitRequest(BaseModel):
    felt: str = ""
    sitting_out: str = ""
    why: str = ""
    why_text: str = ""
    keep: str = ""
    comment: str = ""


class DiscordFormRequest(BaseModel):
    discord_user_id: int


class DiscordSubmitRequest(SubmitRequest):
    discord_user_id: int


class SubmitError(BaseModel):
    detail: str
    errors: List[str]


class Bar(BaseModel):
    key: str
    label: str
    count: int


class SplitSide(BaseModel):
    key: str
    label: str
    count: int
    bars: List[Bar]


class FrameRow(BaseModel):
    key: str
    label: str
    asked_count: int
    asked_percent: int
    answered_count: int
    answered_percent: int


class Chip(BaseModel):
    key: str
    label: str
    count: int
    active: bool


class ResultsResponse(BaseModel):
    show_link: bool
    status: str
    lede: str = ""
    cohort_count: int = 0
    response_count: int = 0
    answered_percent: int = 0
    glad_or_fine_percent: int = 0
    open_replied: int = 0
    open_asked: int = 0
    frame: List[FrameRow] = []
    frame_note: str = ""
    chips: List[Chip] = []
    cut: str = "all"
    sitting_out: List[Bar] = []
    sitting_out_split: List[SplitSide] = []
    sitting_out_help: str = ""
    felt: List[Bar] = []
    felt_split: List[SplitSide] = []
    felt_help: str = ""
    why: List[Bar] = []
    why_help: str = ""
    keep: List[Bar] = []
    quotes: List[str] = []
    quotes_help: str = ""


class CommandRequest(BaseModel):
    discord_user_id: int
    action: str
    confirm: bool = False


class CommandResponse(BaseModel):
    message: str
