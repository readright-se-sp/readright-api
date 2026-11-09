# Figure D-1: ReadRight use-case diagram

```mermaid
flowchart LR
    Learner["👤 Learner"]
    Supabase["Supabase Auth / Database"]
    Storage["Object storage (S3)"]

    subgraph ReadRight["ReadRight platform — app, API, and AI service"]
        direction TB
        UC11(["UC-1.1 Authenticate or register"])
        UC12(["UC-1.2 Start a reading session"])
        UC2(["UC-2.x Check device readiness"])
        UC3a(["UC-3.x Record and submit reading"])
        UC3b(["Answer comprehension questions"])
        Analyze(["Analyze reading and detect miscues"])
        UC41(["UC-4.1 View session results"])
        UC42(["UC-4.2 Save session results"])
        UC43(["UC-4.3 View progress trends"])
        UC44(["UC-4.4 Review miscues and reading behaviors"])
        History(["Browse reading history and past results"])

        UC12 -. "includes" .-> UC2
        UC12 -. "includes" .-> UC3a
        UC12 -. "includes" .-> UC3b
        UC3a -. "includes" .-> Analyze
        UC41 -. "includes" .-> UC42
        UC43 -. "includes" .-> UC44
    end

    Learner --- UC11
    Learner --- UC12
    Learner --- UC2
    Learner --- UC3a
    Learner --- UC3b
    Learner --- UC41
    Learner --- UC43
    Learner --- History

    Supabase --- UC11
    Supabase --- UC42
    Supabase --- UC43
    Storage --- UC3a
```

The diagram covers the learner-facing flow documented in `readright-app`'s `dev` branch and the supporting persistence and recording-upload behavior implemented across the repositories. The frontend's route map names UC-1.1, UC-1.2, UC-2.x, UC-3.x, and UC-4.1 through UC-4.4; it does not assign an ID to the comprehension quiz or history pages, so those are shown without invented IDs. I did not find a separate pre-existing Figure D-1 file in the linked repositories.

Sources: `readright-app` `dev` branch (`src/App.jsx`, `src/lib/api.js`, `src/pages/SessionScreen.jsx`, `ARCHITECTURE.md`); `readright-api` `dev` branch (session, result, dashboard, and storage features); `readright-ai` `dev` branch (`server/app/routes/analyses.py`).
