import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://192.168.49.2:31234';
const STRESS_DURATION_MS = __ENV.STRESS_DURATION_MS || '500';
const TARGET_RPS = parseInt(__ENV.TARGET_RPS || '5', 10);
const DURATION = __ENV.DURATION || '2m';

export const options = {
  scenarios: {
    constant_load: {
      executor: 'constant-arrival-rate',
      rate: TARGET_RPS,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 20,
      maxVUs: 100,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'], // HTTP errors should be under 5%
  },
};

export default function () {
  const url = `${BASE_URL}/stress?duration=${STRESS_DURATION_MS}`;
  const res = http.get(url, { tags: { name: 'CPUStress' } });
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
}
