export type Locales = 'en'
export type ButtonColors = 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green' | 'transparent'
export type ButtonSizes = 'sm' | 'lg'
export type BadgeColors = 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green' | 'fleet-yellow'
export type TagColors = 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green'
export type FlexInlineJustify = 'center' | 'flex-start' | 'flex-end' | 'space-around' | 'space-between'
export type EvEImageServiceSize = 32 | 64 | 128 | 256 | 512 | 1024
export type StructureSlots = 'High Power Slots' | 'Medium Power Slots' | 'Low Power Slots' | 'Rig Slots' | 'Service Slots' | 'Charges'
export type CharacterRaces = 'caldari' | 'minmatar' | 'amarr' | 'gallente' | 'unknown'
export type MetaGroupColors = 'tech-i' | 'tech-ii' | 'storyline' | 'faction' | 'officer' | 'deadspace' | 'tech-iii'
                            | 'abyssal' | 'premium' | 'limited-time' | 'structure-faction' | 'structure-tech-ii' | 'structure-tech-i'

export type spaces = '0' | '1px' | '2px' | 'var(--component-block-gap)' | 'var(--space-3xs)' | 'var(--space-2xs)' | 'var(--space-xs)' 
| 'var(--space-s)' | 'var(--space-m)' | 'var(--space-l)' | 'var(--space-xl)' | 'var(--space-2xl)' | 'var(--space-3xl)' 
| 'var(--space-3xs-2xs)' | 'var(--space-2xs-xs)' | 'var(--space-xs-s)' | 'var(--space-s-m)' | 'var(--space-m-l)' 
| 'var(--space-l-xl)' | 'var(--space-xl-2xl)' | 'var(--space-2xl-3xl)' | 'var(--space-s-l)'

export function is_of_structure_slots_type(value: string): value is StructureSlots {
    return [ 'High Power Slots', 'Medium Power Slots', 'Low Power Slots', 'Rig Slots', 'Service Slots', 'Charges' ].includes(value);
}

export interface FleetItem {
    id:                             number;
    fleet_commander_name:           string;
    fleet_commander_portrait:       string;
    fleet_commander_portrait_small: string;
    type:                           string;
    audience:                       string;
    eve_time:                       string;
    href:                           string;
}

export interface FittingItem {
    fitting_name:   string;
    fitting_type:   string;
    ship_type:      string;
    ship_name:      string;
    ship_id:        number;
    id:             number;
}

export interface DoctrineItemObj {
    doctrine_name:  string;
    href:           string;
    id:             number;
    tags:           Tag[];
    fits:           Fit[];
}

export interface Fit {
    image: string;
    alt:   string;
    name:  string;
    href?: string;
}

export interface Tag {
    name:        string;
    color:       string;
    description: string;
}

/*export interface Slot {
    name:    string;
    modules: Module[];
}

export interface Module {
    image?: string;
    name:   string;
    amount: number;
}*/

export interface ItemListProps {
    title:  string;
    items:  ItemListItem[];
}

export interface ItemListItem {
    image:  string;
    name:   string;
    alt:    string;
}

export interface FitDetails {
    name:           string;
    image:          string;
    alt:            string;
    description:    string;
    fitting_eft:    string;
}

export interface FittingParsed {
    [propName: string]: Fittable[];
}

export interface Fittable {
    name:   string;
    amount: number;
    image:  string;
}

export interface StructureFittingGroups {
    name:       string;
    fittables:  StructureFittable[];
}

export interface StructureFittable {
    name:   string;
    amount: number;
    image:  string;
    slot:   StructureSlots;
}

export interface FittingGroups {
    name:       string;
    fittables:  Fittable[];
}

export interface StructureListItem {
    timer:        string;
    id:           number;
    type:         string;
    name:         string;
    system:       string;
    region:       string;
    alliance_id:  number;
    alliance:     string;
    href?:        string;
}

export interface Structure {
    timer:          string;
    id:             number;
    type:           string;
    name:           string;
    system:         string;
    region:         string;
    constellation:  string;
    alliance_id:    number;
    alliance:       string;
    fitting?:       string;
}

export interface FleetCompositionObj {
    ship_name: string;
    ship_id:   number;
    fitting:   string;
    pilots:    Pilot[];
}

export interface Pilot {
    name: string;
    id:   number;
}

export interface FreightCalculation {
    name:             string;
    ship_to:          string;
    pick_up_station:  string;
    reward:           number;
    collateral:       number;
    expiration:       string;
    days_to_complete: string;
}

export type roles = 'pilot' | 'director' | 'administrator'

export interface PersonaListData {
    id:             number;
    name:           string;
    roles:          roles[];
    character_id:   number;
}

export interface CorporationListData {
    id:             number;
    name:           string;
    members_count:  number;
    corporation_id: number;
}

export interface AllianceListData {
    id:             number;
    name:           string;
    members_count:  number;
    alliance_id:    number;
}

export interface Alert {
    title:          string;
    content:        string;
    partial?:       string;
    hx?:            HXDialogOptions;
}

export type RequestType = 'get' | 'post' | 'put' | 'patch' | 'delete'

export interface HXDialogOptions {
    method?:    RequestType;
    url?:       string;
    target?:    string;
    swap?:      string;
}

export interface PageCoverOptions {
    image:          string;
    image_990:      string;
    alt?:           string;
    animated?:      boolean;
    scrollable?:    boolean;
    overlay?:       boolean;
}

export interface PageVideoOptions {
    id:        string;
    title:     string;
    credits?:  VideoWidgetCredits;
}

export interface ViewportComponents {   
	alert_dialog?:			boolean;
	confirm_dialog?:		boolean;
	modal?:		            boolean;
	personas_finder?:		boolean;
	corporation_finder?:	boolean;
	alliance_finder?:		boolean;
}

export interface GroupListObject {
    id:             number;
    name:           string;
    description:    string;
    image_url:      string;
    status:         string;
    members:        number;
}

export type GroupRequestType = 'join' | 'leave'

export interface ApplicationOld {
    id:                     number;
    applied_corporation:    number;
    character_name:         string;
    corporation_id:         number;
    corporation_name:       string;
    description:            string;
    status:                 CorporationStatusType;
}

export interface CorporationApplications {
    corporation_id:         number;
    corporation_name:       string;
    applications:           ApplicationBasic[];
}

export interface ApplicationBasic {
    id:                     number;
    applied_corporation:    number;
    character_id:           number;
    character_name:         string;
    corporation_id:         number;
    corporation_name:       string;
    status:                 CorporationStatusType;
}

export interface Application {
    id:                     number;
    applied_corporation:    number;
    character_name:         string;
    corporation_id:         number;
    corporation_name:       string;
    description:            string;
    status:                 CorporationStatusType;
}

export interface ApplicationDetail {
    id:                     number;
    applied_corporation:    number;
    character_id:           number;
    character_name:         string;
    corporation_id:         number;
    corporation_name:       string;
    description:            string;
    created_at:             Date;
    updated_at:             Date;
    status:                 CorporationStatusType;
    alts:                   CharacterBasic[];
}

export interface CorporationMembers {
    corporation_id:     number;
    corporation_name:   string;
    type:               CorporationType;
    members:            CharacterKind[];
    active:             boolean;
}

export interface MainCharacters {
    character_id:       number;
    character_name:     string;
    corporation_id:     number;
    corporation_name:   string;
    registered:         boolean;
    alts:               CharacterKind[];
}

export interface CharacterKind {
    character_id:       number;
    character_name:     string;
    corporation_id?:    number;
    corporation_name?:  string;
    registered:         boolean;
    is_main:            boolean;
    main_character?:    CharacterBasic;
}

export type GroupStatus = 'available' | 'requested' | 'confirmed' | 'denied' |'error' | 'unauth'
export type CorporationStatusType = 'available' | 'pending' | 'accepted' | 'rejected' |'error' | 'unauth'
export type CorporationType = 'alliance' | 'associate' | 'militia' | 'public'

export interface CorporationObject {
    corporation_id:     number;
    corporation_name:   string;
    alliance_id:        number;
    alliance_name:      string,
    corporation_type:   CorporationType;
    status?:            CorporationStatusType;
}

export interface CorporationBasic {
    id:     number;
    name:   string;
}

export interface GroupRequest {
    id:             number;
    user:           number;
    group:          number;
    approved:       boolean | null;
    approved_by:    number | null;
}

export interface GroupRequestListUI {
    group_id:           number;
    group_name:         string;
    group_image:        string;
    requests:           GroupRequestUI[];
}

export interface GroupRequestUI {
    request_id:         number;
    approved:           null | boolean;
    character_id:       number;
    character_name:     string;
    corporation_id:     number;
    corporation_name:   string;
    group_id:           number;
    group_name:         string;
    group_image:        string;
    description:        string;
}

export interface ErrorRefetchParams {
    partial:    string;
    message:    string;
    delay:      number;
    target?:    string,
}

export interface CharacterBasic {
    character_id:       number;
    character_name:     string;
    corporation?:       CorporationBasic;
}

export type GroupRequestAction = 'accept' | 'deny'

export interface ModalCover {
    image:          string;
    image_990:      string;
    alt?:           string;
    animated?:      boolean;
    scrollable?:    boolean;
    overlay?:       boolean;
}

export type BadgeSize = 'sm' | 'lg'

export interface CorporationBadgeProps {
    id:             number;
    name?:          string;
    size?:          BadgeSize;
    description?:   string;
}

export interface AllianceBadgeProps {
    id:     number;
    name?:  string;
}

export interface CorporationHistoryItem {
    corporation_id:         number;
    membership_time_text?:  string;
}

export type GroupItemType = 'group' | 'team'

export interface GroupItemUI {
    id:             number;
    name:           string;
    description:    string | null;
    image_url:      string | null;
    status?:        GroupStatus;
}

export interface SkillsetUI {
    id:             number;
    name:           string;
    progress:       number;
    missing_skills: SkillsUI[];
}

export interface SkillsUI {
    skill_name:     string;
    skill_level:    number;
}

export interface SkillsetMissingSkillUI {
    skillsets: Skillset;
    character: CharacterBasic;
}

export interface VideoWidgetCredits {
    character_id?:  number;
    character_name: string;
}

export interface AssetsLocationUI {
    location_name: string;
    assets:        AssetUI[];
}

export interface AssetUI {
    id:     number;
    name:   string;
    count:  number;
}

export interface AssetLocationItemUI {
    location_name:  string;
    assets_count:   number;
}

export interface SkillsetsUI {
    character_id:   number;
    character_name: string;
    skillsets:      Skillset[];
}

export interface Skillset {
    name:           string;
    progress:       number;
    missing_skills: MissingSkill[];
}

export interface MissingSkill {
    skill_name:  string;
    skill_level: number;
}

export interface AssetsUI {
    character_id:   number;
    character_name: string;
    locations:      AssetsLocation[];
    location_icons: AssetsLocationIcons[];
}

export interface AssetsLocation {
    location_name:  string;
    assets:         AssetGroup[];
}

export interface AssetsLocationIcons {
    location_name:  string;
    assets:         Asset[];
}

export interface Asset {
    id:     number;
    name:   string;
}

export interface AssetGroup {
    id:     number;
    name:   string;
    count:  number;
}

export interface GroupMembersUI {
    id:             number;
    name:           string;
    description:    string;
    image_url:      string | null,
    members:        MemberUI[];
    officers:       number[];
}

export interface MemberUI {
    user_id?:           number;
    character_id:       number;
    character_name:     string;
    corporation_id:     number;
    corporation_name:   string;
}

export interface SelectOptions {
    value?: string | number;
    label:  string;
}

export interface PageFinderUI {
    slug:           string;
    alt?:           string;
    path:           string;
    icon?:          string;
    description?:   string;
    publish:        boolean;
    permissions?:   Permissions;
}

export interface Permissions {
    group_officer?: boolean;
    team_director?: boolean;
    superuser?:     boolean;
    auth?:          boolean;
    user?:          string[];
}

export type MetaGroupType = 'Tech I' | 'Tech II' | 'Storyline' | 'Faction' | 'Officer' | 'Deadspace' | 'Tech III'
                            | 'Abyssal' | 'Premium' | 'Limited Time' | 'Structure Faction' | 'Structure Tech II' | 'Structure Tech I'

export type ShipsSlots = 'High Slots' | 'Medium Slots' | 'Low Slots' | 'Rig Slots' | 'Subsystem Slots'
export interface Module {
    id:             number;
    name:           string;
    meta_name:      MetaGroupType;
    module_type:    string;
    slot_name:      string;
}

export interface ShipFittingCapabilities {
    high_slots?:        number;
    med_slots?:         number;
    low_slots?:         number;
    rig_slots?:         number;
    subsystem_slots?:   number;
    pg_output?:         number;
    cpu_output?:        number;
    launchers?:         number;
    turrets?:           number;
}

export interface CargoItem {
    id:     number;
    name:   string;
    amount: number;
}

export interface ShipFitting {
    name:               string;
    ship_name:          string;
    capabilities:       ShipFittingCapabilities;
    low_slots?:         Module[];
    med_slots?:         Module[];
    high_slots?:        Module[];
    rig_slots?:         Module[];
    subsystem_slots?:   Module[];
    drones?:            CargoItem[];
    cargohold?:         CargoItem[];
}

export type ShipsMetaType = 'Tech I' | 'Tech II' | 'Faction' | 'Tech III'

export interface ShipInfo {
    name:    string;
    type:    string;
    race:    string;
    meta:    ShipsMetaType;
}

export interface ShipDNA {
    model:  string;
    skin:   string;
    race:   string;
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

export interface DoctrineType {
    id:                 number;
    name:               string;
    type:               DoctrineTypes;
    created_at:         Date;
    updated_at:         Date;
    description:        string;
    primary_fittings:   FittingItem[];
    secondary_fittings: FittingItem[];
    support_fittings:   FittingItem[];
}