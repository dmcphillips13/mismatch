import { NextResponse } from "next/server";

/** Message shape accepted by this proxy route and forwarded to FastAPI. */
type IncomingMessage = {
  role: string;
  content: string;
};

/** Expected request body for POST /api/chat. */
type ChatRequestBody = {
  messages: IncomingMessage[];
};

const REQUEST_TIMEOUT_MS = 60_000;

function isValidMessage(value: unknown): value is IncomingMessage {
  if (!value || typeof value !== "object") return false;
  const maybe = value as Partial<IncomingMessage>;
  return typeof maybe.role === "string" && typeof maybe.content === "string";
}

/**
 * POST /api/chat
 * Thin server-side proxy to the Python agent backend.
 * - reads NEXT_PUBLIC_AGENT_BASE_URL
 * - applies a 60s timeout
 * - returns a generic error message for upstream failures
 */
export async function POST(request: Request) {
  const baseUrl = process.env.NEXT_PUBLIC_AGENT_BASE_URL;

  if (!baseUrl) {
    return NextResponse.json({ error: "Agent service unavailable" }, { status: 500 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  if (!body || typeof body !== "object" || !Array.isArray((body as { messages?: unknown }).messages)) {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const messages = (body as { messages: unknown[] }).messages;
  if (!messages.every(isValidMessage)) {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const payload: ChatRequestBody = { messages };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const upstream = await fetch(`${baseUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!upstream.ok) {
      return NextResponse.json({ error: "Agent service unavailable" }, { status: 500 });
    }

    const data = await upstream.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Agent service unavailable" }, { status: 500 });
  } finally {
    clearTimeout(timeoutId);
  }
}
