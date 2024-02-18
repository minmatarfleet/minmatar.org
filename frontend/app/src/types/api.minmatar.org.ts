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