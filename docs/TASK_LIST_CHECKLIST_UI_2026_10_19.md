# Task list and checklist controls — 19 October 2026

The task list shows the title on its first line and the existing task reference
in the metadata below it. Task IDs, navigation and API values remain unchanged.

The checklist panel has an accessible collapse/expand button. Its heading and
button remain visible; the body stays mounted while hidden, preserving draft
answers, checked values and template selection. Changing tasks resets the panel
to expanded. Existing permissions and save operations are unchanged.

TypeScript/Vite build and all 37 checklist/browser scenarios passed. Validation
covers desktop/mobile, long and empty titles, navigation, repeated
keyboard toggles, draft and saved value preservation, empty panels and read-only
access. Browser fixtures are synthetic; they do not prove production writes.
Production acceptance uses real read-only browser interactions and exact build
verification. No backend, schema or Telegram changes are part of this release.
