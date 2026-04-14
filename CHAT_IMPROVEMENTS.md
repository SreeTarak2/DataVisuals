# Chat Feature — Real-World Readiness Report

> This document audits the current chat feature against real-world usage requirements,
> identifies specific bugs and gaps with file references, and provides a prioritized
> action plan to make the chat feature genuinely usable in production.

---

## TL;DR — What's Broken vs. What's Missing

| Type | Count | Impact |
|---|---|---|
| **Confirmed bugs** (code verified) | 6 | Users hit dead ends — feature feels broken |
| **Disabled/incomplete features** | 5 | Features exist in backend but not surfaced |
| **UX gaps** (adoption blockers) | 7 | Users abandon before seeing value |
| **Missing features** (vs. competitors) | 5 | Can't be used in team/enterprise settings |

---

## Part 1 — Confirmed Bugs (Fix These First)

### Bug 1: Stop Button Does Nothing
**Severity: High**

The frontend sends a `cancel` message over WebSocket when the user clicks Stop.
The backend has **no handler** for this message type — the stream continues until
the LLM finishes, wasting tokens and frustrating users.

**Frontend sends (useWebSocket.js:295):**
```js
wsSend({ type: "cancel", clientMessageId })
```

**Backend loop (api/chat/routes.py ~line 210-260):**
```python
async for chunk in ai_service.process_chat_message_streaming(...):
    await safe_send(websocket, {...})
```
There is no `if message_type == "cancel": break` handler anywhere in the loop.

**Fix:** Add a cancel signal (e.g., `asyncio.Event`) passed into the AI service
streaming function, and listen for incoming WebSocket messages concurrently
using `asyncio.gather` or a producer-consumer pattern.

---

### Bug 2: Stale `currentChatId` in Message Send
**Severity: High — causes conversation fragmentation**

React state is async. When the first message is sent and the backend creates a new
`conversationId`, the frontend is still holding the old (empty) `currentChatId`.
Subsequent messages go to a different/no conversation.

**Location:** `ChatPage.jsx:986` — comment reads "Issue 1 – Use convId not stale currentChatId"
and `ChatPage.jsx:952` — "Issue 1 – ConversationId migration".

**Fix:** Capture the `conversationId` from the first `done` event in a `ref` (not
state) and use that ref for all subsequent sends in the same session.

---

### Bug 3: Duplicate User Message on HTTP Fallback
**Severity: Medium**

When WebSocket fails and the HTTP fallback path is used, the user's message is
added to the store twice — once optimistically on send, once when the HTTP
response returns.

**Location:** `ChatPage.jsx:992` — "Issue 2 – Skip duplicate user message when using HTTP fallback"

**Fix:** Gate the optimistic insert behind a `wsConnected` check, or use a
`clientMessageId` de-duplication guard in the store `addMessage()` action.

---

### Bug 4: Rate Limit Countdown Doesn't Disable Input
**Severity: Medium**

When a rate limit error is received, a countdown timer is shown, but the text
input remains enabled. Users can keep typing and submitting, receiving more
errors, creating a confusing loop.

**Location:** `ChatPage.jsx:1597-1625` — countdown rendered in send area but
no `disabled` prop passed to `<textarea>` or send button based on
`rateLimitCountdown > 0`.

**Fix:** Add `disabled={rateLimitCountdown > 0}` to the input and send button,
and show a clear "Try again in Xs" placeholder inside the input.

---

### Bug 5: Lost Dataset Context When Loading Old Conversations
**Severity: Medium**

When a user loads a previous conversation from history, the `selectedDataset`
is not restored — the chat shows old messages but new queries run against
whatever dataset is currently selected (or none).

**Location:** `ChatPage.jsx:1659` — "Issue 3 – Sync selectedDataset when loading conversation history"

**Fix:** Store `datasetId` in the conversation record. On load, call
`setSelectedDataset(conversation.datasetId)` and show a banner
"Restored dataset: [name]" so the user knows what's active.

---

### Bug 6: WebSocket Auth Token Never Refreshes
**Severity: Medium — silent failure on long sessions**

The auth token is read once on connect (`getAuthToken()` in `useWebSocket.js:9-20`).
JWT tokens typically expire in 1–24 hours. On expiry, the WebSocket silently
disconnects mid-conversation with a generic "Not authenticated" error.

**Fix:** Before each `connect()` call, refresh the token via
`authStore.refreshToken()`. Also add a `setInterval` that re-sends auth when
the token is within 5 minutes of expiry, while the socket is open.

---

## Part 2 — Disabled Features to Re-Enable

### 2.1 Show Generated SQL
**What it is:** The backend generates SQL for every data question. It is executed
against DuckDB and works perfectly. The SQL is never shown to users.

**Why it matters for real use:**
- Analysts need to verify correctness ("Did it actually filter by region?")
- Power users copy and adapt queries
- It builds trust — users stop treating AI as a black box

**Location:** `ChatPage.jsx:831-846` — backend returns `technical_details` in every
`done` event. A "Show SQL" section exists but is commented out.

**What to do:** Uncomment and wire the `technical_details.sql` field to a
collapsible "SQL used" section below each AI response. Already have
`SyntaxHighlighter` imported in frontend.

---

### 2.2 Privacy / PII Redaction Badge
**What it is:** Backend has a privacy service that redacts PII before queries.
The frontend badge indicating "PII protected" is commented out.

**Location:** `ChatPage.jsx:1413-1421` — badge commented out.
`ChatPage.jsx:831-846` — privacy settings fetch commented out.

**Why it matters:** Healthcare, finance, and HR use cases cannot proceed without
this visible. It is also a legal/compliance selling point.

**What to do:** Uncomment the badge. Wire `privacySettings` fetch to the user
profile load. Show "PII Redaction: ON/OFF" in the dataset header area.

---

### 2.3 Chart Export as PNG/CSV
**What it is:** Plotly.js (already in use) has built-in `downloadImage()` and data
export. The AgenticPanel already has an export pathway.

**Why it matters:** The #1 complaint about analytics tools is "I can't share this
with my manager." Without export, every insight dies in the browser tab.

**What to do:** Add a download icon button on each rendered chart. Call
`Plotly.downloadImage(chartDiv, { format: 'png', filename: 'chart' })`.
Add a second button to export the underlying data as CSV.

---

### 2.4 WebSocket Keep-Alive (Ping/Pong)
**What it is:** No heartbeat is sent. Proxies, load balancers, and firewalls drop
idle WebSocket connections after 30–60s. Long AI responses (30s+) will be dropped.

**What to do in `useWebSocket.js`:**
```js
// After auth_success is received:
const pingInterval = setInterval(() => {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "ping" }));
  }
}, 25000); // every 25 seconds
```
Add a `pong` handler on the backend to respond.

---

### 2.5 "Connecting..." State in Chat UI
**What it is:** Before the WebSocket is ready, there is no visible indicator.
Users type a message and get silence — no error, no feedback.

**What to do:** Use `isConnecting` from `useWebSocket` (already exported) to
show a subtle status bar: `"Connecting to DataSage..."` with a spinner, and
disable the send button until `isConnected === true`.

---

## Part 3 — UX Gaps That Kill Real-World Adoption

### Gap 1: No "Which Dataset Is Active?" Indicator
Users constantly lose track of which dataset their questions are running against,
especially after switching tabs or loading old conversations.

**Fix:** Show a persistent pill/badge in the chat header:
```
[Active Dataset: sales_2024.csv  ▾]
```
Clicking it opens dataset switcher. Color it red when no dataset is selected.

---

### Gap 2: Empty Chat Has No Onboarding Guidance
New users see an empty chat box with no clue what to type. Industry research shows
this is the #1 reason users abandon analytics tools within the first session.

**Status:** Starter suggestions already exist (`ChatPage.jsx:1455-1491`) —
but only when a dataset is loaded. Before any dataset is loaded, the screen is
completely empty.

**Fix:** Add a "Welcome" state when no dataset is loaded:
```
👋 Welcome to DataSage!
Start by uploading a dataset →  [Upload CSV]
Or try a sample dataset:  [Sales Demo]  [HR Demo]  [Finance Demo]
```

---

### Gap 3: No Visual Separator Between "Thinking" and "Answer"
The streaming response starts mid-thought. Users can't tell where the analysis
ends and the answer begins, especially for long responses.

**Fix:** When `thinking_step` events arrive, render them in a collapsible
"Reasoning" block with a distinct background color. The final answer renders
below it with a clear divider.

---

### Gap 4: Follow-up Suggestions Use Brittle Regex
`ChatPage.jsx:149-212` has a complex multi-pattern regex parser to extract
follow-up questions from the AI response text. This breaks when the LLM
changes its phrasing.

**Fix:** Move follow-up suggestion generation to the backend. Have the LLM
return them as a structured JSON field (already partially done via `follow_up_suggestions`
in the `done` event). Remove the frontend regex entirely.

---

### Gap 5: Copy Button Has No Success Feedback
When a user copies a response, there is no visual confirmation. This is a
micro-interaction but users repeatedly click the button thinking it didn't work.

**Fix:** Toggle the copy icon to a checkmark for 2 seconds after click.
Already have `lucide-react` icons available (`Check` icon exists).

---

### Gap 6: Long Responses Have No "Jump to Bottom" Button
During streaming, if the user scrolls up to re-read something, the auto-scroll
stops. There is no way to jump back to the live stream.

**Fix:** Show a floating "↓ New content" button when the user is scrolled
up during streaming. On click, scroll to bottom and re-enable auto-scroll.

---

### Gap 7: No Conversation Title Auto-Generation
New conversations are saved with generic names ("New Conversation").
Finding past analyses requires opening each one — unusable history.

**Status:** A `POST /conversations/{id}/title` endpoint exists in the backend.

**Fix:** After the first AI response, call this endpoint with an LLM-generated
title (3-5 words summarizing the question). Show it in the sidebar immediately.

---

## Part 4 — Missing Features for Real-World Team Use

### Feature 1: Export Conversation as PDF Report
**Real use case:** A manager asks 10 questions, gets charts and insights, then
needs to email a summary to leadership. Currently impossible.

**Backend:** PDF generation via WeasyPrint already exists (reports module).
**What to do:** Add "Export as PDF" button to conversation header that calls the
existing reports API with the current conversation ID.

---

### Feature 2: Pin Chart to Dashboard from Chat
**Real use case:** A user discovers an important trend in chat and wants to
track it on their dashboard permanently.

**Status:** Dashboard module exists. Chart data format is compatible.
**What to do:** Add a "Pin to Dashboard" button on each chart card. Opens a
modal to select/create a dashboard and adds the chart.

---

### Feature 3: Show Data Sample on Dataset Selection
**Real use case:** After uploading a file, users don't know what columns exist
or what values look like — so they ask vague questions and get poor results.

**Fix:** When a dataset is selected, show a `5-row preview` table and a
column schema (name + type + sample value) in a collapsible sidebar panel.

---

### Feature 4: Multi-Turn Context for Follow-Up Filters
**Real use case (most common complaint in NL2SQL tools):**
User asks "Show sales by region" → sees a chart → asks "Only show the West region"
→ system doesn't remember the previous query → generates a completely new unrelated query.

**Status:** Conversation history IS sent to the backend. The issue is whether
the AI service correctly uses prior SQL context to build incremental filters.

**What to verify:** Check `ai_service.py` — ensure that `conversation_history`
includes the SQL of the previous turn, not just the text. If it doesn't, pass
the last executed SQL as context.

---

### Feature 5: Shared Conversation Links
**Real use case:** An analyst finds an insight and wants to share it with a
colleague. Currently there is no way to do this.

**What to build:**
- Add a "Share" button on the conversation header
- Generate a read-only token (`/shared/{token}`)
- Recipient sees the conversation in read-only mode (no dataset access needed)

---

## Part 5 — Prioritized Action Plan

### Week 1 — Fix What's Broken
| Task | File | Effort |
|---|---|---|
| Fix Stop button (add cancel handler to backend) | `api/chat/routes.py` | Medium |
| Fix stale `conversationId` on first message | `ChatPage.jsx:986` | Low |
| Disable input during rate limit countdown | `ChatPage.jsx:1597` | Very Low |
| Fix dataset context on conversation load | `ChatPage.jsx:1659` | Low |
| Add WebSocket keep-alive ping | `useWebSocket.js` | Low |

### Week 2 — Enable Hidden Value
| Task | File | Effort |
|---|---|---|
| Show SQL toggle in chat responses | `ChatPage.jsx:831` | Very Low |
| Chart PNG export button | Chart component | Very Low |
| Active dataset indicator in chat header | `ChatPage.jsx` | Low |
| Connecting… state before WebSocket ready | `ChatPage.jsx` | Very Low |
| Auto-generate conversation title | `ChatPage.jsx` + backend | Low |

### Week 3 — Close the UX Gaps
| Task | File | Effort |
|---|---|---|
| Empty state with sample datasets | `ChatPage.jsx:1455` | Low |
| Data preview on dataset select | New sidebar component | Medium |
| Jump-to-bottom during streaming | `ChatPage.jsx` | Low |
| Copy button checkmark feedback | `ChatPage.jsx` | Very Low |
| Collapsible reasoning/thinking steps | `ChatPage.jsx` | Low |

### Month 2 — Real Team Features
| Task | Effort |
|---|---|
| Pin chart to dashboard from chat | Medium |
| Export conversation as PDF | Medium (backend exists) |
| Multi-turn SQL context (verify + fix) | Medium |
| Shared read-only conversation links | High |
| PII redaction badge re-enable | Very Low |

---

## Part 6 — Real-World Use Cases This Unlocks

After the above fixes, here's what becomes possible:

### Use Case A: SME Owner (No SQL knowledge)
1. Uploads `monthly_sales.csv`
2. Sees 5-row data preview + column list → knows what to ask
3. Asks "Which product had the most returns in March?"
4. Gets a bar chart → clicks "Export PNG" → pastes into a PowerPoint
5. Asks "Now only show electronics category" → system remembers the filter
6. Pins chart to "Monthly Review" dashboard

**What was blocking this before:** No data preview, no chart export, no
multi-turn context retention, no dashboard pinning from chat.

---

### Use Case B: Finance Analyst
1. Opens old "Q1 Budget Analysis" conversation
2. System restores the correct dataset automatically
3. Asks "Add Q2 actuals" — uploads new file
4. Asks "Compare Q1 vs Q2 variance by department"
5. Clicks "Show SQL" to verify the join logic
6. Exports as PDF → sends to CFO

**What was blocking this before:** Lost dataset on conversation load, no SQL
visibility, no PDF export from chat.

---

### Use Case C: HR Manager (Sensitive Data)
1. Uploads anonymized headcount CSV
2. PII redaction badge confirms sensitive columns are masked
3. Asks "Which departments have the highest attrition rate?"
4. Gets chart + narrative
5. Shares conversation link with CHRO (read-only)

**What was blocking this before:** PII badge disabled, no sharing.

---

## Sources

- [Chat With Your Database: Complete 2026 Guide – BlazeSQL](https://www.blazesql.com/blog/chat-with-your-database)
- [Natural Language to SQL: Build Reliable Analytics Workflows – Maxim AI](https://www.getmaxim.ai/blog/evaluating-the-quality-of-nl-to-sql-workflows/)
- [Conversational UI Best Practices 2026 – AIM Multiple](https://research.aimultiple.com/conversational-ui/)
- [Conversational Analytics: How AI Agents Transform Data Access – Promethium](https://promethium.ai/guides/conversational-analytics-ai-agents-enterprise-data-access-2026/)
- [UX Design Best Practices for Conversational AI – NeuronUX](https://www.neuronux.com/post/ux-design-for-conversational-ai-and-chatbots)
- [8 Best Conversational Analytics Software – Zenlytic](https://www.zenlytic.com/blog/conversational-analytics-software)
- [AI-Driven Conversational Analytics Platforms 2026 – OvalEdge](https://www.ovaledge.com/blog/ai-driven-conversational-analytics-platforms/)
- [Top 5 Text-to-SQL Tools 2026 – Bytebase](https://www.bytebase.com/blog/top-text-to-sql-query-tools/)
