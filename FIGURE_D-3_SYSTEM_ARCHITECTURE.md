# Figure D-3: System architecture diagram

```mermaid
flowchart LR
    learner([Learner]) --> app["Frontend<br/>readright-app"]

    app -->|Sign-in, passages, session history| db[("Supabase<br/>Auth + database")]
    app -.->|Legacy POST /analyze<br/>contract mismatch| bff["Backend / BFF<br/>readright-api"]

    bff -->|Learner data and results| db
    bff -->|Signs and verifies uploads| s3[("S3<br/>recordings")]
    app -.->|Signed upload flow<br/>not wired in checked app history| s3
    bff <-->|Analysis request / result| mai["External MAI 1.1.0"]

    subgraph ai["readright-ai — README design only"]
        server["AI server<br/>fetch + preprocess"] --> audio["Audio service"]
        server --> video["Video service"]
    end
    bff -.->|Integration not verified| server
    s3 -.->|README design| server
```

Solid arrows show the current app/backend responsibilities described in the repositories. Dashed arrows mark a legacy or unverified integration. The checked `readright-ai` snapshot contains only its README.
