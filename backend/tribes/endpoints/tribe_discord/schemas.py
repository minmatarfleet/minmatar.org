"""Discord role mapping on a tribe's own server."""

from pydantic import BaseModel, Field


class TribeDiscordRole(BaseModel):
    id: str
    name: str


class TribeDiscordMapping(BaseModel):
    state: str
    role_id: str | None = None
    problem: str | None = None


class TribeDiscordSettings(BaseModel):
    available: bool = False
    connected: bool = False
    guild_name: str | None = None
    can_manage_roles: bool = False
    checked: bool = False
    roles: list[TribeDiscordRole] = Field(default_factory=list)
    mappings: list[TribeDiscordMapping] = Field(default_factory=list)


class TribeDiscordMappingUpdate(BaseModel):
    mappings: list[TribeDiscordMapping] = Field(default_factory=list)
