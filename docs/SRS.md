# Software Requirements Specification (SRS)
## 1. Purpose
The purpose of this project is to develop a professional, modular, and maintainable Python automation bot for the Android game **Word Madness (ZenWord)**.
The bot must automatically solve game levels by interacting with a real Android device using Android Debug Bridge (ADB).
The project must be designed for long-term maintainability, scalability, and reliability.
This document serves as the primary source of truth for the project.
Any implementation that conflicts with this document must be considered incorrect.
---
## 2. Project Goals
The bot shall:
- Detect a connected Android device automatically.
- Determine the connected device's screen resolution.
- Automatically adapt to different Android screen sizes.
- Detect the current game state.
- Read the current level number.
- Load known solutions from a local JSON database.
- Detect the letter wheel.
- Generate swipe paths.
- Swipe every valid word.
- Detect advertisements.
- Close advertisements automatically.
- Continue solving levels indefinitely.
---
## 3. Design Philosophy
This project follows the following principles.
### Principle 1
The project must be modular.
Every component has exactly one responsibility.
No module should perform unrelated work.
---
### Principle 2
The project must be data-driven.
Game knowledge comes from:
levels.json
not from hardcoded words inside Python.
---
### Principle 3
Every component must be replaceable.
Examples:
ADB implementation
↓
ADBUtils
↓
Scrcpy
↓
USB HID
without changing gameplay logic.
Likewise
OCR
↓
EasyOCR
↓
Template Matching
must be replaceable.
---
### Principle 4
No module should directly communicate with unrelated modules.
All communication follows the project architecture.
---
## 4. High Level Architecture
The project follows this pipeline.
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
Each layer communicates only with the layer directly above or below it.
---
## 5. Resolution Independence
Nothing inside the project may depend on one specific phone.
The Galaxy S25 Ultra is used only as the reference device.
All coordinates must be calculated dynamically.
The software must:
• Detect screen width
• Detect screen height
• Detect display density
• Scale every coordinate
• Scale every crop region
• Scale template search regions
The bot should operate on different Android phones without modifying source code.
---
## 6. Coding Standards
Every module must:
- use type hints
- contain docstrings
- avoid duplicated code
- use descriptive names
- use logging instead of print()
- avoid global variables whenever possible
---
## 7. Error Handling
The bot must never crash because of:
- OCR failure
- Template mismatch
- Device disconnect
- Screenshot failure
- Missing JSON entry
Instead it shall:
- retry
- recover
- log the failure
- continue whenever possible
---
## 8. Performance Goals
Screenshot processing should be as fast as practical.
Expensive OCR operations should only be used when required.
Template matching should be preferred whenever possible.
The software should avoid unnecessary processing.
---
## 9. Future Expansion
The architecture must support future additions without requiring major redesign.
Possible future additions include:
- Multiple languages
- Different games
- Different OCR engines
- Cloud database
- Machine learning letter detection
- Different input methods
The architecture must remain flexible enough to support these additions.
