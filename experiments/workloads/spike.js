import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://192.168.49.2:31234';
const STRESS_DURATION_MS = __ENV.STRESS_DURATION_MS || '500';

export const options = {
  scenarios: {
    spike_load: {
      executor: 'ramping-arrival-rate',
      startRate: 2,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 150,
      stages: [
        { target: 2, duration: '1m' },   // Low baseline: 2 RPS for 1 min
        { target: 18, duration: '15s' }, // Sharp spike to 18 RPS
        { target: 18, duration: '45s' }, // Sustained short spike
        { target: 2, duration: '15s' },  // Rapid drop back to 2 RPS
        { target: 2, duration: '2m' },   // Post-spike observation period
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.10'],
  },
};

export default function () {
  const url = `${BASE_URL}/stress?duration=${STRESS_DURATION_MS}`;
  const res = http.get(url, { tags: { name: 'CPUStress' } });
  check(res, {
    'status is 200': (r) => r.status === 200,
  });
}
