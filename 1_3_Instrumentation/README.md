# Instrumentation

In this theoretical section, we will briefly explain OpenTelemetry Instrumentation.

## What is OpenTelemetry instrumentation?

[Instrumentation](https://opentelemetry.io/docs/concepts/instrumentation/) is the process of adding
observability to your application using the OpenTelemetry [APIs and SDKs](https://opentelemetry.io/docs/languages/).
The OTel SDK provides a vendor-neutral way to generate metrics, traces, and logs from your code, so
your application emits telemetry in a standard format regardless of the backend you send it to. This
is what allows you to swap or combine backends (VictoriaMetrics, Jaeger, etc.) without changing your
application code.

## What is Automatic instrumentation?

[Automatic instrumentation](https://opentelemetry.io/docs/concepts/instrumentation/automatic/) (also
called zero-code instrumentation) lets you add telemetry to an application without modifying its
source code. OTel provides auto-instrumentation support for many languages and it typically covers
popular frameworks and libraries out of the box (HTTP servers, database clients, messaging systems,
etc.). There are three main approaches:

* **eBPF-based**: Hooks into the Linux kernel using eBPF probes to observe system calls and network
  traffic at the OS level, with zero changes to the application process. Does not require access to
  the source code or the runtime, but is limited to what is visible at the kernel boundary.
* **Bytecode injection (agent-based)**: For languages with a managed runtime (JVM, .NET CLR), an
  agent is attached to the process at startup and patches bytecode on the fly to inject spans and
  metrics into supported libraries. Requires a compatible runtime but gives rich, framework-level
  coverage.
* **Library auto-instrumentation via environment variables**: For languages like Python, Node.js, or
  Go, the OTel SDK is loaded alongside the application (often triggered by environment variables
  like `OTEL_EXPORTER_OTLP_ENDPOINT`) and automatically wraps well-known libraries. The application
  does not need explicit instrumentation calls, but it does need to import the OTel packages.

![Zero-code](pics/zero-code.svg)
*Source: [OpenTelemetry documentation](https://opentelemetry.io/docs/concepts/instrumentation/zero-code/),
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).*

## True manual instrumentation (and why we need it for C++)

When none of the automatic approaches are available or sufficient, you need to use the
[OTel SDK for your language](https://opentelemetry.io/docs/languages/) directly: creating meters,
defining instruments (counters, histograms, gauges), and recording values explicitly in your code.

This is the case for our demo app, which is written in **C++**. C++ compiles to native machine code,
so there is no bytecode to inject and no managed runtime to hook into. eBPF can observe syscalls and
network events, but it cannot capture business-level metrics like request counts, latency
distributions, or custom application state. The [OpenTelemetry C++ SDK](https://opentelemetry.io/docs/languages/cpp/)
is therefore the only way to generate the application metrics we care about: we add instrumentation
calls directly in the source code to define and record the signals we want to observe.

# Deploy demo app

We will now enable a load generator [hermes](https://github.com/jgomezselles/hermes), which is
manually instrumented with OpenTelemetry. If you're curious about how, you can check the
[`olly`](https://github.com/jgomezselles/hermes/tree/main/src/o11y) folder  or how instruments
are created in the [`stats`](https://github.com/jgomezselles/hermes/blob/main/src/stats/stats.cpp) file.

In order to install it, we will apply now the following changes via the file [step-3.yaml](helm/values/step-3.yaml):

## Application

Important to note how we are routing telemetry to our OTel collector:

```yaml
hermes:
...
  script:
    cm: traffic-script-cm # traffic script with instructions
  o11y: # these are converted to env variables and captured by the app
    metrics_endpoint: http://otelcol:4318/v1/metrics
    traces_endpoint: http://otelcol:4318/v1/traces
```

## Server Mock

Written in go, it just logs and responds. Env variables are used:
```yaml
serverMock:
...
  env: # these are used by the go runtime
    - name: OTEL_EXPORTER_OTLP_PROTOCOL
      value: "http/protobuf"
    - name: OTEL_EXPORTER_OTLP_ENDPOINT
      value: "http://otelcol:4318"
```

## OTel collector

Our apps will be sending logs and traces too. Note that:

1. We don't need to create a new receiver. The same `otlpreceiver` is used for all signals.
2. These new pipelines will just log, via the `debugexporter` the new logs and traces.

```yaml
opentelemetry-collector:
  alternateConfig:
    service:
      pipelines: # We are adding 2 pipelines
        traces:
          receivers: [otlp]
          processors: []
          exporters: [debug]
        logs:
          receivers: [otlp]
          processors: []
          exporters: [debug]
```

Now we can go ahead and upgrade with these changes:

```sh
helm upgrade ws helm/cnd-demo -f helm/values/step-1.yaml -f helm/values/step-2.yaml -f helm/values/step-3.yaml -n cnd-ws
```

In order to check if changes were correctly applied, we can
run again the port-forward and see the **`PipelineZ`** utility to see the pipelines:
```sh
kubectl port-forward -n cnd-ws deployments/otelcol 55679:55679
```

> **EXERCISE**: Inspect the pipeline and OTel collector logs

# Running the app

Let's run traffic in the background in a new console by:
```sh
kubectl exec -n cnd-ws $(kubectl get pod -n cnd-ws -l app.kubernetes.io/name=hermes -o jsonpath='{.items[0].metadata.name}') -- hermes -r10 -p1 -t1000
```

This will send requests at a rate `r=10` rps for time `t=100`s (and print to console stderr every `p=1`s).

> **EXERCISE**: Let's use the `Autocomplete` functionality or navigate back to the `Cardinality explorer`
> to discover which new metrics we have, and how the kubelet is exposing more containers now.

# Continue this workshop
Part 3 is over! Go back to [Index](../README.md#part-i)
