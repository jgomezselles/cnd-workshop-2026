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


# Requirements

## Tooling
* docker
* small k8s distro: minikube, kind or similar
* helm

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
TODO:
* Download charts (helm repo add, )
* Download generic values file of the OTel collector and inspect
  * Notice different important sections (receivers, exporters, processors, connectors and service pipelines)
  * Explain the contrib image we will use: https://github.com/open-telemetry/opentelemetry-collector-contrib
* Explain the concept of presets: https://opentelemetry.io/docs/platforms/kubernetes/helm/collector/#presets

* Create namespace (cnd-ws)
* helm dep update
* install the collector with step-1.yaml like "helm install ws helm/cnd-demo -f helm/values/step-1.yaml -n cnd-ws"

### First approach debugging the collector

We will use the [zpages extension](https://github.com/open-telemetry/opentelemetry-collector/blob/main/extension/zpagesextension/README.md).
After performing a port forwarding like:

```sh
kubectl port-forward -n cnd-ws deployments/otelcol 55679:55679
```
We can observe (taken from the docs):

| zPages route | Description | URL  |
|--------------|-------------|------|
| **ServiceZ** | Overview of the collector services and quick access to the pipelinez, extensionz, and featurez zPages.|  http://localhost:55679/debug/servicez |
| **PipelineZ** | Running pipelines in the collector | http://localhost:55679/debug/pipelinez |
| **ExtensionZ**| Shows the extensions that are active in the collector.|  http://localhost:55679/debug/extensionz |
| **FeatureZ** | Lists the feature gates available along with their current status and description. | http://localhost:55679/debug/featurez |
| **TraceZ**| Available to examine and bucketize spans by latency buckets | http://localhost:55679/debug/tracez |
| ExpvarZ | Useful information about Go runtime | http://localhost:55679/debug/expvarz |


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