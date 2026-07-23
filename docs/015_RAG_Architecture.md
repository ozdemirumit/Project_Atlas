# Project Atlas

## RAG Architecture

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the retrieval-augmented generation architecture for Atlas knowledge usage.

## 2. Knowledge Sources

- Vendor documentation
- REST API documentation
- CLI documentation
- KB articles
- Product manuals
- Internal runbooks
- Incident records
- Problem records
- Change records
- Architecture documents
- CMDB exports
- Operational notes

## 3. Ingestion Requirements

Each ingested item must preserve:

- Source name
- Source type
- Version
- Owner
- Ingestion time
- Document timestamp when available
- Access classification
- Chunk metadata
- Retrieval traceability

## 4. Retrieval Principles

- Prefer trusted enterprise and vendor sources.
- Include source references in AI answers.
- Separate public vendor knowledge from internal operational knowledge.
- Respect user permissions when retrieving knowledge.
- Track stale or superseded documents.

## 5. Open Questions

- Which vector database should be selected first?
- Which document formats are in MVP?
- How will restricted documents be filtered by role?
