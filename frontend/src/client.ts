import createClient from "openapi-fetch";
import type { paths, components } from "./generated/api";

export type Current = components["schemas"]["CurrentResponse"];
export type Preview = components["schemas"]["PreviewResponse"];
export type CommitRequest = components["schemas"]["CommitRequest"];
export type Command = components["schemas"]["CommandResponse"];

function generation(value: number) {
  if (!Number.isSafeInteger(value) || value < 0) throw new ClientError("request_failed");
}

export class ClientError extends Error {
  constructor(readonly code: "session_unavailable" | "request_failed", readonly status?: number) {
    super(code);
  }
}

/** Caller supplies only a trusted local launcher origin. Session exists in this closure. */
export async function connect(origin = window.location.origin) {
  const url = new URL(origin);
  if (url.origin !== origin || url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port) {
    throw new ClientError("session_unavailable");
  }
  const response = await fetch(`${origin}/session`, {
    method: "POST", headers: { "X-Prosper-Bootstrap": "1" }, credentials: "omit", cache: "no-store",
  });
  if (!response.ok) throw new ClientError("session_unavailable", response.status);
  const session: unknown = await response.json();
  if (typeof session !== "object" || session === null || !("token" in session) ||
      typeof session.token !== "string" || session.token.length < 43 ||
      !("token_type" in session) || session.token_type !== "Bearer") {
    throw new ClientError("session_unavailable");
  }
  const client = createClient<paths>({
    baseUrl: origin, credentials: "omit", cache: "no-store",
    headers: { Authorization: `Bearer ${session.token}` },
  });
  return {
    async current(): Promise<Current> {
      const result = await client.GET("/api/v1/current");
      if (!result.data) throw new ClientError("request_failed", result.response.status);
      generation(result.data.generation);
      return result.data;
    },
    async stage(raw: Uint8Array<ArrayBuffer>): Promise<Preview> {
      const result = await client.POST("/api/v1/previews", {
        body: raw,
        bodySerializer: (bytes) => bytes,
        headers: { "Content-Type": "application/octet-stream" },
      });
      if (!result.data) throw new ClientError("request_failed", result.response.status);
      return result.data;
    },
    async preview(identity: string): Promise<Preview> {
      const result = await client.GET("/api/v1/previews/{identity}", {
        params: { path: { identity } },
      });
      if (!result.data) throw new ClientError("request_failed", result.response.status);
      return result.data;
    },
    async commit(body: CommitRequest): Promise<Command> {
      generation(body.expected_generation);
      const result = await client.POST("/api/v1/commit", { body });
      if (!result.data) throw new ClientError("request_failed", result.response.status);
      generation(result.data.generation);
      generation(result.data.expected_generation);
      if (result.data.activation_generation !== null) generation(result.data.activation_generation);
      if (result.data.command_key !== body.command_key || result.data.preview_sha256 !== body.preview_sha256 ||
          result.data.expected_generation !== body.expected_generation) throw new ClientError("request_failed");
      return result.data;
    },
    async reject(identity: string): Promise<Preview> {
      const result = await client.POST("/api/v1/reject", {
        body: { schema_version: "synthetic-import-api-v1", preview_sha256: identity },
      });
      if (!result.data) throw new ClientError("request_failed", result.response.status);
      return result.data;
    },
  };
}
