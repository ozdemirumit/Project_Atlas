# Project Atlas

## Vector Database

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines vector database requirements for Atlas RAG capabilities.

## 2. VectorDB Goals

- Store embeddings for vendor and internal knowledge.
- Support metadata filtering.
- Support access-controlled retrieval.
- Support document versioning and freshness.
- Support local enterprise deployment.

## 3. Required Capabilities

- Collection management
- Metadata filters
- Hybrid retrieval option if needed
- Deletion and re-ingestion
- Backup and restore
- Restricted-network deployment
- Performance suitable for chat use

## 4. Candidate Options

Potential candidates may include Qdrant, PostgreSQL with vector support, or another enterprise-suitable vector store. Selection requires an architecture decision record.

## 5. Open Questions

- Which vector database should be selected first?
- How should embeddings be generated in restricted environments?
- How should access control metadata be enforced?
