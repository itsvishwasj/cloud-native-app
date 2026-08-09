const express = require('express');
const morgan = require('morgan');
const path = require('path');
const { Worker } = require('worker_threads');

const app = express();
const PORT = process.env.PORT || 3000;

// HTTP request logging middleware
app.use(morgan('combined'));

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
