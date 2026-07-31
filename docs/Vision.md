# Vision

## Input and preprocessing

Vision accepts encoded image bytes or in-memory images, decodes them with typed failures, normalizes color/grayscale data, and performs deterministic preprocessing without Android input.

## Templates and shapes

Template matching returns scored normalized regions above an explicit threshold. Circle detection and letter extraction operate on image evidence and return typed observations using resolution-independent coordinates.

## OCR abstraction

OCR is accessed through a replaceable engine contract. Output is normalized into typed results with confidence; empty, malformed, and engine-failure paths remain explicit.

## Classification and game state

The vision classifier combines template, circle, and OCR evidence and preserves an Unknown result when evidence is insufficient. Game-state stability is handled by the gameplay state detector, not by the vision components.

## Safety and testing

Vision modules never import Android input infrastructure. Synthetic fixtures cover preprocessing, matching, extraction, OCR error handling, confidence, and Unknown behavior. Debug artifacts are not package data or tracked runtime outputs.
