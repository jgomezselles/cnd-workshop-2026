# Building dashboards in Grafana

Querying every time we want to know something is nice, and very important because every
investigation usually requires different data. But sometimes we need to:
- Get an overview on how a system is behaving
- Check different metrics at once

For this case, we need a dashboard. In the next step, we will install [`Grafana`](https://github.com/grafana/grafana).
Another option would be using [`Perses`](https://perses.dev/), a novel CNCF project that is gaining
traction.

To install Grafana, we will use the [step-5.yaml](../helm/values/step-5.yaml) file.

```yaml
grafana:
  enabled: true
  plugins:
    - victoriametrics-metrics-datasource
    - victoriametrics-logs-datasource
```

Here, we are installing the VictoriaMetrics and VictoriaLogs
[plugins](https://grafana.com/orgs/victoriametrics/plugins) directly, so we don't need to add them
manually.

> Note: Also mind that the following is applied (from the main [values.yaml](../helm/cnd-demo/values.yaml)
file) to ensure we can load the dashboard.

```yaml
  dashboardProviders:
   dashboardproviders.yaml:
     apiVersion: 1
     providers:
     - name: 'default'
       orgId: 1
       folder: ''
       type: file
       disableDeletion: false
       editable: true
       options:
         path: /var/lib/grafana/dashboards/default

  dashboardsConfigMaps:
    default: "hermes-dashboard"
```

We are ready to install Grafana, along with the dashboard:

```sh
helm upgrade ws helm/cnd-demo -f helm/values/step-1.yaml -f helm/values/step-2.yaml -f helm/values/step-3.yaml -f helm/values/step-4.yaml  -f helm/values/step-5.yaml -n cnd-ws
```

To access Grafana, we need to expose the 3000 port:

```sh
kubectl port-forward -n cnd-ws deployments/ws-grafana 3000:3000
```

> NOTE: we can log in with `admin`:`admin`

## Adding datasources

The next step is to add `Data Sources`. This is just telling Grafana where our backends are,
and which language they use.

### VictoriaMetrics Data Source
Since VictoriaMetrics can be used as a drop-in replacement for
Prometheus, we will add it as a **Prometheus datasource**. For that, we will follow the steps in
https://console.victoriametrics.cloud/integrations/grafana and **select our metrics deployment and
our dedicated Access Token**.

### VictoriaLogs Data Source
For that, we will follow the steps in
https://console.victoriametrics.cloud/integrations/grafana . For VictoriaLogs, we will just **select
our logs deployment and pick our token**.

Since we use headers for tenant identification, set the tenant in the dedicated field:
`Multitenancy` with your `AccountID` and `ProjectID`

## Observing our application in a dashboard

To load the dashboard we added as `ConfigMap`:
1. Navigate to `Dashboards` -> `Hermes dashboard CND`
2. Select your `Logs_datasource` and `Metrics_datasource` in the variable selector at the top

> IMPORTANT: Refresh the page if variables don't load!

## Inspecting our Metric panels

Hover your mouse over any panel. If you press `e` or click on the three dots, you can inspect and
edit a panel.

For reference, the queries are pasted here:

Response time graph
```sh
hermes_response_time_ok_ms_sum{id=~"$request_id"}[1m] / hermes_response_time_ok_ms_count{id=~"$request_id"}[1m]
```

Avg Response time value
```sh
avg(hermes_response_time_ok_ms_sum{id=~"$request_id"}[1m] / hermes_response_time_ok_ms_count{id=~"$request_id"}[1m])
```

Gauge
```sh
sum(hermes_responses_rcv_ok{id=~"$request_id"}) / sum(hermes_requests_sent{id=~"$request_id"}) *100
```

![Metrics Dashboard](pics/metrics_dash.png)


> EXERCISE: Try to reproduce one panel by clicking on `Edit` at the top and later, `Add visualization`.

## Inspecting our Logs panels

HITs panel (Printing graphs from logs):
```sh
GET | stats by (_stream) count() hits | sort by (hits) desc limit 5
```

Logs inspection:
```sh
_stream: {k8s.container.name="server-mock"} AND "GET" | _time:10s
```

![Logs Dashboard](pics/logs_dash.png)

> EXERCISE: Click on a log, and inspect all fields added by OpenTelemetry.


## CONGRATULATIONS! NOW YOU'RE AN OBSERVABILITY EXPERT!

Part I is over! Go back to [Index](../README.md)
