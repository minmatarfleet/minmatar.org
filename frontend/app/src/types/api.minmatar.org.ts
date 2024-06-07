export interface Character {
    character_id:   number;
    character_name: string;
    skills:         Skill[];
}

export interface Skill {
    active_skill_level:   number;
    skill_id:             number;
    skillpoints_in_skill: number;
    trained_skill_level:  number;
}

export type GroupStatus = 'available' | 'requested' | 'confirmed'

export interface Group {
    id:             number;
    name:           string;
    description:    string | null;
    image_url:      string | null;
    officers?:      number[];
    directors?:     number[];
    members:        number[];
}

export interface SigRequest {
    id:             number;
    user:           number;
    sig_id:         number;
    approved:       boolean | null;
    approved_by:    number | null;
    approved_at:    Date;
}

export interface TeamRequest {
    id:             number;
    user:           number;
    team_id:        number;
    approved:       boolean | null;
    approved_by:    number | null;
    approved_at:    Date;
}

export type CorporationType = 'alliance' | 'associate' | 'militia' | 'public'

export interface Corporation {
    corporation_id:     number;
    corporation_name:   string;
    alliance_id:        number;
    alliance_name:      string;
    faction_id:         number;
    faction_name:       string;
    type:               CorporationType;
    introduction:       string;
    biography:          string;
    timezones:          string[];
    requirements:       string[];
    members:            CharacterCorp[];
    active:             boolean;
}

export interface CorporationInfo {
    corporation_id:     number;
    corporation_name:   string;
    alliance_id:        number;
    alliance_name:      string;
    faction_id:         number;
    faction_name:       string;
    type:               CorporationType;
    introduction:       string;
    biography:          string;
    timezones:          string[];
    requirements:       string[];
    active:             boolean;
}

export interface CharacterCorp {
    character_id:           number;
    character_name:         string;
    primary_character_id:   number;
    primary_character_name: string;
    registered:             boolean;
    exempt:                 boolean;
}

export interface CorporationApplication {
    status:         string;
    application_id: number;
    user_id:        number;
    corporation_id: number;
}

export interface CorporationApplicationDetails {
    status:         string;
    application_id: number;
    user_id:        number;
    corporation_id: number;
    description:    string;
    created_at:     Date;
    updated_at:     Date;
    characters:     Character[];
}

export interface Character {
    character_id:   number;
    character_name: string;
}

export interface UserProfile {
    user_id:               number;
    username:              string;
    permissions:           string[];
    is_superuser:          boolean;
    eve_character_profile: EveCharacterProfile | null;
    discord_user_profile:  DiscordUserProfile | null;
}

export interface DiscordUserProfile {
    id:          number;
    discord_tag: string;
    avatar:      string | null;
}

export interface EveCharacterProfile {
    character_id:     number;
    character_name:   string;
    corporation_id:   number;
    corporation_name: string;
    scopes:           string[];
}

export interface CharacterSkillset {
    name:           string;
    progress:       number;
    missing_skills: string[];
}

export interface CharacterAsset {
    type_id:        number;
    type_name:      string;
    location_id:    number;
    location_name:  string;
}

export interface Fitting {
    id:             number;
    name:           string;
    ship_id:        number;
    description:    string;
    created_at:     Date;
    updated_at:     Date;
    tags:           string[];
    eft_format:     string;
    latest_version: string;
}

export type DoctrineTypes = 'shield' | 'armor' | 'armorshield'

export interface Doctrine {
    id:                 number;
    name:               string;
    type:               DoctrineTypes;
    created_at:         Date;
    updated_at:         Date;
    description:        string;
    primary_fittings:   Fitting[];
    secondary_fittings: Fitting[];
    support_fittings:   Fitting[];
}

export const fleet_types = ['strategic', 'non_strategic', 'training'] as const
export type FleetTypes = typeof fleet_types[number]

export interface Fleet {
    id:                 number;
    type:               FleetTypes;
    audience:           string;
    description:        string;
    start_time:         Date;
    fleet_commander:    number;
    doctrine_id:        number;
    location:           string;
    tracking:           Tracking;
}

export interface FleetBasic {
    id:                 number;
    audience:           string;
}

export interface Tracking {
    id:             number;
    start_time:     Date;
    end_time:       Date;
    is_registered:  boolean;
}

export interface FleetRequest {
    type:           FleetTypes;
    description:    string;
    start_time:     Date;
    doctrine_id:    number;
    location_id:    number;
    audience_id:    number;
}

export interface MumbleInformation {
    username:   string,
    password:   string,
    url:        string
}

export interface Audience {
    id:                     number;
    display_name:           string;
    display_channel_name:   string;
}

export interface FleetMember {
    character_id: number,
    character_name: string,
    ship_type_id: number,
    ship_type_name: string,
    solar_system_id: number,
    solar_system_name: string,
}

export interface Location {
    location_id:        number;
    location_name:      string;
    solar_system_id:    number;
    solar_system_name:  string;
}