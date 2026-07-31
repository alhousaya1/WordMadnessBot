"""Pure validation rules for words and wheel-letter multisets."""

from collections import Counter

from word_madness_bot.domain.errors import ValidationIssue


class WordValidator:
    """Validate canonical words independently of persistence and gameplay layers."""

    @staticmethod
    def normalize(word: str) -> str:
        """Return the deterministic uppercase representation used for lookup."""

        return word.strip().upper()

    def can_form(self, word: str, letters: tuple[str, ...]) -> bool:
        """Return whether ``word`` can be formed from the supplied letter multiset."""

        normalized_word = self.normalize(word)
        available = Counter(letter.strip().upper() for letter in letters)
        required = Counter(normalized_word)
        return bool(normalized_word) and all(
            available[letter] >= count for letter, count in required.items()
        )

    def validate_words(
        self,
        words: tuple[str, ...],
        letters: tuple[str, ...],
        *,
        path: str,
    ) -> tuple[ValidationIssue, ...]:
        """Return deterministic semantic issues for a level's word list."""

        issues: list[ValidationIssue] = []
        seen: dict[str, int] = {}
        for index, word in enumerate(words):
            normalized = self.normalize(word)
            word_path = f"{path}[{index}]"
            previous_index = seen.get(normalized)
            if previous_index is not None:
                issues.append(
                    ValidationIssue(
                        path=word_path,
                        message=f"duplicates {path}[{previous_index}] after normalization",
                        code="duplicate_word",
                    )
                )
            else:
                seen[normalized] = index
            if not self.can_form(normalized, letters):
                issues.append(
                    ValidationIssue(
                        path=word_path,
                        message="cannot be formed from the level letter multiset",
                        code="unformable_word",
                    )
                )
        return tuple(issues)
