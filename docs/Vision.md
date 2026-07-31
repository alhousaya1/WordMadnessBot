# Vision

## 1. Overview

The Vision layer converts captured image bytes into confidence-bearing observations. It
is independent of ADB, gameplay, the level database, the state machine, and swipe
planning. It may depend on configuration, logging, domain value objects, and injected OCR
implementations. Detection failure is represented by `None` or low-confidence evidence,
not device input or gameplay recovery.

## 2. Screen Capture

Screenshot acquisition belongs to the preceding capture layer. Vision accepts an
immutable `CapturedFrame`, verifies that encoded dimensions match `ScreenGeometry`, and
decodes it to an RGB array. It never captures a screen itself.

## 3. Circle Detection

The letter wheel is searched only inside a normalized region. Radius limits are fractions
of the shorter current screen dimension. Detection uses low-saturation color evidence,
connected components, aspect ratio, and circular fill ratio. Returned center and radius
are absolute coordinates accompanied by a confidence in `[0, 1]`.

## 4. Letter Extraction

Dark connected glyphs are extracted inside the detected circle. Component size limits
are fractions of the detected radius. Each candidate is passed to the injected OCR
engine, receives a combined OCR/shape confidence, and is ordered clockwise from the top
of the wheel. The extractor never loads words or decides whether a word is playable.

## 5. OCR

`OcrEngine` is a replaceable protocol returning `OcrResult`. The initial adapter invokes
Tesseract through a bounded subprocess and treats missing binaries, timeouts, nonzero
exit codes, and empty recognition as recoverable no-results. `LevelReader` crops a
normalized header region, preprocesses it, requests digits only, and returns a
confidence-bearing positive `LevelReading`.

## 6. Template Matching

Templates are matched only within caller-supplied, dynamically scaled regions. The
matcher uses normalized correlation, falls back to normalized absolute error for a
constant template, performs a coarse search followed by local refinement, and returns
only matches meeting the configured threshold. Assets and normalized metadata live in
`templates/`.

## 7. Screen Classification

Screen classification is explicitly deferred to Milestone 6. Milestone 5 produces the
visual evidence needed by that layer but does not assign game states.

## 8. Debug and Visualization

`DebugRenderer` is disabled unless `Settings.save_debug_images` is true. When enabled it
draws confidence-labeled circles, letters, and template regions and writes only to the
configured debug directory. Merely importing or constructing Vision components does not
create files.
