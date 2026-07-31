"""In-memory level progress that prevents duplicate word submission."""

from dataclasses import dataclass, field

from word_madness_bot.domain.models import LevelDefinition


@dataclass(slots=True)
class LevelProgress:
    """Track one active level, submitted words, and the pending word command."""

    level: LevelDefinition | None = None
    submitted_words: set[str] = field(default_factory=set)
    pending_word: str | None = None
    word_attempts: dict[str, int] = field(default_factory=dict)

    def begin(self, level: LevelDefinition) -> None:
        """Reset progress only when the observed level number changes."""

        if self.level is None or self.level.number != level.number:
            self.level = level
            self.submitted_words.clear()
            self.pending_word = None
            self.word_attempts.clear()

    def next_word(self) -> str | None:
        """Return the first deterministic unsubmitted word when none is pending."""

        if self.level is None or self.pending_word is not None:
            return None
        return next((word for word in self.level.words if word not in self.submitted_words), None)

    def mark_pending(self, word: str) -> None:
        """Record exactly one pending word and reject duplicates."""

        if word in self.submitted_words:
            raise ValueError(f"word already submitted: {word}")
        if self.pending_word is not None:
            raise ValueError("another word is already pending verification")
        self.pending_word = word
        self.word_attempts[word] = self.word_attempts.get(word, 0) + 1

    def verify_pending(self, succeeded: bool) -> str | None:
        """Clear the pending word and record it only after successful verification."""

        word = self.pending_word
        if word is None:
            return None
        if succeeded:
            self.submitted_words.add(word)
        self.pending_word = None
        return word
