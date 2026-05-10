#  Copyright (c) 2024 Victoria Metrics Inc.

import argparse
import logging
import os
import random
import re
import sys
import time
import uuid
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen

import numpy as np
import pandas as pd
import yaml

from query_result import QueryResult, QueryResultKey
from writer.vm import VmWriter

logger = logging.getLogger('dataloader')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

ENV_REF_RE = re.compile(r"%\{([^}]+)\}")


def seed_random(seed):
    random.seed(seed)


def _parse_bound(x, default):
    if x is None:
        return default
    if isinstance(x, str) and x.lower() in {"inf", "+inf", "infty"}:
        return np.inf
    if isinstance(x, str) and x.lower() in {"-inf"}:
        return -np.inf
    return float(x)


def wait_for_victoriametrics(datasource_url: str, timeout_seconds: int) -> None:
    """Wait until VictoriaMetrics accepts HTTP requests."""

    health_url = urljoin(datasource_url.rstrip("/") + "/", "health")
    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=2) as response:
                if 200 <= response.status < 300:
                    logger.info("VictoriaMetrics is ready: %s", health_url)
                    return
        except (OSError, URLError) as exc:
            last_error = exc

        logger.info("Waiting for VictoriaMetrics at %s ...", health_url)
        time.sleep(2)

    raise TimeoutError(
        f"VictoriaMetrics did not become ready within {timeout_seconds}s at {health_url}: {last_error}"
    )


def resolve_env_refs(value):
    if isinstance(value, dict):
        return {k: resolve_env_refs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_env_refs(v) for v in value]
    if not isinstance(value, str):
        return value

    def replace_env_ref(match: re.Match) -> str:
        env_name = match.group(1)
        if env_name not in os.environ:
            raise ValueError(f"Environment variable {env_name} is required by dataloader config")
        return os.environ[env_name]

    return ENV_REF_RE.sub(replace_env_ref, value)


def labels_for_series(base_labels: dict | None, series_labels: list[dict] | None, index: int) -> dict:
    labels = dict(base_labels or {})
    if series_labels:
        if index >= len(series_labels):
            raise ValueError(
                f"series_labels has {len(series_labels)} entries, but n_series requires index {index}"
            )
        labels.update(series_labels[index])
    return labels


def generate_reproducible_uuid(seed):
    # If a seed is provided, use it to seed the random number generator
    if seed is not None:
        seed_random(seed)

    # Generate 16 bytes of random data
    random_bytes = random.getrandbits(128).to_bytes(16, 'big')

    # Create a UUID using the random bytes
    deterministic_uuid = uuid.UUID(bytes=random_bytes)

    return deterministic_uuid


# ─────────────────────────────────────────────────────────────
# 1. extend the function signature
def produce_anomaly_dataframe(
    series_name: str,
    n_series: int,
    anomaly_percentage: float = 0.01,
    freq: str = "1h",
    historical_length: str = "2w",
    future_length: str = "1d",
    cumulative: bool = True,
    colname_timestamp: str = "timestamp",
    seasonal: bool = False,
    seasonality_type: str = "flat",
    data_range: list | tuple | None = None,
    simple_anomaly: bool = False,
    simple_magnitude: float = 3.0,
    seasonal_anomalies: bool = False,
    anomaly_changepoint: bool = False,
    changepoint_magnitude: float = 1.0,
    changepoint_position: float = 0.8,
    scale: float = 1.0,
    random_state: int = 42,
    labels: dict | None = None,
    series_labels: list[dict] | None = None,
) -> list[QueryResult]:

    sampler = np.random.RandomState(random_state)

    start_dt = (pd.Timestamp.now() - pd.Timedelta(historical_length)).round(freq)
    end_dt = (pd.Timestamp.now() + pd.Timedelta(future_length)).round(freq)

    time_idx = pd.date_range(start=start_dt, end=end_dt, freq=freq)
    periods = len(time_idx)

    data: list[QueryResult] = []
    node_id = generate_reproducible_uuid(seed=random_state)
    seen_labelsets = set()
    for i in range(n_series):
        df = pd.DataFrame({colname_timestamp: time_idx})
        if not seasonal:
            target = np.abs(sampler.randn(periods) * (1 + sampler.randn(periods) * 0.1))
            df[series_name] = target
            # artificially introduce anomalies
            anomaly_idx = sampler.choice(np.arange(periods), int(periods * anomaly_percentage))
            df.iloc[anomaly_idx, 1] = (
                df.iloc[anomaly_idx, 1] + (1 + sampler.rand(len(anomaly_idx))) * df[series_name].max()
            )

        elif seasonal and seasonal_anomalies and anomaly_percentage > 0:
            if seasonality_type == "sinusoidal":
                # Create dayofweek BEFORE using it
                df["dayofweek"] = df[colname_timestamp].dt.dayofweek
                hours = df[colname_timestamp].dt.hour
                daily_wave = 0.6 + 0.4 * np.sin(2*np.pi*hours/24)
                sub_daily = 0.2 * np.sin(2*np.pi*hours/8)
                weekday_adj = np.where(df["dayofweek"] < 5, 1.0, 0.7)
                target = (daily_wave + sub_daily) * weekday_adj
            else:
                df['hour'] = df[colname_timestamp].dt.hour
                df['dayofweek'] = df[colname_timestamp].dt.dayofweek

                # Weekly pattern: weekdays (1) vs weekends (weekend_multiplier)
                weekend_multiplier = sampler.uniform(0.6, 0.7) * sampler.uniform(0.98, 1.02, len(df))
                weekday_multiplier = sampler.uniform(0.98, 1.02, len(df))
                df['weekly_pattern'] = np.where(df['dayofweek'] < 5, weekday_multiplier, weekend_multiplier)

                shift = sampler.randint(-1, 1)
                non_wh_multiplier = sampler.uniform(0.6, 0.7)
                # Hourly pattern: working hours (8-17) have higher values compared to other hours
                df['hourly_pattern'] = df['hour'].apply(lambda x: 1 if 8 + shift <= x < 17 + shift else non_wh_multiplier)
                series_variation = sampler.uniform(0.95, 1.05)
                target = (df['weekly_pattern'] * df['hourly_pattern']) * series_variation

            target *= np.abs(1 + sampler.normal(0, 1, len(df)) * 0.1)  # add noise
            n_anomalies = int(len(df) * anomaly_percentage)
            q_low, q_hi = np.quantile(target, [0.05, 0.95])
            spread = np.abs(target.max() - target.min())
            low_zone = np.where(target < q_low)[0]
            low_idx = sampler.choice(low_zone, size=max(1, n_anomalies//2), replace=False)
            target[low_idx] = spread * sampler.uniform(0.8, 1, len(low_idx))

            high_zone = np.where(target > q_hi)[0]
            high_idx = sampler.choice(high_zone, size=max(1, n_anomalies//2), replace=False)
            target[high_idx] = spread * (1 - sampler.uniform(0.8, 0.9, len(high_idx)))

        if simple_anomaly:
            spike_idx = sampler.choice(periods, int(periods * anomaly_percentage), replace=False)
            simple_magnitude = simple_magnitude * sampler.uniform(0.8, 1.2, len(spike_idx))
            direction = 1  # spikes
            spike_val = direction * simple_magnitude * np.abs(target.max())
            target[spike_idx] = spike_val

        if seasonal and seasonal_anomalies:
            off_idx = sampler.choice(periods, int(periods*anomaly_percentage), replace=False)
            q_low, q_hi = np.quantile(target, [0.05, 0.95])
            target[off_idx] = sampler.choice([q_low*0.9, q_hi*1.1], size=len(off_idx))

        if anomaly_changepoint:
            cp_start = int(changepoint_position * periods)
            target[cp_start:] += np.quantile(target[cp_start:], 0.95) * (changepoint_magnitude -1) * sampler.uniform(0.9, 1.1, periods - cp_start)

        target *= (scale * np.abs(1 + sampler.randn()/5))  # scale the target series

        # clip to data_range (after anomalies, before cumulative)
        if data_range:
            lo, hi = map(_parse_bound, data_range, (-np.inf, np.inf))
            target = np.clip(target, lo, hi)

        df[series_name] = target
        df = df[[colname_timestamp, series_name]]

        per_series_labels = labels_for_series(labels, series_labels, i)
        per_series_labels.setdefault("synthetic_series_id", f"{series_name}:{i + 1}")
        if "service_instance_id" in per_series_labels:
            per_series_labels.setdefault("instance", per_series_labels["service_instance_id"])
        metric = {
            "__name__": series_name,
            "instance": str(node_id),  # user labels can override this with service identity
            **per_series_labels,
        }
        labelset = tuple(sorted(metric.items()))
        if labelset in seen_labelsets:
            raise ValueError(f"Duplicate synthetic timeseries labelset generated: {metric}")
        seen_labelsets.add(labelset)

        if cumulative:
            df[series_name] = df[series_name].cumsum().fillna(0)

        qr = QueryResult(df=df, key=QueryResultKey(metric=metric, key=series_name))
        data.append(qr)

    return data


def main():
    # logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser(description='Mock-up data loader to VictoriaMetrics TSDB')
    parser.add_argument(
        'config',
        help=(
            'YAML config file to define what series with such characteristics '
            ' should be created and loaded into the database.'
        ),
    )
    parser.add_argument('wait', type=int, help='Maximum seconds to wait for VictoriaMetrics readiness')
    args = parser.parse_args()
    config_path = args.config
    with open(config_path, 'r') as f:
        config = resolve_env_refs(yaml.safe_load(f))
        logger.info("Loaded dataloader config with %s metric families", len(config.get("series", [])))

    datasource_url = os.getenv("DATALOADER_DATASOURCE_URL") or config.get('datasource_url', 'http://victoriametrics:8428/')
    tenant_id = os.getenv("DATALOADER_TENANT_ID") or config.get('tenant_id')
    bearer_token = os.getenv("DATALOADER_BEARER_TOKEN") or config.get('bearer_token')
    writer = VmWriter(
        datasource_url=datasource_url,
        tenant_id=tenant_id,
        bearer_token=bearer_token,
        metric_format={'__name__': '$VAR'},
    )

    if args.wait > 0:
        logger.info(f'Waiting up to {args.wait} seconds for VictoriaMetrics to set up...')
        wait_for_victoriametrics(datasource_url=datasource_url, timeout_seconds=args.wait)
    else:
        logger.info('Skipping VictoriaMetrics readiness wait')
    logger.info(f'Uploading data to VictoriaMetrics: {datasource_url}')

    series = config.get('series', [])
    for series_config in series:
        series_name = series_config['series_name']
        results = produce_anomaly_dataframe(**series_config)

        for qr in results:
            writer.write(df=qr.df, query_result=qr)
            logger.info(
                f"{qr.df.columns.tolist()}, "
                f"{qr.df.shape}, "
                f"{str(qr.df['timestamp'].min())}, "
                f"{str(qr.df['timestamp'].max())}"
            )
        logger.info(
            f'Successfully written {len(results)} timeseries for simulated `{series_name}` metric to {datasource_url}'
        )

    logger.info(f'Finished uploading data to VictoriaMetrics: {datasource_url}')


if __name__ == '__main__':
    main()
