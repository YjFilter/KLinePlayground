# Project Direction

## Product
KLinePlayground is a Windows desktop application for A-share K-line replay, simulated trading, deliberate practice, and post-session review.

## Target Users
- Individual A-share investors practicing entry, exit, position, and review discipline.
- Strategy learners who need offline market data and repeatable historical scenarios.
- Users who want optional AI assistance without surrendering control of core trading rules.

## Core Value
Provide a realistic, explainable, repeatable training environment that combines chart replay, A-share trading constraints, account simulation, structured reasons, history reports, and AI-assisted review.

## In Scope
- User profiles and settings.
- Historical market-data loading and replay.
- Manual and pending-order simulation.
- A-share market rules and transaction costs.
- Account, position, trade, order, and report history.
- Desktop packaging and offline-friendly operation.
- Optional AI strategy testing and review support.

## Success Metrics
- Core trading invariants are protected by automated regression tests.
- A fresh Codex session can restore project status from repository files.
- A worker can execute a ready task without reading the entire repository.
- Every completed task has owner, scope, diff, commands, evidence, and acceptance.
- Desktop startup and packaging remain repeatable.

## Non-Goals
- Autonomous real-money trading.
- An independent general-purpose Agent orchestration platform.
- Unattended releases or destructive data migrations.
- Large rewrites without an approved migration plan and regression baseline.
