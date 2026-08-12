import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://192.168.49.2:31234';
const STRESS_DURATION_MS = __ENV.STRESS_DURATION_MS || '500';

export const options = {
  scenarios: {
    step_increase: {
      executor: 'ramping-arrival-rate',
      startRate: 2,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 120,
      stages: [
        { target: 2, duration: '1m' },   // Step 1: Baseline 2 RPS (1 min)
        { target: 6, duration: '30s' },  // Ramp to Step 2
        { target: 6, duration: '1m' },   // Step 2: 6 RPS (1 min)
        { target: 12, duration: '30s' }, // Ramp to Step 3
        { target: 12, duration: '1m' },  // Step 3: 12 RPS (1 min)
        { target: 16, duration: '30s' }, // Ramp to Step 4
        { target: 16, duration: '1m' },  // Step 4: 16 RPS (1 min)
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
  },
};

export default function () {
  const url = `${BASE_URL}/stress?duration=${STRESS_DURATION_MS}`;
  const res = http.get(url, { tags: { name: 'CPUStress' } });
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
}
