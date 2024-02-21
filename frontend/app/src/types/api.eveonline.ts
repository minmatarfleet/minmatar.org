export interface CharacterEvE {
    alliance_id:     number;
    birthday:        Date;
    bloodline_id:    number;
    corporation_id:  number;
    description:     string;
    gender:          string;
    name:            string;
    race_id:         number;
    security_status: number;
}

export interface CorporationEvE {
    alliance_id:     number;
    ceo_id:          number;
    creator_id:      number;
    date_founded:    Date;
    description:     string;
    faction_id:      number;
    home_station_id: number;
    member_count:    number;
    name:            string;
    shares:          number;
    tax_rate:        number;
    ticker:          string;
    url:             string;
    war_eligible:    boolean;
}

export interface CorporationEvE {
    alliance_id:     number;
    ceo_id:          number;
    creator_id:      number;
    date_founded:    Date;
    description:     string;
    faction_id:      number;
    home_station_id: number;
    member_count:    number;
    name:            string;
    shares:          number;
    tax_rate:        number;
    ticker:          string;
    url:             string;
    war_eligible:    boolean;
}

export interface AllianceEvE {
    creator_corporation_id:  number;
    creator_id:              number;
    date_founded:            Date;
    executor_corporation_id: number;
    faction_id:              number;
    name:                    string;
    ticker:                  string;
}

export interface CorporationHistoryEvE {
    corporation_id: number;
    record_id:      number;
    start_date:     Date;
}

export interface NamesAndCategoriesEvE {
    category: string;
    id:       number;
    name:     string;
}