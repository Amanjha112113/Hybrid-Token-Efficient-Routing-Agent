# Bugfix Requirements Document

## Introduction

The router system exhibits a critical logic inversion bug where it correctly predicts that a local model can handle a query but then routes the request to an expensive cloud model instead. This completely defeats the purpose of intelligent routing, resulting in 100% cloud usage instead of the expected 85% local routing for simple queries. The bug manifests as a disconnect between the router's reasoning logic and its actual routing decision, causing significant cost increases and resource waste.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the router analyzes a simple query like "hi" THEN the system predicts "Local model can handle this (low complexity)" with 52% confidence but routes to cloud model (Fireworks Ember-1)

1.2 WHEN the router displays "Marginal preference for local" in the UI THEN the system still routes the query to the expensive cloud model instead of the local model

1.3 WHEN the router reasoning indicates low complexity suitable for local processing THEN the system ignores this assessment and sends all traffic to cloud providers

### Expected Behavior (Correct)

2.1 WHEN the router analyzes a simple query and predicts "Local model can handle this (low complexity)" THEN the system SHALL route the query to the local model

2.2 WHEN the router displays "Marginal preference for local" or any local preference THEN the system SHALL honor this decision and route to the local model

2.3 WHEN the router reasoning indicates low complexity suitable for local processing THEN the system SHALL consistently route such queries to the local model to achieve cost savings

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the router predicts that a query requires cloud model capabilities THEN the system SHALL CONTINUE TO route complex queries to cloud models

3.2 WHEN the router confidence is below configured thresholds for local routing THEN the system SHALL CONTINUE TO use appropriate fallback routing logic

3.3 WHEN the router processes high-complexity queries requiring advanced capabilities THEN the system SHALL CONTINUE TO route to cloud models as designed