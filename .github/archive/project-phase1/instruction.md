CloudFolio Migration & Operations Blueprint
Cloudfolio currently a canary project with a single user would be migrated to an early adoption stage. A kanban style github projects have been created for issue and backlog tracking. 

Analyse `codebase` to understand ( cloudfolio ) project. Do an agile review and generate plan/issues to migrate and resolve plan/issues. Document migration plan into `.github/project` and generate files for guiding AI coding agents and human developers to achieve success.

Also document github project board and issue tracking for migration plan and progress. This would be copied to github projects board for tracking.

Context:
Monolithic architecture: `api` currently bundles everything together and not exploiting microservices. stateful operations are bundled with durable orchestration, a high i/o operation, and a model training, a high cpu/gpu compute operation.

Orchestration triggers model training if new fingerprint, we can perform orchestration and store state for model training use.
Model training should ideally occur sparingly so high compute resource can be provisioned for training only purpose and decommissioned immediately after. Resource does not have to be a flex or even a function app.
This way, we can deploy a heavy resource to perform high cpu task and decommission immediately after.

Mission
Decouple bottlenecks: Separate compute-heavy operations (model training), I/O-bound tasks (GitHub sync), and stateful services (cache) into independently scalable services.
Multi-tenant ready: Design each service with tenant isolation patterns (username-based routing, per-user quotas) from day one.
Cost-conscious infrastructure: Start with minimal flex function app; scale only proven bottlenecks.
Zero-downtime migration: Keep Function App running until each microservice proves production-ready.

Guiding Principles
Start with data, not services: The cache layer is the contract between all services—nail it first.
One bottleneck per week: Only extract services that solve measured performance/cost problems.
Feature flags over big-bang: Deploy behind environment variables; roll back via config, not code.
Document as you build: Every service gets a README with local dev setup, API contract, and rollback procedure.
Multi-tenant defaults: All services accept username parameter; log/trace with tenant context for future quota enforcement.
Decouple bottlenecks: Separate compute-heavy operations (model training), I/O-bound tasks (GitHub sync), and stateful services (cache) into independently scalable services.





