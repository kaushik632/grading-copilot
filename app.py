"""
AI Grading Co-Pilot — Streamlit App
Upload student submissions (PDF), enter rubric + answer key, get AI-drafted grades.
Includes grader feedback mechanism for user acceptance testing.
"""

import io
import json
import datetime
import streamlit as st
import pandas as pd
from pdf2image import convert_from_bytes
from grading_engine import grade_submission, results_to_csv_rows, GradingResult


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Grading Co-Pilot",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for a cleaner look ────────────────────────────────────────────
st.markdown("""
<style>
    /* Hero section */
    .hero-title {
        font-size: 2.4rem;
        font-weight: 700;
        margin-bottom: 0;
        line-height: 1.2;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: #6b7280;
        margin-top: 0.25rem;
        margin-bottom: 1.5rem;
    }

    /* Step indicators */
    .step-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.5rem;
    }
    .step-number {
        background: #4F46E5;
        color: white;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.9rem;
        flex-shrink: 0;
    }
    .step-number.done {
        background: #10B981;
    }
    .step-label {
        font-size: 1.1rem;
        font-weight: 600;
    }

    /* Score cards */
    .score-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
    }
    .score-card.flagged {
        border-left: 4px solid #f59e0b;
    }
    .score-card.error-card {
        border-left: 4px solid #ef4444;
    }

    /* Feedback section */
    .feedback-box {
        background: #fefce8;
        border: 1px solid #fde68a;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Better tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Helper: step indicator ───────────────────────────────────────────────────
def step_indicator(number: int, label: str, done: bool = False):
    css_class = "done" if done else ""
    icon = "✓" if done else str(number)
    st.markdown(
        f'<div class="step-header">'
        f'<div class="step-number {css_class}">{icon}</div>'
        f'<span class="step-label">{label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://em-content.zobj.net/source/apple/391/memo_1f4dd.png", width=48)
    st.markdown("### AI Grading Co-Pilot")
    st.caption("Draft grades in seconds, not hours.")

    st.divider()

    provider = st.selectbox(
        "🏢 AI Provider",
        options=["Google Gemini (Free)", "Anthropic Claude (Paid)"],
        index=0,
        help="Gemini has a free tier — great for testing. Claude is more accurate but costs money.",
    )

    if "Gemini" in provider:
        api_key = st.text_input(
            "🔑 Google AI API Key",
            type="password",
            help="Get yours free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)",
        )
        model_choice = st.selectbox(
            "🤖 AI Model",
            options=[
                "gemini-2.0-flash",
                "gemini-1.5-flash",
            ],
            index=0,
            help="2.0 Flash = latest and best. 1.5 Flash = also free, slightly older.",
        )
    else:
        api_key = st.text_input(
            "🔑 Anthropic API Key",
            type="password",
            help="Get yours at [console.anthropic.com](https://console.anthropic.com)",
        )
        model_choice = st.selectbox(
            "🤖 AI Model",
            options=[
                "claude-sonnet-4-20250514",
                "claude-haiku-3-5-20241022",
            ],
            index=0,
            help="Sonnet = more accurate. Haiku = faster and cheaper.",
        )

    st.divider()

    with st.expander("ℹ️ How it works"):
        st.markdown("""
        1. **Enter** your rubric + answer key
        2. **Upload** student submissions as a PDF
        3. **AI reads** each page and drafts scores
        4. **You review** — agree, adjust, or override
        5. **Export** final grades as CSV for Canvas
        """)

    st.divider()
    st.caption("Built by Kaushik Gogi")
    st.caption("MS Engineering Management · Missouri S&T")


# ── Main content ─────────────────────────────────────────────────────────────
st.markdown('<p class="hero-title">📝 AI Grading Co-Pilot</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-subtitle">'
    'Upload scanned submissions · Get AI-drafted grades · Review and export'
    '</p>',
    unsafe_allow_html=True,
)

# Track what's been completed
has_rubric = bool(st.session_state.get("rubric_saved"))
has_pdf = bool(st.session_state.get("images"))
has_results = bool(st.session_state.get("results"))

tab_setup, tab_grade, tab_review, tab_export = st.tabs([
    "1️⃣ Setup",
    "2️⃣ Grade",
    "3️⃣ Review & Feedback",
    "4️⃣ Export",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: SETUP — Assignment info, rubric, answer key
# ══════════════════════════════════════════════════════════════════════════════
with tab_setup:
    step_indicator(1, "Assignment Details", done=has_rubric)

    col_info_l, col_info_r = st.columns(2)
    with col_info_l:
        assignment_title = st.text_input(
            "Assignment Title",
            value=st.session_state.get("assignment_title", ""),
            placeholder="e.g. Assignment #8 — Circuit Analysis",
        )
    with col_info_r:
        course_code = st.text_input(
            "Course Code",
            value=st.session_state.get("course_code", ""),
            placeholder="e.g. EE2800 / EE151",
        )

    st.markdown("---")
    step_indicator(2, "Rubric & Answer Key", done=has_rubric)

    col_left, col_right = st.columns(2)

    with col_left:
        rubric_text = st.text_area(
            "Grading Rubric",
            value=st.session_state.get("rubric_text", ""),
            height=220,
            placeholder=(
                "Paste your rubric here. Example:\n\n"
                "- Correct final answer for Vx (10 points)\n"
                "- Correct final answer for iy (10 points)\n"
                "- Valid methodology — proper use of KVL, KCL, Ohm's Law (10 points)\n"
                "- Clear presentation — organized work, boxed answers (5 points)\n"
                "- Circuit diagram redrawn with labels (5 points)"
            ),
            help="General guidelines work fine — you don't need exact point breakdowns for every sub-step.",
        )

    with col_right:
        answer_key = st.text_area(
            "Answer Key",
            value=st.session_state.get("answer_key", ""),
            height=220,
            placeholder=(
                "Paste the correct answers + method. Example:\n\n"
                "Vx = 4V\n"
                "iy = 1A (downward)\n\n"
                "Method: KVL around the loop gives\n"
                "-16 + Vx + 3Vx = 0 → 4Vx = 16 → Vx = 4V\n"
                "Then Ohm's law for branch currents,\n"
                "KCL at top node for iy."
            ),
            help="Include the methodology so the AI can check the student's approach, not just the final number.",
        )

    if rubric_text.strip() and answer_key.strip():
        if st.button("✅ Save & Continue to Grading", type="primary", use_container_width=True):
            st.session_state["rubric_saved"] = True
            st.session_state["assignment_title"] = assignment_title
            st.session_state["course_code"] = course_code
            st.session_state["rubric_text"] = rubric_text
            st.session_state["answer_key"] = answer_key
            st.success("Setup saved. Go to the **Grade** tab to upload submissions.")
    else:
        st.info("Fill in both the rubric and answer key to continue.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: GRADE — Upload PDF and run AI grading
# ══════════════════════════════════════════════════════════════════════════════
with tab_grade:
    if not st.session_state.get("rubric_saved"):
        st.warning("Complete the **Setup** tab first — enter your rubric and answer key.")
    else:
        step_indicator(3, "Upload Submissions", done=has_pdf)

        uploaded_pdf = st.file_uploader(
            "Upload student submissions (PDF)",
            type=["pdf"],
            help="Scan all submissions into a single PDF — each page = one student's work.",
            key="pdf_uploader",
        )

        if uploaded_pdf is not None:
            pdf_bytes = uploaded_pdf.read()

            with st.spinner("Converting PDF pages to images..."):
                try:
                    images = convert_from_bytes(pdf_bytes, dpi=200)
                    st.session_state["images"] = images
                    st.session_state["pdf_name"] = uploaded_pdf.name
                except Exception as e:
                    st.error(f"Could not process PDF: {e}")
                    images = []

        if st.session_state.get("images"):
            images = st.session_state["images"]
            st.success(f"📄 {len(images)} submissions detected in **{st.session_state.get('pdf_name', 'upload')}**")

            # Thumbnail preview
            with st.expander("Preview submissions", expanded=False):
                cols = st.columns(min(len(images), 5))
                for i, img in enumerate(images[:10]):
                    with cols[i % 5]:
                        st.image(img, caption=f"Page {i+1}", width=140)
                if len(images) > 10:
                    st.caption(f"... and {len(images) - 10} more")

            st.markdown("---")
            step_indicator(4, "Run AI Grading", done=has_results)

            if not api_key:
                st.warning("⬅️ Enter your API key in the sidebar first.")
            else:
                col_btn, col_info = st.columns([2, 3])
                with col_btn:
                    grade_button = st.button(
                        f"🚀 Grade {len(images)} Submissions",
                        type="primary",
                        use_container_width=True,
                    )
                with col_info:
                    est_time = len(images) * 8  # ~8 sec per submission
                    if "gemini" in model_choice:
                        cost_label = "💰 Free (Gemini free tier)"
                    else:
                        est_cost = len(images) * 0.02
                        cost_label = f"💰 ~${est_cost:.2f} API cost"
                    st.caption(
                        f"⏱️ ~{est_time//60}m {est_time%60}s · {cost_label}"
                    )

                if grade_button:
                    results: list[GradingResult] = []
                    progress = st.progress(0, text="Starting AI grading...")

                    for i, img in enumerate(images):
                        progress.progress(
                            i / len(images),
                            text=f"📖 Reading submission {i+1} of {len(images)}...",
                        )

                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        img_bytes = buf.getvalue()

                        result = grade_submission(
                            image_bytes=img_bytes,
                            assignment_title=st.session_state.get("assignment_title", ""),
                            course_code=st.session_state.get("course_code", ""),
                            rubric_text=st.session_state.get("rubric_text", ""),
                            answer_key=st.session_state.get("answer_key", ""),
                            api_key=api_key,
                            model=model_choice,
                            page_number=i + 1,
                        )
                        results.append(result)

                    progress.progress(1.0, text="✅ All submissions graded!")

                    # Store results and initialize feedback tracking
                    st.session_state["results"] = results
                    st.session_state["feedback"] = {}
                    st.session_state["graded_at"] = datetime.datetime.now().isoformat()

                    errors = sum(1 for r in results if r.error)
                    blanks = sum(1 for r in results if r.submission_status == "blank")
                    low_conf = sum(1 for r in results if r.confidence == "low")

                    st.success(f"Graded {len(results)} submissions!")
                    if errors:
                        st.warning(f"{errors} had errors — check the Review tab.")
                    if low_conf:
                        st.info(f"{low_conf} flagged as low confidence — needs your review.")
                    if blanks:
                        st.caption(f"{blanks} blank or question-only pages detected.")

                    st.info("👉 Go to the **Review & Feedback** tab to check the results.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: REVIEW & FEEDBACK — The grader reviews + provides UAT feedback
# ══════════════════════════════════════════════════════════════════════════════
with tab_review:
    if not st.session_state.get("results"):
        st.info("Run grading first — results will appear here for your review.")
    else:
        results = st.session_state["results"]
        images = st.session_state.get("images", [])
        feedback = st.session_state.get("feedback", {})

        # ── Summary dashboard ────────────────────────────────────────────
        st.markdown("### 📊 Grading Summary")

        scored = [r for r in results if r.submission_status not in ("blank", "off_topic") and not r.error]
        scores = [r.overall_score for r in scored]
        max_scores = [r.max_possible_score for r in scored]

        col_a, col_b, col_c, col_d, col_e = st.columns(5)
        col_a.metric("Submissions", len(results))
        col_b.metric("Avg Score",
            f"{sum(scores)/len(scores):.1f}/{max_scores[0] if max_scores else '?'}" if scores else "—"
        )
        col_c.metric("🟢 High Confidence", sum(1 for r in results if r.confidence == "high"))
        col_d.metric("🟡 Medium", sum(1 for r in results if r.confidence == "medium"))
        col_e.metric("🔴 Needs Review", sum(1 for r in results if r.confidence == "low" or r.error))

        # Filter controls
        st.markdown("---")
        filter_col1, filter_col2 = st.columns([1, 3])
        with filter_col1:
            show_filter = st.selectbox(
                "Show",
                ["All", "Needs Review (low confidence)", "Has Errors", "Blank/Off-topic", "Not Yet Reviewed"],
                index=0,
            )

        # Filter results
        filtered_indices = list(range(len(results)))
        if show_filter == "Needs Review (low confidence)":
            filtered_indices = [i for i, r in enumerate(results) if r.confidence == "low"]
        elif show_filter == "Has Errors":
            filtered_indices = [i for i, r in enumerate(results) if r.error]
        elif show_filter == "Blank/Off-topic":
            filtered_indices = [i for i, r in enumerate(results) if r.submission_status in ("blank", "off_topic")]
        elif show_filter == "Not Yet Reviewed":
            filtered_indices = [i for i, r in enumerate(results) if str(i) not in feedback]

        st.caption(f"Showing {len(filtered_indices)} of {len(results)} submissions")

        # ── Per-submission cards ─────────────────────────────────────────
        for idx in filtered_indices:
            r = results[idx]

            # Confidence icon
            if r.error:
                icon = "❌"
                conf_label = "Error"
            elif r.confidence == "low":
                icon = "🔴"
                conf_label = "Low Confidence"
            elif r.confidence == "medium":
                icon = "🟡"
                conf_label = "Medium"
            else:
                icon = "🟢"
                conf_label = "High"

            # Check if this one has feedback already
            has_fb = str(idx) in feedback
            fb_icon = " ✅" if has_fb else ""

            with st.expander(
                f"{icon} Page {r.page_number} · {r.student_id} · "
                f"{r.overall_score}/{r.max_possible_score} · {conf_label}{fb_icon}",
                expanded=(r.confidence == "low" or bool(r.error)),
            ):
                detail_left, detail_right = st.columns([2, 3])

                # Left: submission image
                with detail_left:
                    if idx < len(images):
                        st.image(images[idx], caption=f"Page {r.page_number}", use_container_width=True)

                # Right: AI assessment + grader feedback
                with detail_right:
                    if r.error:
                        st.error(f"**Error:** {r.error}")
                    elif r.submission_status == "blank":
                        st.info("📄 Blank submission — no student work detected.")
                    else:
                        # Status and confidence
                        st.markdown(f"**Status:** {r.submission_status} · **Confidence:** {r.confidence}")
                        if r.confidence_reason:
                            st.caption(r.confidence_reason)

                        # Criteria breakdown
                        st.markdown("**Criteria Breakdown:**")
                        for c in r.criteria_scores:
                            score_pct = (c["score"] / c["max_score"] * 100) if c.get("max_score") else 0
                            bar_color = "🟩" if score_pct >= 80 else "🟨" if score_pct >= 50 else "🟥"

                            line = f"{bar_color} **{c['criterion']}**: {c['score']}/{c['max_score']}"
                            if c.get("assessment"):
                                line += f" — {c['assessment']}"
                            st.markdown(line)

                            if c.get("presentation_flag"):
                                st.caption(f"  ⚠️ Presentation: {c.get('presentation_note', 'Flagged')}")

                        # Draft feedback
                        st.markdown("---")
                        st.markdown(f"**Draft Feedback:** {r.overall_feedback}")

                        if r.grader_notes:
                            st.warning(f"**⚠️ Grader Notes:** {r.grader_notes}")

                    # ── GRADER FEEDBACK SECTION (UAT) ────────────────────
                    st.markdown("---")
                    st.markdown("**Your Review:**")

                    fb_key = str(idx)
                    existing_fb = feedback.get(fb_key, {})

                    verdict = st.radio(
                        "Do you agree with this AI grade?",
                        ["Agree", "Agree with minor edits", "Disagree — needs correction"],
                        index=["Agree", "Agree with minor edits", "Disagree — needs correction"].index(
                            existing_fb.get("verdict", "Agree")
                        ),
                        key=f"verdict_{idx}",
                        horizontal=True,
                    )

                    adjusted_score = st.number_input(
                        "Your final score (adjust if needed)",
                        min_value=0.0,
                        max_value=float(r.max_possible_score) if r.max_possible_score else 100.0,
                        value=float(existing_fb.get("adjusted_score", r.overall_score)),
                        step=1.0,
                        key=f"score_{idx}",
                    )

                    grader_comment = st.text_area(
                        "Comments (what did the AI get wrong?)",
                        value=existing_fb.get("comment", ""),
                        height=80,
                        placeholder="e.g. 'AI missed that the student used superposition instead of KVL — still valid'",
                        key=f"comment_{idx}",
                    )

                    if st.button("💾 Save Review", key=f"save_{idx}"):
                        feedback[fb_key] = {
                            "page": r.page_number,
                            "student_id": r.student_id,
                            "ai_score": r.overall_score,
                            "adjusted_score": adjusted_score,
                            "verdict": verdict,
                            "comment": grader_comment,
                            "ai_confidence": r.confidence,
                        }
                        st.session_state["feedback"] = feedback
                        st.success("Review saved!")

        # ── Feedback summary ─────────────────────────────────────────────
        if feedback:
            st.markdown("---")
            st.markdown("### 📋 Review Progress")

            reviewed = len(feedback)
            total = len(results)
            st.progress(reviewed / total, text=f"{reviewed}/{total} submissions reviewed")

            agrees = sum(1 for f in feedback.values() if f["verdict"] == "Agree")
            minor = sum(1 for f in feedback.values() if f["verdict"] == "Agree with minor edits")
            disagrees = sum(1 for f in feedback.values() if "Disagree" in f["verdict"])

            fc1, fc2, fc3, fc4 = st.columns(4)
            fc1.metric("Reviewed", reviewed)
            fc2.metric("Agreed", agrees)
            fc3.metric("Minor Edits", minor)
            fc4.metric("Disagreed", disagrees)

            if reviewed > 0:
                accuracy = (agrees + minor) / reviewed * 100
                st.metric("AI Accuracy (agree + minor edits)", f"{accuracy:.0f}%")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: EXPORT — CSV download + feedback report
# ══════════════════════════════════════════════════════════════════════════════
with tab_export:
    if not st.session_state.get("results"):
        st.info("Grade submissions first — export options will appear here.")
    else:
        results = st.session_state["results"]
        feedback = st.session_state.get("feedback", {})

        st.markdown("### 📥 Export Grades")

        # ── Grades CSV (uses adjusted scores if feedback exists) ─────────
        st.markdown("**Grades for Canvas:**")
        export_rows = []
        for i, r in enumerate(results):
            fb = feedback.get(str(i), {})
            final_score = fb.get("adjusted_score", r.overall_score)
            export_rows.append({
                "Student": r.student_id,
                "Score": final_score,
                "Max Score": r.max_possible_score,
                "Status": r.submission_status,
                "Feedback": r.overall_feedback,
                "Grader Override": fb.get("comment", ""),
            })

        df_grades = pd.DataFrame(export_rows)
        st.dataframe(df_grades, use_container_width=True)

        csv_grades = df_grades.to_csv(index=False)
        st.download_button(
            label="📥 Download Grades CSV",
            data=csv_grades,
            file_name=f"grades_{st.session_state.get('assignment_title', 'export')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # ── UAT / Feedback report ────────────────────────────────────────
        if feedback:
            st.markdown("---")
            st.markdown("### 📊 UAT Feedback Report")
            st.caption("This is your user acceptance testing data — use it in your portfolio.")

            fb_rows = []
            for key, fb in feedback.items():
                fb_rows.append({
                    "Page": fb.get("page"),
                    "Student": fb.get("student_id"),
                    "AI Score": fb.get("ai_score"),
                    "Final Score": fb.get("adjusted_score"),
                    "Score Difference": fb.get("adjusted_score", 0) - fb.get("ai_score", 0),
                    "AI Confidence": fb.get("ai_confidence"),
                    "Verdict": fb.get("verdict"),
                    "Comment": fb.get("comment"),
                })

            df_feedback = pd.DataFrame(fb_rows)
            st.dataframe(df_feedback, use_container_width=True)

            csv_feedback = df_feedback.to_csv(index=False)
            st.download_button(
                label="📥 Download UAT Report CSV",
                data=csv_feedback,
                file_name="uat_feedback_report.csv",
                mime="text/csv",
                use_container_width=True,
            )

            # Summary stats for portfolio
            st.markdown("**Portfolio-ready stats:**")
            agrees = sum(1 for f in fb_rows if f["Verdict"] == "Agree")
            minor = sum(1 for f in fb_rows if f["Verdict"] == "Agree with minor edits")
            total_reviewed = len(fb_rows)
            accuracy = (agrees + minor) / total_reviewed * 100 if total_reviewed else 0
            avg_diff = sum(abs(f["Score Difference"]) for f in fb_rows) / total_reviewed if total_reviewed else 0

            st.markdown(
                f"- **AI accuracy:** {accuracy:.0f}% (agree + minor edits)\n"
                f"- **Avg score deviation:** {avg_diff:.1f} points\n"
                f"- **Submissions reviewed:** {total_reviewed}\n"
                f"- **Full disagreements:** {total_reviewed - agrees - minor}"
            )
        else:
            st.info(
                "No feedback yet — have the grader review submissions in the "
                "**Review & Feedback** tab to generate the UAT report."
            )
