const express = require('express');
const morgan = require('morgan');
const path = require('path');
const { Worker } = require('worker_threads');
const client = require('prom-client');

const app = express();
const PORT = process.env.PORT || 3000;

// Enable default Node.js and process metrics
client.collectDefaultMetrics();

// Define custom application metrics
const httpRequestCounter = new client.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests processed',
  labelNames: ['method', 'route', 'status_code']
});

const httpRequestDurationHistogram = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 15, 30]
});

const httpRequestsInProgress = new client.Gauge({
  name: 'http_requests_in_progress',
  help: 'Number of HTTP requests currently in progress',
  labelNames: ['method', 'route']
});

// Helper function to normalize routes and prevent high-cardinality labels (e.g. 404s or query parameters)
function getNormalizedRoute(req) {
  if (req.route && req.route.path) {
    return req.route.path;
  }
  if (req.path === '/' || req.path === '/health' || req.path === '/stress') {
    return req.path;
  }
  return 'unmatched';
}

// Middleware for Prometheus metrics collection
app.use((req, res, next) => {
  if (req.path === '/metrics') {
    return next();
  }

  const startBigInt = process.hrtime.bigint();
  const initialRoute = getNormalizedRoute(req);

  httpRequestsInProgress.inc({ method: req.method, route: initialRoute });

  res.on('finish', () => {
    httpRequestsInProgress.dec({ method: req.method, route: initialRoute });

    const endBigInt = process.hrtime.bigint();
    const durationSeconds = Number(endBigInt - startBigInt) / 1e9;

    const matchedRoute = getNormalizedRoute(req);
    const statusCode = res.statusCode ? res.statusCode.toString() : 'unknown';

    httpRequestCounter.inc({
      method: req.method,
      route: matchedRoute,
      status_code: statusCode
    });

    httpRequestDurationHistogram.observe(
      {
        method: req.method,
        route: matchedRoute,
        status_code: statusCode
      },
      durationSeconds
    );
  });

  next();
});

// HTTP request logging middleware
app.use(morgan('combined'));

// Prometheus metrics endpoint
app.get('/metrics', async (req, res) => {
  try {
    res.set('Content-Type', client.register.contentType);
    res.end(await client.register.metrics());
  } catch (error) {
    res.status(500).end(error.message);
  }
});


// Root route
app.get('/', (req, res) => {
  res.json({
    status: 'success',
    message: 'Welcome to our Cloud-Native Scalable App! Node is alive.'
  });
});

// Health check route for Kubernetes Liveness/Readiness probes
app.get('/health', (req, res) => {
  res.json({
    status: 'UP',
    timestamp: new Date().toISOString()
  });
});

// Run CPU-intensive work inside a Worker Thread.
// This keeps the main Express event loop responsive.
function runCpuStress(durationMs) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(
      path.join(__dirname, 'cpu-worker.js'),
      {
        workerData: {
          durationMs
        }
      }
    );

    worker.once('message', (message) => {
      if (message.success) {
        resolve(message.result);
      } else {
        reject(new Error(message.error || 'Worker computation failed'));
      }
    });

    worker.once('error', (error) => {
      reject(error);
    });

    worker.once('exit', (code) => {
      if (code !== 0) {
        reject(
          new Error(`CPU worker stopped with exit code ${code}`)
        );
      }
    });
  });
}

// CPU stress route for triggering HPA auto-scaling behavior
app.get('/stress', async (req, res) => {
  const requestedDuration = parseInt(req.query.duration, 10);

  // Preserve the existing default of 7 seconds.
  // Reject invalid or unsafe values rather than allowing arbitrary values.
  const durationMs = Number.isFinite(requestedDuration)
    ? Math.min(Math.max(requestedDuration, 100), 30000)
    : 7000;

  try {
    const computationResult = await runCpuStress(durationMs);

    res.json({
      status: 'completed',
      message: `CPU stress computation completed after ${durationMs}ms`,
      details: computationResult,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('CPU stress worker error:', error);

    res.status(500).json({
      status: 'error',
      message: 'CPU stress computation failed',
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
