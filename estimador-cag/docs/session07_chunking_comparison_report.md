# Session 07 Chunking Comparison

This report is deterministic and does not call OpenAI.
It uses a small keyword-count fake embedder to show retrieval mechanics.

## Strategy statistics

| Strategy | Chunks | Total tokens | Avg tokens | Min tokens | Max tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| structural_component | 8 | 837 | 104.62 | 97 | 123 |
| whole_budget | 4 | 731 | 182.75 | 174 | 197 |

## Query rankings

### Q-AUTH-001

Query: OAuth JWT authentication token banking authorization flow

Expected budget: BUD-2024-014

Expected components: AUTH-001

#### Strategy: structural_component

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2024-014::AUTH-001 | 0.9364 | [Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance] [Client sector: finance \| Country: ES \| Year: 2024 \| Main technology: ruby_on_rails \| Total estimated hours: 480] Component: OAuth 2.0 authentica |
| 2 | BUD-2024-014::AUDIT-001 | 0.6325 | [Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance] [Client sector: finance \| Country: ES \| Year: 2024 \| Main technology: ruby_on_rails \| Total estimated hours: 480] Component: Regulatory audit log |

#### Strategy: whole_budget

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2024-014::whole_budget | 0.8845 | Full budget: BUD-2024-014 Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance Client sector: finance \| Country: ES \| Year: 2024 Main technology: ruby_on_rails Total estimated hours: 480 Components: - |
| 2 | BUD-2024-021::whole_budget | 0.0870 | Full budget: BUD-2024-021 Project: Marketplace checkout modernization with inventory synchronization and merchant dashboards Client sector: e-commerce \| Country: PL \| Year: 2024 Main technology: python_fastapi Total estimated hours: 390 Com |

### Q-AUDIT-001

Query: immutable audit logging consent changes sensitive banking operations

Expected budget: BUD-2024-014

Expected components: AUDIT-001

#### Strategy: structural_component

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2024-014::AUDIT-001 | 0.7454 | [Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance] [Client sector: finance \| Country: ES \| Year: 2024 \| Main technology: ruby_on_rails \| Total estimated hours: 480] Component: Regulatory audit log |
| 2 | BUD-2025-003::INTAKE-001 | 0.3333 | [Project: Patient intake platform with document upload, triage rules, and clinician review workflow] [Client sector: healthcare \| Country: DE \| Year: 2025 \| Main technology: java_spring_boot \| Total estimated hours: 520] Component: Patient  |

#### Strategy: whole_budget

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2024-014::whole_budget | 0.4811 | Full budget: BUD-2024-014 Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance Client sector: finance \| Country: ES \| Year: 2024 Main technology: ruby_on_rails Total estimated hours: 480 Components: - |
| 2 | BUD-2025-003::whole_budget | 0.1291 | Full budget: BUD-2025-003 Project: Patient intake platform with document upload, triage rules, and clinician review workflow Client sector: healthcare \| Country: DE \| Year: 2025 Main technology: java_spring_boot Total estimated hours: 520 C |

### Q-CHECKOUT-001

Query: checkout orchestration payment authorization discount rules order creation

Expected budget: BUD-2024-021

Expected components: CHECKOUT-001

#### Strategy: structural_component

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2024-021::CHECKOUT-001 | 0.8165 | [Project: Marketplace checkout modernization with inventory synchronization and merchant dashboards] [Client sector: e-commerce \| Country: PL \| Year: 2024 \| Main technology: python_fastapi \| Total estimated hours: 390] Component: Checkout o |
| 2 | BUD-2024-021::INV-001 | 0.2981 | [Project: Marketplace checkout modernization with inventory synchronization and merchant dashboards] [Client sector: e-commerce \| Country: PL \| Year: 2024 \| Main technology: python_fastapi \| Total estimated hours: 390] Component: Inventory  |

#### Strategy: whole_budget

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2024-021::whole_budget | 0.6155 | Full budget: BUD-2024-021 Project: Marketplace checkout modernization with inventory synchronization and merchant dashboards Client sector: e-commerce \| Country: PL \| Year: 2024 Main technology: python_fastapi Total estimated hours: 390 Com |
| 2 | BUD-2024-014::whole_budget | 0.0962 | Full budget: BUD-2024-014 Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance Client sector: finance \| Country: ES \| Year: 2024 Main technology: ruby_on_rails Total estimated hours: 480 Components: - |

### Q-INVENTORY-001

Query: inventory synchronization worker merchant stock levels scheduled conflicts events

Expected budget: BUD-2024-021

Expected components: INV-001

#### Strategy: structural_component

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2024-021::INV-001 | 0.7303 | [Project: Marketplace checkout modernization with inventory synchronization and merchant dashboards] [Client sector: e-commerce \| Country: PL \| Year: 2024 \| Main technology: python_fastapi \| Total estimated hours: 390] Component: Inventory  |
| 2 | BUD-2024-021::CHECKOUT-001 | 0.2500 | [Project: Marketplace checkout modernization with inventory synchronization and merchant dashboards] [Client sector: e-commerce \| Country: PL \| Year: 2024 \| Main technology: python_fastapi \| Total estimated hours: 390] Component: Checkout o |

#### Strategy: whole_budget

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2024-021::whole_budget | 0.6030 | Full budget: BUD-2024-021 Project: Marketplace checkout modernization with inventory synchronization and merchant dashboards Client sector: e-commerce \| Country: PL \| Year: 2024 Main technology: python_fastapi Total estimated hours: 390 Com |
| 2 | BUD-2024-014::whole_budget | 0.0000 | Full budget: BUD-2024-014 Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance Client sector: finance \| Country: ES \| Year: 2024 Main technology: ruby_on_rails Total estimated hours: 480 Components: - |

### Q-DOCS-001

Query: clinical document upload referral lab results secure file validation metadata

Expected budget: BUD-2025-003

Expected components: DOCS-001

#### Strategy: structural_component

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2025-003::DOCS-001 | 0.9272 | [Project: Patient intake platform with document upload, triage rules, and clinician review workflow] [Client sector: healthcare \| Country: DE \| Year: 2025 \| Main technology: java_spring_boot \| Total estimated hours: 520] Component: Clinical |
| 2 | BUD-2025-003::INTAKE-001 | 0.6667 | [Project: Patient intake platform with document upload, triage rules, and clinician review workflow] [Client sector: healthcare \| Country: DE \| Year: 2025 \| Main technology: java_spring_boot \| Total estimated hours: 520] Component: Patient  |

#### Strategy: whole_budget

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2025-003::whole_budget | 0.9037 | Full budget: BUD-2025-003 Project: Patient intake platform with document upload, triage rules, and clinician review workflow Client sector: healthcare \| Country: DE \| Year: 2025 Main technology: java_spring_boot Total estimated hours: 520 C |
| 2 | BUD-2024-014::whole_budget | 0.0000 | Full budget: BUD-2024-014 Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance Client sector: finance \| Country: ES \| Year: 2024 Main technology: ruby_on_rails Total estimated hours: 480 Components: - |

### Q-TELEMETRY-001

Query: machine telemetry ingestion queue consumer equipment events industrial dashboard

Expected budget: BUD-2025-011

Expected components: TELEM-001

#### Strategy: structural_component

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2025-011::TELEM-001 | 0.8006 | [Project: Industrial maintenance dashboard with equipment telemetry ingestion and alerting] [Client sector: industrial \| Country: NL \| Year: 2025 \| Main technology: node_typescript \| Total estimated hours: 430] Component: Telemetry ingestio |
| 2 | BUD-2025-011::ALERT-001 | 0.4330 | [Project: Industrial maintenance dashboard with equipment telemetry ingestion and alerting] [Client sector: industrial \| Country: NL \| Year: 2025 \| Main technology: node_typescript \| Total estimated hours: 430] Component: Maintenance alert  |

#### Strategy: whole_budget

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2025-011::whole_budget | 0.6667 | Full budget: BUD-2025-011 Project: Industrial maintenance dashboard with equipment telemetry ingestion and alerting Client sector: industrial \| Country: NL \| Year: 2025 Main technology: node_typescript Total estimated hours: 430 Components: |
| 2 | BUD-2024-021::whole_budget | 0.1231 | Full budget: BUD-2024-021 Project: Marketplace checkout modernization with inventory synchronization and merchant dashboards Client sector: e-commerce \| Country: PL \| Year: 2024 Main technology: python_fastapi Total estimated hours: 390 Com |

### Q-ALERTS-001

Query: maintenance alert rules threshold violations machine faults operations teams

Expected budget: BUD-2025-011

Expected components: ALERT-001

#### Strategy: structural_component

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2025-011::ALERT-001 | 0.8660 | [Project: Industrial maintenance dashboard with equipment telemetry ingestion and alerting] [Client sector: industrial \| Country: NL \| Year: 2025 \| Main technology: node_typescript \| Total estimated hours: 430] Component: Maintenance alert  |
| 2 | BUD-2025-011::TELEM-001 | 0.4804 | [Project: Industrial maintenance dashboard with equipment telemetry ingestion and alerting] [Client sector: industrial \| Country: NL \| Year: 2025 \| Main technology: node_typescript \| Total estimated hours: 430] Component: Telemetry ingestio |

#### Strategy: whole_budget

| Rank | Chunk ID | Score | Preview |
| ---: | --- | ---: | --- |
| 1 | BUD-2025-011::whole_budget | 0.7778 | Full budget: BUD-2025-011 Project: Industrial maintenance dashboard with equipment telemetry ingestion and alerting Client sector: industrial \| Country: NL \| Year: 2025 Main technology: node_typescript Total estimated hours: 430 Components: |
| 2 | BUD-2024-014::whole_budget | 0.0000 | Full budget: BUD-2024-014 Project: Mobile banking API with OAuth 2.0 authentication, JWT sessions, and PSD2 compliance Client sector: finance \| Country: ES \| Year: 2024 Main technology: ruby_on_rails Total estimated hours: 480 Components: - |

## Caveat

This is a learning report, not a production retrieval evaluation.
The fake embedder is deterministic and useful for mechanics, but it is not semantic.
Live embedding and persisted retrieval should be evaluated separately.
