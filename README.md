# cnd-workshop-2026
Repo with guide and assets to follow the 2026 CND Romania workshop: Observability unlocked with
OpenTelemetry and the VictoriaMetrics Stack

# Abstract

Observability doesn’t have to be hard. In this hands-on workshop, we’ll show how to go from zero to
Kubernetes observability in minutes with Open Source projects like VictoriaMetrics, AlertManager,
OpenTelemetry or Grafana.

This will be done with practical, live examples. We’ll learn how to generate, process and export
metrics and logs by:* Deploying a demo app, collecting data with OpenTelemetry collectors and
exporting them with proper authentication
* Exploring metrics cardinality and integrating dashboards with Grafana
* Learn metrics and logs dynamics over time to improve quality and maintenance of our observability
setup with anomaly detection mechanisms
* Create alerts and get notified before problems escalate
* We’ll give a preview of distributed tracing with VictoriaTraces
* We’ll also cover log visualization and aggregation, together with metrics generation from other
signals

By the end, you’ll have the knowledge to build a production-grade observability stack from scratch - fast, reliable, and scalable.

# Links
* Workshop link: https://cloudnativedays.ro/workshops/a130c5e1-fe82-4b06-93c9-c5f65a3e6d9d
* Repo link: https://github.com/jgomezselles/cnd-workshop-2026

# TODOs
- [ ] Presentation
- [X] Create repo
- [X] Create workshop organization
  - [X] Provide credits for the cluster
  - [ ] Run cluster 2 days before the WS
  - [ ] Invite users into the org
  - [ ] Assign tenants


# Part I

## OpenTelemetry intro
[OpenTelemetry](https://opentelemetry.io/) is a collection of **APIs**, **SDKs**, and **tools**. Use it to
instrument, generate, collect, and export telemetry data (metrics, logs, and traces) to help you
analyze your software’s performance and behavior.

> **NOTE**: OpenTelemetry is NOT (and does not provide):
> * A visualization tool
> * Ways of storing signals (databases)

### Main concepts
* Auto-instrumentation
* Collector
* Standard/Specification
* Libraries for all languages

## OpenTelemetry collector intro
One of this tools is the [OpenTelemetry collector](https://opentelemetry.io/docs/collector/), which
provides a vendor-agnostic implementation that:
* allows to receive, process and export telemetry data
* removes the need to run, operate, and maintain multiple agents/collectors
* allows sending data to one or more open source or commercial backends.

## Install OpenTelemetry collector
TBD

## Watch metrics in Cloud
TBD

## Manual instrumentation
TBD

## Deploy demo app
TBD

## Integrate with Grafana (With backup dashboard)
TBD

## Exploring metrics cardinality
TBD

## LogsQL playthrough
TBD
* _time: 10s
* count()

## Integrate logs with Grafana
TBD

## Integrate alerts with slack
TBD

## Create alert
TBD

## MCP!
TBD