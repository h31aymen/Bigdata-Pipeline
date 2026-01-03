# ELK + Flink Network Monitoring Pipeline

A comprehensive data pipeline for collecting, processing, and analyzing network device logs using Elastic Stack (ELK), Apache Flink, and Redis.

## Architecture Overview
```text
┌─────────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐
│ Network         │ │   Filebeat  │ |  Logstash   │ │     Redis       │
│ Devices         ├►│ (UDP:514)   ├►│   (5044)    ├►│ (Queue)         │
└─────────────────┘ └─────────────┘ └─────────────┘ └────────┬────────┘
															 │
									┌─────────────────┐ ┌────▼────┐
									│ Log Generator   │ │ Flink   │
									│ (Optional)      │ │(JobMgr) │
									└─────────────────┘ └────┬────┘
									                         │
													  ┌──────▼──────┐
													  │ Elastic-    │
													  │ search      │
													  └──────┬──────┘
														     │
													  ┌──────▼──────┐
													  │ Kibana      │
													  │ (Dashboard) │
													  └─────────────┘

```
## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.8+ (for log generator)
- Minimum 4GB RAM allocated to Docker

### Installation

1. **Clone and setup**
```bash
git clone <repository-url>
cd Bigdata-Pipeline
```
2. **Build the custom Flink image**
```bash
docker build -t my-flink-jobmanager -f Dockerfile.flink .
```
3. **Start the pipeline**
```bash
docker-compose up -d
```
4. **Generate sample logs**
```bash
python generate_logs.py
```

## Project Structure
```text
Bigdata-Pipeline/
├── docker-compose.yml          # Main orchestration file
├── filebeat.yml               # Filebeat configuration
├── logstash.conf              # Logstash pipeline configuration
├── logstash.yml               # Logstash settings
├── flink_process.py           # Flink stream processing logic
├── generate_logs.py           # Sample log generator
├── README.md                  # This file
└── C:/Users/Public/logs/      # External log directory (Windows)
```

## Services Configuration
1. Filebeat (Log Shipper)
Port: 514/UDP
Role: Collects syslog data from network devices
Volume Mount: Monitors C:/Users/Public/logs (Windows path)
2. Logstash (Log Processor)
Port: 5044/TCP
Filters: Parses log messages using GROK patterns
Output: Sends processed logs to Redis queue
3. Redis (Message Queue)
Role: Temporary storage for logs before processing
Volume: Persistent storage for data durability
4. Apache Flink (Stream Processor)
Port: 8081 (Web UI)
Job: Processes logs from Redis, aggregates statistics
Output: Updates Elasticsearch with device analytics
5. Elasticsearch (Data Storage)
	* Ports: 9200 (HTTP), 9300 (TCP)
	* Index: network-logs
6. Kibana (Visualization)
Port: 5601
Dashboard: View network device statistics

## Data Flow
1. Ingestion: Network devices send syslog to Filebeat via UDP/514
2. Processing: Logstash parses logs, filters, and pushes to Redis
3. Buffering: Redis acts as a queue (list: logstash:logs)
4. Stream Processing: Flink reads from Redis in batches (100 logs)
5. Aggregation: Flink computes device-level statistics:
	* Total logs per device
	* Warning counts
	* Port status (up/down)
	* Most common log levels
6. Storage: Aggregated data stored in Elasticsearch
7. Visualization: Kibana dashboard displays real-time metrics

## Features
* Real-time Processing: Near real-time log analysis pipeline
* Scalable Architecture: Microservices-based design
* Fault Tolerance: Automatic restart policies for all services
* Persistent Storage: Redis and Elasticsearch data persistence
* Monitoring: Built-in metrics and logging
* Flexible Input: Supports syslog UDP, file monitoring, and simulated data