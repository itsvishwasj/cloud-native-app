import http from 'node:http';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

const execFileAsync = promisify(execFile);
const PORT = Number(process.env.API_PORT || 4174);
const PROMETHEUS_URL = process.env.PROMETHEUS_URL || 'http://localhost:9091';
const PROJECT_DIR = path.resolve(process.cwd(), '..');
const DECISION_LOG = path.join(
  PROJECT_DIR,
  'experiments/controller/decision_log.jsonl'
);

async function prometheusQuery(query) {
  const url = new URL('/api/v1/query', PROMETHEUS_URL);
  url.searchParams.set('query', query);

  const response = await fetch(url, { signal: AbortSignal.timeout(3000) });
  if (!response.ok) throw new Error(`Prometheus HTTP ${response.status}`);

  const body = await response.json();
  if (body.status !== 'success') throw new Error('Prometheus query failed');

  return body.data.result.map((series) => ({
    labels: series.metric,
    value: Number(series.value?.[1]),
    timestamp: Number(series.value?.[0]),
  }));
}

async function queryValue(metric) {
  const result = await prometheusQuery(metric);
  return result.length ? result[0].value : null;
}

async function queryHistory() {
  const end = Math.floor(Date.now() / 1000);
  const start = end - 15 * 60;
  const url = new URL('/api/v1/query_range', PROMETHEUS_URL);

  url.searchParams.set(
    'query',
    '{__name__=~"ema_tap_actual_rps|ema_tap_predicted_rps_30s|ema_tap_current_replicas|ema_tap_desired_replicas"}'
  );
  url.searchParams.set('start', String(start));
  url.searchParams.set('end', String(end));
  url.searchParams.set('step', '5s');

  const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`Prometheus HTTP ${response.status}`);

  const body = await response.json();
  if (body.status !== 'success') throw new Error('Prometheus range query failed');

  const byTime = new Map();

  for (const series of body.data.result) {
    const name = series.metric.__name__;
    const key = {
      ema_tap_actual_rps: 'actual',
      ema_tap_predicted_rps_30s: 'predicted',
      ema_tap_current_replicas: 'replicas',
      ema_tap_desired_replicas: 'desired',
    }[name];

    if (!key) continue;

    for (const [timestamp, value] of series.values || []) {
      const bucket = Math.floor(Number(timestamp) / 5) * 5;
      if (!byTime.has(bucket)) byTime.set(bucket, { timestamp: bucket });
      byTime.get(bucket)[key] = Number(value);
    }
  }

  return [...byTime.values()]
    .sort((a, b) => a.timestamp - b.timestamp)
    .map((point) => ({
      time: new Date(point.timestamp * 1000).toISOString(),
      actual: point.actual ?? null,
      predicted: point.predicted ?? null,
      replicas: point.replicas ?? null,
      desired: point.desired ?? null,
    }));
}

async function kubectlJson(args) {
  const { stdout } = await execFileAsync('kubectl', args, {
    timeout: 5000,
    maxBuffer: 5 * 1024 * 1024,
  });
  return JSON.parse(stdout);
}

async function readKubernetes() {
  const [deployment, pods, hpa] = await Promise.all([
    kubectlJson(['get', 'deployment', 'web-app', '-o', 'json']),
    kubectlJson(['get', 'pods', '-l', 'app=web-app', '-o', 'json']),
    kubectlJson(['get', 'hpa', 'web-app', '-o', 'json']),
  ]);

  const deploymentSpec = deployment.spec || {};
  const deploymentStatus = deployment.status || {};
  const hpaSpec = hpa.spec || {};
  const hpaStatus = hpa.status || {};
  const cpuMetric = (hpaStatus.currentMetrics || []).find(
    (metric) => metric.type === 'Resource' && metric.resource?.name === 'cpu'
  );
  const cpuTarget = (hpaSpec.metrics || []).find(
    (metric) => metric.type === 'Resource' && metric.resource?.name === 'cpu'
  );

  return {
    cluster: { name: 'minikube', namespace: 'default' },
    deployment: {
      name: deployment.metadata?.name || 'web-app',
      desiredReplicas: deploymentSpec.replicas ?? null,
      readyReplicas: deploymentStatus.readyReplicas ?? 0,
      availableReplicas: deploymentStatus.availableReplicas ?? 0,
    },
    pods: (pods.items || []).map((pod) => ({
      name: pod.metadata?.name || 'unknown',
      phase: pod.status?.phase || 'Unknown',
      ready: (pod.status?.conditions || []).some(
        (condition) => condition.type === 'Ready' && condition.status === 'True'
      ),
      restarts: (pod.status?.containerStatuses || []).reduce(
        (total, container) => total + (container.restartCount || 0), 0
      ),
    })),
    hpa: {
      currentReplicas: hpaStatus.currentReplicas ?? null,
      desiredReplicas: hpaStatus.desiredReplicas ?? null,
      cpuUtilization: cpuMetric?.resource?.current?.averageUtilization ?? null,
      targetCpu: cpuTarget?.resource?.target?.averageUtilization ?? null,
      minReplicas: hpaSpec.minReplicas ?? null,
      maxReplicas: hpaSpec.maxReplicas ?? null,
    },
  };
}

async function readDecisionLog() {
  const content = await readFile(DECISION_LOG, 'utf8');
  const lines = content.trim().split('\n').filter(Boolean);
  const rows = [];

  for (const line of lines.slice(-500).reverse()) {
    try {
      const row = JSON.parse(line);
      rows.push({
        id: `${row.timestamp}-${rows.length}`,
        time: row.timestamp || null,
        action: row.action || 'unknown',
        message: row.reason || 'No reason recorded',
        source: 'EMA-TAP',
        actualRps: row.actual_rps ?? null,
        predictedRps30: row.predicted_rps_30s ?? null,
        currentReplicas: row.current_replicas ?? null,
        desiredReplicas: row.desired_replicas ?? null,
      });
    } catch {
      // Ignore malformed log lines; never fabricate a record.
    }
  }

  return rows;
}

async function readEvents() {
  const events = await kubectlJson([
    'get', 'events', '-o', 'json', '--sort-by=.lastTimestamp',
  ]);

  return (events.items || []).slice(-30).reverse().map((event, index) => ({
    id: `${event.metadata?.uid || event.metadata?.name || 'event'}-${index}`,
    time: event.lastTimestamp || event.eventTime || event.metadata?.creationTimestamp || null,
    action: event.type || 'Info',
    message: `${event.reason || 'Event'}: ${event.message || ''}`.trim(),
    source: 'Kubernetes',
  }));
}

async function dashboardData() {
  const metricNames = [
    'ema_tap_actual_rps',
    'ema_tap_predicted_rps_30s',
    'ema_tap_current_replicas',
    'ema_tap_desired_replicas',
    'ema_tap_model_mae',
    'ema_tap_model_rmse',
    'ema_tap_model_r2',
    'ema_tap_evaluation_horizon_seconds',
  ];

  const [metricResults, historyResult, kubernetesResult, logResult, eventsResult] =
    await Promise.allSettled([
      Promise.all(metricNames.map(async (name) => [name, await queryValue(name)])),
      queryHistory(),
      readKubernetes(),
      readDecisionLog(),
      readEvents(),
    ]);

  const metrics = metricResults.status === 'fulfilled'
    ? Object.fromEntries(metricResults.value)
    : {};

  const history = historyResult.status === 'fulfilled' ? historyResult.value : [];
  const kubernetes = kubernetesResult.status === 'fulfilled'
    ? kubernetesResult.value
    : null;
  const decisions = logResult.status === 'fulfilled' ? logResult.value : [];
  const events = eventsResult.status === 'fulfilled' ? eventsResult.value : [];

  const latestDecision = decisions[0] || null;
  const controllerAvailable = metrics.ema_tap_actual_rps != null;

  return {
    updatedAt: new Date().toISOString(),
    sources: {
      prometheus: metricResults.status === 'fulfilled',
      history: historyResult.status === 'fulfilled',
      kubernetes: kubernetesResult.status === 'fulfilled',
      decisionLog: logResult.status === 'fulfilled',
      kubernetesEvents: eventsResult.status === 'fulfilled',
    },
    errors: {
      prometheus: metricResults.status === 'rejected' ? String(metricResults.reason) : null,
      history: historyResult.status === 'rejected' ? String(historyResult.reason) : null,
      kubernetes: kubernetesResult.status === 'rejected' ? String(kubernetesResult.reason) : null,
      decisionLog: logResult.status === 'rejected' ? String(logResult.reason) : null,
      kubernetesEvents: eventsResult.status === 'rejected' ? String(eventsResult.reason) : null,
    },
    metrics: {
      actualRps: metrics.ema_tap_actual_rps ?? null,
      predictedRps30: metrics.ema_tap_predicted_rps_30s ?? null,
      currentReplicas: metrics.ema_tap_current_replicas ?? null,
      desiredReplicas: metrics.ema_tap_desired_replicas ?? null,
    },
    evaluation: {
      mae: metrics.ema_tap_model_mae ?? null,
      rmse: metrics.ema_tap_model_rmse ?? null,
      r2: metrics.ema_tap_model_r2 ?? null,
      horizonSeconds: metrics.ema_tap_evaluation_horizon_seconds ?? null,
    },
    history,
    pods: kubernetes?.pods ?? [],
    hpa: kubernetes?.hpa ?? null,
    deployment: kubernetes?.deployment ?? null,
    cluster: kubernetes?.cluster ?? null,
    controller: {
      status: controllerAvailable ? 'metrics available' : 'unavailable',
      mode: 'read-only dashboard; controller mode is not inferred from metrics',
      lastAction: latestDecision?.action ?? null,
      reason: latestDecision?.message ?? null,
    },
    events: [
      ...decisions.slice(0, 20).map((row) => ({
        ...row,
        message: `${row.message}; actual=${row.actualRps ?? 'n/a'} RPS, forecast=${row.predictedRps30 ?? 'n/a'} RPS`,
      })),
      ...events,
    ].sort((a, b) => String(b.time || '').localeCompare(String(a.time || ''))).slice(0, 50),
    logs: decisions.slice(0, 100).map((row) => ({
      id: row.id,
      time: row.time,
      level: row.action === 'error' ? 'error' : 'info',
      message: `${row.action}: ${row.message}`,
    })),
  };
}

const server = http.createServer(async (request, response) => {
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('Cache-Control', 'no-store');

  if (request.method === 'GET' && request.url === '/api/health') {
    response.writeHead(200);
    response.end(JSON.stringify({ status: 'ok' }));
    return;
  }

  if (request.method !== 'GET' || request.url !== '/api/dashboard') {
    response.writeHead(404);
    response.end(JSON.stringify({ error: 'Not found' }));
    return;
  }

  try {
    const data = await dashboardData();
    response.writeHead(200);
    response.end(JSON.stringify(data));
  } catch (error) {
    response.writeHead(500);
    response.end(JSON.stringify({
      error: 'Unable to assemble dashboard data',
      detail: error.message,
    }));
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Read-only dashboard API listening at http://127.0.0.1:${PORT}`);
  console.log(`Prometheus endpoint: ${PROMETHEUS_URL}`);
  console.log('No Kubernetes scaling commands are exposed by this API.');
});
