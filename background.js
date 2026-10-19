/**
 * AI Grading Co-Pilot — Background Service Worker
 * Opens the side panel when the extension icon is clicked on Canvas/Gradescope pages.
 */

// Open side panel when extension icon is clicked
chrome.action.onClicked.addListener(async (tab) => {
  await chrome.sidePanel.open({ tabId: tab.id });
});

// Enable side panel on Canvas and Gradescope URLs
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (!tab.url) return;

  const isGradingPlatform =
    tab.url.includes("instructure.com") ||
    tab.url.includes("canvas.") ||
    tab.url.includes("gradescope.com");

  await chrome.sidePanel.setOptions({
    tabId,
    enabled: true, // keep enabled everywhere for demo purposes
  });
});

// Listen for messages from content script or side panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SUBMISSION_DETECTED") {
    // Forward to side panel
    chrome.runtime.sendMessage({
      type: "SHOW_SUBMISSION",
      data: message.data,
    });
  }

  if (message.type === "GRADE_REQUEST") {
    // Call Claude API from background (avoids CORS issues)
    gradeWithClaude(message.data)
      .then((result) => sendResponse({ success: true, result }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // keep channel open for async response
  }
});

/**
 * Call Claude API to grade a submission.
 */
async function gradeWithClaude(data) {
  const { apiKey, imageBase64, rubric, answerKey, assignmentTitle, courseCode } = data;

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 2000,
      system: SYSTEM_PROMPT,
      messages: [
        {
          role: "user",
          content: [
            {
              type: "image",
              source: {
                type: "base64",
                media_type: "image/png",
                data: imageBase64,
              },
            },
            {
              type: "text",
              text: `ASSIGNMENT: ${assignmentTitle}\nCOURSE: ${courseCode}\n\nRUBRIC:\n${rubric}\n\nANSWER KEY:\n${answerKey}\n\nEvaluate this student submission against the rubric and answer key. Check correctness, methodology, presentation quality, and clarity. Return JSON.`,
            },
          ],
        },
      ],
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`API ${response.status}: ${err}`);
  }

  const result = await response.json();
  const text = result.content[0].text;

  // Parse JSON, stripping markdown code fences if present
  let jsonText = text.trim();
  if (jsonText.startsWith("```")) {
    jsonText = jsonText.replace(/^```(?:json)?\s*/, "").replace(/\s*```$/, "");
  }
  return JSON.parse(jsonText);
}

const SYSTEM_PROMPT = `You are an AI grading assistant for university engineering courses. Your job is to provide a DRAFT assessment of a student's handwritten submission — you are NOT the final grader.

RULES:
1. PRESENTATION MATTERS. Messy work, no labels, hard to follow = lose points.
2. EXPLAIN DEDUCTIONS. Full credit gets a brief confirmation. Deductions get reasons.
3. FLAG UNCERTAINTY. If handwriting is illegible or steps are ambiguous, mark confidence as "low".
4. EDGE CASES: Blank = "blank" status, score 0. Off-topic = "off_topic", score 0.

Respond ONLY with valid JSON:
{
  "student_id": "name if visible, otherwise Unknown",
  "submission_status": "complete | partial | blank | off_topic",
  "overall_score": 0,
  "max_possible_score": 0,
  "confidence": "high | medium | low",
  "confidence_reason": "why",
  "criteria_scores": [
    {
      "criterion": "name",
      "score": 0,
      "max_score": 0,
      "assessment": "note",
      "presentation_flag": false,
      "presentation_note": ""
    }
  ],
  "overall_feedback": "2-3 sentences",
  "grader_notes": "what to double-check"
}`;
