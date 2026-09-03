# Business Backend Standards (Ruby on Rails)

Refines `docs/base-standards.md` for `business-backend/`. The context map lives in
`business-backend/ARCHITECTURE.md`.

> The patterns below are stack-independent. This Rails app is the reference
> implementation of the *cliente*; if your business backend is not Rails, apply the
> same boundaries with your framework's equivalents.

## The AI service client is the only door

`app/services/estimator_ai/` is the single place that speaks HTTP to the AI service.
Controllers, models and jobs call a client, never Faraday or `Net::HTTP` directly.

`base_client.rb` owns the base URL, the shared `X-Service-Token` header, the timeouts
and the mapping from HTTP status to the shared error taxonomy. One client per context
inherits from it:

```ruby
# app/services/estimator_ai/base_client.rb (extract)
module EstimatorAi
  Error              = Class.new(StandardError)
  InvalidRequest     = Class.new(Error)
  GuardrailViolation = Class.new(Error)
  SessionNotFound    = Class.new(Error)
  ServerError        = Class.new(Error)
  Unauthorized       = Class.new(Error)   # bad service token or API key
  ServiceUnavailable = Class.new(Error)   # a dependency is down — transient
  RateLimited        = Class.new(Error)   # carries Retry-After
  Conflict           = Class.new(Error)   # understood and refused

  SERVICE_TOKEN_HEADER = "X-Service-Token".freeze
end
```

Subclass headers win over the defaults, which is how `RagEstimateClient` keeps its own
`X-API-Key` while still sending the service token. The client does not own retry
*policy* — that belongs to the calling use case, stated explicitly.

**The namespace is `EstimatorAi` and the base-URL variable is
`ESTIMATOR_API_BASE_URL`.** Both are historical and deliberately were not renamed with
the directories. Do not "fix" them.

## Contract POROs mirror the Pydantic schemas 1:1

`from_hash` ↔ `model_validate`. A response becomes a typed object
(`Rag::TaskHoursEstimateView`, `Estimation::Response`) before a view sees it; views
render typed objects, never raw JSON. ActiveRecord roots persist the full payload as
JSONB alongside the parsed columns.

Parsing uses **explicit keys** (`.slice("a", "b")`), which is what makes an added
field on the AI service side backward compatible. That is a property to verify in the
technical contract, not to assume.

## Domain logic does not live in a view object

If a value needs normalizing, converting or interpreting, decide who owns it and say
so in the technical contract. A `0..100` score computed in a Ruby view object is
domain logic that leaked into presentation: every other consumer of that endpoint has
to reimplement it, and no test covers it.

## Degrading gracefully is a product decision

When the AI service returns `503` (`ServiceUnavailable`), the user must see something
honest and useful. The spec states exactly what: a message, a retry affordance, or a
stored previous result — one of them, chosen, never "handle the error".

The `guard_*_errors` controller wrappers must rescue the whole taxonomy, `Unauthorized`
included. An unrescued client exception renders a Rails 500 page, which tells the user
nothing and the operator less.

## Controllers and views

Controllers are thin: parse params, call one service object or client, render. No AI
service calls inline, no business rules, no formatting logic beyond presentation.

## Persistence

Anything the user must be able to see again is persisted by the business backend. The
AI service is stateless with respect to the product: **it is not a source of history**,
and it knows nothing about users. If a spec says "the user can review past estimates",
the data lives in the relational DB.

**Snapshot versus refetch is an explicit decision in every technical contract that
touches AI output**: either the response is stored as it was produced (stable and
auditable), or it is recomputed on read (and may change). Never leave it implicit.

Fields the UI routes on are mirrored from JSONB into real columns
(e.g. `requires_human_review`), with exactly **one writer** per column and a partial
index. Two writers for one mirrored column is a bug waiting for a race.

## Testing

**Minitest**, under `business-backend/test/` (`controllers/`, `integration/`,
`models/`, `services/`, `system/`). Run with `bin/rails test`; add
`bin/rails test:system` when a screen changes.

The AI service clients are tested against stubbed responses that match the current
schema. **When the contract changes, those tests change in the same pull request as
the Pydantic schema**, and `docs/contract/business-backend-consumed-routes.json` is
updated with them.
