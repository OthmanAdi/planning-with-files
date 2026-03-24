# Task Plan: [Analytics Project Description]
<!--
  WHAT: Roadmap for a data analytics or exploration session.
  WHY: Analytics workflows have different phases than software development — hypothesis testing,
       data quality checks, and statistical validation don't map to a generic build cycle.
  WHEN: Create this FIRST before starting any data exploration. Update after each phase.
-->

## Goal
<!--
  WHAT: One clear sentence describing what you're trying to learn or produce.
  EXAMPLE: "Determine which user segments have the highest churn risk using last 90 days of activity data."
-->
[One sentence describing the analytical objective]

## Current Phase
<!--
  WHAT: Which phase you're currently working on (e.g., "Phase 1", "Phase 3").
  WHY: Quick reference for where you are. Update this as you progress.
-->
Phase 1

## Phases

### Phase 1: Data Discovery
<!--
  WHAT: Connect to data sources, understand schemas, assess data quality.
  WHY: Bad data produces bad analysis. This phase prevents wasted effort on unreliable inputs.
-->
- [ ] Identify and connect to data sources
- [ ] Document schemas and field descriptions in findings.md
- [ ] Assess data quality (nulls, duplicates, outliers, date ranges)
- [ ] Estimate dataset size and query performance
- **Status:** in_progress

### Phase 2: Exploratory Analysis
<!--
  WHAT: Distributions, correlations, outliers, initial patterns.
  WHY: Understanding the shape of your data before testing hypotheses prevents false conclusions.
-->
- [ ] Compute summary statistics for key variables
- [ ] Visualize distributions and relationships
- [ ] Identify outliers and anomalies
- [ ] Document initial patterns in findings.md
- **Status:** pending

### Phase 3: Hypothesis Testing
<!--
  WHAT: Formalize hypotheses, run statistical tests, validate findings.
  WHY: Moving from "it looks like X" to "we can confidently say X" requires structured testing.
-->
- [ ] Formalize hypotheses from exploratory phase
- [ ] Select appropriate statistical tests
- [ ] Run tests and record results in findings.md
- [ ] Validate findings against holdout data or alternative methods
- **Status:** pending

### Phase 4: Synthesis & Reporting
<!--
  WHAT: Summarize findings, create visualizations, document conclusions.
  WHY: Analysis without clear communication is wasted work. This phase produces the deliverable.
-->
- [ ] Summarize key findings with supporting evidence
- [ ] Create final visualizations
- [ ] Document conclusions and recommendations
- [ ] Note limitations and areas for further investigation
- **Status:** pending

## Hypotheses
<!--
  WHAT: Questions you're investigating, stated as testable hypotheses.
  WHY: Explicit hypotheses prevent fishing expeditions and keep analysis focused.
  EXAMPLE:
    1. Users who logged in < 3 times in the last 30 days have > 50% churn rate (H1)
    2. Feature X adoption correlates with retention (r > 0.3) (H2)
-->
1. [Hypothesis to test]
2. [Hypothesis to test]

## Decisions Made
<!--
  WHAT: Analytical decisions with reasoning (e.g., choosing a test, filtering criteria).
  EXAMPLE:
    | Use median instead of mean | Revenue data is heavily right-skewed |
    | Filter to last 90 days | Earlier data uses a different tracking schema |
-->
| Decision | Rationale |
|----------|-----------|
|          |           |

## Errors Encountered
<!--
  WHAT: Every error you encounter, what attempt number it was, and how you resolved it.
  EXAMPLE:
    | Query timeout on raw table | 1 | Added date partition filter |
    | Null join keys in user_events | 2 | Inner join instead of left join, documented data loss |
-->
| Error | Attempt | Resolution |
|-------|---------|------------|
|       | 1       |            |

## Notes
- Update phase status as you progress: pending -> in_progress -> complete
- Re-read this plan before major analytical decisions
- Log ALL errors - they help avoid repetition
- Write query results and visual findings to findings.md immediately
