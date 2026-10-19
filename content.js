/**
 * AI Grading Co-Pilot — Content Script
 * Runs on Canvas and Gradescope pages.
 * Detects submissions and adds a floating "Grade with AI" button.
 */

(function () {
  "use strict";

  // Don't run if already injected
  if (document.getElementById("grading-copilot-fab")) return;

  // Detect which platform we're on
  const isCanvas = window.location.hostname.includes("instructure.com") ||
                   window.location.hostname.includes("canvas.");
  const isGradescope = window.location.hostname.includes("gradescope.com");

  // Detect if we're on a submission/grading page
  const isSubmissionPage = detectSubmissionPage();

  if (!isSubmissionPage) return;

  // Add floating action button
  const fab = document.createElement("div");
  fab.id = "grading-copilot-fab";
  fab.innerHTML = `
    <button id="grading-copilot-btn" title="Open AI Grading Co-Pilot">
      <span class="copilot-icon">📝</span>
      <span class="copilot-label">AI Grade</span>
    </button>
  `;
  document.body.appendChild(fab);

  // Click handler — open side panel
  document.getElementById("grading-copilot-btn").addEventListener("click", async () => {
    // Try to capture the current submission image/content
    const submissionData = captureSubmission();

    // Notify background to open side panel
    chrome.runtime.sendMessage({
      type: "SUBMISSION_DETECTED",
      data: submissionData,
    });

    // Visual feedback
    const btn = document.getElementById("grading-copilot-btn");
    btn.querySelector(".copilot-label").textContent = "Opening...";
    setTimeout(() => {
      btn.querySelector(".copilot-label").textContent = "AI Grade";
    }, 1500);
  });

  /**
   * Detect if the current page is a submission/grading view.
   */
  function detectSubmissionPage() {
    const url = window.location.href;

    // Canvas SpeedGrader
    if (url.includes("speed_grader") || url.includes("speedgrader")) return true;

    // Canvas submission view
    if (url.includes("/submissions/")) return true;

    // Gradescope grading view
    if (url.includes("/grade") || url.includes("/review")) return true;

    // Gradescope submission view
    if (url.includes("/submissions/")) return true;

    // Generic grading-related pages
    if (url.includes("/grades") || url.includes("/assignments/")) return true;

    return false;
  }

  /**
   * Attempt to capture submission content from the page.
   * Returns metadata about what's on screen — the actual image capture
   * happens when the user clicks "Grade" in the side panel.
   */
  function captureSubmission() {
    const data = {
      platform: isCanvas ? "canvas" : isGradescope ? "gradescope" : "unknown",
      url: window.location.href,
      pageTitle: document.title,
      studentName: "",
      assignmentTitle: "",
    };

    if (isCanvas) {
      // Try to get student name from SpeedGrader
      const studentEl = document.querySelector(
        "#students_selectmenu option:checked, .student_header .name, #student_name"
      );
      if (studentEl) data.studentName = studentEl.textContent.trim();

      // Try to get assignment title
      const titleEl = document.querySelector(
        ".assignment-title, #assignment_title, .title"
      );
      if (titleEl) data.assignmentTitle = titleEl.textContent.trim();
    }

    if (isGradescope) {
      const studentEl = document.querySelector(
        ".submissionHeader--name, .js-studentName"
      );
      if (studentEl) data.studentName = studentEl.textContent.trim();

      const titleEl = document.querySelector(
        ".assignmentHeader--title, h1"
      );
      if (titleEl) data.assignmentTitle = titleEl.textContent.trim();
    }

    return data;
  }
})();
