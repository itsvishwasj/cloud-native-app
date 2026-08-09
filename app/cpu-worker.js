const { parentPort, workerData } = require('worker_threads');

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

    if (isPrime) {
      count++;
    }

    num++;
  }

  return {
    primesFound: count,
    numbersEvaluated: num - 1
  };
}

try {
  const durationMs = workerData.durationMs;

  const result = runCpuStress(durationMs);

  parentPort.postMessage({
    success: true,
    result
  });
} catch (error) {
  parentPort.postMessage({
    success: false,
    error: error.message
  });
}
