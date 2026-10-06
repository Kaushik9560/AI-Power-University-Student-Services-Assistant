"""Shared constants used by more than one node. Keep this file small."""
from __future__ import annotations

import re

NOT_FOUND_MESSAGE = "I could not find this information in the authorised university sources."
LOGIN_REQUIRED_MESSAGE = ("This question is about personal records, but no student identity was provided. "
                          "Please sign in so I can look up your own data.")
OTHER_STUDENT_MESSAGE = "I can only answer questions about your own student record, not another student's."

STUDENT_ID_PATTERN = re.compile(r"\bS\d{4}\b", re.I)

STOPWORDS = {"what", "is", "the", "for", "of", "a", "an", "to", "in", "on", "and", "or", "my", "i", "am",
             "are", "do", "does", "can", "will", "be", "if", "it", "this", "that", "with", "by", "me",
             "please", "tell", "about", "how", "much", "many", "there", "which", "when", "should", "would"}


def question_terms(question: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", question.lower()) if t not in STOPWORDS]
