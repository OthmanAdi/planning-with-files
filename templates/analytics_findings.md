# Findings & Decisions
<!--
  WHAT: Knowledge base for your analytics session. Stores data sources, hypotheses, and results.
  WHY: Context windows are limited. This file is your "external memory" for analytical work.
  WHEN: Update after ANY discovery, especially after running queries or viewing charts.
-->

## Data Sources
<!--
  WHAT: Every data source you connected to, with schema details and quality notes.
  WHY: Knowing where your data came from and its limitations is critical for reproducibility.
  EXAMPLE:
    | user_events | PostgreSQL prod replica | 2.3M rows | user_id, event_type, ts | 0.2% null user_id |
    | revenue.csv | Finance team export | 45K rows | account_id, mrr, churn_date | Complete, no nulls |
-->
| Source | Location | Size | Key Fields | Quality Notes |
|--------|----------|------|------------|---------------|
|        |          |      |            |               |

## Hypothesis Log
<!--
  WHAT: Each hypothesis you tested, the method used, and the result.
  WHY: Structured tracking prevents p-hacking and makes your reasoning auditable.
  EXAMPLE:
    | H1: Churn > 50% for low-activity users | Chi-squared test | Confirmed (p=0.003) | High |
    | H2: Feature X correlates with retention | Pearson correlation | Rejected (r=0.08) | High |
-->
| Hypothesis | Test Method | Result | Confidence |
|------------|-------------|--------|------------|
|            |             |        |            |

## Query Results
<!--
  WHAT: Key queries you ran and what they revealed.
  WHY: Queries are ephemeral - if you don't write down the results, they're lost on context reset.
  WHEN: After EVERY significant query. Don't wait.
  EXAMPLE:
    ### Churn rate by activity segment
    Query: SELECT activity_bucket, COUNT(*), AVG(churned) FROM user_segments GROUP BY 1
    Result: Low activity: 62% churn, Medium: 28%, High: 8%
    Interpretation: Strong inverse relationship between activity and churn
-->
<!-- Record query, result summary, and interpretation for each significant query -->

## Statistical Findings
<!--
  WHAT: Formal statistical test results with all relevant metrics.
  WHY: Recording p-values, effect sizes, and confidence intervals makes results reproducible.
  EXAMPLE:
    | Chi-squared (churn ~ activity) | p=0.003 | Cramer's V=0.31 | Reject null: activity segments differ significantly in churn |
    | Pearson (feature_x ~ retention) | p=0.42 | r=0.08 | Fail to reject: no meaningful correlation |
-->
| Test | p-value | Effect Size | Conclusion |
|------|---------|-------------|------------|
|      |         |             |            |

## Technical Decisions
<!--
  WHAT: Analytical method choices with reasoning.
  EXAMPLE:
    | Use log transform on revenue | Right-skewed distribution, normalizes for parametric tests |
-->
| Decision | Rationale |
|----------|-----------|
|          |           |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
|       |            |

## Resources
<!-- URLs, file paths, documentation links -->
-

## Visual/Browser Findings
<!--
  CRITICAL: Update after viewing charts, dashboards, or browser results.
  Multimodal content doesn't persist in context - capture as text immediately.
-->
-

---
*Update this file after every 2 view/browser/search operations*
*This prevents visual information from being lost*
