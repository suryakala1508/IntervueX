# IntervueX: AI Interview Practice Platform

An adaptive mock-interview platform. A React dashboard talks to an async FastAPI backend, and a LangGraph agent runs multi-turn interviews that adjust question difficulty based on the candidate's live answers.



## Features

- **Adaptive interviews:** a LangGraph agent (state, nodes, conditional edges) runs multi-turn mock interviews and raises or lowers difficulty from the candidate's live responses
- **Profile-grounded questions:** upload a resume (PDF); skills are parsed with pypdf, embedded, and stored in pgvector to generate relevant questions
- **Structured scoring:** LLM responses come back as JSON validated with Pydantic, so interview scores are reliable
- **Multi-provider LLM routing:** Groq, Anthropic Claude, and an offline fallback
- **Dashboards:** score and performance charts built with Recharts
- **Secure auth:** JWT-based authentication

## Tech Stack

**Frontend:** React 19, Vite, Tailwind CSS 4, Recharts
**Backend:** Python, FastAPI (async), SQLAlchemy 2.0, Alembic, Pydantic
**Database:** PostgreSQL + pgvector
**AI:** LangGraph, Groq, Anthropic Claude
**Other:** JWT, pypdf

## Getting Started

### Prerequisites
- Node.js 18+ and Python 3.11+
- PostgreSQL with the `pgvector` extension
- API keys for Groq and/or Anthropic

### 1. Clone
```bash
git clone https://github.com/suryakala1508/IntervueX.git
cd IntervueX
```

### 2. Backend
```bash
cd backend            # adjust to your folder name
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your values
alembic upgrade head
uvicorn app.main:app --reload
```

### 3. Frontend
```bash
cd frontend           # adjust to your folder name
npm install
npm run dev
```



## What I Built / Challenges

- Designed the LangGraph workflow so difficulty adapts turn by turn instead of following a fixed question list
- Kept LLM output reliable by validating every response against a Pydantic schema
- Added an offline fallback so the app keeps working if an LLM provider is unavailable

## Author

**Suryakala Beesetti**: [LinkedIn](https://www.linkedin.com/in/suryakala-beesetti-a4844434a/) · [GitHub](https://github.com/suryakala1508) · beesettisuryakala@gmail.com
