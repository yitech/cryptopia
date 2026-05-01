export type Visibility = 'public' | 'team';

export interface Me {
  authenticated: boolean;
  username: string | null;
  email: string | null;
  name: string | null;
  groups: string[];
  authelia_url: string;
}

export interface UserPublic {
  id: number;
  username: string;
  email: string;
  display_name: string;
}

export interface NotebookSummary {
  id: string;
  slug: string;
  title: string;
  description: string;
  visibility: Visibility;
  allowed_groups: string[];
  owner: UserPublic;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  published_version: number | null;
}

export interface NotebookDetail extends NotebookSummary {
  can_edit: boolean;
  can_run: boolean;
  is_published: boolean;
}

export interface NotebookVersionInfo {
  version: number;
  content_hash: string;
  published_at: string;
  published_by: number;
}

export interface NotebookCreate {
  title: string;
  slug?: string;
  description?: string;
  visibility?: Visibility;
  allowed_groups?: string[];
}

export interface NotebookUpdate {
  title?: string;
  description?: string;
  visibility?: Visibility;
  allowed_groups?: string[];
}

export interface PublishResponse {
  notebook_id: string;
  version: number;
  published_at: string;
  static_url: string | null;
  run_url: string;
}
