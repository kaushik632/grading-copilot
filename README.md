# AI Grading Co-Pilot

AI-assisted grading for university engineering courses. Upload scanned student submissions (PDF), enter your rubric and answer key, and get structured draft grades with confidence indicators and presentation quality flags.

## Features

- **Multimodal AI grading** — reads handwritten scanned submissions via Claude's vision API
- **Rubric-based evaluation** — scores against your criteria, not just answer correctness
- **Presentation quality flags** — catches messy work, missing labels, unorganized solutions
- **Confidence indicators** — flags uncertain assessments for human review
- **Grader feedback loop** — agree/disagree/adjust scores for UAT tracking
- **CSV export** — Canvas-compatible grade export + UAT feedback report

## Quick Start (Local)

```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/grading-copilot.git
cd grading-copilot
pip install -r requirements.txt

# 2. Install poppler (PDF processing)
# Mac: brew install poppler
# Ubuntu: sudo apt install poppler-utils
# Windows: download from https://github.com/oschwartz10612/poppler-windows

# 3. Run
streamlit run app.py
```

## Deploy to Streamlit Cloud (Free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set main file path: `app.py`
5. Deploy — `packages.txt` handles the poppler dependency automatically

Users enter their own Anthropic API key in the sidebar — no secrets needed on the server.

## Architecture

```
Frontend (Streamlit)          Backend (grading_engine.py)
┌──────────────────┐         ┌──────────────────────────┐
│ Setup Tab        │         │ System Prompt            │
│ - Rubric input   │────────▶│ - Presentation scoring   │
│ - Answer key     │         │ - Deduction explanations │
│                  │         │ - Confidence flags       │
│ Grade Tab        │         │ - Edge case handling     │
│ - PDF upload     │────────▶│                          │
│ - Progress bar   │         │ Claude API (Vision)      │
│                  │         │ - Image + text input     │
│ Review Tab       │◀────────│ - Structured JSON output │
│ - AI scores      │         │                          │
│ - Grader feedback│         │ CSV Export               │
│                  │         │ - Canvas-compatible      │
│ Export Tab       │◀────────│ - UAT feedback report    │
└──────────────────┘         └──────────────────────────┘
```

## Project Structure

```
grading-copilot/
├── app.py                    # Streamlit frontend (4 tabs)
├── grading_engine.py         # Claude API integration + prompts
├── requirements.txt          # Python dependencies
├── packages.txt              # System packages (poppler for Streamlit Cloud)
├── .streamlit/config.toml    # Theme + server config
├── .gitignore
├── .env.example
└── sample_data/              # Test submissions (not committed)
```

## Built By

Kaushik Gogi — MS Engineering Management, Missouri S&T
