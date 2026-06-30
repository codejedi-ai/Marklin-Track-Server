// --- CMDB ----------------------------------------------------------------
export type CILabel =
  | "Device" | "User" | "App"
  | "Location" | "Department" | "Team" | "OperatingSystem";

export interface GraphNode {
  id: string;
  label: CILabel | string;
  display: string;
  props: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CIRelationship {
  rel: string;
  direction: "in" | "out";
  node: Record<string, unknown>;
}

export interface CIDetail {
  ci: Record<string, unknown>;
  relationships: CIRelationship[];
}

export interface IngestResult {
  source: string;
  detected: string;
  nodes_written: number;
  edges_written: number;
  errors: string[];
}

export interface AskResponse {
  question: string;
  answer: string;
  cypher?: string | null;
  rows: Record<string, unknown>[];
  thoughts?: string[] | null;
  iterations?: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  cypher?: string | null;
  rows?: Record<string, unknown>[] | null;
  thoughts?: string[] | null;
  ts?: string | null;
}

export interface Chat {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ChatSummary {
  id: string;
  title: string;
  message_count: number;
  created_at?: string | null;
  updated_at?: string | null;
}

// --- Tickets (legacy, retained for type completeness) --------------------
export type Status = "New" | "In Progress" | "Resolved";
export type Priority = "Low" | "Medium" | "High";

export interface RelatedCI {
  type: "device" | "user" | "app";
  id: string;
  name?: string | null;
}

export interface Ticket {
  id: string;
  title: string;
  description: string;
  email?: string | null;
  department?: string | null;
  priority: Priority;
  status: Status;
  category?: string | null;
  tags: string[];
  suggested_response?: string | null;
  related_cis: RelatedCI[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface Suggestion {
  category: string;
  tags: string[];
  priority: Priority;
  suggested_response: string;
  related_cis: RelatedCI[];
  grounded: boolean;
}

export interface TicketDraft {
  title: string;
  description: string;
  email: string;
  department: string;
  priority: Priority | "";
  category: string;
  tags: string[];
  suggested_response: string;
  related_cis: RelatedCI[];
}
