export interface CharacterBasic {
  character_id: number;
  character_name: string;
}

export interface PostListUI {
  post_id: number;
  title: string;
  state: string;
  slug: string;
  date_posted: Date;
  user_id: number;
  author: CharacterBasic;
  tags: string[];
  image?: string;
}

export interface PostUI extends PostListUI {
  excerpt: string;
  content: string;
}
