export interface Character {
    character_id:   number;
    character_name: string;
}

export type GroupStatus = 'available' | 'requested' | 'confirmed'

export interface Group {
    id:             number;
    name:           string;
    description:    string;
    image_url:      string;
    status?:        GroupStatus;
}

export interface GroupRequest {
    id:             number;
    user:           number;
    group:          number;
    approved:       boolean;
    approved_by:    number;
    approved_at:    string;
}

export interface Corporation {
    corporation_id:     number;
    corporation_name:   string;
    alliance_id:        number;
    alliance_name:      string,
    corporation_type:   string;
}

export interface CorporationApplication {
    status:         string;
    user_id:        number;
    corporation_id: number;
}

export interface UserProfile {
    user_id:               number;
    username:              string;
    permissions:           any[];
    is_superuser:          boolean;
    eve_character_profile: EveCharacterProfile;
    discord_user_profile:  DiscordUserProfile;
}

export interface DiscordUserProfile {
    id:          number;
    discord_tag: string;
    avatar:      string;
}

export interface EveCharacterProfile {
    character_id:     number;
    character_name:   string;
    corporation_id:   number;
    corporation_name: string;
    scopes:           string[];
}