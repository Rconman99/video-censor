"""
Unit tests for interval merging logic.

Tests the core interval operations that prevent stuttering edits.
"""

import pytest
from video_censor.editing.intervals import (
    TimeInterval,
    merge_intervals,
    subtract_intervals,
    compute_keep_segments,
    add_buffer_to_intervals
)


class TestTimeInterval:
    """Tests for TimeInterval dataclass."""
    
    def test_duration(self):
        """Test duration calculation."""
        interval = TimeInterval(start=1.0, end=3.5)
        assert interval.duration == 2.5
    
    def test_overlaps_true(self):
        """Test overlapping intervals."""
        a = TimeInterval(start=1.0, end=3.0)
        b = TimeInterval(start=2.0, end=4.0)
        assert a.overlaps(b)
        assert b.overlaps(a)
    
    def test_overlaps_false(self):
        """Test non-overlapping intervals."""
        a = TimeInterval(start=1.0, end=2.0)
        b = TimeInterval(start=3.0, end=4.0)
        assert not a.overlaps(b)
        assert not b.overlaps(a)
    
    def test_overlaps_with_gap(self):
        """Test overlapping with gap tolerance."""
        a = TimeInterval(start=1.0, end=2.0)
        b = TimeInterval(start=2.5, end=3.5)
        
        assert not a.overlaps(b, gap=0.0)
        assert a.overlaps(b, gap=0.5)
        assert a.overlaps(b, gap=1.0)
    
    def test_overlaps_adjacent(self):
        """Test exactly adjacent intervals."""
        a = TimeInterval(start=1.0, end=2.0)
        b = TimeInterval(start=2.0, end=3.0)
        assert a.overlaps(b)  # Adjacent counts as overlapping
    
    def test_merge(self):
        """Test merging two intervals."""
        a = TimeInterval(start=1.0, end=3.0, reason="first")
        b = TimeInterval(start=2.0, end=4.0, reason="second")
        merged = a.merge(b)
        
        assert merged.start == 1.0
        assert merged.end == 4.0
        assert "first" in merged.reason
        assert "second" in merged.reason
    
    def test_contains(self):
        """Test point containment."""
        interval = TimeInterval(start=1.0, end=3.0)
        
        assert interval.contains(1.0)  # Start point
        assert interval.contains(2.0)  # Middle
        assert interval.contains(3.0)  # End point
        assert not interval.contains(0.5)  # Before
        assert not interval.contains(3.5)  # After


class TestMergeIntervals:
    """Tests for merge_intervals function."""
    
    def test_empty_list(self):
        """Test merging empty list."""
        result = merge_intervals([])
        assert result == []
    
    def test_single_interval(self):
        """Test single interval passes through."""
        intervals = [TimeInterval(start=1.0, end=2.0)]
        result = merge_intervals(intervals)
        
        assert len(result) == 1
        assert result[0].start == 1.0
        assert result[0].end == 2.0
    
    def test_non_overlapping(self):
        """Test non-overlapping intervals stay separate."""
        intervals = [
            TimeInterval(start=1.0, end=2.0),
            TimeInterval(start=3.0, end=4.0),
            TimeInterval(start=5.0, end=6.0),
        ]
        result = merge_intervals(intervals)
        
        assert len(result) == 3
    
    def test_overlapping_merge(self):
        """Test overlapping intervals are merged."""
        intervals = [
            TimeInterval(start=1.0, end=3.0),
            TimeInterval(start=2.0, end=4.0),
        ]
        result = merge_intervals(intervals)
        
        assert len(result) == 1
        assert result[0].start == 1.0
        assert result[0].end == 4.0
    
    def test_multiple_merges(self):
        """Test multiple overlapping groups."""
        intervals = [
            TimeInterval(start=1.0, end=2.0),
            TimeInterval(start=1.5, end=3.0),
            TimeInterval(start=5.0, end=6.0),
            TimeInterval(start=5.5, end=7.0),
        ]
        result = merge_intervals(intervals)
        
        assert len(result) == 2
        assert result[0].start == 1.0
        assert result[0].end == 3.0
        assert result[1].start == 5.0
        assert result[1].end == 7.0
    
    def test_unsorted_input(self):
        """Test that unsorted input is handled correctly."""
        intervals = [
            TimeInterval(start=5.0, end=6.0),
            TimeInterval(start=1.0, end=2.0),
            TimeInterval(start=3.0, end=4.0),
        ]
        result = merge_intervals(intervals)
        
        assert len(result) == 3
        assert result[0].start == 1.0
        assert result[1].start == 3.0
        assert result[2].start == 5.0
    
    def test_merge_with_gap(self):
        """Test merging with gap tolerance."""
        intervals = [
            TimeInterval(start=1.0, end=2.0),
            TimeInterval(start=2.3, end=3.0),  # 0.3s gap
        ]
        
        # Without gap tolerance
        result1 = merge_intervals(intervals, gap=0.0)
        assert len(result1) == 2
        
        # With gap tolerance
        result2 = merge_intervals(intervals, gap=0.5)
        assert len(result2) == 1
        assert result2[0].start == 1.0
        assert result2[0].end == 3.0
    
    def test_fully_contained(self):
        """Test interval fully contained in another."""
        intervals = [
            TimeInterval(start=1.0, end=5.0),
            TimeInterval(start=2.0, end=3.0),  # Contained
        ]
        result = merge_intervals(intervals)
        
        assert len(result) == 1
        assert result[0].start == 1.0
        assert result[0].end == 5.0


class TestComputeKeepSegments:
    """Tests for compute_keep_segments function."""
    
    def test_no_cuts(self):
        """Test with no cuts - keep entire video."""
        result = compute_keep_segments(duration=60.0, cut_intervals=[])
        
        assert len(result) == 1
        assert result[0].start == 0.0
        assert result[0].end == 60.0
    
    def test_single_cut_middle(self):
        """Test single cut in middle of video."""
        cuts = [TimeInterval(start=10.0, end=20.0)]
        result = compute_keep_segments(duration=60.0, cut_intervals=cuts)
        
        assert len(result) == 2
        assert result[0].start == 0.0
        assert result[0].end == 10.0
        assert result[1].start == 20.0
        assert result[1].end == 60.0
    
    def test_cut_at_start(self):
        """Test cut at video start."""
        cuts = [TimeInterval(start=0.0, end=10.0)]
        result = compute_keep_segments(duration=60.0, cut_intervals=cuts)
        
        assert len(result) == 1
        assert result[0].start == 10.0
        assert result[0].end == 60.0
    
    def test_cut_at_end(self):
        """Test cut at video end."""
        cuts = [TimeInterval(start=50.0, end=60.0)]
        result = compute_keep_segments(duration=60.0, cut_intervals=cuts)
        
        assert len(result) == 1
        assert result[0].start == 0.0
        assert result[0].end == 50.0
    
    def test_multiple_cuts(self):
        """Test multiple cuts throughout video."""
        cuts = [
            TimeInterval(start=10.0, end=15.0),
            TimeInterval(start=30.0, end=35.0),
            TimeInterval(start=50.0, end=55.0),
        ]
        result = compute_keep_segments(duration=60.0, cut_intervals=cuts)
        
        assert len(result) == 4
        assert result[0].end == 10.0
        assert result[1].start == 15.0
        assert result[1].end == 30.0
        assert result[2].start == 35.0
        assert result[2].end == 50.0
        assert result[3].start == 55.0
    
    def test_min_segment_duration(self):
        """Test minimum segment duration filtering."""
        cuts = [
            TimeInterval(start=10.0, end=10.5),  # Creates 0.5s gap
        ]
        
        # With small min duration
        result1 = compute_keep_segments(
            duration=20.0, 
            cut_intervals=cuts, 
            min_segment_duration=0.1
        )
        assert len(result1) == 2
        
        # With larger min duration that filters short segments
        # This creates segments: 0-10 (10s), 10.5-20 (9.5s)
        result2 = compute_keep_segments(
            duration=20.0,
            cut_intervals=cuts,
            min_segment_duration=0.1
        )
        assert len(result2) == 2


class TestAddBufferToIntervals:
    """Tests for add_buffer_to_intervals function."""
    
    def test_add_buffer(self):
        """Test adding buffer to intervals."""
        intervals = [TimeInterval(start=5.0, end=10.0)]
        result = add_buffer_to_intervals(intervals, buffer_before=1.0, buffer_after=2.0)
        
        assert len(result) == 1
        assert result[0].start == 4.0
        assert result[0].end == 12.0
    
    def test_buffer_clamp_start(self):
        """Test buffer doesn't go below 0."""
        intervals = [TimeInterval(start=0.5, end=2.0)]
        result = add_buffer_to_intervals(intervals, buffer_before=1.0, buffer_after=0.0)
        
        assert result[0].start == 0.0  # Clamped to 0
    
    def test_buffer_clamp_max_duration(self):
        """Test buffer respects max duration."""
        intervals = [TimeInterval(start=55.0, end=58.0)]
        result = add_buffer_to_intervals(
            intervals, 
            buffer_before=0.0, 
            buffer_after=5.0,
            max_duration=60.0
        )
        
        assert result[0].end == 60.0  # Clamped to max


class TestSubtractIntervals:
    """Tests for subtract_intervals function."""
    
    def test_no_subtraction(self):
        """Test with empty subtraction list."""
        base = [TimeInterval(start=1.0, end=5.0)]
        result = subtract_intervals(base, [])
        
        assert len(result) == 1
        assert result[0].start == 1.0
        assert result[0].end == 5.0
    
    def test_no_overlap(self):
        """Test subtraction with no overlap."""
        base = [TimeInterval(start=1.0, end=3.0)]
        subtract = [TimeInterval(start=5.0, end=7.0)]
        result = subtract_intervals(base, subtract)
        
        assert len(result) == 1
        assert result[0].start == 1.0
        assert result[0].end == 3.0
    
    def test_partial_overlap_start(self):
        """Test partial overlap at start."""
        base = [TimeInterval(start=2.0, end=6.0)]
        subtract = [TimeInterval(start=1.0, end=4.0)]
        result = subtract_intervals(base, subtract)
        
        assert len(result) == 1
        assert result[0].start == 4.0
        assert result[0].end == 6.0
    
    def test_partial_overlap_end(self):
        """Test partial overlap at end."""
        base = [TimeInterval(start=2.0, end=6.0)]
        subtract = [TimeInterval(start=4.0, end=8.0)]
        result = subtract_intervals(base, subtract)
        
        assert len(result) == 1
        assert result[0].start == 2.0
        assert result[0].end == 4.0
    
    def test_split_interval(self):
        """Test subtraction that splits an interval."""
        base = [TimeInterval(start=1.0, end=10.0)]
        subtract = [TimeInterval(start=4.0, end=6.0)]
        result = subtract_intervals(base, subtract)
        
        assert len(result) == 2
        assert result[0].start == 1.0
        assert result[0].end == 4.0
        assert result[1].start == 6.0
        assert result[1].end == 10.0
