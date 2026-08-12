import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://192.168.49.2:31234';
const STRESS_DURATION_MS = __ENV.STRESS_DURATION_MS || '500';

export const options = {
  scenarios: {
    sustained_high_load: {
      executor: 'ramping-arrival-rate',
      startRate: 2,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 150,
      stages: [
        { target: 14, duration: '30s' }, // Rapid ramp-up to 14 RPS
        { target: 14, duration: '4m' },  // Sustained high load for 4 mins
        { target: 2, duration: '30s' },  // Ramp-down to 2 RPS
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
