"""
AI Grading Co-Pilot — Core Engine
Sends student submission images to Claude API for rubric-based evaluation.
Returns structured scores, feedback, and confidence indicators.
"""

import anthropic
import base64
import json
import re
from dataclasses import dataclass, field


SYSTEM_PROMPT = """You are an AI grading assistant for university engineering courses. Your job is to provide a DRAFT assessment of a student's handwritten submission — you are NOT the final grader, you are saving the human grader time by doing the first pass.

CRITICAL RULES:

1. PRESENTATION MATTERS AS MUCH AS CORRECTNESS.
   A correct answer with terrible presentation (messy work, no labels, hard to follow, no boxed final answer) should still lose points for presentation. The grader wants students to communicate their work clearly.

2. SHOW YOUR REASONING FOR EVERY DEDUCTION.
   For full-credit items, a one-line confirmation is enough ("Correct, used KVL properly").
   For deductions, explain exactly what went wrong and why points were taken off.

3. IF YOU ARE UNCERTAIN — FLAG IT.
   If handwriting is illegible, steps are ambiguous, or you cannot confidently determine if an approach is valid, mark that criterion as confidence: "low" and explain why in grader_notes. Do NOT guess.

4. HANDLE EDGE CASES:
   - Blank submission (no work shown) → submission_status: "blank", score: 0
   - Only the question is present with no student work → submission_status: "blank", score: 0
   - Off-topic or wrong assignment → submission_status: "off_topic", score: 0
   - Partial work (some parts attempted, others blank) → submission_status: "partial"

5. You are producing a DRAFT for review. Always frame feedback as a suggestion the grader can edit.

Respond ONLY with valid JSON in this exact structure — no markdown, no explanation outside the JSON:

{
  "student_id": "name or identifier if visible on the page, otherwise Unknown",
  "submission_status": "complete | partial | blank | off_topic",
  "overall_score": 0,
  "max_possible_score": 0,
  "confidence": "high | medium | low",
  "confidence_reason": "why you are or aren't confident in this assessment",
  "criteria_scores": [
    {
      "criterion": "name of rubric criterion",
      "score": 0,
      "max_score": 0,
      "assessment": "brief note — explain deductions, confirm full credit briefly",
      "presentation_flag": false,
      "presentation_note": "if flagged: what is wrong with presentation for this criterion"
    }
  ],
  "overall_feedback": "2-3 sentence draft feedback for the student — what they did well, what to improve",
  "grader_notes": "anything the human grader should double-check or override"
}"""


USER_PROMPT_TEMPLATE = """ASSIGNMENT: {assignment_title}
COURSE: {course_code}

RUBRIC:
{rubric_text}

ANSWER KEY:
{answer_key}

The attached image is a scan of one student's handwritten submission. Evaluate it against the rubric and answer key above.

Check each of these:
1. Are the final answers correct? Compare to the answer key.
2. Is the methodology shown and valid? Did they use appropriate laws/formulas?
3. Are proper units, labels, and variable names used?
4. Is the submission well-organized and clearly presented — can you easily find the final answers and follow the solution steps?
5. Are there any steps that are illegible, skipped, or ambiguous?

Return your assessment in the JSON format specified in your instructions."""


@dataclass
class GradingResult:
    """Structured result from grading a single submission."""
    student_id: str = "Unknown"
    submission_status: str = "complete"
    overall_score: float = 0
    max_possible_score: float = 0
    confidence: str = "medium"
    confidence_reason: str = ""
    criteria_scores: list = field(default_factory=list)
    overall_feedback: str = ""
    grader_notes: str = ""
    page_number: int = 0
    raw_json: dict = field(default_factory=dict)
    error: str = ""


def encode_image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string for the API."""
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def grade_submission(
    image_bytes: bytes,
    assignment_title: str,
    course_code: str,
    rubric_text: str,
    answer_key: str,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    page_number: int = 0,
) -> GradingResult:
    """
    Grade a single student submission image against a rubric.

    Args:
        image_bytes: The submission image as bytes (PNG/JPEG)
        assignment_title: Name of the assignment
        course_code: Course code (e.g., "EE2800")
        rubric_text: The grading rubric as text
        answer_key: The correct answers and methodology
        api_key: Anthropic API key
        model: Which Claude model to use
        page_number: Which page of the PDF this came from

    Returns:
        GradingResult with structured scores and feedback
    """
    result = GradingResult(page_number=page_number)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            assignment_title=assignment_title,
            course_code=course_code,
            rubric_text=rubric_text,
            answer_key=answer_key,
        )

        image_b64 = encode_image_to_base64(image_bytes)

        message = client.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                }
            ],
        )

        response_text = message.content[0].text

        # Parse JSON from response — handle markdown code blocks if model wraps it
        json_text = response_text.strip()
        if json_text.startswith("```"):
            json_text = re.sub(r"^```(?:json)?\s*", "", json_text)
            json_text = re.sub(r"\s*```$", "", json_text)

        data = json.loads(json_text)
        result.raw_json = data
        result.student_id = data.get("student_id", "Unknown")
        result.submission_status = data.get("submission_status", "complete")
        result.overall_score = data.get("overall_score", 0)
        result.max_possible_score = data.get("max_possible_score", 0)
        result.confidence = data.get("confidence", "medium")
        result.confidence_reason = data.get("confidence_reason", "")
        result.criteria_scores = data.get("criteria_scores", [])
        result.overall_feedback = data.get("overall_feedback", "")
        result.grader_notes = data.get("grader_notes", "")

    except json.JSONDecodeError as e:
        result.error = f"Failed to parse AI response as JSON: {e}"
    except anthropic.APIError as e:
        result.error = f"API error: {e}"
    except Exception as e:
        result.error = f"Unexpected error: {e}"

    return result


def results_to_csv_rows(results: list[GradingResult]) -> list[dict]:
    """Convert a list of GradingResults into flat dicts for CSV/DataFrame export."""
    rows = []
    for r in results:
        row = {
            "Page": r.page_number,
            "Student": r.student_id,
            "Status": r.submission_status,
            "Score": r.overall_score,
            "Max Score": r.max_possible_score,
            "Confidence": r.confidence,
            "Feedback": r.overall_feedback,
            "Grader Notes": r.grader_notes,
        }

        # Flatten criteria scores into columns
        for i, c in enumerate(r.criteria_scores, 1):
            row[f"Criterion {i}"] = c.get("criterion", "")
            row[f"C{i} Score"] = c.get("score", "")
            row[f"C{i} Max"] = c.get("max_score", "")
            row[f"C{i} Note"] = c.get("assessment", "")
            if c.get("presentation_flag"):
                row[f"C{i} Presentation"] = c.get("presentation_note", "Flagged")

        if r.error:
            row["Error"] = r.error

        rows.append(row)
    return rows
