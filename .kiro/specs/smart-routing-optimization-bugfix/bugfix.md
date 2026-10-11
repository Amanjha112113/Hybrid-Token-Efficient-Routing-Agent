# Bugfix Requirements Document

## Introduction

The hybrid router is currently over-routing technical educational queries to expensive cloud models when local models can provide excellent responses. This defeats the router's core purpose of cost optimization. Additionally, the frontend DebugChat component crashes when displaying router decision details, preventing users from understanding routing decisions and debugging the system.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a user asks technical educational queries (like "explain Tuples in python") THEN the router sends the query to expensive cloud models unnecessarily

1.2 WHEN the router processes queries that local models excel at THEN it wastes API costs by routing to cloud instead of leveraging local model capabilities

1.3 WHEN the frontend DebugChat component tries to display router decision details THEN it crashes with "Cannot read properties of undefined (reading 'toFixed')" at line 458

1.4 WHEN users want to understand router decisions for debugging THEN they cannot access the information due to frontend crashes

### Expected Behavior (Correct)

2.1 WHEN a user asks technical educational queries (like "explain Tuples in python") THEN the router SHALL recognize these as queries local models handle excellently and route to local model

2.2 WHEN the router processes educational/explanatory queries about programming concepts THEN it SHALL prioritize local models to optimize costs while maintaining response quality

2.3 WHEN the frontend DebugChat component displays router decision details THEN it SHALL render without crashing and show complete router decision information

2.4 WHEN users access the DebugChat component THEN they SHALL be able to see routing decisions, costs, and performance metrics for debugging purposes

### Unchanged Behavior (Regression Prevention)

3.1 WHEN queries require complex reasoning, creative tasks, or specialized knowledge beyond local model capabilities THEN the router SHALL CONTINUE TO route to cloud models appropriately

3.2 WHEN queries involve tasks that genuinely benefit from larger cloud models THEN the router SHALL CONTINUE TO make cost-effective routing decisions

3.3 WHEN the router processes queries that local models cannot handle well THEN it SHALL CONTINUE TO route to cloud models to maintain response quality

3.4 WHEN users interact with other frontend components THEN they SHALL CONTINUE TO function normally without crashes or regressions