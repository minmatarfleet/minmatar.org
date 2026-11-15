"""Response and request schemas for /api/tasks."""

from datetime import date, datetime
from typing import Optional

from ninja import Schema


class PersonResponse(Schema):
    user_id: int
    # The main character's name (the username when there is no main).
    name: str
    character_id: Optional[int] = None


class WaitingOnResponse(Schema):
    id: int
    title: str


class TaskResponse(Schema):
    id: int
    # "automatic" (opened and closed by the site) or "assigned".
    kind: str
    rule: str
    title: str
    detail: str
    body: str
    link_url: str
    link_label: str
    # "needs_you" or "suggestion".
    weight: str
    # "open", "done", "stopped" or "cancelled".
    status: str
    # "this_week", "no_rush" or "date".
    when: str
    due_date: Optional[date] = None
    recurrence: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    close_note: str
    snoozed_until: Optional[datetime] = None
    assignee: Optional[PersonResponse] = None
    created_by: Optional[PersonResponse] = None
    thanked_by: Optional[PersonResponse] = None
    # "" for a pilot's own task; "corporation", "tribe_group" or "staff"
    # for work a team shares until someone takes it.
    team_kind: str
    team_id: Optional[int] = None
    team_role: str
    team_label: str
    project_id: Optional[int] = None
    project_name: str
    stage: str
    waiting_on: Optional[WaitingOnResponse] = None
    # Its author was asked whether it is still needed.
    still_needed: bool
    comment_count: int
    # What the viewer may do: done, snooze, not_now, bring_back, hand_back,
    # take, keep, let_close, thank.
    actions: list[str]


class TaskCommentResponse(Schema):
    id: int
    author: Optional[PersonResponse] = None
    body: str
    created_at: datetime


class TaskDetailResponse(TaskResponse):
    comments: list[TaskCommentResponse]


class MyTasksResponse(Schema):
    # The viewer, named by their main.
    me: Optional[PersonResponse] = None
    # Paused by the pilot or On Leave: nothing counts or reminds.
    paused: bool
    show_suggestions: bool
    # Leaders write tasks and start projects.
    can_assign: bool
    # The Neocom count.
    needs_you: int
    # Ask once: "Want one Discord DM a week?"
    weekly_prompt: bool = False
    snoozed: int
    now: list[TaskResponse]
    this_week: list[TaskResponse]
    later: list[TaskResponse]
    # Suggestions and "still needed?" asks.
    minute: list[TaskResponse]
    up_for_grabs: list[TaskResponse]
    closed_this_week: list[TaskResponse]
    stopped: list[TaskResponse]


class TaskCountResponse(Schema):
    needs_you: int


class TaskCreateRequest(Schema):
    title: str
    # A person (user id) or a manage screen key for its team.
    assignee_id: Optional[int] = None
    screen: str = ""
    when: str = "this_week"
    due_date: Optional[date] = None
    body: str = ""
    link_url: str = ""
    project_id: Optional[int] = None
    stage_id: Optional[int] = None


class TaskCommentRequest(Schema):
    body: str


class AssigneeTeamResponse(Schema):
    screen: str
    label: str


class AssigneePersonResponse(PersonResponse):
    # How much they already have open, so nobody gets piled on.
    open_tasks: int = 0


class AssigneesResponse(Schema):
    people: list[AssigneePersonResponse]
    teams: list[AssigneeTeamResponse]


class TeamRowResponse(Schema):
    # "corporation", "tribe" or "tribe_group".
    kind: str
    id: int
    name: str
    open: int
    closed_this_week: int
    detail: str


class RuleRollupResponse(Schema):
    rule: str
    label: str
    weight: str
    waiting: int
    closed_this_week: int


class TeamOverviewResponse(Schema):
    corporations: list[TeamRowResponse]
    tribes: list[TeamRowResponse]
    # Alliance-wide pilot rollup (superusers).
    pilots: list[RuleRollupResponse]


class TeamGroupResponse(Schema):
    id: int
    tribe_id: int
    name: str
    chief: Optional[PersonResponse] = None
    open: int
    closed_this_week: int


class TeamDetailResponse(Schema):
    kind: str
    id: int
    name: str
    leader_tasks: list[TaskResponse]
    leader_closed_this_week: int
    groups: list[TeamGroupResponse]
    members: list[RuleRollupResponse]
    # Members on leave or paused, left out of every count.
    members_paused: int


class TeamRulePilotResponse(Schema):
    task_id: int
    pilot: Optional[PersonResponse] = None
    detail: str
    opened_at: datetime
    # A leader's one reminder, if sent.
    reminded_at: Optional[datetime] = None
    # It has waited long enough and nobody reminded them yet.
    can_remind: bool = False


class ProjectRowResponse(Schema):
    id: int
    name: str
    kind: str
    kind_label: str
    status: str
    lead: Optional[PersonResponse] = None
    team_label: str
    link_url: str
    link_label: str
    starts_on: Optional[date] = None
    # A target, not a deadline.
    target_date: Optional[date] = None
    finished_at: Optional[datetime] = None
    tasks_total: int
    tasks_done: int
    up_for_grabs: int
    # The latest update's health, or "".
    health: str
    # Open a week with no update in the last week.
    update_missing: bool


class ProjectListRowResponse(ProjectRowResponse):
    i_lead: bool
    i_have_tasks: bool


class ProjectTemplateRowResponse(Schema):
    id: int
    kind: str
    name: str
    description: str
    task_count: int


class ProjectsResponse(Schema):
    can_start: bool
    open: list[ProjectListRowResponse]
    finished: list[ProjectListRowResponse]
    templates: list[ProjectTemplateRowResponse]


class ProjectStageResponse(Schema):
    id: int
    name: str
    done: int
    total: int
    tasks: list[TaskResponse]


class ProjectUpdateResponse(Schema):
    id: int
    author: Optional[PersonResponse] = None
    # "on_track", "at_risk" or "off_track".
    health: str
    body: str
    created_at: datetime


class ProjectPersonResponse(Schema):
    person: PersonResponse
    is_lead: bool
    open: int
    done: int


class ProjectDetailResponse(ProjectRowResponse):
    can_edit: bool
    stages: list[ProjectStageResponse]
    updates: list[ProjectUpdateResponse]
    waiting_longest: Optional[WaitingOnResponse] = None
    people: list[ProjectPersonResponse]


class ProjectCreateRequest(Schema):
    name: str
    template_id: Optional[int] = None
    lead_id: Optional[int] = None
    starts_on: Optional[date] = None
    target_date: Optional[date] = None
    link_url: str = ""


class ProjectUpdateRequest(Schema):
    health: str
    body: str


class RuleSettingResponse(Schema):
    rule: str
    label: str
    description: str
    # "pilot", "chief", "ceo" or "staff".
    audience: str
    weight: str
    enabled: bool
    stop_after_days: Optional[int] = None
    claim_expires_days: Optional[int] = None
    # A leader may remind once after this many days (pilot rules).
    remind_after_days: Optional[int] = None
    open_now: int


class RuleSettingPatch(Schema):
    enabled: Optional[bool] = None
    stop_after_days: Optional[int] = None
    claim_expires_days: Optional[int] = None
    remind_after_days: Optional[int] = None


class TemplateTaskResponse(Schema):
    id: int
    stage: str
    title: str
    # "lead" or "screen:<key>".
    goes_to: str
    offset_days: Optional[int] = None
    recurrence: str


class ProjectTemplateResponse(ProjectTemplateRowResponse):
    tasks: list[TemplateTaskResponse]


class TaskPreferencesResponse(Schema):
    show_suggestions: bool
    paused: bool
    # On Leave also pauses tasks; only reviewers change it.
    on_leave: bool
    # The weekly list on Discord.
    weekly_dm: bool = False
    # Quiet hours in EVE (UTC) hours; both null means none.
    quiet_start: Optional[int] = None
    quiet_end: Optional[int] = None


class TaskPreferencesPatch(Schema):
    show_suggestions: Optional[bool] = None
    paused: Optional[bool] = None
    # Yes or no to the weekly list (answers the one-time prompt too).
    weekly_dm: Optional[bool] = None
    quiet_start: Optional[int] = None
    quiet_end: Optional[int] = None
    # Clear quiet hours.
    clear_quiet_hours: bool = False


class DigestSettingsResponse(Schema):
    enabled: bool
    # Monday is 0.
    weekday: int
    # EVE (UTC) hour.
    hour: int
    # Pilots who said yes to the weekly list.
    opted_in: int
    # At the last send: how many had something waiting (got one), and of
    # those, delivered and not delivered (DMs closed).
    had_waiting: int
    delivered: int
    not_delivered: int
    last_sent_at: datetime
    next_send_at: datetime


class DigestSettingsPatch(Schema):
    enabled: Optional[bool] = None
    weekday: Optional[int] = None
    hour: Optional[int] = None
