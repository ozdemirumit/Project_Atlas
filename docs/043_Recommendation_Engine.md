# Project Atlas

## Recommendation Engine

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines how Atlas produces operational recommendations.

## 2. Recommendation Requirements

Every recommendation must include:

- Recommended action
- Reason
- Evidence
- Confidence
- Risk level
- Expected impact
- Estimated duration
- Service interruption risk
- Preconditions
- Required approvals
- Rollback plan
- Alternatives

## 3. Recommendation Sources

- AI reasoning
- Policy rules
- Vendor documentation
- Internal runbooks
- Historical incidents
- Health check results
- Infrastructure graph analysis

## 4. Safety Requirements

- Recommendations must not be silently executed.
- Destructive actions must be blocked by default.
- Low-confidence recommendations must be clearly labeled.
- User approval must be audited.

## 5. Open Questions

- What is the first recommendation schema?
- How should recommendations be versioned?
- Which recommendations can be generated in MVP?
