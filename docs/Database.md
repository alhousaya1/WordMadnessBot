# Level Repository

## Overview

Game knowledge is packaged JSON accessed through `LevelRepository`; gameplay never hardcodes level words.

## Storage format

`word_madness_bot.resources.levels/levels.json` contains a root `levels` array. Every item has a positive integer `number` and a non-empty `words` array.

## Validation and normalization

Loading rejects malformed JSON, unknown fields, invalid numbers, empty words, and duplicate level numbers with typed repository errors. Words are trimmed, Unicode NFC-normalized, uppercased, and deduplicated while retaining order.

## Lookup

`JsonLevelRepository.from_package()` loads installed package data. `get_level()` raises a typed missing-level error; `all_levels()` returns levels ordered by number.
