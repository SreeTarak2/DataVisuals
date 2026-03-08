# DataSage Chat Page: Design Review & Improvement Recommendations

This document analyzes the DataSage chat experience (frontend + backend), compares it with top AI/data tools, and suggests concrete improvements.

---

## 1. Current Architecture Summary

### Backend
- **Transport**: WebSocket (`/api/ws/chat`) for streaming; HTTP POST (`/datasets/{id}/chat`) as fallback.
- **Streaming**: Token-by-token streaming via `process_chat_message_streaming()`; supports chart events and `done` with `conversationId`.
- **Modes**: HTTP supports `learning`, `quick`, `deep`, `forecast`; WebSocket uses default (learning) and does not expose mode in payload.
- **Rate limiting**: Redis-backed (or in-memory fallback); 30 messages/min, 5 connections per user.
- **Conversations**: Paginated fetch (`get_conversation_page`), archive at 400 messages, delete supported.
- **Security**: Token in WebSocket query param; intent guardrails and input sanitization; audit logging.

### Frontend
- **State**: Zustand `chatStore` with persisted conversations; streaming state (`streamingContent`, `isStreaming`).
- **UI**: Single full-page chat with dataset requirement; starter suggestions when empty; message list with user (right) / AI (left + avatar); inline charts, SQL in `<details>`, follow-up suggestion cards; edit/rerun/copy on user messages.
- **Input**: Fixed bottom composer (glass gradient), textarea with Enter to send / Shift+Enter newline; Plus button (no action yet).
- **History**: Modal with search, delete, smart titles from first user message; no sidebar thread list on main chat page.

---

## 2. Comparison with Top Tools

| Aspect | DataSage (current) | ChatGPT / Claude | Perplexity | Hex / Noteable (data) |
|--------|--------------------|------------------|------------|------------------------|
| **Streaming** | ✅ WebSocket token stream | ✅ SSE/streaming | ✅ Streaming | ✅ Streaming |
| **Stop generation** | ❌ No cancel button | ✅ Stop button | ✅ Stop | ✅ Stop |
| **Mode selection** | ❌ WS ignores mode; HTTP has mode | ✅ Model/mode in UI | ✅ Focus (e.g. Academic) | N/A or minimal |
| **Thread list** | Modal only | Sidebar + modal | Tabs / history | Sidebar or project threads |
| **Composer** | Single line hint | Multi-line, attach files | Multi-line, attach | Multi-line, attach data/code |
| **Copy / Regenerate** | ✅ Copy; ✅ Rerun; ✅ Edit | ✅ Copy; ✅ Regenerate; ✅ Edit | ✅ Copy; ✅ New search | ✅ Copy; rerun cell/query |
| **Charts in chat** | ✅ Inline Plotly | ✅ MCP / code blocks | ✅ Inline | ✅ Native charts + tables |
| **Suggested prompts** | ✅ Start only | ✅ Start + sometimes mid | ✅ Related questions | ✅ Template queries |
| **Connection status** | ❌ Not in main UI | Often subtle | Subtle | Often shown |
| **Rate limit UX** | ✅ Banner + remaining | Soft limits / queue | Clear messaging | Depends on plan |
| **Keyboard** | Enter send, Shift+Enter newline | Same | Same | Same + shortcuts |
| **Accessibility** | Partial (ARIA on errors) | Good (live regions) | Good | Varies |
| **Mobile** | Responsive but dense | Optimized | Optimized | Often desktop-first |

---

## 3. Strengths of Your Current Design

1. **Streaming + fallback**: WebSocket streaming with HTTP fallback and conversation ID migration (temp → backend ID) is solid.
2. **Data-specific UX**: Dataset-scoped chat, inline charts, SQL in collapsible block, follow-up suggestions parsed from content—all align with “analytics assistant” positioning.
3. **Error handling**: Typed errors (rate limit, timeout, unavailable), retry/dismiss, and rate-limit banner improve trust.
4. **Edit & rerun**: Edit user message and truncate + rerun is on par with ChatGPT-style flows.
5. **Backend robustness**: Guardrails, sanitization, QUIS routing, pagination, and archiving show production-minded design.

---

## 4. Recommended Improvements (Prioritized)

### 4.1 High impact, moderate effort

#### A. **Stop / Cancel generation**
- **Gap**: No way to abort a streaming response.
- **Compare**: ChatGPT/Claude/Perplexity all expose “Stop generating.”
- **Backend**: WebSocket: track per-message “cancel” (e.g. `clientMessageId`); on cancel message, stop consuming the async generator and send `done` (or `cancelled`) so client can finalize. HTTP: support `AbortController`-style cancellation if you add SSE later; for now, only WS matters.
- **Frontend**: While `isStreaming`, show a “Stop” button (e.g. next to the composer). On click: send WS message `{ type: "cancel", clientMessageId }` and call `cancelStreaming()`; optionally save partial content as the final message so the user keeps what was generated so far.

#### B. **Expose chat mode in UI (and in WebSocket)**
- **Gap**: HTTP has `learning` / `quick` / `deep` / `forecast`; WebSocket ignores mode.
- **Compare**: ChatGPT/Claude expose model/mode; Perplexity exposes focus.
- **Backend**: Add optional `mode` to WebSocket payload; pass through to `process_chat_message_streaming` (and non-streaming path) and use it the same way as HTTP.
- **Frontend**: In composer area or header, add a compact mode selector (dropdown or segmented control): “Quick”, “Learning”, “Deep”, “Forecast” with short tooltips. Store last-used mode in `chatStore` or localStorage and send with each message.

#### C. **Connection status in main chat view**
- **Gap**: `ConnectionStatus` exists in `ChatErrorDisplay.jsx` but is not rendered on the main chat page.
- **Compare**: Many products show a small “Live” / “Reconnecting” / “Offline” indicator.
- **Frontend**: In the chat header (e.g. top-right near “New Chat” / “History”), render `<ConnectionStatus isConnected={isConnected} isReconnecting={isConnecting} />`. Use `isConnecting` from `useWebSocket` so “Reconnecting…” is visible after drops.

#### D. **Use Plus button in composer**
- **Gap**: Plus button in the composer has no action.
- **Compare**: Plus often opens “attach file”, “use template”, or “new chat”.
- **Options**: (1) New chat (same dataset), (2) Attach a CSV/snippet (if you add attachment support later), (3) Open a “templates” or “suggested questions” popover. Easiest win: “New chat” that calls `startNewConversation` and clears URL `chatId`, same as the header “New Chat” but closer to the input.

### 4.2 High impact, higher effort

#### E. **Sidebar thread list (optional but strong)**
- **Gap**: Thread list only in modal; switching threads requires opening history.
- **Compare**: ChatGPT/Claude use a persistent sidebar for recent threads.
- **Frontend**: Add a collapsible left sidebar on the chat page (or reuse layout sidebar) showing last N conversations for the current dataset: title (from first user message), date, optional snippet. Click switches conversation (same as modal: set `currentConversationId`, sync dataset, update URL). Keeps “History” modal for search/delete; sidebar for quick switch.

#### F. **Structured suggestions (backend-driven)**
- **Gap**: Follow-ups are parsed from AI text with regex; starter suggestions are static per dataset.
- **Compare**: Top tools often drive suggestions from backend (e.g. “related questions”, “try this”).
- **Backend**: Optional endpoint or extend `done` (or a new event) with `suggested_queries: string[]` (3–5 items). Populate from: template list, last N user queries, or a small LLM call (“suggest 3 follow-ups to this answer”).
- **Frontend**: Prefer rendering `suggested_queries` from the backend when present; fall back to current regex-based “Explore further” when absent. Use same click handler as today (send as new user message).

#### G. **Regenerate last AI response**
- **Gap**: User can “Rerun” a user message (edit then rerun exists); no one-click “Regenerate” for the last AI reply.
- **Compare**: ChatGPT/Claude “Regenerate” is a primary action.
- **Frontend**: On the last AI message in the thread, add a “Regenerate” (or “Try again”) button. Behavior: take the previous user message, optionally truncate conversation to that turn, and call the same send path (WS or HTTP) without adding a new user message. Reuse existing `reExecuteQuery`/rerun logic where possible.

### 4.3 Medium impact

#### H. **Keyboard shortcut to focus composer**
- **Compare**: Many apps use Cmd/Ctrl+K or “/” to focus the input.
- **Frontend**: Add a global shortcut (e.g. `useEffect` + `keydown`: when not in an input/textarea, focus the composer textarea). Optionally show a hint “⌘K to focus” near the composer on first visit.

#### I. **Paste handling (e.g. tables)**
- **Gap**: Pasting tables from Excel/Sheets often becomes messy text.
- **Compare**: Some data tools detect table paste and offer “Paste as table” or auto-detect.
- **Frontend**: On paste in composer, detect tab/newline structure; optionally show a small toast “Pasted as table” and wrap in markdown table or a predefined format so the model can interpret it. Low priority unless users ask for it.

#### J. **Conversation title from backend**
- **Gap**: Title is derived on frontend from first user message.
- **Compare**: Backend can store a dedicated `title` (or first_message_summary) for search and consistency.
- **Backend**: When creating or updating a conversation, set `title` (e.g. first 60 chars of first user message, sanitized). Return `title` in conversation list and in `get_conversation`.
- **Frontend**: Prefer `conversation.title` in history modal and sidebar when present; fall back to current `generateTitle(messages, datasetName)`.

#### K. **Accessibility (ARIA live region for streaming)**
- **Compare**: Best practice is a live region for the streaming message so screen readers get updates.
- **Frontend**: Wrap the streaming content (and final AI message) in a div with `aria-live="polite"` and `aria-atomic="false"` so tokens are announced without overwhelming. Keep `role="status"` or similar for the typing indicator.

### 4.4 Lower priority / polish

- **Typing indicator stages**: You have “thinking” / “generating” / “chart”; backend could send a `status` event like `{ type: "status", stage: "thinking" | "generating" | "chart" }` so the UI shows “Creating visualization…” when a chart is about to be sent.
- **Message timestamps**: You already have them; consider “Today, 3:42 PM” vs “Yesterday” for older messages to match common chat UIs.
- **Scroll behavior**: You scroll on message count change; consider also scrolling when the user is near the bottom (e.g. within 100px) so auto-scroll doesn’t fight manual scroll.
- **Rate limit**: Expose “retry after” (e.g. from `retry_after_seconds`) in the banner or error so users know when to retry.

---

## 5. Backend: Actual & Relevant Information

**Does the backend provide actual and relevant information for user queries?**

- **HTTP path**: Yes. Data questions (totals, counts, filters, trends) use **real SQL execution** via `query_executor` and return actual numbers and charts. No hallucination for those.
- **WebSocket (streaming) path**: No. It never runs SQL; the LLM only gets RAG context (schema, sample rows). So streamed answers to questions like "What is total sales?" can be **made up**.

Because the UI prefers WebSocket when connected, most users get ungrounded answers for data questions. **Fix**: In `process_chat_message_streaming`, classify with `query_classifier.needs_sql_execution(query)`; when true, run `query_executor.execute_query`, then stream the pre-computed response token-by-token and attach SQL + chart. See **[CHAT_BACKEND_GROUNDING_AND_UPDATES.md](./CHAT_BACKEND_GROUNDING_AND_UPDATES.md)** for step-by-step updates.

---

## 6. Backend-Specific Notes (UX / Protocol)

- **WebSocket auth**: Token in query param works but is less ideal than sending auth in first message; consider moving to first JSON message with `type: "auth", token: "..."` and rejecting before processing other messages.
- **Streaming protocol**: Typed events (`token`, `chart`, `done`, `error`, `status`) are good. Adding `cancelled` and `suggested_queries` would round out the protocol.
- **Conversation list**: Ensure `GET /chat/conversations` returns conversations for the current user only and includes `dataset_id`/`dataset_name` and `title` if you add it; frontend already uses these for history and dataset context.

---

## 7. Quick Wins Checklist

- [ ] **Stop button**: Show “Stop” while streaming; send cancel over WS; call `cancelStreaming()` and optionally persist partial reply.
- [ ] **Connection status**: Render `<ConnectionStatus />` in chat header.
- [ ] **Plus button**: Wire to “New chat” (or template menu).
- [ ] **Mode in WebSocket**: Add `mode` to WS payload and pass to `process_chat_message_streaming`; add mode selector in UI.
- [ ] **Regenerate**: “Regenerate” on last AI message reuses last user message and resends.
- [ ] **Focus shortcut**: e.g. Cmd/Ctrl+K focuses composer.
- [ ] **Backend title**: Set and return `title` on conversations; use in history/sidebar.

---

## 8. Summary

Your chat stack is strong: streaming, fallback, rate limits, edit/rerun, and data-specific features (charts, SQL, follow-ups) are all in a good place. The largest gaps vs. top tools are **stop generation**, **visible connection status**, **chat mode in the UI (and WS)**, and **better discovery of threads** (sidebar or improved history). Implementing the quick wins above will bring the experience much closer to ChatGPT/Claude/Perplexity-level expectations without large rewrites.
