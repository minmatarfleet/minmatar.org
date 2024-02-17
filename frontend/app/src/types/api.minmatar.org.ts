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
    status:         GroupStatus;
}

export interface GroupRequest {
    id:             number;
    user:           number;
    group:          number;
    approved:       boolean;
    approved_by:    number;
    approved_at:    string;
}