# Architecture
## Overview
The Word Madness Bot follows a strict layered architecture.
Every layer has exactly one responsibility.
No layer may bypass another layer.
The architecture is intentionally modular to simplify debugging, maintenance, testing, and future expansion.
---
# System Architecture
Configuration
↓
Logging
↓
ADB Interface
↓
Screenshot Capture
↓
Vision Engine
↓
Game State Detector
↓
Decision Engine
↓
Database
↓
Swipe Generator
↓
ADB Input
↓
Android Device
---
# Layer Responsibilities
## Configuration
Responsible for:
- project configuration
- constants
- file paths
- runtime options
This layer never communicates directly with Android.
---
## Logging
Responsible for:
- debug logs
- runtime logs
- screenshots
- crash reports
Logging must be available to every layer.
---
## ADB Interface
Responsible only for communication with Android.
Functions include:
- device detection
- shell commands
- screenshots
- tap
- swipe
- key events
No gameplay decisions are made here.
---
## Screenshot Capture
Responsible for obtaining screenshots from the device.
It should not perform OCR.
It should not perform template matching.
Its only responsibility is image acquisition.
---
## Vision Engine
Responsible for image analysis.
Includes:
- template matching
- OCR
- color detection
- letter detection
- circle detection
- image preprocessing
The Vision Engine never generates input events.
---
## Game State Detector
Responsible for determining:
- Home screen
- Playing
- Victory
- Advertisement
- Unknown state
It converts vision results into logical game states.
---
## Decision Engine
Responsible for deciding what the bot should do next.
Examples:
Home
↓
Read level
↓
Load words
↓
Play level
↓
Handle advertisement
↓
Return home
The Decision Engine never performs OCR.
---
## Database
Responsible for:
levels.json
word lookup
level lookup
future storage systems
No screenshots are processed here.
---
## Swipe Generator
Responsible for converting words into swipe paths.
It receives:
letters
↓
word
↓
coordinates
↓
swipe path
No ADB calls occur here.
---
## ADB Input
Responsible for executing touches.
Only receives completed swipe paths.
It never makes gameplay decisions.
---
# Communication Rules
Allowed
Configuration
↓
ADB
↓
Vision
↓
State Machine
↓
Database
↓
Swipe
↓
ADB Input
Forbidden
Vision → Tap
Database → Screenshot
ADB → OCR
Swipe Generator → Screenshot
Decision Engine → OCR
Every module communicates only with adjacent layers.
---
# Replaceability
Every layer must be replaceable.
Examples
OCR
EasyOCR
Template Matching
ADB
ADBUtils
Scrcpy
USB HID
The rest of the application should remain unchanged.
---
# Error Recovery
Every layer reports failures upward.
Higher layers decide recovery.
Lower layers never decide gameplay.
---
# Future Expansion
Architecture must support
multiple games
multiple OCR engines
multiple Android devices
multiple databases
remote control
without redesigning the system.
