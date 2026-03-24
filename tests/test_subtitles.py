"""
Tests for subtitle parsing and filtering modules.

Covers:
- video_censor/subtitles/parser.py (parse_srt, _parse_timestamp)
- video_censor/subtitles/filter.py (censor_word, censor_text_line,
  parse_srt_content, format_srt_content, censor_srt_content, censor_subtitle_file)
"""

import pytest
from pathlib import Path

from video_censor.subtitles.parser import parse_srt, _parse_timestamp
from video_censor.subtitles.filter import (
    censor_word, censor_text_line, parse_srt_content, format_srt_content,
    censor_srt_content, censor_subtitle_file
)
from video_censor.editing.intervals import TimeInterval, MatchSource, Action


# ---------------------------------------------------------------------------
# Sample SRT content used across multiple tests
# ---------------------------------------------------------------------------

VALID_SRT = """\
1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,500 --> 00:00:08,200
This is a test subtitle

3
00:00:10,000 --> 00:00:13,750
Third block with multiple
lines of text
"""

MALFORMED_SRT = """\
1
00:00:01,000 --> 00:00:04,000
Good block

bad
no arrow here
some text

3
Only two lines here

4
00:00:10,000 --> 00:00:12,000
Also good
"""


# ===========================================================================
# _parse_timestamp tests
# ===========================================================================

class TestParseTimestamp:
    def test_comma_separator(self):
        assert _parse_timestamp("00:00:20,000") == 20.0

    def test_dot_separator(self):
        assert _parse_timestamp("00:00:20.000") == 20.0

    def test_hours_minutes_seconds(self):
        result = _parse_timestamp("01:02:03,500")
        expected = 1 * 3600 + 2 * 60 + 3.5
        assert result == pytest.approx(expected)

    def test_invalid_string_returns_zero(self):
        assert _parse_timestamp("not-a-timestamp") == 0.0

    def test_empty_string_returns_zero(self):
        assert _parse_timestamp("") == 0.0


# ===========================================================================
# parse_srt tests
# ===========================================================================

class TestParseSrt:
    def test_valid_srt_file(self, tmp_path: Path):
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(VALID_SRT, encoding="utf-8")

        intervals = parse_srt(srt_file)

        assert len(intervals) == 3
        assert intervals[0].start == pytest.approx(1.0)
        assert intervals[0].end == pytest.approx(4.0)
        assert intervals[0].reason == "Hello world"
        assert intervals[0].source == MatchSource.SUBTITLE
        assert intervals[0].action == Action.NONE
        assert intervals[0].metadata == {"text": "Hello world"}

    def test_multiline_text_joined(self, tmp_path: Path):
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(VALID_SRT, encoding="utf-8")

        intervals = parse_srt(srt_file)
        # Third block has two text lines joined with space
        assert intervals[2].reason == "Third block with multiple lines of text"

    def test_nonexistent_file_returns_empty(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.srt"
        assert parse_srt(missing) == []

    def test_malformed_blocks_skipped(self, tmp_path: Path):
        srt_file = tmp_path / "bad.srt"
        srt_file.write_text(MALFORMED_SRT, encoding="utf-8")

        intervals = parse_srt(srt_file)
        # Only blocks 1 and 4 are valid (block 2 has no '-->', block 3 has <3 lines)
        assert len(intervals) == 2
        assert intervals[0].reason == "Good block"
        assert intervals[1].reason == "Also good"

    def test_crlf_line_endings(self, tmp_path: Path):
        srt_file = tmp_path / "crlf.srt"
        srt_file.write_text(VALID_SRT.replace("\n", "\r\n"), encoding="utf-8")

        intervals = parse_srt(srt_file)
        assert len(intervals) == 3


# ===========================================================================
# censor_word tests
# ===========================================================================

class TestCensorWord:
    def test_preserves_trailing_punctuation(self):
        assert censor_word("damn!") == "[...]!"

    def test_preserves_leading_punctuation(self):
        assert censor_word("(damn") == "([...]"

    def test_preserves_both_punctuation(self):
        assert censor_word("(damn!)") == "([...]!)"

    def test_no_punctuation(self):
        assert censor_word("damn") == "[...]"

    def test_custom_replacement(self):
        assert censor_word("damn!", replacement="***") == "***!"

    def test_only_punctuation(self):
        # Edge case: all punctuation, no alphanumeric core
        result = censor_word("!!!")
        assert "[...]" in result


# ===========================================================================
# censor_text_line tests
# ===========================================================================

class TestCensorTextLine:
    def test_profanity_in_middle(self):
        result = censor_text_line("What the damn thing", {"damn"})
        assert result == "What the [...] thing"

    def test_case_insensitive(self):
        result = censor_text_line("That is DAMN loud", {"damn"})
        assert result == "That is [...] loud"

    def test_no_profanity_unchanged(self):
        text = "This is a clean sentence"
        assert censor_text_line(text, {"damn", "hell"}) == text

    def test_multiple_profanity_words(self):
        result = censor_text_line("damn this hell", {"damn", "hell"})
        assert result == "[...] this [...]"

    def test_profanity_with_punctuation(self):
        result = censor_text_line("Oh damn!", {"damn"})
        assert result == "Oh [...]!"

    def test_custom_replacement(self):
        result = censor_text_line("What the damn", {"damn"}, replacement="***")
        assert result == "What the ***"


# ===========================================================================
# parse_srt_content tests
# ===========================================================================

class TestParseSrtContent:
    def test_valid_content(self):
        entries = parse_srt_content(VALID_SRT)
        assert len(entries) == 3
        assert entries[0]["index"] == 1
        assert entries[0]["timestamp"] == "00:00:01,000 --> 00:00:04,000"
        assert entries[0]["text"] == ["Hello world"]

    def test_crlf_line_endings(self):
        entries = parse_srt_content(VALID_SRT.replace("\n", "\r\n"))
        assert len(entries) == 3
        assert entries[1]["text"] == ["This is a test subtitle"]

    def test_skips_invalid_index(self):
        content = """\
abc
00:00:01,000 --> 00:00:04,000
Some text

2
00:00:05,000 --> 00:00:08,000
Valid block
"""
        entries = parse_srt_content(content)
        assert len(entries) == 1
        assert entries[0]["index"] == 2

    def test_multiline_text(self):
        entries = parse_srt_content(VALID_SRT)
        assert entries[2]["text"] == ["Third block with multiple", "lines of text"]

    def test_empty_content(self):
        assert parse_srt_content("") == []


# ===========================================================================
# format_srt_content tests
# ===========================================================================

class TestFormatSrtContent:
    def test_roundtrip(self):
        entries = parse_srt_content(VALID_SRT)
        formatted = format_srt_content(entries)
        re_parsed = parse_srt_content(formatted)

        assert len(re_parsed) == len(entries)
        for orig, rtrip in zip(entries, re_parsed):
            assert orig["index"] == rtrip["index"]
            assert orig["timestamp"] == rtrip["timestamp"]
            assert orig["text"] == rtrip["text"]

    def test_output_ends_with_newline(self):
        entries = parse_srt_content(VALID_SRT)
        formatted = format_srt_content(entries)
        assert formatted.endswith("\n")


# ===========================================================================
# censor_srt_content tests
# ===========================================================================

class TestCensorSrtContent:
    def test_end_to_end(self):
        srt = """\
1
00:00:01,000 --> 00:00:04,000
What the damn thing

2
00:00:05,000 --> 00:00:08,000
This is clean
"""
        result = censor_srt_content(srt, {"damn"})
        entries = parse_srt_content(result)
        assert entries[0]["text"] == ["What the [...] thing"]
        assert entries[1]["text"] == ["This is clean"]

    def test_custom_replacement(self):
        srt = """\
1
00:00:01,000 --> 00:00:04,000
Oh hell no
"""
        result = censor_srt_content(srt, {"hell"}, replacement="***")
        entries = parse_srt_content(result)
        assert entries[0]["text"] == ["Oh *** no"]


# ===========================================================================
# censor_subtitle_file tests
# ===========================================================================

class TestCensorSubtitleFile:
    def test_writes_output_file(self, tmp_path: Path):
        input_file = tmp_path / "input.srt"
        output_file = tmp_path / "output.srt"

        srt = """\
1
00:00:01,000 --> 00:00:04,000
What the damn thing

2
00:00:05,000 --> 00:00:08,000
This is clean
"""
        input_file.write_text(srt, encoding="utf-8")

        result = censor_subtitle_file(input_file, output_file, {"damn"})
        assert result == output_file
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert "[...]" in content
        assert "damn" not in content
        # Clean line should be preserved
        assert "This is clean" in content

    def test_returns_none_on_read_error(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.srt"
        output = tmp_path / "output.srt"

        result = censor_subtitle_file(missing, output, {"damn"})
        assert result is None

    def test_creates_output_directory(self, tmp_path: Path):
        input_file = tmp_path / "input.srt"
        input_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nhello\n", encoding="utf-8")

        nested_output = tmp_path / "subdir" / "deep" / "output.srt"
        result = censor_subtitle_file(input_file, nested_output, set())
        assert result == nested_output
        assert nested_output.exists()
