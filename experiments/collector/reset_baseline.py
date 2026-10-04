#!/usr/bin/env python3
"""
Baseline Reset and Pre-Experiment Readiness Verifier.
Ensures application starts at minReplicas (2), all 2 replicas are ready/available,
HPA target is at 2, and CPU utilization is at low idle baseline (<15%).
"""

import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request


def ensure_port_forward():
    try:
        urllib.request.urlopen("http://localhost:9090/-/healthy", timeout=1)
        return None
    except Exception:
        proc = subprocess.Popen(
            ["kubectl", "port-forward", "svc/monitoring-kube-prometheus-prometheus", "-n", "monitoring", "9090:9090"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        return proc


def query_prom(query):
    url = "http://localhost:9090/api/v1/query?" + urllib.parse.urlencode({"query": query})
    try:
        with urllib.request.urlopen(url, timeout=5) as res:
            d = json.loads(res.read().decode("utf-8"))
            if d.get("status") == "success":
                result = d.get("data", {}).get("result", [])
                if result:
                    return float(result[0]["value"][1])
    except Exception:
        pass
    return 0.0


def reset_to_baseline():
    print("[*] Initiating pre-experiment baseline reset...")

    # Refresh HPA resource to reset scale-down stabilization timer to minReplicas=2
    subprocess.run(["kubectl", "delete", "hpa", "web-app-hpa", "--ignore-not-found=true"], check=True)
    subprocess.run(["kubectl", "scale", "deployment", "web-app", "--replicas=2"], check=True)
    subprocess.run(["kubectl", "apply", "-f", "k8s/hpa.yaml"], check=True)
    print("[*] Reset HPA status and scaled Deployment/web-app to 2 replicas.")

    pf = ensure_port_forward()

    max_wait_seconds = 180
    start_wait = time.time()

    try:
        while time.time() - start_wait < max_wait_seconds:
            curr_rep = int(query_prom('kube_deployment_status_replicas{deployment="web-app"} or vector(0)'))
            avail_rep = int(query_prom('kube_deployment_status_replicas_available{deployment="web-app"} or vector(0)'))
            hpa_des = int(query_prom('kube_horizontalpodautoscaler_status_desired_replicas{horizontalpodautoscaler="web-app-hpa"} or vector(0)'))
            cpu_pct = query_prom('(sum(rate(process_cpu_seconds_total{app="web-app"}[2m])) / sum(kube_pod_container_resource_requests{resource="cpu", container="web-app"})) * 100 or vector(0)')

            print(f"[Wait] Current: {curr_rep} | Avail: {avail_rep} | HPA Desired: {hpa_des} | CPU%: {cpu_pct:.1f}%")

            if curr_rep == 2 and avail_rep == 2 and hpa_des == 2 and cpu_pct < 15.0:
                print("\n[✓] BASELINE READY: 2 replicas ready, HPA desired=2, CPU low idle baseline.")
                return True

            time.sleep(5)

        print("\n[!] Timeout waiting for baseline state.", file=sys.stderr)
        return False
    finally:
        if pf:
            pf.terminate()


if __name__ == "__main__":
    success = reset_to_baseline()
    sys.exit(0 if success else 1)
