# JobPilot web

The website for JobPilot: a **job-hunting chatbot** and **resume upload + tailoring**.
Next.js 14 (App Router), TypeScript (strict), Tailwind CSS. Runtime dependencies are
`next`, `react`, `react-dom`, `clsx`, `zod` and `lucide-react`; there is no UI kit and
no state library, only React hooks and context.

```
npm install
cp .env.example .env.local     # defaults to mock mode
npm run dev                    # http://localhost:3000
npm run typecheck && npm run lint && npm run build && npm test
```

## Mock mode vs live mode

| `NEXT_PUBLIC_API_MODE` | Behaviour |
|---|---|
| `mock` (default) | Everything runs in the browser against seeded data. No backend needed. |
| `live` | Talks to the real web API. Also set `NEXT_PUBLIC_API_BASE_URL` (the client appends `/api/v1`). |

Both modes implement one interface, `ApiClient` (`src/lib/api/client.ts`). `src/lib/api/index.ts`
is the only file that picks an implementation; components just `import { api } from "@/lib/api"`.

Mock mode (`src/lib/api/mock/`) is realistic enough to demo every state:

- 12 invented jobs at invented companies (`jobs.ts`) and a sample parsed resume (`resumeSample.ts`).
- A scripted agent turn (`agent.ts`) emits `status` -> `tool_call` -> `tool_result` -> `token`... -> `job_cards` -> `done`
  with small delays. There is no model: a few regexes pick "search", "tailor" or "help", and `match.ts`
  ranks the seed jobs against your words and the resume's skills.
- Ask "tailor my resume for the first one" and the agent emits `tailoring_started`.
- Tailoring (`tailoring.ts`) is `running` for ~2.8 s, then `ready` with ~6 suggestions.
- Demo hooks: sign in with any email and any 6-digit code except `000000`; type `/fail` in a chat message to see the
  retryable error state (the retry succeeds); upload a file whose name contains `fail` to see a failed parse.
- State is a module singleton (`db.ts`): it survives navigation and resets on reload.
- Mock "Export DOCX" produces RTF (a real .docx needs zipping); PDF export is a small hand-built valid PDF.

## Layout

```
src/
  app/                       routes (App Router)
    page.tsx                 marketing landing
    login/                   email -> 6-digit code
    app/                     signed-in area (layout = route guard + sidebar shell)
      chat/ chat/[conversationId]/   chat (new / existing)
      jobs/[jobId]/ saved/           job detail, saved grid
      resume/                        upload + parsed view
      tailor/new/ tailor/[tailoringId]/
  components/{chat,jobs,resume,tailor,layout,marketing,ui}/
  hooks/                     useChatStream, useConversation, useConversationList,
                             useResumeUpload, useResumes, useTailoring, usePolling
  lib/
    api/                     client.ts (interface), http.ts, schemas.ts (zod), types.ts, errors.ts, mock/
    auth/                    token.ts (memory + sessionStorage), AuthProvider.tsx
    sse.ts                   SSE parser over fetch streams
    markdown.tsx             safe markdown-lite renderer
    diff.ts                  LCS word diff
    resumeApply.ts           apply accepted suggestions to a resume (preview + export)
```

Rules of thumb: routes in `app/` are thin and just mount a component; components never call
`fetch`; every network call goes through `api`; every response is validated by a zod schema at
the boundary (`http.ts` -> `schemas.ts`), so a backend that drifts from `docs/web-api.md`
fails with one clear `bad_response` error instead of an `undefined` deep in the UI.

## Auth

`/login` calls `POST /auth/request-code`, then `POST /auth/verify-code`. The access token is held in a
module variable and mirrored to `sessionStorage` (survives refresh, dies with the tab; not `localStorage`).
`AuthProvider` confirms a stored token with `GET /me` before showing the app. Any `401` calls `clearToken()`,
which flips auth to anonymous, and `RequireAuth` (used by `app/app/layout.tsx`) redirects to
`/login?next=...` (only `/app...` return paths are honored).

## Data flow of one chat turn

1. **Compose.** `Composer` calls `ChatView.handleSend`. A UUID `client_message_id` is generated with
   `crypto.randomUUID` and the user bubble is appended optimistically (keyed by that id).
   On `/app/chat` (no conversation yet) the view first calls `POST /conversations`, stores the message in
   `lib/chat/pending.ts` and navigates to `/app/chat/<id>`, where the thread sends it.
2. **Post.** `useChatStream.run` calls `POST /conversations/{id}/messages` and gets `{message_id, turn_id}`.
   Sending the same `client_message_id` again returns the same ids, so retries and double-clicks never make a second turn.
3. **Stream.** `api.streamTurn` does `fetch(.../stream)` with the Authorization header and parses the body with
   `lib/sse.ts`. (The browser's `EventSource` cannot send custom headers, which is why we don't use it.)
   Each frame is JSON-parsed and validated against the `streamEvent` zod union; unknown events are skipped.
4. **Fold.** Events are applied by the pure reducer `applyEvent`: `tool_call`/`tool_result` drive the live activity
   list ("Searching remote backend roles..." -> "Found 6 matching roles"), `token` grows the text, `job_cards` and
   `tailoring_started` add cards. `StreamingBubble` renders that state inside an `aria-live` region; `MessageList`
   auto-scrolls only while you are near the bottom.
5. **Finish.** On `done` the accumulated reply becomes a normal `ChatMessage`, is appended to the thread, and the
   sidebar list refreshes. On `error` (or a dropped stream) the bubble shows a message with **Retry**, which re-sends
   with the *same* `client_message_id`.

## Data flow of one tailoring

1. `/app/tailor/new?jobId=...` (or "Tailor my resume" in chat, which creates it server-side and emits `tailoring_started`)
   sends `POST /tailorings` with `{resume_id, job_id}` or `{resume_id, job_description_text}`.
2. `/app/tailor/[id]` mounts `useTailoring`, which polls `GET /tailorings/{id}` (`usePolling`, chained timeouts so
   requests never overlap) until the status leaves `running`.
3. The score meter, keyword chips (required/preferred; on resume / covered by edits / missing) and suggestion cards render.
   Each card shows a word diff (`lib/diff.ts`, inline or side-by-side).
4. Accept / Reject / Accept all update the UI optimistically, then `POST /tailorings/{id}/decisions` (requests are
   chained so responses can't land out of order; a failure rolls back). The response replaces local state.
5. The live preview is `applySuggestions(resume.sections, suggestions)` (accepted edits only), highlighted where changed.
6. Export downloads via `fetch` (needs the auth header) and a temporary object URL.

## Contract notes and ambiguities

- **`score_after`** is not defined precisely. The UI treats it as the server's projection with all non-rejected
  suggestions applied, and always takes it from the latest server response. The mock computes it that way.
- **`reorder_section`**: the contract doesn't say what `proposed` holds. The UI assumes a comma-separated section
  order (`"summary, skills, experience, projects, education"`); unknown names are ignored.
- **Retrying a failed turn**: the contract says reposting a `client_message_id` returns the original ids, but not
  whether that turn's stream can be reopened after an `error`. The client assumes it can (or that the server starts a
  fresh attempt for the same turn).
- **`rewrite_bullet.target_id`** is matched against bullet ids in both experience and projects.
- **Unknown stream events** are ignored rather than treated as errors, so the server can add events safely.
- **Auth `expires_at`** is honored client-side: an expired stored token is dropped before any request.

## Accessibility

Labelled form controls; visible focus rings (`:focus-visible`); the file input is a real `<input type=file>`;
the streaming reply and upload status use `aria-live`; the mobile drawer is `inert` while closed and closes on Escape;
diffs never rely on color alone (strikethrough / underline); `prefers-reduced-motion` is respected.

## Tests

`npm test` (vitest) covers the SSE parser, the markdown renderer's parsing and link safety, the word diff, the stream
reducer, and the mock client's event ordering, idempotency and tailoring lifecycle.
