const express = require('express');
const morgan = require('morgan');

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

// Helper function to generate heavy CPU load for a specified duration (ms)
function runCpuStress(durationMs) {
  const startTime = Date.now();
  let count = 0;
  let num = 2;

  while (Date.now() - startTime < durationMs) {
    let isPrime = true;
    for (let i = 2; i <= Math.sqrt(num); i++) {
      if (num % i === 0) {
        isPrime = false;
        break;
      }
    }
    if (isPrime) count++;
    num++;
  }

  return { primesFound: count, numbersEvaluated: num - 1 };
}

// CPU stress route for triggering HPA auto-scaling behavior
app.get('/stress', (req, res) => {
  const durationMs = parseInt(req.query.duration, 10) || 7000; // Default 7 seconds
  const computationResult = runCpuStress(durationMs);

  res.json({
    status: 'completed',
    message: `CPU stress computation completed after ${durationMs}ms`,
    details: computationResult,
    timestamp: new Date().toISOString()
  });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
