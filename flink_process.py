import redis
import json
import time
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch, ConnectionError

# Configuration du logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Configuration des services
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
ES_HOST = os.getenv("ES_HOST", "http://elasticsearch:9200")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 5))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", 10))
STARTUP_DELAY = 10

# Variable globale pour les statistiques par appareil
device_stats = {}

def connect_to_redis() -> redis.Redis:
    """Connexion à Redis avec gestion des erreurs"""
    for attempt in range(MAX_RETRIES):
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            if client.ping():
                logger.info("Connexion à Redis réussie.")
                return client
        except Exception as e:
            logger.error(f"Erreur de connexion à Redis (tentative {attempt + 1}/{MAX_RETRIES}): {e}")
        time.sleep(RETRY_DELAY)
    raise ConnectionError("Impossible de se connecter à Redis.")


def connect_to_elasticsearch() -> Elasticsearch:
    """Connexion à Elasticsearch avec gestion des erreurs"""
    for attempt in range(MAX_RETRIES):
        try:
            client = Elasticsearch([ES_HOST])
            if client.ping():
                logger.info("Connexion à Elasticsearch réussie.")
                return client
        except ConnectionError as e:
            logger.error(f"Erreur de connexion à Elasticsearch (tentative {attempt + 1}/{MAX_RETRIES}): {e}")
        time.sleep(RETRY_DELAY)
    raise ConnectionError("Impossible de se connecter à Elasticsearch.")

def get_logs_from_redis(redis_client: redis.Redis) -> List[str]:
    """Récupération des logs depuis Redis"""
    logs = [redis_client.lpop("logstash:logs") for _ in range(BATCH_SIZE) if redis_client.llen("logstash:logs") > 0]
    logger.info(f"{len(logs)} logs récupérés depuis Redis.")
    return logs

def parse_and_validate_log(log: str) -> Optional[Dict]:
    """Validation des logs"""
    try:
        log_dict = json.loads(log)
        required_fields = ["device", "level", "status", "port", "@timestamp"]
        return log_dict if all(field in log_dict for field in required_fields) else None
    except json.JSONDecodeError:
        return None

def analyze_logs(logs: List[Dict]) -> Dict:
    """Analyse et cumul des logs"""
    global device_stats

    # Reset device_stats for the current batch
    device_stats = {}

    for log in logs:
        device = log["device"]
        level = log["level"]
        timestamp = log["@timestamp"]

        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"

        try:
            log_time = datetime.fromisoformat(timestamp)
        except ValueError:
            continue

        if device not in device_stats:
            device_stats[device] = {
                "total_logs": 0,
                "warnings": 0,
                "ports_up": 0,
                "ports_down": 0,
                "log_levels": {},
            }

        # Increment total_logs by 1 for each log
        device_stats[device]["total_logs"] += 1
        if log["level"] == "WARNING":
            device_stats[device]["warnings"] += 1
        if log["status"] == "up":
            device_stats[device]["ports_up"] += 1
        elif log["status"] == "down":
            device_stats[device]["ports_down"] += 1

        device_stats[device]["log_levels"][level] = device_stats[device]["log_levels"].get(level, 0) + 1

    return device_stats

def update_elasticsearch(es_client: Elasticsearch, logs: List[Dict]):
    """Mise à jour cumulative des logs dans Elasticsearch"""
    for log in logs:
        device = log["device"]
        stats = device_stats[device]

        avg_logs_per_device = stats["total_logs"]
        most_common_level = max(stats["log_levels"], key=stats["log_levels"].get) if stats["log_levels"] else "N/A"

        script = {
            "script": {
                "source": """
                    ctx._source.total_logs += 1;  // Increment by 1 for each log
                    ctx._source.warnings += params.warnings;
                    ctx._source.ports_up += params.ports_up;
                    ctx._source.ports_down += params.ports_down;
                    ctx._source.analysis.avg_logs_per_device = params.avg_logs_per_device;
                    ctx._source.analysis.most_common_level = params.most_common_level;
                """,
                "params": {
                    "warnings": stats["warnings"],
                    "ports_up": stats["ports_up"],
                    "ports_down": stats["ports_down"],
                    "avg_logs_per_device": avg_logs_per_device,
                    "most_common_level": most_common_level,
                }
            },
            "upsert": {
                "device": device,
                "total_logs": 1,
                "warnings": stats["warnings"],
                "ports_up": stats["ports_up"],
                "ports_down": stats["ports_down"],
                "timestamp": int(datetime.fromisoformat(log["@timestamp"].replace("Z", "+00:00")).timestamp() * 1000),
                "analysis": {
                    "avg_logs_per_device": avg_logs_per_device,
                    "most_common_level": most_common_level,
                }
            }
        }

        try:
            es_client.update(index="network-logs", id=device, body=script)
            logger.info(f"Mise à jour réussie pour {device}")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de {device}: {e}")

    es_client.indices.refresh(index="network-logs")

def process_and_store_logs(redis_client: redis.Redis, es_client: Elasticsearch):

    while True:
        logs = get_logs_from_redis(redis_client)
        if not logs:
            logger.info("Aucun nouveau log. En attente...")
            time.sleep(5)
            continue

        parsed_logs = [parse_and_validate_log(log) for log in logs if parse_and_validate_log(log)]
        analyze_logs(parsed_logs)
        update_elasticsearch(es_client, parsed_logs)

        logger.info("Logs traités et stockés dans Elasticsearch.")

def main():

    try:
        logger.info(f"Attente de {STARTUP_DELAY} secondes pour Redis et Elasticsearch...")
        time.sleep(STARTUP_DELAY)

        redis_client = connect_to_redis()
        es_client = connect_to_elasticsearch()

        process_and_store_logs(redis_client, es_client)
    except KeyboardInterrupt:
        logger.info("Arrêt du script par l'utilisateur.")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
    finally:
        logger.info("Fin du script.")

if __name__ == "__main__":
    main()
