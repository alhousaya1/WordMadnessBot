# Software Requirements Specification

## Document Control

| Field | Value |
|-------|-------|
| Project | Word Madness Bot |
| Target Application | Word Madness (ZenWord) — Android |
| Document Version | 0.1 |
| Status | Draft |
| Last Updated | — |

### Related Documents

| Document | Description |
|----------|-------------|
| [Architecture.md](Architecture.md) | System design and component structure |
| [Vision.md](Vision.md) | Screen capture, detection, and OCR requirements |
| [Gameplay.md](Gameplay.md) | Game state, level flow, and input automation |
| [Ads.md](Ads.md) | Advertisement and popup handling |
| [Database.md](Database.md) | Dictionary and word list requirements |

### Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | — | — | Initial documentation structure |

---

## 1. Introduction

### 1.1 Purpose

<!-- Describe the purpose of this document and its intended audience. -->

### 1.2 Product Overview

<!-- Brief summary of the Word Madness Bot: what it does, how it interacts with the game. -->

### 1.3 Document Conventions

#### Requirement Identifiers

| Prefix | Category |
|--------|----------|
| `FR-xxx` | Functional requirement |
| `NFR-xxx` | Non-functional requirement |
| `CON-xxx` | Constraint |
| `ASM-xxx` | Assumption |

#### Requirement Status Values

| Status | Meaning |
|--------|---------|
| Proposed | Identified, not yet reviewed |
| Approved | Accepted for implementation |
| Implemented | Built and verified |
| Deferred | Out of scope for current milestone |

#### Priority Levels

| Priority | Meaning |
|----------|---------|
| Must | Required for minimum viable product |
| Should | Important but not blocking |
| Could | Desirable enhancement |
| Won't | Explicitly excluded from current scope |

---

## 2. Scope

### 2.1 In Scope

<!-- List capabilities the bot will provide. -->

### 2.2 Out of Scope

<!-- List capabilities explicitly excluded. -->

### 2.3 Target Environment

<!-- Hardware, OS, game version, connection method. -->

---

## 3. Definitions and Acronyms

### 3.1 Definitions

| Term | Definition |
|------|------------|
| Letter wheel | Circular arrangement of draggable letters on the puzzle screen |
| Level | A single puzzle instance requiring one or more words to complete |
| Bonus word | Valid dictionary word not required to finish the level |
| Template | Reference image used for UI element matching |
| — | — |

### 3.2 Acronyms

| Acronym | Expansion |
|---------|-----------|
| ADB | Android Debug Bridge |
| OCR | Optical Character Recognition |
| SRS | Software Requirements Specification |
| — | — |

---

## 4. Overall Description

### 4.1 Product Perspective

<!-- How the bot fits into the user's workflow. Standalone desktop tool controlling an Android device. -->

### 4.2 Product Functions

<!-- High-level capability summary. -->

| ID | Function | Reference |
|----|----------|-----------|
| — | — | — |

### 4.3 User Classes and Characteristics

<!-- Primary operator profile, technical expectations. -->

### 4.4 Operating Environment

<!-- Windows host, Python runtime, ADB, connected Android device, Tesseract. -->

### 4.5 Design and Implementation Constraints

<!-- See Section 7. Cross-reference CON-xxx items. -->

### 4.6 External Interfaces

#### 4.6.1 Hardware Interfaces

<!-- Android device via USB/Wi-Fi ADB. -->

#### 4.6.2 Software Interfaces

<!-- ADB, Tesseract, OpenCV, game application. -->

#### 4.6.3 Communication Interfaces

<!-- None expected beyond local ADB. -->

---

## 5. Functional Requirements

### 5.1 Device Connection and Control

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-001 | — | — | Proposed |
| FR-002 | — | — | Proposed |

<!-- ADB connect, device info, screenshot, tap, swipe. See Architecture.md → ADB layer. -->

### 5.2 Vision and Perception

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-010 | — | — | Proposed |
| FR-011 | — | — | Proposed |

<!-- Circle detection, letter extraction, screen classification. See Vision.md. -->

### 5.3 Word Solving

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-020 | — | — | Proposed |
| FR-021 | — | — | Proposed |

<!-- Dictionary lookup, valid word generation. See Database.md, Gameplay.md. -->

### 5.4 Input Automation

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-030 | — | — | Proposed |
| FR-031 | — | — | Proposed |

<!-- Swipe path calculation, word submission, timing. See Gameplay.md. -->

### 5.5 Game Flow and State Management

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-040 | — | — | Proposed |
| FR-041 | — | — | Proposed |

<!-- State machine, level navigation, completion detection. See Gameplay.md. -->

### 5.6 Advertisement and Popup Handling

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-050 | — | — | Proposed |
| FR-051 | — | — | Proposed |

<!-- Ad detection and dismissal. See Ads.md. -->

### 5.7 Logging and Diagnostics

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-060 | — | — | Proposed |
| FR-061 | — | — | Proposed |

<!-- Log output, debug screenshots, error reporting. -->

### 5.8 Configuration

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-070 | — | — | Proposed |
| FR-071 | — | — | Proposed |

<!-- Runtime settings, timing, thresholds, device selection. -->

---

## 6. Non-Functional Requirements

### 6.1 Performance

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NFR-001 | — | — | Proposed |

<!-- Level solve time, screenshot latency, OCR throughput. -->

### 6.2 Reliability

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NFR-010 | — | — | Proposed |

<!-- Error recovery, retry behavior, session stability. -->

### 6.3 Usability

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NFR-020 | — | — | Proposed |

<!-- Setup steps, CLI clarity, log readability. -->

### 6.4 Maintainability

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NFR-030 | — | — | Proposed |

<!-- Modular layers, testability, documentation coverage. -->

### 6.5 Compatibility

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NFR-040 | — | — | Proposed |

<!-- Supported Android versions, screen resolutions, host OS. -->

### 6.6 Security and Safety

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NFR-050 | — | — | Proposed |

<!-- No credential storage, local-only operation, no network exfiltration. -->

---

## 7. Constraints

| ID | Constraint | Category |
|----|------------|----------|
| CON-001 | Bot operates via ADB; no game API or memory injection | Technical |
| CON-002 | Host platform is Windows | Platform |
| CON-003 | Game UI changes may break template matching | External |
| CON-004 | — | — |

---

## 8. Assumptions and Dependencies

### 8.1 Assumptions

| ID | Assumption |
|----|------------|
| ASM-001 | User has USB debugging enabled on the Android device |
| ASM-002 | ADB is installed and accessible on the system PATH |
| ASM-003 | Game is installed and reachable from the device home screen |
| ASM-004 | — |

### 8.2 Dependencies

| Dependency | Purpose | Required Version |
|------------|---------|------------------|
| Python | Runtime | — |
| ADB | Device communication | — |
| OpenCV | Image processing | — |
| Tesseract | OCR | — |
| — | — | — |

---

## 9. Acceptance Criteria

### 9.1 Minimum Viable Product

<!-- Conditions that define MVP completion. -->

- [ ] —
- [ ] —

### 9.2 Full Release

<!-- Conditions that define production-ready release. -->

- [ ] —
- [ ] —

---

## 10. Traceability Matrix

<!-- Map functional requirements to design documents and milestones. -->

| Requirement | Document | Milestone | Notes |
|-------------|----------|-----------|-------|
| FR-001 | Architecture.md | M0 | — |
| FR-010 | Vision.md | M1 | — |
| FR-020 | Database.md | M2 | — |
| FR-030 | Gameplay.md | M3 | — |
| FR-040 | Gameplay.md | M4 | — |
| FR-050 | Ads.md | M4 | — |
| — | — | — | — |

---

## 11. Open Items

<!-- Questions and decisions pending stakeholder input. -->

| # | Item | Owner | Status |
|---|------|-------|--------|
| 1 | — | — | Open |
| 2 | — | — | Open |
