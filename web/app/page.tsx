"use client";

import { FormEvent, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Chat message state used by the thin frontend client. */
type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

/** Response shape from the backend /chat endpoint. */
type ChatResponse = {
  answer?: string;
  citations?: Record<string, unknown>[];
  debug?: Record<string, unknown>;
};

/**
 * Thin chat UI:
 * - keeps local message state
 * - forwards conversation to /api/chat
 * - renders assistant response as markdown
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
        data.answer?.trim() || "I could not generate a response.";

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: assistantContent },
      ]);
    } catch {
      setError("The chat service is currently unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <h1 className="header">Mismatch Chat</h1>

      <div className="messages">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={message.role === "user" ? "message-user" : "message-assistant"}
          >
            <span className="message-label">
              {message.role === "user" ? "You" : "Assistant"}
            </span>
            {message.role === "assistant" ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            ) : (
              <p style={{ margin: 0 }}>{message.content}</p>
            )}
          </div>
        ))}
      </div>

      {error ? <p className="error">{error}</p> : null}
      {loading ? <p className="loading">Thinking</p> : null}

      <form onSubmit={onSubmit} className="input-area">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about mismatch opportunities..."
          disabled={loading}
          className="chat-input"
        />
        <button
          type="submit"
          disabled={loading || input.trim().length === 0}
          className="chat-button"
        >
          Send
        </button>
      </form>
    </main>
  );
}
