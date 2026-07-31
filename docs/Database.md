# Database

## 1. Overview

The database layer is the sole owner of static game knowledge. It provides immutable
level definitions through the `LevelRepository` contract and has no dependency on ADB,
screenshots, vision, OCR, gameplay decisions, or swipe generation. The initial adapter
loads a local JSON document once, validates the complete document, and builds immutable
indexes. A different storage adapter may replace JSON without changing callers.

## 2. Dictionary

Words use uppercase ASCII letters. Lookup trims surrounding whitespace and converts the
query to uppercase. Lookup is exact after that normalization: prefixes and fuzzy matches
are not accepted. A reverse word index returns matching levels in ascending level-number
order.

## 3. Word Lists

Each level has one or more unique solution words. Word order in `levels.json` is
significant and is preserved in `LevelDefinition`; it is the deterministic submission
order for later layers. Every word must be at least two characters and must be formable
from the level's letter multiset. A wheel letter may not be reused more often than it
appears in that multiset.

## 4. Level Data

Level numbers are unique positive integers. Exact lookup returns the immutable definition
or `None` when no definition exists. Enumerating the JSON repository always returns
levels in ascending numerical order, regardless of their source order.

## 5. Storage Format

`database/levels.json` uses schema version 1:

```json
{
  "schema_version": 1,
  "levels": [
    {
      "number": 1,
      "letters": ["A", "C", "T"],
      "words": ["ACT", "CAT"]
    }
  ]
}
```

Validation is strict:

- The root must contain exactly `schema_version` and `levels`.
- `schema_version` must equal integer `1`.
- `levels` must be a non-empty array.
- Every level must contain exactly `number`, `letters`, and `words`.
- Additional properties are rejected at every object level.
- Letters are single uppercase ASCII characters.
- Words contain at least two uppercase ASCII characters.
- Duplicate levels, normalized duplicate words, and unformable words are rejected.
- All detected failures are returned together as path-addressed validation issues when
  the document structure permits continued validation.

Run `PYTHONPATH=src python tools/validate_database.py` to validate the production file.
