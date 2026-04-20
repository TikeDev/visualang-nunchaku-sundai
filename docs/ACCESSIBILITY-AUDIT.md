# Accessibility Audit: Visualang SPA

## Audit Summary
- Date: 2026-04-19
- Audit type: Static code review only
- Scope: Frontend SPA flow in `frontend/` covering input, loading, preview/export, and download states
- Target standard: WCAG 2.2 AA
- Runtime status: No localhost or public URL was available, so this report does not include browser-rendered or assistive-technology verification

## Method
- Reviewed `frontend/index.html`, `frontend/src/App.jsx`, `frontend/src/components/UrlInput.jsx`, `frontend/src/components/LoadingScreen.jsx`, `frontend/src/components/Player.jsx`, and `frontend/src/index.css`
- Checked structure, headings, landmarks, forms, keyboard access, focus treatment, status messaging, link/button naming, and motion handling
- Used static contrast calculations for hard-coded color pairs in CSS where the code made the result unambiguous

## Findings At A Glance
- Critical: 0
- Serious: 4
- Moderate: 3
- Minor: 1

## Critical
No critical issues were identified from static review alone.

## Serious

### 1. SPA state changes do not move focus to the newly rendered content
- Affected state/component: App-level transitions between input, loading, preview, and export states
- WCAG: 2.4.3 Focus Order, 3.2.1 On Focus
- Evidence: `frontend/src/App.jsx:124-132`, `frontend/src/App.jsx:177-258`, `frontend/src/App.jsx:350-462`
- Impact: Submitting the form swaps out the currently focused controls and mounts a different screen, but there is no focus management to move keyboard and screen-reader users to the new heading or status region. In practice this often leaves focus on `body` or in an undefined place, making the new state easy to miss.
- Recommended remediation: Add explicit focus management for each major state transition. When loading starts, move focus to the loading heading or an announced progress container. When preview becomes ready, move focus to the preview heading or primary player control. When an error occurs, move focus to the alert or invalid field as appropriate.

### 2. Primary button text likely fails minimum contrast
- Affected state/component: Primary CTA buttons such as “Generate Illustrated Preview” and “Download Video”
- WCAG: 1.4.3 Contrast (Minimum)
- Evidence: `frontend/src/index.css:323-326`
- Impact: The primary button uses `#b96e4d` with `#fffaf4` text. Static contrast is approximately `3.75:1`, which is below the required `4.5:1` for normal-sized text. Users with low vision may have difficulty reading the primary actions.
- Recommended remediation: Darken the primary button background, darken the text, or increase the text size to true large-text thresholds. Recheck the final computed contrast in the browser after the visual update.

### 3. Global focus indicators are too low-contrast, and the upload control has no reliable visible focus state
- Affected state/component: Global interactive controls and the audio upload control
- WCAG: 2.4.11 Focus Appearance, 2.4.7 Focus Visible
- Evidence: `frontend/src/index.css:29`, `frontend/src/index.css:75-78`, `frontend/src/components/UrlInput.jsx:131-142`
- Impact: The shared focus ring is `rgba(143, 77, 50, 0.38)`, which works out to roughly `1.8:1` against the light card backgrounds, below the required `3:1` contrast for focus indicators. The upload control is more problematic because the actual file input is visually clipped with `.sr-only`, while the visible `.file-picker` label has no `:focus-within` treatment; keyboard users may tab to the control with little or no visible indication.
- Recommended remediation: Replace the translucent ring with a solid high-contrast focus style that reaches at least `3:1` against adjacent colors. Add visible focus styling on the upload label via `.file-picker:focus-within` so the visual control reflects the hidden input’s focus state.

### 4. Loading and status announcements are likely noisy or unreliable for assistive technology
- Affected state/component: Loading workflow, export progress, warning messaging
- WCAG: 4.1.3 Status Messages
- Evidence: `frontend/src/components/LoadingScreen.jsx:40-57`, `frontend/src/App.jsx:313-334`, `frontend/src/App.jsx:395-425`, `frontend/src/components/Player.jsx:208-210`
- Impact: The loading card exposes the whole ordered list as a live status region while the active step detail is updated inside it. Additional nested `role="status"` messages are rendered for warnings, preview readiness, export progress, and completion. This pattern often causes full-region re-announcements, duplicated speech, or announcements that are too verbose to be useful during long-running async work.
- Recommended remediation: Use one dedicated live region for concise progress updates and keep the visible checklist outside of that live region. Announce only the current step and major transitions such as “Generating image 2 of 5” or “Export complete.” Avoid nesting multiple simultaneous status regions for related events.

## Moderate

### 5. No skip link or other bypass mechanism is provided
- Affected state/component: Global page structure
- WCAG: 2.4.1 Bypass Blocks
- Evidence: `frontend/index.html:1-19`, `frontend/src/App.jsx:350-365`
- Impact: Keyboard users must traverse the header area before reaching the main app content on every load and reset. The app is small today, but the lack of a skip link still removes a standard navigation shortcut for keyboard and screen-reader users.
- Recommended remediation: Add a visible-on-focus skip link near the top of the document that targets the main content container.

### 6. The document title is too generic and does not reflect app state
- Affected state/component: Document metadata
- WCAG: 2.4.2 Page Titled
- Evidence: `frontend/index.html:8`
- Impact: The title is always `Visualang`, which does not help users distinguish the app from other tabs or understand whether they are on the input screen, loading state, or preview/export state.
- Recommended remediation: Use a more descriptive default title such as `Create Illustrated Language Videos - Visualang` and update it as major states change, for example `Generating Images - Visualang` or `Preview Ready - Visualang`.

### 7. File upload help and error text are attached to the label, not the actual file input
- Affected state/component: Audio upload flow
- WCAG: 1.3.1 Info and Relationships, 3.3.1 Error Identification
- Evidence: `frontend/src/components/UrlInput.jsx:127-145`, `frontend/src/components/UrlInput.jsx:149-153`
- Impact: In upload mode, the visible label receives `aria-describedby`, but the actual `<input type="file">` only gets `aria-labelledby`. Screen-reader users who focus the real input may not hear the accepted file types, file size limit, or any validation error association.
- Recommended remediation: Move the descriptive relationship onto the file input itself by wiring `aria-describedby` to the help text and error text IDs. Keep the visible label for click/tap behavior, but make sure the control owns its instructions and errors programmatically.

## Minor

### 8. Decorative motion has no reduced-motion fallback
- Affected state/component: Player animations and spinner treatments
- WCAG: Advisory for WCAG 2.2 AA target; relevant future consideration for 2.3.3 Animation from Interactions
- Evidence: `frontend/src/components/Player.jsx:190-196`, `frontend/src/index.css:665-713`
- Impact: The player uses persistent Ken Burns image motion and rotating spinners, but there is no `prefers-reduced-motion` branch. Some motion-sensitive users may find the preview uncomfortable even if the pattern is not a clear AA failure from static review.
- Recommended remediation: Add a reduced-motion media query that disables non-essential animation and preserves the player state with static imagery and non-animated loading indicators.

## Reviewed Scenarios
- Source input state: YouTube mode, file-upload mode, invalid URL handling, invalid file type handling, oversized file handling, disabled submit state
- Loading state: transcript fetch, concept extraction, image-generation progress, retry messaging, gate warning messaging
- Preview/export state: preview ready, export in progress, export complete, reset flow, download links, custom player controls
- Cross-cutting checks: keyboard traversal expectations, heading continuity across conditional views, focus treatment, live-region behavior, and likely contrast issues

## Runtime Follow-Up Needed
The following checks remain unverified until a live URL is available:
- Actual tab order through the rendered interface, especially after state transitions
- Computed accessible names for icon-bearing controls from the browser accessibility tree
- Whether screen readers announce loading, warning, preview-ready, and export-complete updates as intended
- Final computed contrast after gradients, translucency, and browser rendering are applied
- Real focus visibility for the hidden file input and custom player controls in the browser
- Whether the custom player remains fully usable across browsers and assistive technologies without the native audio UI

## Notes
- This report is intentionally limited to code-backed findings. A runtime audit could confirm or reduce uncertainty around focus behavior, live-region verbosity, and rendered contrast.
