#!/usr/bin/env python3
"""
Host Watch — publish host health to MQTT so CPU starvation is diagnosed in seconds.

The 2026-08-17 Omnispindle 524 storm was 89.6% CPU steal on a t3.micro whose burst
credits had run dry. Every in-guest signal looked healthy — PM2 procs online at 0%
cpu, the process idle, load average alone ambiguous — so the investigation
reasonably concluded the application was at fault and hunted a response-path bug
for 17 hours. The single number that settles it is the `st` column, and nothing was
watching it.

Runs as its own PM2 process, deliberately NOT inside Omnispindle: Omnispindle being
starved is the condition this measures, so the monitor must not share its fate.
Stdlib only, for the same reason — a monitor with dependencies is a monitor that can
break for reasons that have nothing to do with what it monitors.

Publishes two topics:

  status/<device>/host            retained, every interval. Current state, so a
                                  reader gets the answer without touching the box.
                                  This is the point: when the host IS throttled,
                                  `ssh` + `top` on it took 8-14s, while reading a
                                  retained topic from anywhere else costs nothing
                                  and cannot be slowed down by the thing it is
                                  reporting on.

  status/<device>/alert/cpu_steal edge-triggered, on committed state transitions
                                  only. Not published every interval — an alert
                                  that fires constantly is not an alert.

STALENESS IS THE READER'S JOB. A retained topic outlives its publisher, so a dead
watcher leaves a permanently cheerful "ok" behind for anyone who trusts it. Every
payload carries `ts`; anything consuming this MUST reject samples older than a few
intervals rather than believe them. (Omnispindle's own status/<host>/alive gets this
wrong in the other direction: it retains "0" on exit but publishes "1" unretained on
start, so the retained value reads offline while the service is running fine.)

Usage:
    python3 scripts/host_watch.py [--interval 60] [--device eaws] [--mqtt-port 4140]

On eaws, run under pm2:
    pm2 start scripts/host_watch.py --name host-watch --interpreter python3 \
        -- --device eaws --mqtt-port 4140
    pm2 save
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

# --- thresholds -------------------------------------------------------------
# t3.micro baseline is 10% per vCPU across 2 vCPUs, so a fully credit-starved box
# reads ~80% steal (the observed incident hit 89.6%). WARN catches partial
# throttling well before that; CRIT is far enough above normal jitter that
# reaching it means the hypervisor really is taking the CPU away.
WARN_PCT = 10.0
CRIT_PCT = 25.0

# Debounce. Steal is spiky, and a single bad sample is not an incident.
ENTER_SAMPLES = 3   # consecutive critical samples before committing to "throttled"
EXIT_SAMPLES = 3    # consecutive ok samples before committing back to "ok"

# Prime the first delta over a short window so the first publish is immediate and
# real, rather than making a reader wait a full interval for any data at all.
PRIME_SECS = 2

# Log an "everything is fine" line this often, so an idle log still proves liveness.
OK_HEARTBEAT_EVERY = 30


def log(msg):
    """PM2 captures stdout; flush so the log is live rather than block-buffered."""
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}] {msg}", flush=True)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- sampling ---------------------------------------------------------------

def read_cpu():
    """
    Aggregate jiffies from /proc/stat's `cpu` line.

    Fields: user nice system idle iowait irq softirq steal guest guest_nice.
    Only the first 8 are summed — `guest` is already counted inside `user` and
    `guest_nice` inside `nice`, so including them double-counts the total and
    quietly deflates every percentage derived from it.
    """
    with open("/proc/stat") as f:
        for line in f:
            if line.startswith("cpu "):
                vals = [int(v) for v in line.split()[1:9]]
                return {
                    "user": vals[0], "nice": vals[1], "system": vals[2],
                    "idle": vals[3], "iowait": vals[4], "irq": vals[5],
                    "softirq": vals[6], "steal": vals[7],
                    "total": sum(vals),
                }
    raise RuntimeError("no 'cpu ' line in /proc/stat")


def cpu_delta(prev, cur):
    """
    Percentages over the window between two /proc/stat reads.

    Steal MUST be a delta. A single instantaneous read is a since-boot average and
    would have shown a calm number straight through the incident.
    """
    total = cur["total"] - prev["total"]
    if total <= 0:
        return None
    pct = lambda k: round(100.0 * (cur[k] - prev[k]) / total, 1)
    return {
        "steal_pct": pct("steal"),
        "iowait_pct": pct("iowait"),
        "idle_pct": pct("idle"),
        "nproc": os.cpu_count(),
    }


PM2_PIDS_DIR = os.path.expanduser("~/.pm2/pids")
CLK_TCK = os.sysconf("SC_CLK_TCK")
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")


def read_procs():
    """
    Raw per-process counters for everything PM2 is running.

    Sourced from ~/.pm2/pids/<name>-<id>.pid rather than `pm2 jlist`, which spawns a
    node process per call. On a box already too starved to schedule anything, the
    measurement must not need the resource being measured.

    Two traps, both paid for:

    /proc/<pid>/stat cannot be whitespace-split. Field 2 is the comm in parentheses
    and it contains spaces for anything started as `node /opt/madness-backend/
    server.js`, which shifts every later field and yields confident garbage — a
    naive split reported state="/opt/madne)" and starttime=0. Split after the LAST
    ')' instead.

    Stale pid files accumulate in that directory (several from March, pointing at
    long-dead pids). A pid whose /proc entry is gone is skipped. `cmd` is carried so
    that a pid recycled by an unrelated process is visible rather than silently
    mislabelled with whatever PM2 name happened to be on the file.
    """
    out = {}
    try:
        names = os.listdir(PM2_PIDS_DIR)
    except Exception:
        return out

    for fname in names:
        if not fname.endswith(".pid"):
            continue
        base = fname[:-4]
        name, _, pm_id = base.rpartition("-")
        try:
            with open(os.path.join(PM2_PIDS_DIR, fname)) as f:
                pid = int(f.read().strip())
            raw = open(f"/proc/{pid}/stat").read()
            fields = raw[raw.rindex(")") + 2:].split()
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode(errors="replace").strip()
        except Exception:
            continue  # dead process, stale pid file, or a race against a restart
        try:
            out[pid] = {
                "name": name or base,
                "pm_id": pm_id,
                "pid": pid,
                "state": fields[0],                                    # field 3
                "cpu_j": int(fields[11]) + int(fields[12]),            # utime+stime
                "threads": int(fields[17]),                            # field 20
                "start_j": int(fields[19]),                            # field 22
                "rss_mb": int(fields[21]) * PAGE_SIZE // (1024 * 1024),  # field 24
                "cmd": cmd[:60],
            }
        except (IndexError, ValueError):
            continue
    return out


def proc_deltas(prev, cur, window_s, uptime_s):
    """
    Two per-process snapshots into reportable rows, sorted busiest first.

    Reports BOTH cpu numbers, explicitly named, because confusing them is what cost
    seventeen hours. `cpu_pct` is this window. `cpu_pct_life` is the average since
    the process started. PM2's list column looks like one and reads like the other,
    and a screenshot of it is indistinguishable either way — the 143.8% that seeded
    the original investigation was never resolved into which it was.

    CAVEAT, load-bearing whenever this is worth reading: per-process CPU is inflated
    by steal. The kernel charges a process for ticks during which its vCPU was
    preempted by the hypervisor, so under heavy throttling these percentages sum
    past what the box demonstrably had to give — measured live at 87.5% steal, the
    rows summed to 82% of total capacity while the system line showed 9.8% user+sys.
    Read them as a ranking of who is busiest, and read cpu.steal_pct first.
    """
    prev_by_name = {p["name"]: p["pid"] for p in prev.values()}
    rows = []
    for pid, c in cur.items():
        life = max(uptime_s - c["start_j"] / CLK_TCK, 1.0)
        row = {
            "name": c["name"],
            "pid": pid,
            "state": c["state"],
            "rss_mb": c["rss_mb"],
            "threads": c["threads"],
            "uptime_s": int(life),
            "cpu_pct_life": round(100.0 * c["cpu_j"] / CLK_TCK / life, 1),
        }
        p = prev.get(pid)
        if p and window_s > 0:
            row["cpu_pct"] = round(100.0 * (c["cpu_j"] - p["cpu_j"]) / CLK_TCK / window_s, 1)
        else:
            # First sighting. Report null rather than 0 — a process with no previous
            # counter to diff against is unmeasured, not idle, and 0 would read as
            # an alibi.
            row["cpu_pct"] = None
            row["new"] = True
            # A name whose pid moved since the last tick restarted between samples.
            # PM2's restart counter resets with the daemon; this does not.
            if c["name"] in prev_by_name and prev_by_name[c["name"]] != pid:
                row["restarted"] = True
                row["cmd"] = c["cmd"]
        rows.append(row)

    rows.sort(key=lambda r: (r["cpu_pct"] is None, -(r["cpu_pct"] or 0)))
    return rows


def top_line(procs, n=3):
    """Busiest processes, for the human log line. Names the suspect at a glance."""
    parts = []
    for r in procs[:n]:
        cpu = "?" if r["cpu_pct"] is None else f"{r['cpu_pct']:.0f}%"
        parts.append(f"{r['name']}={cpu}/{r['rss_mb']}mb")
    return " ".join(parts) if parts else "(no procs)"


def read_mem():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                if key in ("MemTotal", "MemAvailable"):
                    info[key] = int(rest.split()[0]) // 1024  # kB -> MB
    except Exception:
        return {}
    return {"avail_mb": info.get("MemAvailable"), "total_mb": info.get("MemTotal")}


def read_disk(path="/"):
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        avail = st.f_bavail * st.f_frsize
        if total <= 0:
            return {}
        # Match `df`: used% is against total minus root-reserved, not raw free.
        used = total - (st.f_bfree * st.f_frsize)
        return {
            "root_used_pct": round(100.0 * used / (used + avail), 1),
            "root_avail_gb": round(avail / (1024 ** 3), 2),
        }
    except Exception:
        return {}


def read_uptime():
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return None


def read_ec2():
    """
    IMDSv2 instance metadata, fetched once. Best-effort: a non-EC2 host, a blocked
    link-local route, or IMDSv1-only just yields no ec2 block rather than an error.
    Instance type matters to a reader — 'is this even a burstable instance' decides
    whether burst-credit exhaustion is a candidate explanation at all.
    """
    try:
        req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "300"},
        )
        token = urllib.request.urlopen(req, timeout=2).read().decode()

        def get(path):
            r = urllib.request.Request(
                f"http://169.254.169.254/latest/meta-data/{path}",
                headers={"X-aws-ec2-metadata-token": token},
            )
            return urllib.request.urlopen(r, timeout=2).read().decode().strip()

        return {
            "itype": get("instance-type"),
            "instance_id": get("instance-id"),
            "region": get("placement/region"),
        }
    except Exception as e:
        log(f"EC2 metadata unavailable ({e.__class__.__name__}) — continuing without it")
        return {}


# --- publishing -------------------------------------------------------------

class Publisher:
    """
    Shells out to mosquitto_pub, matching the house style in src/Omnispindle/mqtt.py
    and keeping this script dependency-free.

    Never raises. A broker that is down or slow must not stop the sampling loop —
    the local log stays useful even when nothing can be published, and that log is
    the fallback record of what the host was doing.
    """

    def __init__(self, host, port):
        self.host = host
        self.port = str(port)
        self.available = shutil.which("mosquitto_pub") is not None
        if not self.available:
            log("mosquitto_pub not found — sampling to log only, nothing will publish")
        self._warned = False

    def publish(self, topic, payload, retain=False):
        body = json.dumps(payload, separators=(",", ":"))
        if not self.available:
            return False
        cmd = ["mosquitto_pub", "-h", self.host, "-p", self.port, "-t", topic, "-m", body]
        if retain:
            cmd.append("-r")
        try:
            # Timeout is load-bearing: a hung broker connection would otherwise
            # block the loop forever, and a monitor that stops sampling during
            # trouble is worse than no monitor.
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
            self._warned = False
            return True
        except Exception as e:
            if not self._warned:  # don't spam a log for a broker that stays down
                log(f"MQTT publish to {topic} failed: {e.__class__.__name__}: {e}")
                self._warned = True
            return False


# --- state machine ----------------------------------------------------------

class StealState:
    """
    Separates what one sample says from what we are confident about.

    `level` is this sample alone (ok / elevated / critical). `state` is the
    debounced, committed view (ok / throttled) and is the only thing that drives
    the edge alert. Publishing both means a reader sees the instantaneous truth
    without the alert channel flapping on a single spike.

    Each transition reports the number that transition is actually evidence for,
    rather than one field that means neither: entering says how long confirmation
    took, recovering says how long the outage lasted and how bad it got. "Time in
    the current state" is deliberately not reported at a transition — it is always
    zero there, which reads like data and is not.
    """

    def __init__(self, interval):
        self.state = "ok"
        self.run = 0            # consecutive samples pushing toward a change
        self.since = time.time()
        self.peak = 0.0         # worst steal seen in the current event
        self.interval = interval

    @staticmethod
    def level_for(steal_pct):
        if steal_pct >= CRIT_PCT:
            return "critical"
        if steal_pct >= WARN_PCT:
            return "elevated"
        return "ok"

    def update(self, steal_pct):
        """Returns a dict describing the transition if one just happened, else None."""
        level = self.level_for(steal_pct)
        if self.state == "ok":
            if level == "critical":
                # Peak tracking starts with the run, not with the commit, so the
                # samples that built the case are part of the event they caused.
                self.peak = steal_pct if self.run == 0 else max(self.peak, steal_pct)
                self.run += 1
                if self.run >= ENTER_SAMPLES:
                    self.state, self.run, self.since = "throttled", 0, time.time()
                    return {"state": "throttled",
                            "confirmed_after_s": ENTER_SAMPLES * self.interval}
            else:
                self.run = 0
                self.peak = 0.0
        else:
            self.peak = max(self.peak, steal_pct)
            self.run = self.run + 1 if level == "ok" else 0
            if self.run >= EXIT_SAMPLES:
                out = {"state": "ok",
                       "throttled_for_s": int(time.time() - self.since),
                       "peak_steal_pct": self.peak}
                self.state, self.run, self.since, self.peak = "ok", 0, time.time(), 0.0
                return out
        return None


# --- main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Publish host health to MQTT")
    parser.add_argument("--device", default=os.getenv("DeNa", "eaws"),
                        help="device name used in the topic path")
    parser.add_argument("--interval", type=int, default=int(os.getenv("HOST_WATCH_INTERVAL", "60")),
                        help="seconds between samples; also the averaging window")
    parser.add_argument("--mqtt-host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--mqtt-port", default=os.getenv("MQTT_PORT", "1883"))
    parser.add_argument("--no-sample-log", action="store_true",
                        help="stop writing the SAMPLE JSONL history line each tick")
    args = parser.parse_args()

    state_topic = f"status/{args.device}/host"
    alert_topic = f"status/{args.device}/alert/cpu_steal"

    pub = Publisher(args.mqtt_host, args.mqtt_port)
    ec2 = read_ec2()
    steal = StealState(args.interval)

    log(f"=== Host Watch === device={args.device} interval={args.interval}s "
        f"broker={args.mqtt_host}:{args.mqtt_port}")
    log(f"topics: {state_topic} (retained) | {alert_topic} (edge)")
    log(f"thresholds: warn>={WARN_PCT}% crit>={CRIT_PCT}% "
        f"enter={ENTER_SAMPLES} exit={EXIT_SAMPLES} samples")
    if ec2:
        log(f"ec2: {ec2.get('itype')} {ec2.get('instance_id')} {ec2.get('region')}")

    def on_term(sig, frame):
        # Overwrite the retained payload on the way out. Leaving a stale "ok"
        # behind would be actively misleading — the next reader cannot tell a
        # healthy host from a dead watcher. Say the watcher stopped instead.
        pub.publish(state_topic, {
            "device": args.device, "ts": now_iso(),
            "watcher": "stopped", "state": "unknown",
        }, retain=True)
        log(f"received signal {sig}, published watcher=stopped, exiting")
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    prev = read_cpu()
    prev_procs = read_procs()
    window = PRIME_SECS
    time.sleep(PRIME_SECS)
    tick = 0

    while True:
        try:
            cur = read_cpu()
            cpu = cpu_delta(prev, cur)
            prev = cur

            if cpu is None:  # clock/counter went backwards; skip rather than lie
                time.sleep(args.interval)
                window = args.interval
                continue

            uptime_f = float(open("/proc/uptime").read().split()[0])
            cur_procs = read_procs()
            procs = proc_deltas(prev_procs, cur_procs, window, uptime_f)
            prev_procs = cur_procs

            changed = steal.update(cpu["steal_pct"])
            level = StealState.level_for(cpu["steal_pct"])
            load1, load5, load15 = os.getloadavg()

            payload = {
                "device": args.device,
                "ts": now_iso(),
                "watcher": "up",
                "state": steal.state,
                "level": level,
                "window_s": window,
                "cpu": cpu,
                "load": {"1m": round(load1, 2), "5m": round(load5, 2), "15m": round(load15, 2)},
                "mem": read_mem(),
                "disk": read_disk(),
                "uptime_s": read_uptime(),
                "procs": procs,
            }
            if ec2:
                payload["ec2"] = ec2

            pub.publish(state_topic, payload, retain=True)

            # Rolling history. The retained topic answers "right now" and says
            # nothing about last Tuesday, which is when you will be asked. One JSON
            # line per tick into a log pm2-logrotate already rotates costs nothing
            # to maintain and makes the whole sample greppable after the fact:
            #   grep '^\[.*\] SAMPLE ' host-watch-out.log | sed 's/.*SAMPLE //' | jq
            if not args.no_sample_log:
                log("SAMPLE " + json.dumps(payload, separators=(",", ":")))

            if changed:
                alert = {
                    "device": args.device,
                    "ts": now_iso(),
                    "steal_pct": cpu["steal_pct"],
                    **changed,
                }
                if ec2.get("itype"):
                    alert["itype"] = ec2["itype"]
                if changed["state"] == "throttled":
                    alert["hint"] = ("host is taking the CPU away; on a burstable "
                                     "instance this is burst-credit exhaustion, not app code")
                # Ship the suspects with the alert. Naming who was busiest at the
                # moment it fired is most of the triage, and by the time anyone
                # reads it the moment is gone.
                alert["top"] = [
                    {k: v for k, v in r.items() if k in ("name", "cpu_pct", "cpu_pct_life", "rss_mb")}
                    for r in procs[:3]
                ]
                pub.publish(alert_topic, alert)
                log(f"STATE -> {changed['state']} (steal {cpu['steal_pct']}%) {changed} "
                    f"| top: {top_line(procs)}")

            if level != "ok":
                log(f"steal={cpu['steal_pct']}% iowait={cpu['iowait_pct']}% "
                    f"load1={load1:.2f} level={level} state={steal.state} "
                    f"| top: {top_line(procs)}")
            elif tick % OK_HEARTBEAT_EVERY == 0:
                log(f"ok — steal={cpu['steal_pct']}% idle={cpu['idle_pct']}% "
                    f"load1={load1:.2f} | top: {top_line(procs)}")

            for r in procs:
                if r.get("restarted"):
                    log(f"RESTART {r['name']} -> pid {r['pid']} ({r.get('cmd', '')})")

            tick += 1

        except Exception as e:
            # Sampling must survive anything. A watcher that dies on a transient
            # read error is exactly the watcher you needed during the incident.
            log(f"sample failed: {e.__class__.__name__}: {e}")

        time.sleep(args.interval)
        window = args.interval


if __name__ == "__main__":
    main()
