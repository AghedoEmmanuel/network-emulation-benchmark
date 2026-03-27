# Network Emulation Benchmark: SEED IE vs Mininet (SDN)

## 1. Overview

This project presents a **comparative evaluation of network emulation platforms** using a controlled experimental framework. The study investigates how different network paradigms—traditional routing and Software-Defined Networking (SDN)—perform under identical topological conditions.

Two environments are implemented:

* **SEED Internet Emulator (SEED IE)** — traditional routing using OSPF
* **Mininet + POX controller** — SDN-based forwarding using OpenFlow

The goal is to analyse performance, scalability, and convergence behaviour across both approaches.

---

## 2. Research Aim

To evaluate and compare the performance of network emulation platforms under controlled experimental conditions.

---

## 3. Research Objectives

* Design a **consistent 6-node ring topology** across both environments
* Implement **traditional routing (OSPF)** in SEED IE
* Implement **SDN forwarding logic** using a POX controller in Mininet
* Develop an **automated benchmarking framework**
* Measure and compare:

  * Latency
  * Jitter
  * Throughput
  * Bandwidth
  * Packet loss
  * Convergence time (failure & recovery)
  * CPU utilisation
  * Memory utilisation
* Analyse differences between routing paradigms

---

## 4. System Architecture

### 4.1 SEED IE (Traditional Routing)

* Docker-based emulation
* Single Autonomous System (AS100)
* OSPF routing protocol
* Router-based forwarding decisions

### 4.2 Mininet + POX (SDN)

* OpenFlow-based switches
* Centralised POX controller
* Proactive flow installation
* Ring-aware shortest path forwarding

---

## 5. Topology Design

A **6-node ring topology** is used across both environments:

R1 — R2 — R3 — R4 — R5 — R6
|                                 |
└─────────────── R6 ─────────────┘

Characteristics:

* Each node connected via point-to-point links
* Single failure point introduced for convergence testing
* Identical logical structure across platforms

---

## 6. Repository Structure

```
network-emulation-benchmark/
│
├── seed_ie/
│   ├── SEED_Ring.py
│   └── benchmark_ospf.py
│
├── mininet/
│   ├── mininet_pox_topology.py
│   ├── ring_controller.py
│   └── benchmark_mininet_iterative.py
│
├── results/
│   ├── seed_ie/
│   └── mininet/
│
├── docs/
│   └── diagrams/
│
└── README.md
```

---

## 7. Metrics and Definitions

All metrics are implemented using consistent operational definitions.

### Latency

Measured using ICMP ping round-trip time (RTT).

### Jitter

Calculated as:

* Mean absolute deviation of RTT samples from the average RTT
* Provides a stable variation measure compared to standard deviation

### Throughput

Receiver-side TCP rate using iperf3.

### Bandwidth

Sender-side TCP rate using iperf3.

### Packet Loss

Percentage of lost ICMP packets.

### Convergence Time

Time taken for the network to recover after:

* Link failure (failure convergence)
* Link restoration (recovery convergence)

Measured using continuous probing.

### CPU Utilisation

Measured via Docker (SEED IE) and system monitoring (Mininet), averaged across samples.

### Memory Utilisation

Measured per node and aggregated across the network.

---

## 8. Methodology

### Phase 1: Steady-State Benchmarking

* 1000 iterations
* Measures performance under normal operation

### Phase 2: Convergence Testing

* ~30 iterations
* Simulates link failure and recovery
* Measures routing adaptation time

### Data Collection

* Results stored in CSV and JSON format
* Each iteration logged independently
* Supports statistical analysis

---

## 9. Implementation Details

### SEED IE

* Networks configured using Python API
* OSPF automatically computes routing paths
* Docker containers simulate routers

### Mininet

* Custom topology script creates ring network
* POX controller installs forwarding rules
* Shortest path determined using ring logic

---

## 10. Key Design Decisions

### Subnet Configuration
Both SEED IE and Mininet environments utilise /24 subnet addressing for consistency.

In SEED IE, each point-to-point link is assigned a separate /24 subnet to emulate router-based network segmentation.

In Mininet, IP addressing operates within a logically flat SDN environment, where forwarding decisions are handled by the controller rather than traditional routing protocols. As a result, subnet boundaries do not influence forwarding behaviour in the same way as in SEED IE.

### Separate Convergence Testing

* Prevents distortion of steady-state metrics
* Improves experimental validity

### Iterative Benchmarking

* Large sample size improves statistical reliability
* Aligns with experimental research standards

---

## 11. How to Run

### SEED IE

```bash
python3 seed_ie/SEED_Ring.py
python3 seed_ie/benchmark_ospf.py
```

---

### Mininet + POX

Start controller:

```bash
cd ~/pox
python3 pox.py log.level --DEBUG openflow.of_01 ring_controller
```

Start topology:

```bash
sudo python3 mininet/mininet_pox_topology.py
```

Run benchmark:

```bash
python3 mininet/benchmark_mininet_iterative.py
```

---

## 12. Expected Outputs

* CSV files containing iteration results
* JSON files for convergence analysis
* Logs for debugging and validation

---

## 13. Limitations

* Mininet uses SDN (not router-based), so comparison is architectural
* Docker networking may introduce overhead
* Some iterations may experience timeouts due to emulation constraints

---

## 14. Contribution

This project provides:

* A **reproducible benchmarking framework**
* A **direct comparison of SDN vs traditional routing**
* Automated performance evaluation tools
* A structured dataset for further analysis

---

## 15. Future Work

* Extend to additional emulators (e.g., EVE-NG)
* Introduce traffic variability
* Add security performance evaluation
* Apply machine learning for anomaly detection

---

## 16. Author

MSc Computing Project – Teesside University
EMMANUEL ODIANOSE AGHEDO