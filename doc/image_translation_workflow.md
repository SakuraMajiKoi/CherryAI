**Image Translation Workflow**

Goal
----
Provide a reproducible, format-preserving pipeline to translate text contained in images. Pipeline must support local and cloud OCR/translation, enforce resolution/quality checks, preserve PNG transparency and special BMP behaviors, and offer a "section-only" mode to translate only a selected region.

Pipeline Overview
-----------------
High-level steps (recommended):

- OCR -> Clean -> Translate -> Validate -> Re-insert

Steps (details)
----------------

1. OCR
   - Input: Original Image. 
   - Goal: Find and extract text and bounding boxes from images via OCR (support Tesseract locally, and provider OCR via API).
   - Output: Text blocks with coordinates, confidence scores and style notes.

2. Clean
   - Input: Original Image. 
   - Goal: Remove the OCR'd Text from the Image.
   - Optionally run language detection and split into translatable segments.
   - Output: Cleaned Image without text. 

3. Translate
   - Input: Text block from the original image (#1). 
   - Goal: Translate segments using configured translation provider or local model.
   - Maintain mapping to original bounding boxes for reinsertion.
   - Output: Translated text blocks. 

4. Insert / Render Output
   - Input: Cleaned Image from #2, translated text blocks with style notes and optionally Original Image with original text blocks. 
   - Render translated text back into an image layer or export as sidecar text + coordinates.
   - Preserve original image style, format and metadata when possible. Optionally scale and convert automatically.
   - Output: Translated Image. 

5. Validate
   - Input: Original Image, Image from #4, optional translated text blocks and original text blocks. 
   - Check translated text for length overflow, layout breakage, and quality (spell/grammar quick-check).
   - Mark low-confidence OCR regions for manual review.
   - Output: Failure Log. 


Format & I/O Considerations
---------------------------

- PNG: Preserve alpha channel. When rendering text back, write to a new RGBA image and copy/preserve original transparency and metadata.
- BMP: Some BMP variants (indexed color, unusual bit depths) require explicit handling; provide conversion helpers to canonical BMP (24/32-bit) when necessary and convert back on export if strict format preservation is requested.
- Compressed Images: RPG Maker MV / MZ support
- Input/Output parity: Default behavior is same-format output. Offer `--force-format` and `--preserve-format` CLI flags.

Selection and Section Mode
--------------------------

- Support region selection via interactive GUI selection.
- `--section-only` mode accepts a bounding box to limit OCR/translate/rendering scope.

Validation, Resolution & Resizing
---------------------------------

- Minimum recommended resolution: 300 DPI for small fonts; provide configurable thresholds.
- Implement `validate_image_resolution()` that returns PASS/WARN/FAIL and suggested resize scale.
- Offer `--auto-resize` to upsample using a high-quality resizer (e.g., Lanczos) before OCR, and `--dry-run` to report changes.

Cloud Usage Warning & Heuristics
--------------------------------

- Warning: Sending images to cloud OCR/translation can incur costs and privacy exposure.
- Heuristic: only send images to cloud if a text-density metric exceeds a threshold (e.g., average OCR confidence > 0.6 and text pixel area > X%). Provide `--allow-cloud` flag to require explicit opt-in.
- Provide per-image cost estimate (based on provider prices) before sending.

Implementation Notes & Suggested Locations
----------------------------------------

- Handlers: `formats/image.py` (new) — format-aware read/write preserving PNG/BMP specifics.
- OCR: `functions/ocr.py` — adapters for Tesseract (local) and remote OCR providers.
- Cleaning: `modi/image_clean.py` — pre/post OCR text cleaning and heuristics.
- Translation orchestration: add `functions/image_translate.py` to map segments -> translation providers and maintain coordinates.
- CLI scripts: `dev/img_translate.py` with flags: `--input`, `--output`, `--section`, `--allow-cloud`, `--auto-resize`, `--preserve-format`.
- Tests: `dev/test_image_translation.py` (script tests mocking OCR and providers; include PNG alpha and BMP edge cases).
- GUI: Add a new step (Images) which is unlocked when images are found
- Extend manifest to include images and image folder per project. Copy Original Images into \images\original, Save Cleaned Images into \images\cleaned and translated Images into \images\translated. Path to each image, text coordinates, section, original and translated will be part of the manifest, as will the error. Each image can have several of these depending on how many sections are taken out and text is OCR'd and sectioned.
- Optional opt out for every step (OCR | Clean | Translate | Insert | Validate)
- Optionally combine certain steps, primarily to skip cleaning and halve costs.

Estimates
---------

- Rough implementation effort: 16-32 hours (design, scripts, handlers, tests).
- Per-image processing cost: depends on chosen OCR/translation provider; provide a per-image quick estimate and show a cloud/usage warning.

Developer Recommendations
------------------------

- Keep processing logic out of GUI; expose functions in `functions/` and `modi/` for re-use by CLI and GUI.
- Start with local Tesseract + a local translation mock for integration tests, then add cloud adapters behind provider interfaces.
- Add automated tests for transparency preservation (PNG) and BMP conversion round-trips.

Security & Privacy
------------------

- Always display a consent prompt when `--allow-cloud` is enabled and log which images are sent. Provide opt-out per-session.
