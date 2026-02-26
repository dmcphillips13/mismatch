"use client";

import { FormEvent, useState } from "react";

/** Minimal citation shape returned by the backend for assistant responses. */
type Citation = {
  id?: string;
  season_id?: string;
};

/** Chat message state used by the thin frontend client. */
type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};

/**
 * Flexible response shape so the UI can handle either:
 * - { message: { content, citations } }
 * - { content, citations }
 */
type ChatResponse = {
  message?: {
    role?: "assistant";
    content?: string;
    citations?: Citation[];
  };
  content?: string;
  citations?: Citation[];
};

/**
 * Thin chat UI:
 * - keeps local message state
 * - forwards conversation to /api/chat
 * - renders assistant citations when present
 */
export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Sends the current conversation to the Next.js API proxy and appends the assistant reply. */
  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const nextUserMessage: ChatMessage = { role: "user", content: trimmed };
    const nextMessages = [...messages, nextUserMessage];

    setMessages(nextMessages);
    setInput("");
    setError(null);
    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: nextMessages.map(({ role, content }) => ({ role, content })),
        }),
      });

      if (!response.ok) {
        throw new Error("Agent service unavailable");
      }

      const data = (await response.json()) as ChatResponse;

      const assistantContent =
        data.message?.content?.trim() || data.content?.trim() || "I could not generate a response.";
      const assistantCitations = data.message?.citations ?? data.citations;

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: assistantContent,
          citations: assistantCitations,
        },
      ]);
    } catch {
      setError("The chat service is currently unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 720, margin: "0 auto", padding: "2rem" }}>
      <h1>Mismatch Chat</h1>

      <div style={{ marginBottom: "1rem" }}>
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} style={{ marginBottom: "1rem" }}>
            <strong>{message.role === "user" ? "You" : "Assistant"}:</strong>
            <p style={{ margin: "0.25rem 0" }}>{message.content}</p>

            {message.role === "assistant" && message.citations && message.citations.length > 0 ? (
              <ul style={{ marginTop: "0.25rem" }}>
                {message.citations.map((citation, citationIndex) => (
                  <li key={`${index}-${citationIndex}`}>
                    id: {citation.id ?? "n/a"}
                    {citation.season_id ? ` | season_id: ${citation.season_id}` : ""}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </div>

      {error ? <p style={{ color: "crimson" }}>{error}</p> : null}
      {loading ? <p>Loading...</p> : null}

      <form onSubmit={onSubmit}>
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about mismatch opportunities..."
          disabled={loading}
          style={{ width: "100%", marginBottom: "0.5rem" }}
        />
        <button type="submit" disabled={loading || input.trim().length === 0}>
          Send
        </button>
      </form>
    </main>
  );
}
