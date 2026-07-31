# Vision Templates

Template assets are optional, versioned inputs to the Vision layer. Each asset must be
listed in `manifest.json` with its source resolution and a normalized search region.
Runtime code scales that region against the current screenshot and must never embed
reference-device pixel coordinates.

No production templates are required by Milestone 5. Later state-classification work may
add reviewed assets without changing the `TemplateMatcher` implementation.
