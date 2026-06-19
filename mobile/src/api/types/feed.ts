export interface ApiFeedEventItem {
  id: string;
  kind: string;
  occurred_at: string;
  title: string;
  subheader: string;
  preview: string;
  body: string;
  accent: string;
  payload: Record<string, unknown>;
}

export interface ApiFeedListResponse {
  items: ApiFeedEventItem[];
  next_cursor: string | null;
}
