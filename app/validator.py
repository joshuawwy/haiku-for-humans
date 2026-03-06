import re

from cmudict import dict as cmu_dict

from app.models import ValidationResult

EXPECTED = [5, 7, 5]

# Load CMU dict once at import time
_CMU = cmu_dict()


def _count_syllables_cmu(word: str) -> int | None:
    """Count syllables using CMU Pronouncing Dictionary."""
    phones = _CMU.get(word.lower())
    if not phones:
        return None
    # Count vowel phonemes (digits in ARPAbet indicate stress on vowels)
    return sum(1 for ph in phones[0] if ph[-1].isdigit())


def _count_syllables_heuristic(word: str) -> int:
    """Fallback syllable counter for words not in CMU dict."""
    word = word.lower().strip()
    if not word:
        return 0

    # Remove trailing silent e
    if word.endswith("e") and len(word) > 2 and word[-2] not in "aeiou":
        word = word[:-1]

    # Count vowel groups
    count = len(re.findall(r"[aeiouy]+", word))
    return max(1, count)


# Letters that are 1 syllable when spoken: B, C, D, G, P, T, V, Z, Q, K
# Letters that are 2+ syllables: W (3), Y (1 — but contextual)
# For simplicity, use CMU dict per-letter which handles this correctly.
_LETTER_SYLLABLES = {}
for _ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _phones = _CMU.get(_ch.lower())
    if _phones:
        _LETTER_SYLLABLES[_ch] = sum(1 for ph in _phones[0] if ph[-1].isdigit())
    else:
        _LETTER_SYLLABLES[_ch] = 1


def count_syllables(word: str) -> int:
    """Count syllables for a single word, CMU dict first, heuristic fallback."""
    clean = re.sub(r"[^a-zA-Z']", "", word)
    if not clean:
        return 0

    # Acronyms: all-uppercase, 2-4 letters → spell out each letter
    if clean.isupper() and 2 <= len(clean) <= 4:
        return sum(_LETTER_SYLLABLES.get(ch, 1) for ch in clean)

    cmu = _count_syllables_cmu(clean)
    if cmu is not None:
        return cmu
    return _count_syllables_heuristic(clean)


def count_line_syllables(line: str) -> int:
    """Count total syllables in a line of text."""
    words = line.strip().split()
    return sum(count_syllables(w) for w in words)


def validate_haiku(text: str) -> ValidationResult:
    """Validate that text is a proper 5-7-5 haiku."""
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

    if len(lines) != 3:
        return ValidationResult(
            valid=False,
            message=f"A haiku needs exactly 3 lines, but you sent {len(lines)}. "
            "Send your haiku with each line on a new line.",
        )

    syllables = [count_line_syllables(line) for line in lines]

    if syllables == EXPECTED:
        return ValidationResult(
            valid=True,
            message="Beautiful haiku! It's been published.",
            line_syllables=syllables,
        )

    problems = []
    for i, (got, want) in enumerate(zip(syllables, EXPECTED)):
        if got != want:
            problems.append(f"Line {i + 1}: {got} syllables (needs {want})")

    return ValidationResult(
        valid=False,
        message="Not quite 5-7-5:\n" + "\n".join(problems),
        line_syllables=syllables,
    )
