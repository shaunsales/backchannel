const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────────────

export interface DashboardData {
  total_stored: number;
  connected_count: number;
  last_sync_ago: string;
  accounts: AccountSummary[];
  recent_runs: RunSummary[];
}

export interface AccountSummary {
  id: string;
  display_name: string;
  service_type: string;
  stored: number;
  last_sync: string;
  status?: string;
}

export interface AccountDetail extends AccountSummary {
  phone: string;
  email: string;
  token_preview: string;
  recent_runs: RunSummary[];
}

export interface RunSummary {
  id: number;
  service_id?: string;
  run_type: string;
  status: string;
  items_fetched: number;
  items_new?: number;
  items_updated?: number;
  duration: string;
  time: string;
  error?: string | null;
}

export interface DocSummary {
  id: number;
  title: string;
  service_id: string;
  preview: string;
  time: string;
}

export interface DocDetail {
  id: number;
  title: string;
  body: string;
  service_id: string;
  source_id: string;
  version: number;
  time: string;
}

export interface MessageItem {
  id: number;
  service_id: string;
  sender: string;
  recipients: string;
  conversation: string;
  body: string;
  source_ts: string;
  time: string;
}

export interface ConversationSummary {
  conversation: string;
  thread_id: string | null;
  service_id: string;
  msg_count: number;
  last_sender: string;
  preview: string;
  time: string;
}

export interface ServiceStats {
  email?: string;
  total_messages: number;
  oldest_date: string | null;
  newest_date: string | null;
  folders: { name: string; count: number }[];
}

export interface SyncResult {
  run_id: number;
  status: string;
  items_fetched: number;
  items_new: number;
  items_updated: number;
  duration: string;
}

// ── API Functions ─────────────────────────────────────────────────────────

export const api = {
  dashboard: () => request<DashboardData>("/dashboard"),

  // Services
  listServices: () => request<AccountSummary[]>("/services"),
  getService: (id: string) => request<AccountDetail>(`/services/${id}`),
  createService: (service_type: string, display_name: string) =>
    request<{ id: string }>("/services", {
      method: "POST",
      body: JSON.stringify({ service_type, display_name }),
    }),
  renameService: (id: string, display_name: string) =>
    request<{ ok: boolean }>(`/services/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ display_name }),
    }),
  deleteService: (id: string) =>
    request<{ ok: boolean }>(`/services/${id}`, { method: "DELETE" }),
  connectService: (id: string, credentials: Record<string, string>) =>
    request<{ ok: boolean }>(`/services/${id}/connect`, {
      method: "POST",
      body: JSON.stringify({ credentials }),
    }),
  disconnectService: (id: string) =>
    request<{ ok: boolean }>(`/services/${id}/disconnect`, { method: "POST" }),
  testService: (id: string) =>
    request<{ ok: boolean; message: string }>(`/services/${id}/test`, { method: "POST" }),
  syncService: (id: string) =>
    request<SyncResult>(`/services/${id}/sync`, { method: "POST" }),
  clearServiceData: (id: string) =>
    request<{ ok: boolean }>(`/services/${id}/clear`, { method: "POST" }),
  getServiceStats: (id: string) =>
    request<ServiceStats>(`/services/${id}/stats`),

  // Documents
  listDocuments: (params?: { q?: string }) => {
    const sp = new URLSearchParams();
    if (params?.q) sp.set("q", params.q);
    const qs = sp.toString();
    return request<DocSummary[]>(`/documents${qs ? `?${qs}` : ""}`);
  },
  getDocument: (id: number) => request<DocDetail>(`/documents/${id}`),

  // Messages & Conversations
  listConversations: (params?: { q?: string; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.q) sp.set("q", params.q);
    if (params?.limit) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return request<ConversationSummary[]>(`/conversations${qs ? `?${qs}` : ""}`);
  },
  getConversation: (name: string, opts?: { service?: string; thread_id?: string }) => {
    const sp = new URLSearchParams();
    if (opts?.service) sp.set("service", opts.service);
    if (opts?.thread_id) sp.set("thread_id", opts.thread_id);
    const qs = sp.toString();
    return request<MessageItem[]>(`/conversations/${encodeURIComponent(name)}${qs ? `?${qs}` : ""}`);
  },
  listMessages: (params?: { q?: string; service?: string; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.q) sp.set("q", params.q);
    if (params?.service) sp.set("service", params.service);
    if (params?.limit) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return request<MessageItem[]>(`/messages${qs ? `?${qs}` : ""}`);
  },

  // History
  getHistory: (limit = 50) => request<RunSummary[]>(`/history?limit=${limit}`),
};
