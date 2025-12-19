"""Tests for giant.eval.answer_extraction module (Spec-10)."""

from __future__ import annotations

from giant.eval.answer_extraction import ExtractedAnswer, extract_label


class TestExtractedAnswer:
    """Tests for ExtractedAnswer dataclass."""

    def test_extracted_answer_with_label(self) -> None:
        """Test ExtractedAnswer with valid label."""
        answer = ExtractedAnswer(label=1, raw="Option 1")
        assert answer.label == 1
        assert answer.raw == "Option 1"

    def test_extracted_answer_no_label(self) -> None:
        """Test ExtractedAnswer with no label."""
        answer = ExtractedAnswer(label=None, raw="I don't know")
        assert answer.label is None


class TestExtractLabelPanda:
    """Tests for PANDA benchmark answer extraction."""

    def test_panda_json_isup_grade(self) -> None:
        """Test extracting ISUP grade from JSON object."""
        prediction = '{"isup_grade": 3, "reasoning": "Gleason 4+3"}'
        result = extract_label(prediction, benchmark_name="panda", options=None)
        assert result.label == 3

    def test_panda_json_embedded_in_text(self) -> None:
        """Test extracting JSON from surrounding text."""
        prediction = 'Based on the findings, my answer is {"isup_grade": 4}.'
        result = extract_label(prediction, benchmark_name="panda", options=None)
        assert result.label == 4

    def test_panda_fallback_to_integer(self) -> None:
        """Test fallback to integer extraction when JSON fails."""
        prediction = "The ISUP grade is 2"
        result = extract_label(prediction, benchmark_name="panda", options=None)
        assert result.label == 2

    def test_panda_grade_zero(self) -> None:
        """Test extracting grade 0 (benign)."""
        prediction = '{"isup_grade": 0}'
        result = extract_label(prediction, benchmark_name="panda", options=None)
        assert result.label == 0


class TestExtractLabelMultipleChoice:
    """Tests for multiple-choice answer extraction."""

    def test_extract_letter_a(self) -> None:
        """Test extracting letter A."""
        options = ["Lung", "Breast", "Colon", "Liver"]
        prediction = "The answer is A."
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        assert result.label == 1  # 1-based

    def test_extract_letter_d(self) -> None:
        """Test extracting letter D."""
        options = ["Lung", "Breast", "Colon", "Liver"]
        prediction = "I believe the answer is D"
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        assert result.label == 4

    def test_extract_letter_lowercase(self) -> None:
        """Test extracting lowercase letter."""
        options = ["Lung", "Breast", "Colon", "Liver"]
        prediction = "My answer is b."
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        assert result.label == 2

    def test_extract_integer_1_based(self) -> None:
        """Test extracting 1-based integer."""
        options = ["Lung", "Breast", "Colon"]
        prediction = "Option 2 is correct"
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        assert result.label == 2

    def test_extract_option_text_match(self) -> None:
        """Test matching option text."""
        options = ["Lung adenocarcinoma", "Breast invasive carcinoma"]
        prediction = "This appears to be lung adenocarcinoma"
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        assert result.label == 1

    def test_extract_option_text_case_insensitive(self) -> None:
        """Test option text matching is case-insensitive."""
        options = ["Lung adenocarcinoma", "Breast invasive carcinoma"]
        prediction = "LUNG ADENOCARCINOMA"
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        assert result.label == 1

    def test_extract_option_text_longer_first(self) -> None:
        """Test that longer options are matched before shorter substrings."""
        # "heart" should match before "art" even though "art" is first in list
        options = ["art", "heart", "lung"]
        prediction = "This is a heart sample"
        result = extract_label(prediction, benchmark_name="gtex", options=options)
        assert result.label == 2  # "heart" is option 2

    def test_letter_only_for_4_options(self) -> None:
        """Test letter extraction only applies for 4-option questions."""
        options = ["Lung carcinoma", "Breast carcinoma"]  # Only 2 options
        prediction = "The answer is A"
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        # Should NOT match letter A since not 4 options
        # Falls back to text matching, but "Lung" and "Breast" not in "The answer is A"
        assert result.label is None


class TestExtractLabelGtex:
    """Tests for GTEx benchmark answer extraction."""

    def test_gtex_organ_match(self) -> None:
        """Test matching GTEx organ names."""
        options = ["Heart", "Lung", "Liver", "Brain"]
        prediction = "This tissue sample is from the liver."
        result = extract_label(prediction, benchmark_name="gtex", options=options)
        assert result.label == 3  # Liver is option 3 (1-based)

    def test_gtex_letter_extraction(self) -> None:
        """Test letter extraction for GTEx."""
        options = ["Heart", "Lung", "Liver", "Brain"]
        prediction = "The organ is C (liver)"
        result = extract_label(prediction, benchmark_name="gtex", options=options)
        assert result.label == 3


class TestExtractLabelEdgeCases:
    """Tests for edge cases in answer extraction."""

    def test_no_match_returns_none(self) -> None:
        """Test that no match returns None label."""
        options = ["Lung", "Breast", "Colon"]
        prediction = "I cannot determine the answer"
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        assert result.label is None

    def test_preserves_raw_text(self) -> None:
        """Test that raw text is always preserved."""
        prediction = "Some complex response with option 2"
        result = extract_label(prediction, benchmark_name="tcga", options=["A", "B"])
        assert result.raw == prediction

    def test_integer_out_of_range_ignored(self) -> None:
        """Test that integers outside option range are ignored."""
        options = ["Lung adenocarcinoma", "Breast carcinoma", "Colon cancer"]
        prediction = "Option 5 is the answer"
        result = extract_label(prediction, benchmark_name="tcga", options=options)
        assert result.label is None  # 5 is out of range

    def test_integer_extraction_no_options(self) -> None:
        """Test integer extraction when no options provided."""
        prediction = "The grade is 3"
        result = extract_label(prediction, benchmark_name="panda", options=None)
        assert result.label == 3

    def test_whitespace_handling(self) -> None:
        """Test handling of leading/trailing whitespace."""
        prediction = "   Option 1   "
        result = extract_label(prediction, benchmark_name="tcga", options=["A", "B"])
        assert result.label == 1

    def test_multiline_json(self) -> None:
        """Test JSON extraction from multiline response."""
        prediction = """Based on my analysis:
        {
            "isup_grade": 2
        }
        This indicates moderate disease."""
        result = extract_label(prediction, benchmark_name="panda", options=None)
        assert result.label == 2
