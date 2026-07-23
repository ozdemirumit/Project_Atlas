# Project Atlas

## Root Cause Analysis

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the root cause analysis capability for Atlas.

## 2. RCA Goals

- Correlate events across domains.
- Use topology and dependency data.
- Compare current signals with historical incidents.
- Retrieve relevant vendor and internal knowledge.
- Present probable causes with evidence and uncertainty.

## 3. RCA Inputs

- Alerts
- Logs
- Metrics
- Connector health data
- Infrastructure graph
- Incident history
- Change history
- Knowledge retrieval results

## 4. RCA Output Format

- Incident summary
- Affected components
- Affected services
- Probable root causes
- Evidence per hypothesis
- Confidence
- Recommended next checks
- Recommended remediation plan
- Risk and rollback notes

## 5. Open Questions

- Which domain should be first RCA target?
- How should false positives be measured?
- How should RCA output be reviewed by engineers?
