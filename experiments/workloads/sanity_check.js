import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://192.168.49.2:31234';
const STRESS_DURATION_MS = __ENV.STRESS_DURATION_MS || '300';
const TARGET_RPS = parseInt(__ENV.TARGET_RPS || '4', 10);
const DURATION = __ENV.DURATION || '40s';

export const options = {
  scenarios: {
    sanity_check: {
      executor: 'constant-arrival-rate',
      rate: TARGET_RPS,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: 10,
      maxVUs: 30,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.10'],
  },
};

export default function () {
  const url = `${BASE_URL}/stress?duration=${STRESS_DURATION_MS}`;
  const res = http.get(url, { tags: { name: 'SanityStress' } });
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
}
