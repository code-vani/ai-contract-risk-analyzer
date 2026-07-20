# ClauseForce — AI-Powered Contract & SOW Risk Analyzer

> **Tech Mahindra CODE Hackathon | Team 14 | Problem Statement 04**

ClauseForce automatically detects risks, contradictions, and conflicts between a Master Service Agreement (MSA) and a Statement of Work (SOW). What takes a lawyer 4–6 hours is done in under 2 minutes — with AI-generated redlines, severity scores, and an interactive clause knowledge graph.

## Demo Video

[![ClauseForce Demo](https://img.shields.io/badge/Watch%20Demo-Google%20Drive-blue?style=for-the-badge&logo=google-drive)](https://drive.google.com/file/d/1DAEf6t7JA89nE6ACLFvs9LYgEtsxYcJp/view?usp=sharing)

> Click the badge above or [open this link](https://drive.google.com/file/d/1DAEf6t7JA89nE6ACLFvs9LYgEtsxYcJp/view?usp=sharing) to watch the full demo.

---

## Table of Contents

- [Demo Video](#demo-video)
- [Problem Statement](#problem-statement)
- [What We Built](#what-we-built)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [API Key Access](#api-key-access)
- [Project Structure](#project-structure)
- [Team](#team)

---

## Problem Statement

When companies sign contracts, an MSA defines the overall terms while an SOW defines the specific deliverables. These two documents are often drafted separately — by different teams, at different times — and nobody systematically checks whether they contradict each other.

A single missed contradiction (e.g., one document says "payment in 30 days", the other says "45 days") can escalate into a legal dispute worth crores. Manual review is slow, expensive, and error-prone.

**ClauseForce solves this end to end — automatically.**

---

## What We Built

- **Smart PDF Extraction** — detects whether a PDF is structured, unstructured, or scanned and routes it through the correct extraction pipeline
- **Hybrid Clause Extraction** — for structured documents, uses a TF-IDF + regex classifier trained on the LEDGAR legal dataset (zero API calls, no hallucinations). For unstructured text, routes through Gemini with JSON-mode prompting
- **Scanned PDF Support** — renders each page as an image via PyMuPDF and sends to Gemini Vision for OCR + extraction
- **3-Type Risk Detection** running in parallel:
  - **Contradiction Detection** — two-pass Gemini approach finds where MSA and SOW directly conflict
  - **Override Detection** — catches when one document silently overrides a term in the other
  - **Financial Clause Detection** — flags all money-related clauses (amounts, rates, dates) for mandatory human review
- **AI Redline Generator** — for HIGH and MEDIUM severity risks, generates a rewritten version of the clause that resolves the conflict, using a 3-key Gemini pool with round-robin retry
- **Clause Knowledge Graph** — interactive vis.js graph showing clause relationships, cross-references, contradictions, and override links across both documents
- **Review Workspace** — side-by-side diff view, accept/reject redlines, human review flags for financial clauses

---

## Architecture

```
MSA.pdf + SOW.pdf
        │
        ▼
┌─────────────────────────────────┐
│         SMART EXTRACTOR         │
│  word-density check per page    │
│  MarkItDown → clean Markdown    │
└────────┬──────────┬─────────────┘
         │          │
   structured   unstructured / scanned
         │          │
         ▼          ▼
┌──────────────┐  ┌──────────────────────┐
│ HYBRID       │  │ GEMINI CLAUSE        │
│ EXTRACTOR    │  │ EXTRACTOR / VISION   │
│ LEDGAR ML    │  │ JSON mode + chunked  │
│ 0 API calls  │  │ parallel processing  │
└──────┬───────┘  └──────────┬───────────┘
       └──────────┬───────────┘
                  │
                  ▼
     TABLE DETECTOR + SUB-CLAUSE SPLITTER
     (A. / B. / C. lettered sections → individual clauses)
                  │
                  ▼
┌─────────────────────────────────────────┐
│              RISK PIPELINE              │
│  Contradiction │ Override │ Financial   │
└──────────────────────┬──────────────────┘
                       │
                       ▼
          REDLINE GENERATOR
          3-key Gemini pool | round-robin retry
          HIGH/MEDIUM → AI redline
          FINANCIAL → human review flag
                       │
                       ▼
     FastAPI REST + SQLite → React 19 Frontend
     Review Workspace + Clause Knowledge Graph
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS, vis.js |
| Backend | FastAPI, Python 3.11, SQLite, SQLAlchemy |
| AI / ML | Google Gemini Flash (google-genai SDK) |
| Clause Classification | LEDGAR dataset, scikit-learn (TF-IDF + Logistic Regression) |
| PDF Processing | MarkItDown, PyMuPDF |
| Dev Tools | Git, GitHub, Anaconda, Node.js |

---

## Setup & Installation

### Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- A Gemini API key (see [API Key Access](#api-key-access))

### 1. Clone the repository

```bash
git clone https://github.com/Aryannjainnn/Contract-SOW-Risk-Analyzer.git
cd Contract-SOW-Risk-Analyzer
```

### 2. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Create your environment file
cp .env.example .env
```

Open `backend/.env` and fill in your Gemini API key:

```
GEMINI_API_KEY=your_key_here
GEMINI_API_KEY_2=your_second_key_here   # optional but recommended
GEMINI_API_KEY_3=your_third_key_here    # optional
```

> Adding multiple keys increases the effective rate limit (15 RPM per key). With 3 keys you get ~45 RPM.

### 3. Train the LEDGAR Classifier (one-time)

The LEDGAR classifier enables zero-API-call extraction for structured documents. Run this once:

```bash
cd backend
python ai/train_ledgar_classifier.py
```

This generates `backend/ai/ledgar_classifier.pkl`. If skipped, the pipeline falls back to Gemini for all documents.

### 4. Frontend Setup

```bash
cd frontend
npm install
```

---

## Running the Application

Open **two terminals** and run both simultaneously:

**Terminal 1 — Backend**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

### Demo Documents

Sample MSA and SOW files are included in `backend/demo/` for testing:

| File | Description |
|---|---|
| `TexasAM_MSA.pdf` | Texas A&M University Master Service Agreement |
| `Real_MSA.pdf` | Real-world MSA document |
| `Real_SOW.pdf` | Corresponding SOW document |
| `Sample_MSA.docx` | Sample MSA for quick testing |
| `Sample_SOW.docx` | Sample SOW for quick testing |

---

## API Key Access

This project uses the **Google Gemini API** (free tier).

To get your own API key: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

If you need access to the API keys used during the hackathon for evaluation/testing purposes, contact:

**Aryan Jain (Team Lead)**
- Email: aryanjain8130@gmail.com
- Phone: 9810577964

---

## Project Structure

```
Contract-SOW-Risk-Analyzer/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment config + API keys
│   ├── requirements.txt
│   ├── .env.example
│   ├── ai/
│   │   ├── clause_extractor.py    # Main extraction orchestrator
│   │   ├── hybrid_extractor.py    # LEDGAR-based zero-API extractor
│   │   ├── gemini_client.py       # Gemini API client with retry logic
│   │   ├── key_pool.py            # 3-key round-robin pool
│   │   ├── redline_client.py      # Redline generation client
│   │   ├── table_detector.py      # Financial table stripper
│   │   └── train_ledgar_classifier.py
│   ├── analysis/
│   │   ├── contradiction_detector.py   # MSA vs SOW contradiction detection
│   │   ├── override_detector.py        # Override/supremacy detection
│   │   ├── financial_risk_detector.py  # Financial clause flagging
│   │   └── risk_pipeline.py            # Orchestrates all 3 detectors
│   ├── ingestion/
│   │   └── smart_extractor.py     # PDF routing (structured/unstructured/scanned)
│   ├── graph/
│   │   └── graph_builder.py       # Clause knowledge graph construction
│   ├── output/
│   │   └── redline_generator.py   # AI redline generation
│   ├── routes/                    # FastAPI route handlers
│   ├── database/                  # SQLite models + ORM
│   └── demo/                      # Sample contract PDFs for testing
├── frontend/
│   └── src/
│       ├── App.jsx                # Main application
│       ├── components/
│       │   ├── ReviewWorkspace.jsx    # Side-by-side risk review
│       │   ├── ClauseGraph.jsx        # Knowledge graph visualization
│       │   ├── GraphLegend.jsx        # Graph legend
│       │   ├── InlineDiff.jsx         # Redline diff view
│       │   └── GraphSidePanel.jsx     # Clause detail panel
│       └── lib/
│           └── analysisMapping.js     # Risk type mapping
├── architecture.png               # System architecture diagram
├── workflow.png                   # User workflow diagram
└── .gitignore
```

---

## Team

## Team ClauseForce — Team 14

| Name |
|------|
| Aryan Jain |
| Vanshika Garg |
| Aryan Kataria |
| Devashish Gupta |
| Panvir Singh |
