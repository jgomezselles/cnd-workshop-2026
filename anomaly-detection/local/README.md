# Local anomaly detection stack

The local stack is self-contained. It starts VictoriaMetrics, vmagent,
vmanomaly, Grafana, vmalert, Alertmanager, and an optional one-shot dataloader.
Alertmanager sends demo notifications to a local webhook inbox that shows
alerts on a tiny local web page and in Docker logs, so no Slack, email, or
external credentials are needed.

```mermaid
flowchart LR
  loader["dataloader<br/>one-shot seed"] -->|"seed synthetic metrics"| agent["vmagent<br/>buffer + relabel"]
  anomaly["vmanomaly"] -->|"write model outputs"| agent
  agent -->|"buffer + relabel writes"| vm["VictoriaMetrics<br/>single-node"]
  vm -->|"read raw series"| anomaly
  vm -->|"query dashboards"| grafana["Grafana"]
  vm -->|"run alert rules"| vmalert["vmalert"]
  vmalert -->|"notify alerts"| alertmanager["Alertmanager"]
  alertmanager -->|"send webhook"| webhook["webhook inbox<br/>page + logs"]
```

## Start

Put the vmanomaly license at:

```bash
anomaly-detection/.secret/license
```

These commands assume a POSIX shell. Use Terminal on Linux/macOS or WSL 2 on
Windows.

Start from this directory:

```bash
cd anomaly-detection/local
./up.sh
```

By default, local startup resets Docker volumes and runs the dataloader once.
That gives a reproducible dataset for each demo run.

Reuse an already seeded dataset:

```bash
./up.sh --skip-dataloader --keep-volumes
```

Run the dataloader but keep existing volumes:

```bash
./up.sh --with-dataloader --keep-volumes
```

Reset volumes explicitly:

```bash
./up.sh --reset-volumes
```

## Follow

Open:

- Grafana: http://localhost:3000
- VictoriaMetrics: http://localhost:8428
- vmanomaly UI: http://localhost:8490
- vmalert: http://localhost:8880
- Alertmanager: http://localhost:9093
- Alert webhook inbox: http://localhost:5001

Useful logs:

```bash
docker compose logs -f dataloader
docker compose logs -f vmanomaly
docker compose logs -f vmagent
docker compose logs -f alert-webhook
```

## Inspect In Grafana

After vmanomaly starts, use Grafana to inspect both model outputs and service
health:

- The anomaly score dashboard shows `anomaly_score`, `y`, `yhat`, and
  confidence bands for each configured query/model. In this workshop these
  output metric names use the `otel_apm_` prefix. Full guide:
  https://docs.victoriametrics.com/anomaly-detection/presets/#grafana-dashboard
- The self-monitoring dashboard shows vmanomaly runtime health, scheduler/model
  run timing, errors, and data flow metrics. Full guide:
  https://docs.victoriametrics.com/anomaly-detection/self-monitoring/

## Stop

Stop and remove generated data:

```bash
./down.sh
```

Stop but keep Docker volumes:

```bash
./down.sh --keep-volumes
```

## Notes

- The dataloader writes 21 days of history and 2 days into the future.
- vmanomaly backtesting replays the recent window from `shared/env-common.sh`
  and defaults to the last 3 days.
- vmagent relabeling maps `backfill_online` to `online` and
  `backfill_offline` to `offline`, so dashboard series imitate continuous
  periodic scheduling.
