# Project Atlas

## Graph Engine

**Version:** 0.1 Draft  
**Status:** In Progress

## 1. Purpose

This document defines the infrastructure graph model used by Atlas for topology, dependency, impact, and root cause analysis.

## 2. Graph Goals

- Model infrastructure components and relationships.
- Support blast radius analysis.
- Support root cause analysis.
- Support change impact analysis.
- Support service dependency mapping.
- Support digital twin capabilities in later phases.

## 3. Example Entities

- Site
- Datacenter
- Rack
- Storage system
- Controller
- Pool
- Volume
- LUN
- SAN fabric
- SAN switch
- Host
- Cluster
- VM
- Datastore
- Application service
- Backup job

## 4. Example Relationships

- Application runs on VM
- VM uses datastore
- Datastore maps to volume
- Volume belongs to pool
- Pool belongs to storage system
- Host connects to SAN switch
- Backup job protects VM

## 5. Open Questions

- Which graph database should be selected first?
- Which relationships are mandatory for MVP?
- How will stale relationships be detected?
