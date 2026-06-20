export interface ApiPostListItem {
  post_id: number;
  state: string;
  title: string;
  seo_description: string;
  slug: string;
  image: string;
  date_posted: string;
  user_id: number;
  author_character_id: number;
  author_character_name: string;
  tag_ids: number[];
}

export interface ApiPostDetail extends ApiPostListItem {
  content: string;
}

export interface ApiTag {
  tag_id: number;
  tag: string;
}

export interface ApiFleetTracking {
  id: number;
  start_time: string;
  end_time?: string | null;
  is_registered: boolean;
}

export interface ApiFleet {
  id: number;
  type: 'strategic' | 'non_strategic' | 'training';
  audience: string;
  description: string;
  objective?: string | null;
  start_time?: string | null;
  fleet_commander: number;
  doctrine_id?: number | null;
  location: string;
  disable_motd: boolean;
  status?: string | null;
  aar_link?: string | null;
  tracking?: ApiFleetTracking | null;
}

export type FleetFilter = 'active' | 'upcoming' | 'recent';

export interface ApiFitting {
  fitting_id: number;
  fitting_name: string;
  role: string;
}

export interface ApiDoctrine {
  id: number;
  name: string;
  type: string;
  description: string;
  primary_fittings: ApiFitting[];
  secondary_fittings: ApiFitting[];
  support_fittings: ApiFitting[];
}

export interface ApiEveCharacterProfile {
  character_id: number;
  character_name: string;
}

export interface ApiUserProfile {
  user_id: number;
  username: string;
  eve_character_profile?: ApiEveCharacterProfile | null;
}
