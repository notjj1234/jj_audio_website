export type JobStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";
export type JobKind = "tab" | "isolate";

export type JobResponse = {
  id: string;
  status: JobStatus;
  kind: JobKind;
  stage: string;
  message: string;
  error: string | null;
  artifacts: Record<string, string>;
};

const TOKEN_KEY = "att_access_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function api<T>(
  path: string,
  init: RequestInit = {},
  auth = true
): Promise<T> {
  const headers = new Headers(init.headers);
  if (auth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers, credentials: "include" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function login(email: string, password: string): Promise<{ email: string }> {
  const data = await api<{ access_token: string; email: string }>(
    "/v1/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
    false
  );
  setAccessToken(data.access_token);
  return { email: data.email };
}

export async function logout(): Promise<void> {
  try {
    await api("/v1/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}

export async function me(): Promise<{ id: string; email: string }> {
  return api("/v1/auth/me");
}

export async function uploadAudio(file: File): Promise<{ upload_id: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  return api("/v1/uploads/audio", { method: "POST", body: form });
}

export async function createTabJob(body: Record<string, unknown>): Promise<JobResponse> {
  return api("/v1/jobs", { method: "POST", body: JSON.stringify(body) });
}

export async function createIsolateJob(body: Record<string, unknown>): Promise<JobResponse> {
  return api("/v1/isolate/jobs", { method: "POST", body: JSON.stringify(body) });
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return api(`/v1/jobs/${jobId}`);
}

export async function cancelJob(jobId: string): Promise<JobResponse> {
  return api(`/v1/jobs/${jobId}/cancel`, { method: "POST" });
}

export type ProgressHandler = (job: JobResponse) => void;

/** WebSocket progress with 2s polling fallback. */
export function watchJob(jobId: string, onUpdate: ProgressHandler): () => void {
  let stopped = false;
  let ws: WebSocket | null = null;
  let pollTimer: number | null = null;

  const poll = async () => {
    if (stopped) return;
    try {
      const job = await getJob(jobId);
      onUpdate(job);
      if (["succeeded", "failed", "cancelled"].includes(job.status)) {
        stop();
        return;
      }
    } catch {
      /* keep polling */
    }
    pollTimer = window.setTimeout(poll, 2000);
  };

  const token = getAccessToken();
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const qs = token ? `?access_token=${encodeURIComponent(token)}` : "";
  try {
    ws = new WebSocket(`${proto}://${location.host}/v1/jobs/${jobId}/ws${qs}`);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "heartbeat") return;
        onUpdate(data as JobResponse);
        if (["succeeded", "failed", "cancelled"].includes(data.status)) stop();
      } catch {
        /* */
      }
    };
    ws.onerror = () => {
      /* fall through to poll */
    };
    ws.onclose = () => {
      if (!stopped) void poll();
    };
  } catch {
    void poll();
  }

  // Always start polling as mobile fallback
  pollTimer = window.setTimeout(poll, 2000);

  function stop() {
    stopped = true;
    if (ws) {
      try {
        ws.close();
      } catch {
        /* */
      }
      ws = null;
    }
    if (pollTimer !== null) window.clearTimeout(pollTimer);
  }

  return stop;
}
