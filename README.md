# Network Emulation Benchmark: Mininet FRR/OSPF vs SEED Internet Emulator

## 1. Overview

This repository contains the implementation, benchmarking scripts, result files, and supporting documentation for a Masters dissertation project comparing two network emulation environments:

- **Mininet using FRRouting (FRR) and OSPF**
- **SEED Internet Emulator using BIRD OSPF-based routing**

The project evaluates how both platforms perform under controlled experimental conditions using the same logical six-node ring topology. The aim is to compare emulator behaviour in terms of network performance, convergence behaviour, resource overhead, and inter-emulator communication.

The artefact includes:

- topology implementation scripts
- OSPF routing configuration
- automated benchmarking scripts
- raw CSV/JSON result files
- comparison and analysis scripts
- inter-emulator latency testing
- supporting diagrams and documentation

This repository supports the dissertation by providing a reproducible technical framework for collecting and analysing performance data from both emulation platforms.

---

## 2. Research Aim

The aim of this project is to evaluate and compare the performance of Mininet and SEED Internet Emulator under controlled network emulation conditions using equivalent OSPF-based routing designs.

The comparison focuses on the effect of emulator architecture on measured performance and resource usage.

---

## 3. Research Objectives

The main objectives of the project are to:

- design a consistent six-node ring topology for both environments
- implement OSPF-based routing in Mininet using FRRouting
- implement OSPF-based routing in SEED Internet Emulator using BIRD
- develop automated Python benchmarking scripts
- collect repeated performance measurements
- export raw results to CSV and JSON
- compare latency, throughput, bandwidth, packet loss, convergence, CPU usage, and memory usage
- test inter-emulator communication between Mininet and SEED IE
- provide a reproducible benchmarking artefact for academic evaluation

---

## 4. Repository Structure

```text
network-emulation-benchmark/
│
├── docs/
│   └── diagrams/
│   └── figures/
│   └── tables/
│
├── hybrid_system_comparison/
│   └── inter-emulator testing files
│
├── mininet_ospf/
│   └── Mininet topology, FRR/OSPF configuration, and benchmark scripts
│
├── mininet_ospf_hybrid/
│   └── Mininet files used for hybrid/inter-emulator testing
│
├── result/
│   └── raw and processed benchmark result files
│
├── seed_ie/
│   └── SEED IE topology, SEED IE hybrid topology, OSPF setup, and benchmark scripts
│
├── comparison.py
├── convergence_comparison.py
├── final_comparison_script.py
├── inter_latency.py
├── latency_table.py
├── mininet.py
├── seed.py
└── README.md
````

---

## 5. Platform Descriptions

### 5.1 Mininet with FRR/OSPF

Mininet is used to create a lightweight emulated network using Linux-based virtual networking. In this project, Mininet is configured to behave as a routed network rather than only an SDN switching environment.

The Mininet implementation uses:

* Linux network namespaces
* virtual Ethernet links
* router-style nodes
* FRRouting (FRR)
* OSPF dynamic routing
* Python-based topology creation
* automated benchmark scripts

FRR provides the OSPF routing functionality inside the Mininet environment. Each router advertises its connected networks, forms OSPF relationships where appropriate, and dynamically learns routes through the topology.

This allows the Mininet environment to be compared more fairly against SEED IE because both platforms use OSPF-based routing.

### 5.2 SEED Internet Emulator with OSPF

SEED Internet Emulator is a Docker-based network emulation platform. It allows routers, networks, and larger Internet-style environments to be created programmatically.

The SEED IE implementation uses:

* Docker containers
* Python-based topology creation
* router-based network design
* OSPF dynamic routing
* automated benchmark scripts
* CSV/JSON result output

In this project, SEED IE is configured using the same logical six-node ring topology as Mininet. OSPF is used so that routers can exchange routing information and forward packets dynamically.

---

## 6. Topology Design

The benchmark uses a six-node ring topology.

```text
        R1 ---- R2
       /        |
      /         |
     R6        R3
      \         |
       \        |
        R5 ---- R4
```

The topology is designed to support both short-path and longer-path testing. This makes it possible to observe whether performance changes across different route distances.

Example test pairs include:

| Nodes | Hop Count |
| ----- | --------: |
| R1-R2 |         1 |
| R1-R3 |         2 |
| R3-R2 |         1 |
| R3-R6 |         2 |
| R1-R6 |         1 |
| R2-R5 |         2 |
| R4-R5 |         1 |
| R4-R6 |         2 |
| R6-R1 |         1 |

The same logical topology is used across both platforms to improve fairness and repeatability.

---

## 7. Metrics Collected

The benchmark scripts collect the following metrics.

| Metric                 | Description                                                        | Unit |
| ---------------------- | ------------------------------------------------------------------ | ---- |
| Latency                | Round-trip delay between source and destination                    | ms   |
| Jitter                 | Variation in latency between repeated packets                      | ms   |
| Throughput             | Actual data transfer rate achieved during testing                  | Mbps |
| Bandwidth              | Measured transfer capacity of the path                             | Mbps |
| Packet Loss            | Percentage of packets lost during testing                          | %    |
| Convergence Time       | Time taken for the network to recover after failure or restoration | ms   |
| CPU Utilisation        | Processing overhead placed on the host system                      | %    |
| Memory Utilisation     | Memory overhead during the benchmark                               | %    |
| Inter-Emulator Latency | Latency between Mininet and SEED IE environments                   | ms   |

---

## 8. Benchmarking Methodology

The benchmarking process is automated using Python scripts to improve repeatability and reduce manual testing errors.

The general process is:

1. Build the six-node topology.
2. Configure interfaces and IP addressing.
3. Start OSPF routing.
4. Confirm reachability between routers.
5. Run repeated benchmark tests.
6. Store raw per-iteration results.
7. Export results to CSV and/or JSON.
8. Generate descriptive statistics.
9. Compare Mininet and SEED IE results.
10. Analyse the performance and resource overhead differences.

The project uses repeated measurements so that results can be analysed using summary statistics such as:

* minimum
* maximum
* mean
* median
* standard deviation

Where required, the raw result files can also be used for further statistical testing.

---

## 9. Main Benchmark Categories

### 9.1 Latency Testing

Latency is measured using ICMP ping round-trip time.

The benchmark records individual RTT values for each tested route and stores them for later analysis.

### 9.2 Jitter Testing

Jitter is calculated from variation in latency values across repeated samples.

Lower jitter indicates more stable packet delay behaviour.

### 9.3 Throughput and Bandwidth Testing

Throughput and bandwidth testing is performed using traffic generation tools such as `iperf3`.

The results are used to compare the actual data transfer behaviour of both emulators.

### 9.4 Packet Loss Testing

Packet loss is measured during connectivity and performance testing.

This helps identify whether packets are being dropped during communication.

### 9.5 Convergence Testing

Convergence testing measures how quickly the network reacts to changes such as link failure and recovery.

The project records:

* failure convergence time
* recovery convergence time

This is used to compare how each emulated environment responds to routing changes.

### 9.6 CPU and Memory Overhead

CPU and memory measurements are collected to compare the resource cost of running each emulator.

This is important because an emulator may perform well in terms of network metrics but still place a heavy load on the host system.

### 9.7 Inter-Emulator Latency Testing

The project also includes inter-emulator testing between Mininet and SEED IE.

This checks whether the two emulated environments can communicate successfully when connected together.

The inter-emulator tests measure latency between Mininet routers and SEED IE routers/gateway nodes.

---

## 10. Result Files

The `result/` folder contains raw and processed output files from the benchmark experiments.

Typical result files include:

```text
mininet_raw_latency_time_results.csv
seed_ie_raw_latency_time_results.csv
mininet_throughput_bandwidth_cpu_memory_raw.csv
seed_ie_throughput_bandwidth_cpu_memory_raw.csv
ospf_benchmark_results_iterative_ms.csv
ospf_benchmark_results_iterative_ms_convergence.csv
inter_emulator_latency_summary.csv
```

These files support:

* descriptive statistics
* comparison tables
* dissertation figures
* statistical analysis
* reproducibility checks

---

## 11. How to Run

> Note: Some scripts require root privileges because network namespaces, virtual interfaces, routing services, and Mininet topology creation require administrative access.

### 11.1 Clone the Repository

```bash
git clone https://github.com/AghedoEmmanuel/network-emulation-benchmark.git
cd 
network-emulation-benchmark
```

### 11.2 Install Common Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip iputils-ping iperf3 docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
```

### 11.3 Run the Mininet OSPF Environment

Clone Mininet:

```bash
git clone https://github.com/mininet/mininet.git
cd mininet
```

Move the Mininet OSPF and Mininet OSPF hybrid folder into the mininet folder:

```bash
mv [source_folder] [destination_folder]
```

Replace `[source_folder]` with the actual destination of the mininet OSPF folder.
Replace `[destination_folder]` with the actual destination of the mininet folder.

Move into the Mininet OSPF folder:

```bash
cd mininet/mininet_ospf or cd mininet/mininet_ospf_hybrid
```
Install Mininet Dependencies:

```bash
sudo util/install.sh -n
```
Make config_frr.sh executable:

```bash
chmod +x config_frr.sh
```
Run config_frr.sh:

```bash
sudo ./config_frr.sh
```

Run the Mininet topology script:

```bash
sudo python3 mn_topo.py
```

Confirm that the FRR configuration files are in the expected location before running the benchmark.

### 11.4 Run Comparison Scripts

From the project root:

```bash
sudo python3 newbenchmark_mininet.py
sudo python3 benchmark_mininet_tbcm.py
```

### 11.5 Run the SEED IE Environment

Clone SEED IE:

```bash
git clone https://github.com/seed-labs/seed-emulator.git
cd seed-emulator
```

Move the seed_ie folder into the seed-emulator examples  folder:

```bash
mv [source_folder] [destination_folder]
```

Replace `[source_folder]` with the actual destination of the seed_ie folder.
Replace `[destination_folder]` with the actual destination of the seed-emulator/examples folder.
In this implementation, the SEED IE scripts should be run from the examples directory of the SEED Emulator installation.

Move into the SEED IE folder:

```bash
cd seed-emulator
```

Install a Python Virtual Environment:

```bash
sudo python3 -m venv venv
```

Install your requirements inside the virtual environment:

```bash
source venv/bin/activate
pip install -r requirements.txt
source development.env
```

Move into the seed_ie folder:

```bash
cd examples/seed_ie
```

Run the SEED IE topology script:

```bash
python3 SEED_Ring.py
and for the hybrid layout
python3 SEED_ring_hybrid.py
```

This will produce an output folder.

Move into the output folder:

```bash
cd output
```
Depending on the SEED setup, the generated Docker environment may then need to be built and started using Docker Compose.

Example:

```bash
docker compose build
docker compose up
```

### 11.6 Run Comparison Scripts

From the project root:

```bash
python3 newbenchmark_seed.py
python3 benchmark_seed_tbcm.py
```

### 11.7 Hybrid Mininet–SEED IE Configuration


This project includes a hybrid configuration that connects the Mininet FRR/OSPF topology to the SEED Internet Emulator topology. The purpose of this setup is to allow latency testing between the two emulation environments while still keeping routing behaviour controlled and reproducible.

The hybrid connection is configured in three stages because creating a physical/logical link and advertising routes through OSPF are different tasks.

### Hybrid route design

The final hybrid setup uses the following address structure:

```text
Mininet network:        10.1.0.0/16
SEED IE network:        10.0.0.0/16
Hybrid bridge network:  172.16.100.0/30

Mininet R1 bridge IP:   172.16.100.2
SEED gateway bridge IP: 172.16.100.1
SEED gateway internal:  10.0.200.253
SR1 internal:           10.0.200.254
````

A `/16` route is used instead of a broader `/8` route to avoid unnecessary overlap across the private `10.x.x.x` address space. This keeps the Mininet and SEED IE networks separate and makes the benchmark environment more controlled.

### Files used

```text
scripts/part1_setup_hybrid_link.sh
scripts/part2_configure_mininet_r1_frr.sh
scripts/part3_configure_sr1_bird.sh
configs/sr1_bird_mininet_static.conf
```

### Part 1: Create the hybrid link

File:

```text
scripts/part1_setup_hybrid_link.sh
```

This script creates the direct Linux veth link between Mininet R1 and the SEED gateway:

```text
Mininet R1 <-> SEED gateway <-> SR1
```

It creates the veth pair, assigns the bridge IP addresses, enables IPv4 forwarding, and adds the immediate Linux routes needed for R1, the SEED gateway, and SR1 to reach each other.

Run:

```bash
sudo ./scripts/part1_setup_hybrid_link.sh <seed_gateway_container> <sr1_container>
```

Example:

```bash
sudo ./scripts/part1_setup_hybrid_link.sh 270e61e94928 1377af43db50
```

After this stage, connectivity is tested using ping between Mininet R1, the SEED gateway, and SR1.

### Part 2: Advertise SEED routes inside Mininet

File:

```text
scripts/part2_configure_mininet_r1_frr.sh
```

This script configures FRRouting on Mininet R1. R1 is given a static route to the SEED network and then redistributes that static route into OSPF.

This means the other Mininet routers learn:

```text
To reach 10.0.0.0/16, forward traffic through R1.
```

Run:

```bash
sudo ./scripts/part2_configure_mininet_r1_frr.sh
```

This replaces the manual process of entering the R1 namespace and running `vtysh -N r1`.

The equivalent FRR logic is:

```text
ip route 10.0.0.0/16 172.16.100.1
router ospf
 redistribute static
```

After this stage, other Mininet routers should be able to route towards SEED IE through R1.

### Part 3: Advertise Mininet routes inside SEED IE

Files:

```text
scripts/part3_configure_sr1_bird.sh
configs/sr1_bird_mininet_static.conf
```

The `.conf` file contains the BIRD configuration snippet added to SR1:

```bird
protocol static mininet_static {
    ipv4;

    route 10.1.0.0/16 via 10.0.200.253;
    route 172.16.100.0/30 via 10.0.200.253;
}
```

Inside the existing BIRD OSPF section, static routes must be exported into OSPF:

```bird
ipv4 {
    import all;
    export where source = RTS_STATIC;
};
```

The `.sh` script automates adding this configuration into SR1’s `/etc/bird/bird.conf` and reloads BIRD.

Run:

```bash
sudo ./scripts/part3_configure_sr1_bird.sh <sr1_container>
```

Example:

```bash
sudo ./scripts/part3_configure_sr1_bird.sh 1377af43db50
```

This allows SEED routers to learn:

```text
To reach 10.1.0.0/16, forward traffic through SR1.
```

This avoids manually adding static return routes to every SEED router.

### Why both `.conf` and `.sh` files are included for SR1

The SR1 BIRD setup is provided in two forms:

```text
configs/sr1_bird_mininet_static.conf
scripts/part3_configure_sr1_bird.sh
```

The `.conf` file shows the exact BIRD configuration that was added to SR1. It is included for transparency and manual reproduction.

The `.sh` file automates the process of applying that configuration inside the SR1 container. It backs up `/etc/bird/bird.conf`, inserts the Mininet static route block, and reloads BIRD.

This means the setup can be reproduced manually or automatically.

### Recommended execution order

Run the scripts in this order:

```bash
sudo ./scripts/part1_setup_hybrid_link.sh <seed_gateway_container> <sr1_container>
sudo ./scripts/part2_configure_mininet_r1_frr.sh
sudo ./scripts/part3_configure_sr1_bird.sh <sr1_container>
```

### Verification commands

Check the Mininet route table:

```bash
sudo mnexec -a "$(pgrep -f 'mininet:r1' | head -n 1)" ip route
```

Ping the SEED gateway from Mininet R1:

```bash
sudo mnexec -a "$(pgrep -f 'mininet:r1' | head -n 1)" ping -c 4 172.16.100.1
```

Ping SR1 from Mininet R1:

```bash
sudo mnexec -a "$(pgrep -f 'mininet:r1' | head -n 1)" ping -c 4 10.0.200.254
```

Check that SR1 has the Mininet route in BIRD:

```bash
sudo docker exec -it <sr1_container> birdc show route | grep 10.1
```

Check that another SEED router has learned the Mininet route:

```bash
sudo docker exec -it <another_seed_router> birdc show route | grep 10.1
```

### Design explanation

The hybrid setup is separated into three stages because direct connectivity and routing advertisement are not the same thing.

The first stage creates the direct veth bridge between Mininet R1 and the SEED gateway. This proves that the two emulator environments can communicate at the boundary.

The second stage configures Mininet R1 to advertise the SEED network into the Mininet OSPF domain. This allows other Mininet routers to learn that SEED IE is reachable through R1.

The third stage configures BIRD on SEED SR1 to advertise the Mininet network into the SEED routing domain. This allows SEED routers to learn the return path dynamically.

This design avoids manually configuring static routes on every router and produces a cleaner, more realistic routed hybrid network for inter-emulator latency testing.

````

Then in your main README file, add a small link to it if you want to keep the main README shorter:

```markdown
For the hybrid Mininet-SEED IE setup, see the section **Hybrid Mininet-SEED IE Configuration**.
````

Or, if you are using a separate file, add:

```markdown
Detailed hybrid setup instructions are available in [`docs/HYBRID_SETUP.md`](docs/HYBRID_SETUP.md).
```


---

## 12. Key Findings

The experiments show that both Mininet and SEED IE can be used for repeatable network emulation benchmarking, but they show different performance and resource usage patterns.

Key findings include:

* SEED IE generally showed very low CPU overhead.
* SEED IE often produced more stable resource usage.
* Mininet achieved strong throughput and bandwidth values on several tested paths.
* Mininet showed higher variation in some throughput and bandwidth tests.
* SEED IE had a slightly higher but more stable memory footprint.
* Inter-emulator testing confirmed that Mininet and SEED IE could communicate successfully in the combined test environment.
* Occasional outliers were observed in some routes, which is expected in virtualised/emulated environments.

These findings suggest that emulator architecture has a measurable effect on performance, stability, and resource overhead.

---

## 13. Artefact Contribution

This repository provides a technical artefact for the dissertation project.

The contribution of the artefact is that it provides:

* an equivalent OSPF-based topology across two emulation platforms
* automated benchmark scripts
* raw experimental datasets
* comparison-ready result outputs
* inter-emulator testing scripts
* evidence for evaluating emulator performance and resource overhead

The artefact is intended to support reproducibility and allow the results discussed in the dissertation to be traced back to the scripts and data used during testing.

---

## 14. Limitations

The results should be interpreted as emulator performance results, not physical network performance results.

Main limitations include:

* Results may vary depending on host machine specifications.
* VirtualBox, Docker, Mininet, Linux kernel behaviour, and background load can affect measurements.
* The comparison is based on a six-node ring topology.
* The results may not generalise to very large or production-scale networks.
* Some values may include temporary spikes caused by host scheduling or emulator overhead.
* The experiments were carried out in a controlled lab environment rather than a live production network.

---

## 15. Future Work

Possible future extensions include:

* testing larger topologies
* adding EVE-NG or GNS3 as additional comparison platforms
* testing more routing protocols
* adding automated graph generation
* developing a dashboard for results
* repeating the experiment across different host machines
* adding security attack simulations
* comparing OSPF routing with SDN forwarding as a separate experiment
* improving automation for full setup and teardown

---

## 16. Academic Context

This repository supports a Masters dissertation project at Teesside University.

The project investigates network emulation performance using controlled benchmarking, automated data collection, and comparative analysis.

---

## 17. Author

**Emmanuel Odianose Aghedo**
MSc Computing Project
Teesside University

---

## 18. Disclaimer

This project is intended for academic and controlled lab use only.

The scripts should not be run on production networks or third-party systems without permission.

````



