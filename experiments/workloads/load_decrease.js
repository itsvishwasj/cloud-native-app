import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://192.168.49.2:31234';
const STRESS_DURATION_MS = __ENV.STRESS_DURATION_MS || '500';

export const options = {
  scenarios: {
    load_decrease: {
      executor: 'ramping-arrival-rate',
      startRate: 15,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 150,
      stages: [
        { target: 15, duration: '2m' }, // High initial load: 15 RPS (2 mins)
        { target: 8, duration: '30s' }, // Decrease step 1 to 8 RPS
        { target: 8, duration: '2m' },  // Hold 8 RPS
        { target: 2, duration: '30s' }, // Decrease step 2 to 2 RPS
        { target: 2, duration: '3m' },  // Low load for scale-down observation (300s HPA window)
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
