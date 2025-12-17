"""Unit tests for pyramid level selection algorithm.

Tests PyramidLevelSelector including:
- Standard case with oversampling bias
- Undershoot correction logic
- Tie-breaker preferring finer levels
- Edge cases (small regions, exact matches)
- Property-based invariant verification
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from giant.core.level_selector import PyramidLevelSelector, SelectedLevel
from giant.geometry import Region
from giant.wsi.types import WSIMetadata

# --- Fixtures ---


@pytest.fixture
def selector() -> PyramidLevelSelector:
    """Create a default pyramid level selector."""
    return PyramidLevelSelector()


@pytest.fixture
def standard_metadata() -> WSIMetadata:
    """Create standard 3-level pyramid metadata.

    Levels: ds=[1, 4, 16]
    """
    return WSIMetadata(
        path="/path/to/slide.svs",
        width=100000,
        height=80000,
        level_count=3,
        level_dimensions=(
            (100000, 80000),
            (25000, 20000),
            (6250, 5000),
        ),
        level_downsamples=(1.0, 4.0, 16.0),
        vendor="aperio",
        mpp_x=0.25,
        mpp_y=0.25,
    )


@pytest.fixture
def two_level_metadata() -> WSIMetadata:
    """Create 2-level pyramid metadata.

    Levels: ds=[1, 4]
    """
    return WSIMetadata(
        path="/path/to/slide.svs",
        width=50000,
        height=40000,
        level_count=2,
        level_dimensions=(
            (50000, 40000),
            (12500, 10000),
        ),
        level_downsamples=(1.0, 4.0),
        vendor="aperio",
        mpp_x=0.25,
        mpp_y=0.25,
    )


@pytest.fixture
def single_level_metadata() -> WSIMetadata:
    """Create single-level (no pyramid) metadata."""
    return WSIMetadata(
        path="/path/to/slide.svs",
        width=10000,
        height=8000,
        level_count=1,
        level_dimensions=((10000, 8000),),
        level_downsamples=(1.0,),
        vendor="generic",
        mpp_x=None,
        mpp_y=None,
    )


# --- Test SelectedLevel ---


class TestSelectedLevel:
    """Tests for SelectedLevel NamedTuple."""

    def test_selected_level_creation(self) -> None:
        """Test SelectedLevel can be created."""
        result = SelectedLevel(level=2, downsample=4.0)
        assert result.level == 2
        assert result.downsample == 4.0

    def test_selected_level_is_tuple(self) -> None:
        """Test SelectedLevel is a proper NamedTuple."""
        result = SelectedLevel(level=1, downsample=2.0)
        assert isinstance(result, tuple)
        assert result[0] == 1
        assert result[1] == 2.0

    def test_selected_level_unpacking(self) -> None:
        """Test SelectedLevel can be unpacked."""
        result = SelectedLevel(level=0, downsample=1.0)
        level, downsample = result
        assert level == 0
        assert downsample == 1.0


# --- Test Standard Cases (from spec) ---


class TestPyramidLevelSelectorStandardCases:
    """Tests for standard level selection scenarios from spec."""

    def test_standard_case_spec_example(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test standard case from spec: Region 10,000px, S=1000, bias=0.85.

        From spec:
        - target_native = 1000 / 0.85 ≈ 1176
        - Levels: ds=[1, 4, 16] → L=[10000, 2500, 625]
        - Closest to 1176: L1=2500 (diff=1324) vs L2=625 (diff=551) → L2 is closer
        - Undershoot check: 625 < 1000 → move to L1
        - L1=2500 >= 1000 → Result: Level 1
        """
        region = Region(x=0, y=0, width=10000, height=8000)  # Long side = 10000
        result = selector.select_level(region, standard_metadata, target_size=1000)

        assert result.level == 1
        assert result.downsample == 4.0

    def test_undershoot_correction_spec_example(
        self, selector: PyramidLevelSelector, two_level_metadata: WSIMetadata
    ) -> None:
        """Test undershoot correction from spec: Region 2000px, S=1000, bias=0.85.

        From spec:
        - target_native ≈ 1176
        - Levels: ds=[1, 4] → L=[2000, 500]
        - Closest to 1176: L0=2000 (diff=824) vs L1=500 (diff=676) → L1 is closer
        - Undershoot check: 500 < 1000 → move to L0
        - L0=2000 >= 1000 → Result: Level 0
        """
        region = Region(x=0, y=0, width=2000, height=1600)  # Long side = 2000
        result = selector.select_level(region, two_level_metadata, target_size=1000)

        assert result.level == 0
        assert result.downsample == 1.0

    def test_small_region_at_level0(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test small region: Region 500px at Level-0 with S=1000.

        Even Level-0 undershoots. Return Level 0 (can't go finer).
        """
        region = Region(x=0, y=0, width=500, height=400)  # Long side = 500
        result = selector.select_level(region, standard_metadata, target_size=1000)

        assert result.level == 0
        assert result.downsample == 1.0

    def test_exact_match_selects_level(self, selector: PyramidLevelSelector) -> None:
        """Test exact match: Region where Lk == target_native exactly."""
        # Create metadata where Lk matches target_native exactly
        # With target_size=1000, bias=0.85: target_native ≈ 1176.47
        # If L0 = 1176.47 at some level, it should select that level
        metadata = WSIMetadata(
            path="/path/to/slide.svs",
            width=10000,
            height=8000,
            level_count=3,
            level_dimensions=(
                (10000, 8000),
                (2500, 2000),
                (625, 500),
            ),
            level_downsamples=(1.0, 4.0, 16.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )

        # Region with long side = 4705.88, so at level 1 (ds=4): 4705.88/4 ≈ 1176.47
        region = Region(x=0, y=0, width=4706, height=3000)
        selector = PyramidLevelSelector()
        result = selector.select_level(region, metadata, target_size=1000, bias=0.85)

        # Level 1 gives us ~1176, which is very close to target_native
        # And 1176 >= 1000, so no undershoot correction needed
        assert result.level == 1

    def test_single_level_always_returns_level0(
        self, selector: PyramidLevelSelector, single_level_metadata: WSIMetadata
    ) -> None:
        """Test single-level pyramid always returns level 0."""
        region = Region(x=0, y=0, width=5000, height=4000)
        result = selector.select_level(region, single_level_metadata, target_size=1000)

        assert result.level == 0
        assert result.downsample == 1.0


# --- Test Tie-Breaker Logic ---


class TestPyramidLevelSelectorTieBreaker:
    """Tests for tie-breaker logic (prefer finer level)."""

    def test_tiebreaker_prefers_finer_level(self) -> None:
        """Test tie-breaker selects finer level (smaller k) when equidistant."""
        metadata = WSIMetadata(
            path="/path/to/slide.svs",
            width=8000,
            height=6000,
            level_count=2,
            level_dimensions=(
                (8000, 6000),
                (4000, 3000),
            ),
            level_downsamples=(1.0, 2.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )

        # target_native = target_size / bias = 1500 / 0.5 = 3000
        # size_at_level: L0=4000, L1=2000 -> both are exactly 1000px away from 3000
        # Tie-breaker must prefer the finer level (k=0).
        region = Region(x=0, y=0, width=4000, height=3000)
        selector = PyramidLevelSelector()
        result = selector.select_level(region, metadata, target_size=1500, bias=0.5)

        assert result.level == 0
        assert result.downsample == 1.0


# --- Test Custom Parameters ---


class TestPyramidLevelSelectorCustomParams:
    """Tests for custom target_size and bias parameters."""

    def test_custom_target_size(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test level selection with custom target_size."""
        region = Region(x=0, y=0, width=10000, height=8000)

        # With target_size=500, target_native = 500/0.85 ≈ 588
        # Levels: ds=[1, 4, 16] → L=[10000, 2500, 625]
        # Closest to 588: L2=625 (diff=37)
        # Undershoot check: 625 >= 500 → no correction
        result = selector.select_level(region, standard_metadata, target_size=500)

        assert result.level == 2

    def test_custom_bias(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test level selection with custom bias."""
        region = Region(x=0, y=0, width=10000, height=8000)

        # With target_size=1000, bias=1.0 (no oversampling bias):
        # target_native = 1000/1.0 = 1000
        # Levels: ds=[1, 4, 16] → L=[10000, 2500, 625]
        # Closest to 1000: L2=625 (diff=375) vs L1=2500 (diff=1500)
        # L2 is closer, but 625 < 1000 → undershoot correction → L1
        result = selector.select_level(
            region, standard_metadata, target_size=1000, bias=1.0
        )

        assert result.level == 1

    def test_lower_bias_tends_to_select_finer_level(
        self, selector: PyramidLevelSelector
    ) -> None:
        """Test that smaller bias tends to select finer levels (more oversampling)."""
        metadata = WSIMetadata(
            path="/path/to/slide.svs",
            width=3000,
            height=2000,
            level_count=3,
            level_dimensions=(
                (3000, 2000),
                (2000, 1333),
                (1500, 1000),
            ),
            level_downsamples=(1.0, 1.5, 2.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )
        region = Region(x=0, y=0, width=1500, height=1000)  # Long side = 1500

        default_bias_result = selector.select_level(
            region, metadata, target_size=1000, bias=0.85
        )
        low_bias_result = selector.select_level(
            region, metadata, target_size=1000, bias=0.5
        )

        assert default_bias_result.level == 1
        assert low_bias_result.level == 0


# --- Test Edge Cases ---


class TestPyramidLevelSelectorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_large_region(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test selection with very large region (entire slide)."""
        region = Region(x=0, y=0, width=100000, height=80000)  # Full slide
        result = selector.select_level(region, standard_metadata, target_size=1000)

        # With long_side=100000 and target_native≈1176:
        # L0=100000, L1=25000, L2=6250
        # L2=6250 is closest to 1176 (diff=5074)
        # 6250 >= 1000 → select L2
        assert result.level == 2

    def test_height_as_long_side(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test region where height is the long side."""
        region = Region(x=0, y=0, width=5000, height=10000)  # Long side = height
        result = selector.select_level(region, standard_metadata, target_size=1000)

        # Same as standard case since long_side = 10000
        assert result.level == 1

    def test_square_region(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test square region where width == height."""
        region = Region(x=0, y=0, width=10000, height=10000)
        result = selector.select_level(region, standard_metadata, target_size=1000)

        # Long side = 10000 (same as standard case)
        assert result.level == 1

    def test_region_at_arbitrary_position(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test that region position doesn't affect level selection."""
        region1 = Region(x=0, y=0, width=10000, height=8000)
        region2 = Region(x=50000, y=30000, width=10000, height=8000)

        result1 = selector.select_level(region1, standard_metadata, target_size=1000)
        result2 = selector.select_level(region2, standard_metadata, target_size=1000)

        assert result1 == result2

    def test_minimum_dimension_region(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test region with minimum dimensions (1x1)."""
        region = Region(x=0, y=0, width=1, height=1)
        result = selector.select_level(region, standard_metadata, target_size=1000)

        # Long side = 1, way below target_size
        # Must return level 0
        assert result.level == 0
        assert result.downsample == 1.0


# --- Test Input Validation ---


class TestPyramidLevelSelectorValidation:
    """Tests for input validation."""

    def test_rejects_zero_target_size(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test select_level rejects zero target_size."""
        region = Region(x=0, y=0, width=1000, height=1000)
        with pytest.raises(ValueError, match="target_size must be positive"):
            selector.select_level(region, standard_metadata, target_size=0)

    def test_rejects_negative_target_size(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test select_level rejects negative target_size."""
        region = Region(x=0, y=0, width=1000, height=1000)
        with pytest.raises(ValueError, match="target_size must be positive"):
            selector.select_level(region, standard_metadata, target_size=-100)

    def test_rejects_zero_bias(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test select_level rejects zero bias."""
        region = Region(x=0, y=0, width=1000, height=1000)
        with pytest.raises(ValueError, match="bias must be positive"):
            selector.select_level(region, standard_metadata, bias=0.0)

    def test_rejects_negative_bias(
        self, selector: PyramidLevelSelector, standard_metadata: WSIMetadata
    ) -> None:
        """Test select_level rejects negative bias."""
        region = Region(x=0, y=0, width=1000, height=1000)
        with pytest.raises(ValueError, match="bias must be positive"):
            selector.select_level(region, standard_metadata, bias=-0.5)


# --- Property-Based Tests ---


class TestPyramidLevelSelectorProperties:
    """Property-based tests for invariants."""

    @given(
        region_long_side=st.integers(min_value=100, max_value=100000),
        target_s=st.integers(min_value=500, max_value=2000),
        bias=st.floats(min_value=0.7, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_selected_level_within_bounds(
        self,
        region_long_side: int,
        target_s: int,
        bias: float,
    ) -> None:
        """Verify selected level index is always within bounds."""
        metadata = WSIMetadata(
            path="/path/to/slide.svs",
            width=100000,
            height=80000,
            level_count=4,
            level_dimensions=(
                (100000, 80000),
                (50000, 40000),
                (25000, 20000),
                (12500, 10000),
            ),
            level_downsamples=(1.0, 2.0, 4.0, 8.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )

        region_height = region_long_side // 2 + 1
        region = Region(x=0, y=0, width=region_long_side, height=region_height)
        selector = PyramidLevelSelector()
        result = selector.select_level(
            region, metadata, target_size=target_s, bias=bias
        )

        assert 0 <= result.level < metadata.level_count
        assert result.downsample == metadata.level_downsamples[result.level]

    @given(
        region_long_side=st.integers(min_value=1000, max_value=100000),
        target_s=st.integers(min_value=500, max_value=2000),
        bias=st.floats(min_value=0.7, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_no_upsample_unless_forced(
        self,
        region_long_side: int,
        target_s: int,
        bias: float,
    ) -> None:
        """Verify invariant: size_at_level >= target_s OR level == 0."""
        metadata = WSIMetadata(
            path="/path/to/slide.svs",
            width=100000,
            height=80000,
            level_count=4,
            level_dimensions=(
                (100000, 80000),
                (50000, 40000),
                (25000, 20000),
                (12500, 10000),
            ),
            level_downsamples=(1.0, 2.0, 4.0, 8.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )

        # Ensure region is large enough that we're not in forced-upsample territory
        region_height = region_long_side // 2 + 1
        region = Region(x=0, y=0, width=region_long_side, height=region_height)
        selector = PyramidLevelSelector()
        result = selector.select_level(
            region, metadata, target_size=target_s, bias=bias
        )

        # Calculate size at selected level (paper notation: Lk)
        long_side = max(region.width, region.height)
        size_at_level = long_side / result.downsample

        # Invariant: either we have enough pixels, or we're at the finest level
        assert size_at_level >= target_s or result.level == 0

    @given(
        region_width=st.integers(min_value=100, max_value=50000),
        region_height=st.integers(min_value=100, max_value=50000),
        target_s=st.integers(min_value=500, max_value=2000),
        bias=st.floats(min_value=0.7, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_deterministic_output(
        self,
        region_width: int,
        region_height: int,
        target_s: int,
        bias: float,
    ) -> None:
        """Verify same inputs always produce same output."""
        metadata = WSIMetadata(
            path="/path/to/slide.svs",
            width=100000,
            height=80000,
            level_count=3,
            level_dimensions=(
                (100000, 80000),
                (25000, 20000),
                (6250, 5000),
            ),
            level_downsamples=(1.0, 4.0, 16.0),
            vendor="aperio",
            mpp_x=0.25,
            mpp_y=0.25,
        )

        region = Region(x=0, y=0, width=region_width, height=region_height)
        selector = PyramidLevelSelector()

        result1 = selector.select_level(
            region, metadata, target_size=target_s, bias=bias
        )
        result2 = selector.select_level(
            region, metadata, target_size=target_s, bias=bias
        )

        assert result1 == result2


# --- Test with Realistic Pyramid Configurations ---


class TestPyramidLevelSelectorRealisticPyramids:
    """Tests with realistic WSI pyramid configurations."""

    def test_aperio_typical_pyramid(self) -> None:
        """Test with typical Aperio pyramid (non-power-of-2 downsamples)."""
        metadata = WSIMetadata(
            path="/data/slides/TCGA-XX-XXXX.svs",
            width=98304,
            height=71680,
            level_count=5,
            level_dimensions=(
                (98304, 71680),
                (49152, 35840),
                (24576, 17920),
                (12288, 8960),
                (6144, 4480),
            ),
            level_downsamples=(1.0, 2.0, 4.0, 8.0, 16.0),
            vendor="aperio",
            mpp_x=0.2522,
            mpp_y=0.2522,
        )

        # Region 10K x 8K
        region = Region(x=10000, y=10000, width=10000, height=8000)
        selector = PyramidLevelSelector()
        result = selector.select_level(region, metadata, target_size=1000)

        # Verify valid selection
        assert 0 <= result.level < 5
        assert result.downsample == metadata.level_downsamples[result.level]

    def test_hamamatsu_ndpi_pyramid(self) -> None:
        """Test with Hamamatsu NDPI-style pyramid."""
        metadata = WSIMetadata(
            path="/data/slides/slide.ndpi",
            width=122880,
            height=86016,
            level_count=8,
            level_dimensions=(
                (122880, 86016),
                (61440, 43008),
                (30720, 21504),
                (15360, 10752),
                (7680, 5376),
                (3840, 2688),
                (1920, 1344),
                (960, 672),
            ),
            level_downsamples=(1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0),
            vendor="hamamatsu",
            mpp_x=0.2206,
            mpp_y=0.2206,
        )

        region = Region(x=0, y=0, width=15000, height=12000)
        selector = PyramidLevelSelector()
        result = selector.select_level(region, metadata, target_size=1000)

        # Verify valid selection
        assert 0 <= result.level < 8

        # Verify no unnecessary upsampling (paper notation: L0, Lk)
        long_side = max(region.width, region.height)  # 15000
        size_at_level = long_side / result.downsample
        assert size_at_level >= 1000 or result.level == 0
