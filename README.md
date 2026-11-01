# VerbNet Pair Challenge

A synchronous six-team semantic-role quiz with instructor-controlled reveal.

## Run

1. Install Python 3.10+.
2. `pip install -r requirements.txt`
3. `streamlit run app.py`
4. Open the app in the instructor's browser, select **Instructor**, and use the instructor password (default `change-me` for local testing; set `VERBNET_ADMIN_PASSWORD` environment variable before deployment).
5. Students open the same URL on their laptops and select **Team**. The instructor shares the session code.

## Deployment

All users must connect to the **same running server and same SQLite database**. Do not use ephemeral multi-replica hosting for a live class; SQLite on a single persistent server is suitable for a small classroom. Streamlit Community Cloud may restart and lose local SQLite data; use a persistent host or replace the database with PostgreSQL for reliable public hosting. Secure access with HTTPS and a strong admin password. Team access is by session code and team PIN.

## Quiz

20 curated, simplified VerbNet-style thematic role questions. These test semantic role concepts, not automatic VerbNet class/frame assignment. Questions and explanations are in `questions.py`.

## Flow

Instructor creates round, teams join and submit. Submission progress is visible, but marks and answers are hidden until instructor clicks Reveal. If everyone submits, Reveal becomes available; instructor may also close an unfinished round and reveal results (unsubmitted teams receive zero). After reveal, everyone sees scores and explanations. Tie ranking uses shared rank; no speed bonus.
