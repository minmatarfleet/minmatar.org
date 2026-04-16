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
    content?:       string;
}

export interface TribeCharacterRef {
    character_id:   number;
    character_name: string;
}

export interface TribeQualifyingAssetType {
    type_id:        number;
    type_name:      string;
    minimum_count:  number;
    location_id:    number | null;
}

export interface TribeQualifyingSkill {
    skill_type_id:  number;
    skill_name:     string;
    minimum_level:  number;
}

export interface TribeRequirement {
    id:                     number;
    asset_types:            TribeQualifyingAssetType[];
    qualifying_skills:      TribeQualifyingSkill[];
}

export interface TribeGroup {
    id:                     number;
    tribe_id:               number;
    tribe_name:             string;
    name:                   string;
    description:            string;
    discord_channel_id:     number | null;
    chief:                  TribeCharacterRef | null;
    ship_type_ids:          number[];
    blueprint_type_ids:     number[];
    is_active:              boolean;
    member_count:           number;
    requirements:           TribeRequirement[];
}

export interface Tribe {
    id:                     number;
    name:                   string;
    slug:                   string;
    description:            string;
    content:                string;
    image_url:              string | null;
    banner_url:             string | null;
    discord_channel_id:     number | null;
    chief:                  TribeCharacterRef | null;
    is_active:              boolean;
    group_count:            number;
    total_member_count:     number;
}

export interface TribeGroupOutputSummary {
    tribe_group_id:     number;
    tribe_group_name:   string;
    tribe_id:           number;
    period_start:       string | null;
    period_end:         string | null;
    totals:             Record<string, number>;  // e.g. { "kills (kills)": 5, "mining_contribution (m3)": 150000 }
}

export interface TribeLeaderboardEntry {
    user_id:        number;
    character_id:   number | null;
    character_name: string | null;
    total:          number;
    unit:           string;
}

export type TribeMembershipStatus = 'pending' | 'active' | 'inactive'

export interface TribeMembershipCharacter {
    id:             number;
    character_id:   number;
    character_name: string;
    committed_at:   string | null;
    left_at:        string | null;
    /** Requirement qualification (present when viewer is chief). */
    qualifies?:     boolean | null;
    missing_skills?: boolean | null;
    missing_assets?: boolean | null;
}

export interface TribeMembership {
    id:                     number;
    user_id:                number;
    tribe_group_id:         number;
    tribe_group_name:       string;
    tribe_id:               number;
    status:                 TribeMembershipStatus;
    inactive_reason:        string | null;
    requirement_snapshot:   Record<string, unknown> | null;
    created_at:             string;
    approved_by_id:         number | null;
    approved_at:            string | null;
    left_at:                string | null;
    /** Always present when available; returned for all viewers. */
    primary_character_id:   number | null;
    primary_character_name: string;
    /** Committed characters (alts); only populated when viewer is a tribe chief/manager. */
    characters:             TribeMembershipCharacter[];
}

/** Per-requirement qualification result for one character (memberships/characters-available). */
export interface TribeRequirementQualification {
    requirement_id: string;
    display: string;
    met: boolean;
    detail: string;
}

/** User character with qualification status for a group's requirements (memberships/characters-available). */
export interface TribeAvailableCharacter {
    character_id: number;
    character_name: string;
    qualifies: boolean;
    requirements: TribeRequirementQualification[];
    /** When qualifies is false: missing skills, assets, or both (for simple UI). */
    missing_skills: boolean;
    missing_assets: boolean;
}

export interface TribeActivity {
    id:             number;
    tribe_group_id: number;
    tribe_group_name: string;
    user_id:        number;
    character_id:   number | null;
    activity_type:  ActivityType;
    quantity:       number;
    unit:           string;
    description:    string;
    created_at:     string;
}

/** Single activity record for group timeline (GET group activity). */
export interface TribeGroupActivityRecord {
    id:                         number;
    created_at:                 string;
    activity_type:              string;
    activity_type_display:      string;
    character_id:               number | null;
    character_name:             string;
    primary_character_id:       number | null;
    primary_character_name:     string;
    user_id:                    number | null;
    username:                   string;
    source_type_id:             number | null;
    target_type_id:             number | null;
    quantity:                   number | null;
    unit:                       string;
    reference_type:             string;
    reference_id:               string;
}

/** Paginated list of tribe group activity records. */
export interface TribeGroupActivityList {
    items:   TribeGroupActivityRecord[];
    total:   number;
    limit:   number;
    offset:  number;
}

/** Per-activity metrics for one TribeGroupActivity (GET tribe activity metrics). */
export interface TribeActivityMetrics {
    activity_id:            number;
    activity_type:          string;
    activity_type_display:  string;
    group_id:               number;
    group_name:             string;
    unit:                   string;
    record_count:           number;
    total_quantity:         number | null;
    total_points:           number;
}

/** Per-activity-type breakdown item for member activity. */
export interface TribeMemberActivityBreakdownItem {
    activity_type:  string;
    unit:           string;
    record_count:   number;
    total_quantity: number | null;
}

/** Activity summary for one tribe member (GET member activity). */
export interface TribeMemberActivity {
    primary_character_id:   number | null;
    primary_character_name:  string;
    alts:                   TribeCharacterRef[];
    total_points:           number;
    record_count:           number;
    breakdown:              TribeMemberActivityBreakdownItem[];
}

/** One leaderboard entry (points only). */
export interface TribeActivityLeaderboardEntry {
    user_id:                number;
    primary_character_id:   number | null;
    primary_character_name: string;
    alts:                   TribeCharacterRef[];
    total_points:           number;
}

/** Paginated tribe activity leaderboard. */
export interface TribeActivityLeaderboardList {
    items:   TribeActivityLeaderboardEntry[];
    total:   number;
    limit:   number;
    offset:  number;
}

export const activity_types = [
    'fleet_participation',
    'kills',
    'losses',
    'mining_contribution',
    'freight_contribution',
    'industry_job_completed',
    'content_contribution',
    'doctrine_update',
    'fitting_update',
    'custom',
] as const
export type ActivityType = typeof activity_types[number]

export interface LogActivityPayload {
    user_id: number;
    character_id?: number | null;
    activity_type: ActivityType;
    quantity: number;
    unit: string;
    description?: string;
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
    user_id:            number;
    character_id:       number;
    character_name:     string;
    corporation_id:     number;
    corporation_name:   string;
    scopes:             string[];
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

export type FittingTagSlug =
    | 'highsec'
    | 'industry'
    | 'lowsec'
    | 'nullsec'
    | 'faction_warfare'
    | 'solo'
    | 'nanogang'
    | 'fleet_composition'
    | 'new_player_friendly'
    | 'budget'
    | 'capitals'
    | 'command_bursts'
    | 'escape_frigate'

export interface Fitting {
    id:                 number;
    name:               string;
    ship_id:            number;
    description:        string;
    created_at:         Date;
    updated_at:         Date;
    eft_format:         string;
    minimum_pod:        string;
    recommended_pod:    string;
    latest_version:     string;
    tags:               FittingTagSlug[];
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
    sig_ids:            number[];
    location_ids:       number[];
}

export const fleet_status = ['active', 'upcoming', 'recent'] as const
export type FleetStatus = typeof fleet_status[number]

export const fleet_types = ['strategic', 'non_strategic', 'training'] as const
export type FleetTypes = typeof fleet_types[number]

export interface Fleet {
    id:                 number;
    type:               FleetTypes;
    audience?:          string;
    description:        string;
    objective?:         string;
    start_time:         Date;
    fleet_commander?:   number;
    doctrine_id:        number;
    location:           string;
    disable_motd:       boolean;
    tracking?:          Tracking;
    status?:            TrackingStatus;
    aar_link:           string;
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
    type:               FleetTypes;
    description:        string;
    start_time:         Date;
    doctrine_id:        number | null;
    location_id?:       number | null;
    audience_id:        number;
    disable_motd:       boolean;
    immediate_ping?:    boolean;
    status?:            TrackingStatus;
}

export interface FleetPatchRequest {
    type?:              FleetTypes;
    description?:       string;
    start_time?:        Date;
    doctrine_id?:       number | null;
    location_id?:       number;
    audience_id?:       number;
    disable_motd?:      boolean;
    immediate_ping?:    boolean;
    status?:            TrackingStatus;
    aar_link?:          string;
}

export const tracking_status = ['pending', 'active', 'complete', 'cancelled', 'unknown'] as const
export type TrackingStatus = typeof tracking_status[number]

export interface MumbleInformation {
    username:   string;
    password:   string;
    url:        string;
}

export interface Audience {
    id:                     number;
    display_name:           string;
    display_channel_name:   string;
    image_url:              string | null;
}

export interface FleetMember {
    character_id:       number;
    character_name:     string;
    ship_type_id:       number;
    ship_type_name:     string;
    solar_system_id:    number;
    solar_system_name:  string;
}

export interface BaseLocation {
    location_id:    number;
    location_name:  string;
}

export interface Location extends BaseLocation {
    solar_system_id:    number;
    solar_system_name:  string;
    short_name:         string;
    region_id:          number | null;
    market_active:      boolean;
    prices_active:      boolean;
    freight_active:     boolean;
    staging_active:     boolean;
}

export interface FleetUsers {
    fleet_id:   number;
    user_ids: number[];
}

export interface StructureTimer {
    id:                 number;
    name:               string;
    state:              string;
    type:               string;
    timer:              Date;
    created_at:         Date;
    updated_at:         Date;
    created_by:         number;
    updated_by:         number;
    system_name:        string;
    corporation_name:   string;
    alliance_name:      string;
    structure_id:       number;
}

export const structure_states = [ 'anchoring', 'armor', 'hull', 'unanchoring' ] as const
export type StructureState = typeof structure_states[number]

export const structure_types = [
    'astrahus',
    'fortizar',
    'keepstar',
    'raitaru',
    'azbel',
    'sotiyo',
    'athanor',
    'tatara',
    'tenebrex_cyno_jammer',
    'pharolux_cyno_beacon',
    'ansiblex_jump_gate',
    'orbital_skyhook',
    'metenox_moon_drill',
    'mercenary_den',
    'player_owned_customs_office',
    'player_owned_starbase',
] as const
export type StructureType = typeof structure_types[number]

export interface StructureTimerRequest {
    selected_item_window:   string;
    corporation_name:       string;
    state:                  StructureState;
    type:                   StructureType;
}

export interface VerifyStructureTimerRequest {
    corporation_name:   string;
    alliance_name:      string;
}

export interface Post {
    post_id:            number;
    state:              PostStates;
    title:              string;
    seo_description:    string;
    slug:               string;
    content?:           string;
    image?:             string;
    date_posted:        Date;
    user_id:            number;
    tag_ids:            number[];
}

export interface PostParams {
    title?:             string;
    seo_description?:   string;
    state?:             PostStates;
    content?:           string;
    tag_ids?:           number[];
}

export interface PostTag {
    tag_id:     number;
    tag:        string;
}

export const post_states = [ 'draft', 'published', 'trash' ] as const
export type PostStates = typeof post_states[number]

export interface FreightRoute {
    orgin:              FreightLocation;
    destination:        FreightLocation;
    route_id:           number;
    expiration_days:    number;
    days_to_complete:   number;
    collateral_modifier: number;
}

export interface FreightLocation {
    location_id:    number;
    name:           string;
    short_name:     string;
}

export interface RouteCost {
    route_id:   number;
    cost:       number;
}


export interface SystemMoon {
    id:         number;
    system:     string;
    planet:     string;
    moon:       number;
    detail:     SystemMoonDetails;
}

export interface SystemMoonDetails {
    monthly_revenue?:   number;
    reported_by:        string;
}

export interface MoonSummarySystem {
    system:         string;
    scanned_moons:  number;
}

export interface CombatLog {
    logged_events:      number;
    damage_done:        number;
    damage_taken:       number;
    weapons:            CombatLogItem[];
    enemies:            CombatLogItem[];
    times:              CombatLogItem[];
    start:              Date;
    end:                Date;
    db_id:              number;
    user_id:            number;
    fitting_id:         number;
    fleet_id:           number;
    character_name:     string;
    armor_repaired:     number;
    shield_repaired:    number;
    max_from:           CombatLogMax;
    max_to:             CombatLogMax;
    repairs:            Repairs[];
    rep_modules:        Repairs[];
}

export type RepairTypes = 'shield' | 'armor' | 'hull'

export interface Repairs {
    name:       string;
    category:   string;
    rep_type:   RepairTypes;
    cycles_to:  number;
    repairs_to: number;
    max_to:     number;
    avg_to:     number
    first:      Date;
    last:       Date;
}

export interface SavedCombatLog {
    id:             number;
    uploaded_at:    Date;
    user_id:        number;
    fleet_id:       number;
    fitting_id:     number;
    character_name: string;
    system_name:    string;
}

export interface CombatLogMax {
    event_time:     string;
    damage:         number;
    direction:      DamageDirection;
    entity:         string;
    weapon:         string;
    outcome:        string;
    location:       string;
    text:           string;
}

export interface CombatLogStoreOptions {
    access_token:   string;
    fitting_id?:    number;
    fleet_id?:      number;
}

export const damage_direction = [ 'from', 'to' ] as const
export type DamageDirection = typeof damage_direction[number]

export const combatlog_item_category = [ 'Weapon', 'Enemy', 'TimeBucket' ] as const
export type CombatlogItemCategory = typeof combatlog_item_category[number]

export interface CombatLogItem {
    name:           string;
    category:       CombatlogItemCategory;
    volleys_from:   number;
    damage_from:    number;
    max_from:       number;
    avg_from:       number;
    volleys_to:     number;
    damage_to:      number;
    reps_to:        number;
    max_to:         number;
    avg_to:         number;
    first:          Date;
    last:           Date;
}

export interface SavedLogsRequest {
    user_id?:   number;
    fleet_id?:  number;
    fitting_id?:  number;
}

export interface ContractDoctrine {
    id:     number;
    name:   string;
    type:   string;
    role:   string;
}

export interface Contract {
    expectation_id:             number | null;
    title:                      string;
    fitting_id:                 number;
    structure_id:               number | null;
    location_name:              string;
    desired_quantity:           number;
    current_quantity:           number;
    latest_contract_timestamp:  string | null;
    historical_quantity:        History[];
    responsibilities:           Responsability[];
    doctrines:                  ContractDoctrine[];
}

export interface History {
    date:       string;
    quantity:   number;
}

export interface Responsability {
    entity_type:    string;
    entity_id:      number;
    entity_name:    string;
}

export interface MarketCorporation {
    corporation_id:     number;
    corporation_name:   string;
}

export interface MarketExpectation {
    expectation_id:     number;
    fitting_id:         number;
    fitting_name:       string;
    location_id:        number;
    location_name:      string;
    quantity:           number;
}

export interface MarketLocation {
    id:             number;
    name:           string;
    system_name:    string;
    contracts:      number;
    expectations:   number;
    structure_id:   number;
}

export interface DoctrineFitting {
    fitting_id:         number;
    fitting_name:       string;
    role:               string;
}

export interface MarketDoctrine {
    doctrine_id:        number;
    doctrine_name:      string;
    fittings:           DoctrineFitting[];
}

export interface MarketLocationDoctrine {
    location_id:        number;
    location_name:      string;
    solar_system_name:  string;
    short_name:         string;
    doctrines:          MarketDoctrine[];
}

export const srp_status = [ 'pending', 'approved', 'rejected', 'withdrawn' ] as const
export type SRPStatus = typeof srp_status[number]

export interface SRP {
    id:                         number;
    fleet_id:                   number;
    external_killmail_link:     string;
    status:                     SRPStatus;
    character_id:               number;
    character_name:             string;
    primary_character_id:       number;
    primary_character_name:     string;
    ship_type_id:               number;
    ship_name:                  string;
    killmail_id:                number;
    amount:                     number;
    is_corp_ship:               boolean;
    corp_id:                    number;
    comments:                   string;
    category:                   SRPCategory;
    combat_log_id:              number;
}

export interface SRPFilter {
    fleet_id?:  number;
    status?:    SRPStatus;
}

export interface PostRequest {
    user_id?:       number;
    tag_id?:        number;
    page_size?:     number;
    page_num?:      number;
    status?:        PostStates;
}

export interface ReferralLinkStats {
    name:       string;
    user_id:    number;
    referrals:  number;
}

export interface ReferralLink {
    name:       string;
    link:       string;
}

export interface ExternalReferralLink {
    name:       string;
    slug:       string;
    link:       string;
    target:     string;
    decription: string;
}

export interface NotificationSubscription {
    id:             number;
    subscription:   string;
}

export interface NotificationSubscriptionsFull {
    id:             number;
    user_id:        number | null;
    subscription:   string;
}

export interface CharacterSummary {
    user_id:        number;
    user_name:      string;
    discord_id:     string;
    characters:     SummaryCharacter[];
}

export const esi_token_status = [ 'ACTIVE', 'SUSPENDED' ] as const
export type ESITokenStatus = typeof esi_token_status[number]

export const character_errors = [ 'MAIN_NOT_IN_FL33T', 'NO_TOKEN_LEVEL', 'ESI_SUSPENDED', 'NO_MAIN_SET', 'NO_TAGS' ] as const
export type CharacterErrors = typeof character_errors[number]
export interface SummaryCharacter {
    character_id:       number;
    character_name:     string;
    is_primary:         boolean;
    corp_id:            number;
    corp_name:          string;
    alliance_id:        number;
    alliance_name:      string;
    esi_token:          string;
    token_status:       ESITokenStatus;
    flags:              CharacterErrors[];
    requested_groups:   string[];
}

export interface CharacterESITokens {
    id:                 number;
    created:            Date;
    expires:            Date;
    can_refresh:        boolean;
    owner_hash:         string;
    scopes:             string[];
    level:              string;
    requested_groups:   string[];
    actual_groups:      string[];
    requested_count:    number;
    actual_count:       number;
    token_state:        string;
    requested_level:    string;
    actual_level:       string;
}

export interface CharacterTag {
    id:             number;
    title:          string;
    description:    string;
    image_name:     string;
}

export const esi_token_roles = [ 'Public', 'Basic', 'Director', 'Industry', 'Market', 'Executor' ] as const
export type ESITokenRoles = typeof esi_token_roles[number]

export const prime_times = [ 'US', 'AP', 'EU' ] as const
export type PrimeTime = typeof prime_times[number]

export interface Player {
    id:                     number;
    nickname:               string;
    user_id:                number;
    primary_character_id:   number;
    prime_time:             PrimeTime | null;
}

export const srp_categories = [ 'logistics', 'support', 'dps', 'capital' ] as const
export type SRPCategory = typeof srp_categories[number]

export interface SRPRequest {
    external_killmail_link:     string;
    fleet_id?:                  number;
    combatlog_id?:              number;
    is_corp_ship:               boolean;
    category?:                  SRPCategory;
    comments?:                  string;
}

export interface BaseIndustryOrder {
    name:       string;
    type_id:    number;
    quantity:   number;
}

export interface NestedIndustryOrder extends BaseIndustryOrder {
    source:     string;
    depth:      number;
    children:   NestedIndustryOrder[];
}

export interface Producer {
    id:                 number;
    name:               string;
    total_value_isk?:   number;
}

export interface ProductBase {
    id:         number;
    type_id:    number;
    name:       string;
}

export interface Product extends ProductBase {
    strategy:                       string;
    volume:                         number;
    blueprint_or_reaction_type_id:  number;
    supplied_for:                   ProductBase[];
    supplies:                       ProductBase[];
    character_producers:            Producer[];
    corporation_producers:          Producer[]
}

/** Planetary (PI) API types */
export interface PlanetaryCharacterRef {
    character_id:   number;
    character_name: string;
}

export interface HarvestOverviewItem {
    type_id:                number;
    name:                   string;
    total_extractors:       number;
    total_daily_quantity?:  number | null;
}

export interface HarvestDrillDownItem {
    primary_character:  PlanetaryCharacterRef;
    actual_character:   PlanetaryCharacterRef;
    extractor_count:    number;
    daily_quantity?:    number | null;
}

export interface ProductionOverviewItem {
    type_id:                number;
    name:                   string;
    total_factories:        number;
    total_daily_quantity?:  number | null;
}

export interface ProductionDrillDownItem {
    primary_character:  PlanetaryCharacterRef;
    actual_character:   PlanetaryCharacterRef;
    factory_count:      number;
    daily_quantity?:    number | null;
}

/** One colony on a planet (primary + actual character). */
export interface ColonyEntry {
    primary_character:  PlanetaryCharacterRef;
    actual_character:   PlanetaryCharacterRef;
}

/** One planet with list of characters that have colonies on it. */
export interface PlanetWithColoniesItem {
    planet_id:        number;
    solar_system_id:  number;
    planet_type:     string;
    colonies:        ColonyEntry[];
}

export interface HarvestDrillDownResponse {
    characters:  PlanetaryCharacterRef[];
    entries:     HarvestDrillDownItem[];
}

export interface ProductionDrillDownResponse {
    characters:  PlanetaryCharacterRef[];
    entries:     ProductionDrillDownItem[];
}

/** @deprecated Use PlanetWithColoniesItem for GET /planetary/planets */
export interface PlanetSummaryItem {
    primary_character:  PlanetaryCharacterRef;
    actual_character:   PlanetaryCharacterRef;
}

export interface RootItem {
    eve_type_id:                number;
    eve_type_name:              string;
    quantity:                   number;
    target_unit_price?:         string | null;
    target_estimated_margin?:   string | null;
}

export interface IndustryOrder {
    id:                 number;
    created_at:         Date;
    needed_by:          Date;
    fulfilled_at:       Date | null;
    public_short_code:  string;
    character_id:       number;
    character_name:     string;
    location:           BaseLocation;
    items:              RootItem[];
    assigned_to:        Character[];
}

export const freight_contract_statuses = [ 'outstanding', 'in_progress', 'finished'  ] as const
export type FreightContractStatus = typeof freight_contract_statuses[number]

export interface FreightContract {
    contract_id:                    number;
    status:                         FreightContractStatus;
    start_location_name:            string;
    end_location_name:              string;
    volume:                         number;
    collateral:                     number;
    reward:                         number;
    date_issued:                    Date;
    date_completed:                 Date | null;
    issuer_id:                      number;
    issuer_character_name:          string;
    completed_by_id:                number;
    completed_by_character_name:    string | null;
}

export interface SpaceTruckerStatistics {
    primary_character_id:       number;
    primary_character_name:     string;
    completed_contracts_count:  number;
}

export const blueprint_owner_entity = [ 'character', 'corporation'  ] as const
export type BlueprintOwnerEntity = typeof blueprint_owner_entity[number]

export const blueprint_location_flag = [ 'Hangar', 'Cargo', 'AssetSafety', 'FleetHangar', 'Deliveries', 'CorpSAG'  ] as const
export type BlueprintLocationFlag = typeof blueprint_location_flag[number]

export interface BlueprintOwner {
    entity_id:              number;
    entity_type:            BlueprintOwnerEntity;
    primary_character_id:   number;
}

export interface Blueprint {
    item_id:                number;
    type_id:                number;
    blueprint_name:         string;
    type_name:              string;
    location_id:            number;
    location_flag:          BlueprintLocationFlag;
    material_efficiency:    number;
    time_efficiency:        number;
    runs:                   number;
    owner:                  BlueprintOwner;
}

export type BlueprintIndustryJobSource = 'character' | 'corporation'

export interface BlueprintIndustryJob {
    job_id:                 number;
    source:                 BlueprintIndustryJobSource;
    activity_id:            number;
    blueprint_type_id:      number;
    status:                 string;
    installer_id:           number;
    start_date:             string;
    end_date:               string;
    completed_date:         string | null;
    duration:               number;
    runs:                   number;
    licensed_runs:          number;
    cost:                   string | null;
    location_id:            number;
    output_location_id:     number;
    blueprint_location_id:  number;
    facility_id:            number;
    character_id:           number | null;
    character_name:         string | null;
    corporation_id:         number | null;
    corporation_name:       string | null;
}

export interface BlueprintDetail extends Blueprint {
    quantity:               number;
    is_original:            boolean;
    current_jobs:           BlueprintIndustryJob[];
    historical_jobs:        BlueprintIndustryJob[];
}

export interface FittingMarketData {
    fitting_id:             number;
    fitting_name:           string
    ship_id:                number;
    ship_name:              string;
    role:                   'primary' | 'secondary' | 'support';
    expectation_quantity:   number | null;
    current_quantity:       number;
    doctrine_name?:         string;
    eft?:                   string;
}

export interface DoctrineMarketData {
    doctrine_id:        number;
    doctrine_name:      string;
    fittings:           FittingMarketData[];
}

export interface LocationMarketData {
    location_id:        number;
    location_name:      string;
    solar_system_name:  string;
    short_name:         string;
    doctrines:          DoctrineMarketData[];
}

export interface LocationFittingExpectation {
    fitting_id:         number;
    fitting_name:       string;
    expectation_id:     number;
    quantity:           number;
}

export interface LocationExpectations {
    location_id:            number;
    location_name:          string;
    solar_system_name:      string;
    short_name:             string;
    expectations:           LocationFittingExpectation[];
}

export interface SellOrderItem {
    item_name:              string;
    type_id:                number | null;
    category_id:            number | null;
    category_name:          string;
    group_id:               number | null;
    group_name:             string;
    expected_quantity:      number;
    current_quantity:       number;
    fulfilled:              boolean;
    issuer_ids:             number[];
    current_lowest_price:   number | null;
    baseline_price:         number | null;
    baseline_sell_price:    number | null;
    baseline_buy_price:     number | null;
    baseline_split_price:   number | null;
}

export interface SellOrderLocation {
    location_id:        number;
    location_name:      string;
    short_name:         string;
    is_price_baseline:  boolean;
    items:              SellOrderItem[];
}

export interface OrderAssignmentsBreakdownItem {
    name:                   string;
    type_id:                number;
    quantity:               number;
    source:                 string;
    depth:                  number;
    children:               OrderAssignmentsBreakdownItem[],
    industry_product_id:    number;
}

export interface OrderAssignmentsBreakdown {
    character_id:       number;
    character_name:     string;
    quantity:           number;
    breakdown:          OrderAssignmentsBreakdownItem;
}

export interface OrderAssignment {
    id:                         number;
    character_id:               number;
    character_name:             string;
    quantity:                   number;
    target_unit_price:          number | null;
    target_estimated_margin:    number | null;
    delivered_at:               Date | null;
}

export interface RootSingleItem {
    id:                             number;
    eve_type_id:                    number;
    eve_type_name:                  string;
    quantity:                       number;
    unassigned_quantity:            number;
    self_assign_maximum:            number | null;
    self_assign_window_ends_at:     Date;
    target_unit_price:              string | null,
    target_estimated_margin:        string | null,
    assignments:                    OrderAssignment[];
}

export interface IndustrySingleOrder {
    id:                 number;
    created_at:         Date;
    needed_by:          Date;
    fulfilled_at:       Date | null;
    public_short_code:  string;
    contract_to:        string;
    character_id:       number;
    character_name:     string;
    location:           BaseLocation;
    items:              RootSingleItem[];
}

export interface FleetMetrics {
    fleet_id:           number;
    members:            number;
    time_region:        string;
    location_name:      string;
    status:             string;
    fc_corp_name:       string;
    corporation_id:     number | null;
    corporation_name:   string | null;
    audience_name:      string;
}

export interface FleetCommanderMetrics {
    user_id:                    number;
    primary_character_id:       number;
    primary_character_name:     string;
    corporation_id:             number | null;
    corporation_name:           string | null;
    fleet_count:                number;
}

export interface CandidateFleetCommander {
    character_id:           number;
    character_name:         string;
    corporation_id:        number;
    corporation_name:       string;
}

export interface CandidateFleet {
    id:                         number;
    type:                       string;
    start_time:                 Date;
    objective:                  string;
    audience:                   string;
    fleet_commander:            CandidateFleetCommander;
}

export interface EVEType {
    id:     number;
    name:   string;
}

export interface EVEGroup {
    id:     number;
    name:   string;
}

export interface EVECAtegory {
    id:     number;
    name:   string;
}

export interface SRPCurrentAmount {
    id:             number;
    program_id:     number;
    srp_value:      number;
    created_at:     string;
}

export interface SRPProgram {
    id:                 number;
    eve_type:           EVEType;
    eve_group:          EVEGroup;
    eve_category:       EVECAtegory;
    current_amount:     SRPCurrentAmount;
}

export interface KillmailResolve {
    killmail_time:                  Date;
    killmail_id:                    number;
    victim_character_id:            number;
    victim_character_name:          string;
    ship_type_id:                   number;
    ship_name:                      string;
    candidate_fleets:               CandidateFleet[];
}

export interface SRPStatsOverview {
    pending_requests:           number;
    pending_total:              number;
    average_response_days:      number;
}

export interface SRPStatsHistoryRequests {
    total:      number;
    approved:   number;
    rejected:   number;
}

export interface SRPStatsHistoryAmounts {
    total:      number;
    approved:   number;
    rejected:   number;
}

export interface SRPStatsHistoryGroup {
    group_name:     string,
    group_id:       number;
    total:          number;
    approved:       number;
    rejected:       number;
}

export interface SRPStatsHistoryType {
    type_name:  string,
    type_id:    number;
    total:      number;
    approved:   number;
    rejected:   number;
}

export interface SRPStatsHistory {
    requests:   SRPStatsHistoryRequests;
    amounts:    SRPStatsHistoryAmounts;
    groups:     SRPStatsHistoryGroup[];
    types:      SRPStatsHistoryType[];
}

export interface OnboardingStatusResponse {
    program_type:           string;
    current_version:        string;
    acknowledged_version:   string | null;
    is_current:             boolean;
}