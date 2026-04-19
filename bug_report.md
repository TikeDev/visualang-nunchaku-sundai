Subtle bug in App.jsx:211-240: kickOffExport reads images from React state but that state was just set via setImages(data.images) moments earlier — React batches state updates, so images inside the new call may still be stale (empty). The export will use image_url: '' for every entry. Quick fix: pass the data.images array through explicitly.

Unused variable App.jsx:85: audioPath is set but never read (export router reads it from transcriptData instead).

Frontend doesn't use the new gate key in transcript responses — so warnings from TranscriptGate are silently ignored. Not broken, just wasted signal.