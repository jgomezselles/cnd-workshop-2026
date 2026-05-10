#  Copyright (c) 2024 Victoria Metrics Inc.

import argparse
import logging
import os
import re
import sys
import time
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
FOREVER = {"forever", "inf", "+inf", "infinite", "until_end"}


def _parse_bound(x, default):
    if x is None:
        return default
    if isinstance(x, str) and x.lower() in {"inf", "+inf", "infty"}:
        return np.inf
    if isinstance(x, str) and x.lower() in {"-inf"}:
        return -np.inf
    return float(x)


def _resolve_value_range(value_range, data_range):
    if value_range is not None:
        return value_range
    return data_range


def _clip_target(target: np.ndarray, value_range: list | tuple | None) -> np.ndarray:
    if not value_range:
        return target
    lo, hi = map(_parse_bound, value_range, (-np.inf, np.inf))
    return np.clip(target, lo, hi)


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


def _value_for_series(value, index: int, *, default=None, required: bool = False):
    if value is None:
        if required:
            raise ValueError(f"Missing required per-series value for index {index}")
        return default
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        if index >= len(value):
            if required:
                raise ValueError(f"Only {len(value)} values configured for series index {index}")
            return default
        return value[index]
    return value


def labels_for_series(base_labels: dict | None, series_labels: list[dict] | None, index: int) -> dict:
    labels = {k: _value_for_series(v, index, required=True) for k, v in dict(base_labels or {}).items()}
    if series_labels:
        if index >= len(series_labels):
            raise ValueError(
                f"series_labels has {len(series_labels)} entries, but n_series requires index {index}"
            )
        labels.update({k: _value_for_series(v, index, required=True) for k, v in series_labels[index].items()})
    return labels


def _duration(value):
    if value is None:
        return None
    if isinstance(value, str) and value.lower() in FOREVER:
        return None
    return pd.Timedelta(value)


def _resolve_relative_time(value, now_dt: pd.Timestamp) -> pd.Timestamp:
    """Resolve workshop-friendly offsets relative to now.

    "1h" means now minus 1h. "-5m" means now plus 5m, so scenarios can be
    placed just into the generated future window.
    """

    if value is None or str(value).lower() == "now":
        return now_dt
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("-"):
            return now_dt + pd.Timedelta(value[1:])
        if value.startswith("+"):
            return now_dt + pd.Timedelta(value[1:])
    return now_dt - pd.Timedelta(value)


def _series_matches(anomaly: dict, index: int) -> bool:
    selected = anomaly.get("series", "all")
    if selected == "all":
        return True
    if isinstance(selected, int):
        return index == selected
    if isinstance(selected, list):
        return index in selected
    raise ValueError(f"Unsupported anomaly series selector: {selected!r}")


def _select_for_anomaly(value, anomaly: dict, index: int, *, default=None, required: bool = False):
    selected = anomaly.get("series", "all")
    if isinstance(value, list) and isinstance(selected, list) and len(value) == len(selected) and index in selected:
        return value[selected.index(index)]
    return _value_for_series(value, index, default=default, required=required)


def _window_mask(time_idx: pd.DatetimeIndex, now_dt: pd.Timestamp, anomaly: dict, index: int) -> np.ndarray:
    start_value = _select_for_anomaly(
        anomaly.get("starts", anomaly.get("start")),
        anomaly,
        index,
        required=True,
    )
    default_duration = "forever" if anomaly.get("type") in {"changepoint", "level_shift", "slow_trend", "trend"} else "point"
    duration_value = _select_for_anomaly(anomaly.get("duration", default_duration), anomaly, index, default=default_duration)
    start_dt = _resolve_relative_time(start_value, now_dt)
    if isinstance(duration_value, str) and duration_value.lower() == "point":
        sample_step = time_idx[1] - time_idx[0] if len(time_idx) > 1 else pd.Timedelta(anomaly.get("freq", "30s"))
        return np.asarray(np.abs(time_idx - start_dt) <= sample_step / 2)
    duration = _duration(duration_value)
    if duration is None:
        return np.asarray(time_idx >= start_dt)
    return np.asarray((time_idx >= start_dt) & (time_idx < start_dt + duration))


def _random_window_masks(
    time_idx: pd.DatetimeIndex,
    now_dt: pd.Timestamp,
    anomaly: dict,
    index: int,
    sampler: np.random.RandomState,
) -> list[np.ndarray]:
    window = anomaly.get("window", "history")
    if window in {"history", "past"}:
        eligible = np.asarray(time_idx < now_dt)
    elif window == "future":
        eligible = np.asarray(time_idx > now_dt)
    elif window == "all":
        eligible = np.ones(len(time_idx), dtype=bool)
    else:
        raise ValueError(f"Unsupported random anomaly window: {window!r}")

    duration_value = _select_for_anomaly(anomaly.get("duration", "2m"), anomaly, index, default="2m")
    duration = _duration(duration_value) or pd.Timedelta(0)
    sample_step = time_idx[1] - time_idx[0] if len(time_idx) > 1 else pd.Timedelta(anomaly.get("freq", "30s"))
    duration_samples = max(1, int(np.ceil(duration / sample_step)))

    occurrences = anomaly.get("occurrences")
    if occurrences is None:
        share = float(anomaly.get("sample_share", 0.001))
        occurrences = max(1, int((eligible.sum() * share) / duration_samples))
    occurrences = int(_select_for_anomaly(occurrences, anomaly, index, default=0))
    if occurrences <= 0:
        return []

    possible_starts = np.where(eligible)[0]
    possible_starts = possible_starts[possible_starts + duration_samples <= len(time_idx)]
    if len(possible_starts) == 0:
        return []

    starts = sampler.choice(possible_starts, size=min(occurrences, len(possible_starts)), replace=False)
    masks = []
    for start in starts:
        mask = np.zeros(len(time_idx), dtype=bool)
        mask[start : start + duration_samples] = True
        mask &= eligible
        masks.append(mask)
    return masks


def _anomaly_masks(
    time_idx: pd.DatetimeIndex,
    now_dt: pd.Timestamp,
    anomaly: dict,
    index: int,
    sampler: np.random.RandomState,
) -> list[np.ndarray]:
    placement = anomaly.get("placement")
    if placement == "random" or anomaly.get("start") == "random" or anomaly.get("starts") == "random":
        return _random_window_masks(time_idx, now_dt, anomaly, index, sampler)
    return [_window_mask(time_idx, now_dt, anomaly, index)]


def _apply_component(target: np.ndarray, component: dict, time_idx: pd.DatetimeIndex, index: int) -> np.ndarray:
    kind = component.get("type", "daily_sinusoid")
    mode = component.get("mode", "multiply")

    if kind == "daily_sinusoid":
        hours = time_idx.hour + time_idx.minute / 60 + time_idx.second / 3600
        period_hours = float(component.get("period_hours", 24))
        phase_hours = float(_value_for_series(component.get("phase_hours", 0), index, default=0))
        amplitude = float(_value_for_series(component.get("amplitude", 0.2), index, default=0.2))
        values = 1 + amplitude * np.sin(2 * np.pi * (hours - phase_hours) / period_hours)
    elif kind == "sinusoid_sum":
        hours = (
            time_idx.dayofweek * 24
            + time_idx.hour
            + time_idx.minute / 60
            + time_idx.second / 3600
        )
        values = np.ones(len(target), dtype=float)
        for wave in component.get("waves", []):
            period_hours = float(wave.get("period_hours", 24))
            phase_hours = float(_value_for_series(wave.get("phase_hours", 0), index, default=0))
            amplitude = float(_value_for_series(wave.get("amplitude", 0.1), index, default=0.1))
            values += amplitude * np.sin(2 * np.pi * (hours - phase_hours) / period_hours)
        values = np.maximum(float(component.get("min", 0.05)), values)
    elif kind == "business_hours":
        hours = time_idx.hour + time_idx.minute / 60
        start_hour = float(_value_for_series(component.get("start_hour", 8), index, default=8))
        end_hour = float(_value_for_series(component.get("end_hour", 18), index, default=18))
        high = float(_value_for_series(component.get("high", 1.0), index, default=1.0))
        low = float(_value_for_series(component.get("low", 0.65), index, default=0.65))
        values = np.where((hours >= start_hour) & (hours < end_hour), high, low)
    elif kind == "weekly_workload":
        weekday = float(_value_for_series(component.get("weekday", 1.0), index, default=1.0))
        weekend = float(_value_for_series(component.get("weekend", 0.7), index, default=0.7))
        values = np.where(time_idx.dayofweek < 5, weekday, weekend)
    elif kind == "linear_trend":
        start = float(_value_for_series(component.get("start", 1.0), index, default=1.0))
        end = float(_value_for_series(component.get("end", 1.0), index, default=1.0))
        values = np.linspace(start, end, len(target))
    else:
        raise ValueError(f"Unsupported seasonality/trend component type: {kind!r}")

    values = np.asarray(values, dtype=float)
    if mode == "add":
        return target + values
    if mode == "multiply":
        return target * values
    raise ValueError(f"Unsupported component mode: {mode!r}")


def _apply_noise(target: np.ndarray, noise: dict | None, sampler: np.random.RandomState, index: int) -> np.ndarray:
    if not noise:
        return target

    kind = noise.get("type", "normal")
    mode = noise.get("mode", "multiply")
    stddev = float(_value_for_series(noise.get("stddev", 0.03), index, default=0.03))

    if kind != "normal":
        raise ValueError(f"Unsupported noise type: {kind!r}")

    values = sampler.normal(0, stddev, len(target))
    if mode == "add":
        return target + values
    if mode == "multiply":
        return target * np.maximum(0, 1 + values)
    raise ValueError(f"Unsupported noise mode: {mode!r}")


def _apply_anomalies(
    target: np.ndarray,
    time_idx: pd.DatetimeIndex,
    now_dt: pd.Timestamp,
    anomalies: list[dict] | None,
    index: int,
    sampler: np.random.RandomState,
) -> np.ndarray:
    if not anomalies:
        return target

    target = target.copy()
    for anomaly in anomalies:
        if not _series_matches(anomaly, index):
            continue

        masks = _anomaly_masks(time_idx, now_dt, anomaly, index, sampler)
        masks = [mask for mask in masks if mask.any()]
        if not masks:
            logger.warning("Anomaly %s did not match any samples for series index %s", anomaly.get("name"), index)
            continue

        kind = anomaly.get("type", "contextual")
        direction = anomaly.get("direction", "spike")
        mode = anomaly.get("mode", "multiply")

        for mask in masks:
            if kind in {"changepoint", "level_shift"}:
                factor = float(_select_for_anomaly(anomaly.get("factor", anomaly.get("magnitude", 2.0)), anomaly, index))
                value = factor if direction != "drop" else 1 / factor
                target[mask] = target[mask] * value if mode == "multiply" else target[mask] + value
            elif kind in {"slow_trend", "trend"}:
                from_factor = float(_select_for_anomaly(anomaly.get("from_factor", 1.0), anomaly, index, default=1.0))
                to_factor = float(_select_for_anomaly(anomaly.get("to_factor", anomaly.get("factor", 2.0)), anomaly, index))
                if direction == "drop":
                    to_factor = 1 / to_factor
                ramp = np.linspace(from_factor, to_factor, mask.sum())
                target[mask] = target[mask] * ramp if mode == "multiply" else target[mask] + ramp
            elif kind in {"contextual", "spike", "drop"}:
                factor = float(_select_for_anomaly(anomaly.get("factor", anomaly.get("magnitude", 3.0)), anomaly, index))
                is_drop = direction == "drop" or kind == "drop"
                value = 1 / factor if is_drop else factor
                target[mask] = target[mask] * value if mode == "multiply" else target[mask] + (-factor if is_drop else factor)
            else:
                raise ValueError(f"Unsupported anomaly type: {kind!r}")

    return target


def _legacy_signal_config(kwargs: dict) -> tuple[dict, list[dict]]:
    signal = {
        "base": 1.0,
        "scale": kwargs.get("scale", 1.0),
        "seasonalities": [],
        "noise": {"type": "normal", "mode": "multiply", "stddev": 0.08},
    }
    if kwargs.get("seasonal"):
        if kwargs.get("seasonality_type") == "sinusoidal":
            signal["seasonalities"].append({"type": "daily_sinusoid", "amplitude": 0.35})
        else:
            signal["seasonalities"].extend(
                [
                    {"type": "weekly_workload", "weekday": 1.0, "weekend": 0.68},
                    {"type": "business_hours", "start_hour": 8, "end_hour": 17, "high": 1.0, "low": 0.65},
                ]
            )

    anomalies = []
    if kwargs.get("simple_anomaly"):
        anomalies.append(
            {
                "type": "contextual",
                "start": "30m",
                "duration": "10m",
                "factor": kwargs.get("simple_magnitude", 3.0),
            }
        )
    if kwargs.get("anomaly_changepoint"):
        anomalies.append(
            {
                "type": "changepoint",
                "start": "1h",
                "duration": "forever",
                "factor": kwargs.get("changepoint_magnitude", 2.0),
            }
        )
    return signal, anomalies


def _build_target(
    time_idx: pd.DatetimeIndex,
    now_dt: pd.Timestamp,
    signal: dict,
    anomalies: list[dict] | None,
    sampler: np.random.RandomState,
    index: int,
) -> np.ndarray:
    base = float(_value_for_series(signal.get("base", 1.0), index, default=1.0))
    scale = float(_value_for_series(signal.get("scale", 1.0), index, default=1.0))
    target = np.full(len(time_idx), base, dtype=float)

    for component in signal.get("seasonalities", []):
        target = _apply_component(target, component, time_idx, index)

    target = _apply_component(target, signal["trend"], time_idx, index) if "trend" in signal else target
    target *= scale
    target = _apply_noise(target, signal.get("noise"), sampler, index)
    return _apply_anomalies(target, time_idx, now_dt, anomalies, index, sampler)


def _fallback_instance(series_name: str, index: int) -> str:
    return f"{series_name}:{index + 1}"


def produce_anomaly_dataframe(
    series_name: str,
    n_series: int,
    freq: str = "1h",
    historical_length: str = "2w",
    future_length: str = "1d",
    cumulative: bool = True,
    colname_timestamp: str = "timestamp",
    value_range: list | tuple | None = None,
    data_range: list | tuple | None = None,
    random_state: int = 42,
    labels: dict | None = None,
    series_labels: list[dict] | None = None,
    signal: dict | None = None,
    anomalies: list[dict] | None = None,
    **legacy_kwargs,
) -> list[QueryResult]:

    sampler = np.random.RandomState(random_state)

    now_dt = pd.Timestamp.now().round(freq)
    start_dt = (now_dt - pd.Timedelta(historical_length)).round(freq)
    end_dt = (now_dt + pd.Timedelta(future_length)).round(freq)

    time_idx = pd.date_range(start=start_dt, end=end_dt, freq=freq)
    value_range = _resolve_value_range(value_range, data_range)
    if signal is None:
        signal, legacy_anomalies = _legacy_signal_config(legacy_kwargs)
        anomalies = anomalies or legacy_anomalies

    data: list[QueryResult] = []
    seen_labelsets = set()
    for i in range(n_series):
        df = pd.DataFrame({colname_timestamp: time_idx})
        target = _build_target(time_idx, now_dt, signal, anomalies, sampler, i)
        target = _clip_target(target, value_range)

        df[series_name] = target
        df = df[[colname_timestamp, series_name]]

        per_series_labels = labels_for_series(labels, series_labels, i)
        per_series_labels.setdefault("instance", _fallback_instance(series_name, i))
        metric = {
            "__name__": series_name,
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
