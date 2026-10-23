# 07 — Responsive UI

The frontend adapts to two form factors: **mobile phones** and **desktop**.

## Breakpoint

- `max-width: 768px` → mobile layout; above it → desktop layout.
- Very narrow screens (`max-width: 400px`) also get a full-width auth card.

## Desktop (two-pane)

- Sidebar (340px, chat list / contacts / search / invites) on the left; chat window fills the rest.
- This is the default layout and needs no state.

## Mobile (single-pane, Telegram-style)

- The **chat list** fills the whole screen when no chat is selected.
- Selecting a chat switches to a **full-screen chat pane** (sidebar hidden).
- A **back button** (`←`, `data-testid="back-button"`) in the chat header returns to the list.

## Implementation

- `App.tsx` tracks `isMobile` with `window.matchMedia('(max-width: 768px)')` (state + `change` listener) and toggles the `chat-open` class on `.layout` when a chat is selected.
- `ChatWindow.tsx` accepts an optional `onBack` callback and renders the back button; CSS shows it only on mobile.
- Visibility switching is pure CSS (`display: none/flex` inside the media query) — no unmounting, so chat state survives pane switches.
- Mobile tweaks: message rows up to 85% width, 16px composer font (avoids iOS input zoom), narrower invite input.

## Tests

- `frontend/e2e/responsive.spec.ts` — Playwright spec with a 390×844 viewport covering: list fills screen → open chat (sidebar hidden) → send message → back button returns to list → the other user receives the message on mobile.
- All desktop specs keep running unchanged against the default (desktop) viewport.

## Status: done
