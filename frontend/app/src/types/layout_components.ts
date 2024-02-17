export type ButtonColors = 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green'
export type ButtonSizes = 'sm' | 'lg'
export type BadgeColors = 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green'
export type TagColors = 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green'
export type FlexInlineJustify = 'center' | 'flex-start' | 'flex-end' | 'space-around' | 'space-between'
export type EvEImageServiceSize = 32 | 64 | 128 | 256 | 512 | 1024
export type StructureSlots = 'High Power Slots' | 'Medium Power Slots' | 'Low Power Slots' | 'Rig Slots' | 'Service Slots' | 'Charges'

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

export interface FitItem {
    image:        string;
    fitting_name: string;
    fitting_type: string;
    ship_type:    string;
    ship_name:    string;
    href:         string;
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

export type RequestType = 'get' | 'post' | 'put' | 'pathc' | 'delete'

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
    credits?:  string;
}

export interface ViewportComponents {   
	alert_dialog?:			boolean;
	confirm_dialog?:		boolean;
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

export interface RequestListObject {
    id:             number;
    type:           GroupRequestType;
    character_name: string;
    character_corp: string;
    character_org:  string;
    group_name:     string;
}