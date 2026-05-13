# cnd-workshop-2026
Repo with guide and assets to follow the 2026 CND Romania workshop: Observability unlocked with
OpenTelemetry and the VictoriaMetrics Stack

# Abstract

Observability doesn’t have to be hard. In this hands-on workshop, we’ll show how to go from zero to
Kubernetes observability in minutes with Open Source projects like VictoriaMetrics, AlertManager,
OpenTelemetry or Grafana.

This will be done with practical, live examples. We’ll learn how to generate, process and export
metrics and logs by:
* Deploying a demo app, collecting data with OpenTelemetry collectors and
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
- [ ] Add pics
- [ ] Correct links to yamls
- [ ] Correct pics links

# Requirements

## Tooling
* Docker (tested on versions:  Client - 28.2.2 , Server 29.4.0)
* Docker compose (tested on version v2.13.0)
* POSIX shell for helper scripts: Linux/macOS Terminal or WSL 2 on Windows
* Small k8s distro: minikube, kind or similar
* kubectl: (tested on version: v1.33.1)
* Helm: (tested on version: v3.18.1)

# Part I

## [OpenTelemetry Introduction](1-1-OpenTelemetry-Intro/Readme.md)
## [Forwarding Metrics](1-2-Forwarding-metrics/Readme.md)
## [Instrumentation](1-3-Instrumentation/Readme.md)
## [Forwarding Logs](1-4-Forwarding-logs/Readme.md)
## [Dashboards](1-5-Dashboards/Readme.md)

