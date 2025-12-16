import pandas as pd
from scoring import score_grad_suitability

# Example “jobs” – replace with real scraped output later
jobs = [
    {
        "title": "Operations Coordinator",
        "location": "London",
        "url": "https://example.com/job1",
        "description": "Entry-level role. Training provided. Internship experience welcome.",
        "department": "Operations",
        "seniority": ""
    },
    {
        "title": "Senior Commercial Manager",
        "location": "London",
        "url": "https://example.com/job2",
        "description": "5+ years experience required. Lead strategy.",
        "department": "Commercial",
        "seniority": "Senior"
    },
]

rows = []
for j in jobs:
    res = score_grad_suitability(
        title=j["title"],
        description=j.get("description", ""),
        department=j.get("department", ""),
        seniority=j.get("seniority", ""),
    )
    if res.bucket != "EXCLUDE":
        rows.append({
            **j,
            "bucket": res.bucket,
            "score": res.score,
            "reasons": " | ".join(res.reasons),
        })

df = pd.DataFrame(rows)
df.to_csv("jobs_output.csv", index=False)
print(df[["title", "bucket", "score"]])
