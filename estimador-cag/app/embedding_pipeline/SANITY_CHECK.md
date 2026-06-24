# Session 07 Embedding Sanity Check

Model used:

    text-embedding-3-small

Date:

    2026-06-04

Live run timestamp:

    2026-06-04 12:22 Europe/Warsaw

## Results

| Pair | Text A | Text B | Expected intuition | Cosine similarity |
| --- | --- | --- | --- | --- |
| A | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app | Authorization service using JSON Web Tokens for a banking application | High similarity, roughly above 0.6 | 0.5957 |
| B | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app | Database migration from MySQL to PostgreSQL with zero downtime | Lower similarity, roughly below 0.4 | 0.1920 |
| C | Backend services | API development | Ambiguous generic pair | 0.5407 |

## Comment

Pair A landed just below the rough 0.6 expectation, but it is still much closer than Pair B. That is a useful reminder that thresholds are not universal laws; wording, model behavior, and domain overlap matter.

Pair B behaved as expected: authentication for a fintech app and database migration are both software topics, but semantically different enough to produce a clearly lower score.

Pair C is intentionally ambiguous. “Backend services” and “API development” are broad, overlapping phrases, so a moderate score is plausible even though the texts are not very specific.

This is a smoke sanity check only. It proves that the embedding pipeline runs end to end and gives plausible distances for three hand-picked pairs. It is not a formal retrieval evaluation, and it does not measure recall@k, NDCG, ranking quality, chunking quality, or production retrieval behavior.
