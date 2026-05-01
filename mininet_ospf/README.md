# Mininet FRR/OSPF Benchmark Topology

This folder contains the Mininet implementation used for the benchmarking artefact. It builds a six-router emulated network using Mininet and FRRouting (FRR), with OSPF used as the dynamic routing protocol.

The purpose of this implementation is to provide the Mininet side of the controlled comparison against the SEED Internet Emulator. Both environments use a comparable six-router topology and automated benchmarking scripts so that latency, jitter, throughput, bandwidth, packet loss, convergence time, CPU usage and memory usage can be measured under repeatable conditions.

## Role in the Project

This folder supports the dissertation artefact:

**A reproducible Python-based benchmarking framework for comparing network emulation platforms using a controlled six-router OSPF topology.**

The Mininet/FRR implementation is used to evaluate how a kernel-based network emulator behaves when running dynamic routing and network performance tests. The same benchmark logic is then compared with the SEED Internet Emulator implementation.

This folder is the OSPF/FRR version of the Mininet experiment. It does not rely on a POX/OpenFlow controller for routing decisions. Routing is handled by FRRouting using OSPF.

## Topology Overview

The Mininet topology contains six emulated routers:

- R1
- R2
- R3
- R4
- R5
- R6

Each router is configured with FRRouting and participates in the same OSPF routing domain. The topology is designed to represent a controlled six-router ring-style emulation environment where both one-hop and multi-hop paths can be tested.

The topology allows benchmarking across route pairs such as:

- R1 to R2
- R1 to R3
- R1 to R6
- R2 to R5
- R3 to R2
- R3 to R6
- R4 to R5
- R4 to R6
- R6 to R1

These paths allow comparison of adjacent and multi-hop communication behaviour inside the emulated network.

## Folder Structure

```text
mininet_ospf/
│
├── mn_topo.py
│   └── Builds the Mininet topology and creates the six-router emulated network.
│
├── config_frr.sh
│   └── Starts and configures FRRouting services for the routers.
│
├── benchmark_mininet_tbcm.py
│   └── Benchmark script for throughput, bandwidth, CPU and memory testing.
│
├── newbenchmark_mininet.py
│   └── Benchmark script for latency, jitter, packet loss and/or convergence-related testing.
│
├── r1/
│   └── FRR configuration files for Router 1.
│
├── r2/
│   └── FRR configuration files for Router 2.
│
├── r3/
│   └── FRR configuration files for Router 3.
│
├── r4/
│   └── FRR configuration files for Router 4.
│
├── r5/
│   └── FRR configuration files for Router 5.
│
└── r6/
    └── FRR configuration files for Router 6.