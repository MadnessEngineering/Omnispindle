#!/usr/bin/env python3
"""
MongoDB Gateway Statistics Collector and MQTT Publisher

This script connects to MongoDB, retrieves gateway and sensor data,
calculates statistics, and publishes them to MQTT for the Gateway Statistics Dashboard.
"""

import datetime
import json
import logging
import os
import time
from typing import Any
from typing import Dict
from typing import List

import paho.mqtt.client as mqtt
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pymongo.errors import ServerSelectionTimeoutError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mongo_tasks")

# MongoDB connection settings
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://10.10.1.4:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "dataset_beta2_raw_ingest")
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION", "2025-03-09")

# MQTT connection settings
MQTT_HOST = os.environ.get("MQTT_HOST", "52.44.236.251")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 3003))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "projects/em-beta/subscriptions/gateway-stats")
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", f"mongo-stats-collector-{int(time.time())}")

# Processing settings
UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL", 60))  # seconds
DEBUG = "true"


class GatewayStatsCollector:
    """
    Collects gateway statistics from MongoDB and publishes them to MQTT
    """

    def __init__(self):
        """Initialize MongoDB connection and MQTT client"""
        self.mongo_client = None
        self.mqtt_client = None
        self.db = None
        self.collection = None
        self.gateway_field = "gateway"  # Default gateway field
        self.timestamp_field = None
        self.sensor_type_stats = {}
        self.connected = False
        self.mqtt_connected = False

    def connect_mongo(self) -> bool:
        """
        Connect to MongoDB
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to MongoDB at {MONGO_URI}")
            self.mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            self.mongo_client.admin.command('ping')
            self.db = self.mongo_client[MONGO_DB]
            self.collection = self.db[MONGO_COLLECTION]
            logger.info(f"Connected to MongoDB: {MONGO_DB}.{MONGO_COLLECTION}")

            # Print a sample document if in debug mode
            if DEBUG:
                sample = list(self.collection.find().limit(1))
                # if sample:
                #     logger.info(f"Sample document structure: {json.dumps(self._sanitize_doc(sample[0]), indent=2)}")

            return True

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection error: {e}")
            return False

    def _sanitize_doc(self, doc):
        """Helper method to sanitize MongoDB document for logging (removing ObjectId)"""
        if not doc:
            return {}

        # Create a deep copy to avoid modifying the original
        doc_copy = {}

        # Process each key/value pair
        for key, value in doc.items():
            # Handle ObjectId
            if key == '_id':
                doc_copy[key] = str(value)
            # Handle datetime objects
            elif isinstance(value, datetime.datetime):
                doc_copy[key] = value.isoformat()
            # Handle nested dictionaries
            elif isinstance(value, dict):
                doc_copy[key] = self._sanitize_doc(value)
            # Handle lists containing dictionaries or other objects
            elif isinstance(value, list):
                doc_copy[key] = [
                    self._sanitize_doc(item) if isinstance(item, dict)
                    else str(item) if hasattr(item, '__str__') and not isinstance(item, (str, int, float, bool, type(None)))
                    else item
                    for item in value
                ]
            # Handle other non-serializable objects
            elif not isinstance(value, (str, int, float, bool, type(None))):
                doc_copy[key] = str(value)
            else:
                doc_copy[key] = value

        return doc_copy

    def connect_mqtt(self) -> bool:
        """
        Connect to the MQTT broker
        
        Returns:
            bool: True if connected, False otherwise
        """
        try:
            if self.mqtt_client:
                try:
                    self.mqtt_client.disconnect()
                except:
                    pass

            client_id = f'mongo-tasks-{os.getpid()}'
            self.mqtt_client = mqtt.Client(client_id=client_id, clean_session=True)

            # Set up callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect

            # Connect to broker
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.mqtt_client.loop_start()

            # Wait for the connection to be established
            for _ in range(10):
                if self.mqtt_connected:
                    logger.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
                    return True
                time.sleep(0.5)

            logger.error(f"Failed to connect to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to MQTT: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """
        Callback when connected to MQTT
        """
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self.mqtt_connected = True
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            self.mqtt_connected = False

    def _on_disconnect(self, client, userdata, rc):
        """
        Callback when disconnected from MQTT
        """
        logger.warning(f"Disconnected from MQTT broker with code {rc}")
        self.mqtt_connected = False

    def analyze_document_structure(self):
        """
        Analyze the structure of documents in the collection
        
        This method examines sample documents to determine:
        - Key fields like gateway ID and timestamps
        - Common document structure
        """
        try:
            # Get a sample document
            sample_doc = self.collection.find_one()
            if not sample_doc:
                logger.warning("No documents found in collection")
                return

            # Log document structure
            sanitized_doc = self._sanitize_doc(sample_doc)
            if DEBUG:
                sample_json = json.dumps(sanitized_doc, indent=2)
                # logger.info(f"Sample document structure: {sample_json}")

            # Detect timestamp field if not already set
            if self.timestamp_field is None:
                # Check for common timestamp field names
                timestamp_fields = [
                    "backend_processed_timestamp",
                    "timestamp",
                    "sample_timestamp",
                    "message_timestamp",
                    "pubsub_received_timestamp"
                ]

                for field in timestamp_fields:
                    if field in sample_doc:
                        self.timestamp_field = field
                        logger.info(f"Using timestamp field: {field}")
                        break

                if self.timestamp_field is None:
                    logger.warning("No timestamp field found, using message_timestamp as default")
                    self.timestamp_field = "message_timestamp"

            # Identify other useful fields
            if "gateway" in sample_doc:
                self.gateway_field = "gateway"

        except Exception as e:
            logger.error(f"Error analyzing document structure: {e}")

    def get_unique_gateways(self) -> List[str]:
        """
        Get a list of unique gateway IDs from MongoDB, filtering for gateways with a length of 32
        
        Returns:
            List[str]: List of unique gateway IDs with length 32
        """
        try:
            gateways = self.collection.distinct("gateway")
            full_gateways = [gateway for gateway in gateways if len(gateway) == 32]
            logger.info(f"Found {len(full_gateways)} unique gateways with length 32")
            return full_gateways
        except Exception as e:
            logger.error(f"Error fetching unique gateways with length 32: {e}")
            return []

    def get_timestamp_field(self) -> str:
        """
        Get the timestamp field to use for queries
        
        Returns:
            str: Name of the timestamp field
        """
        if self.timestamp_field:
            return self.timestamp_field

        # If not set, try to determine it
        self.analyze_document_structure()

        # Return the field or a default
        return self.timestamp_field or "message_timestamp"

    def convert_timestamp_string_to_unix(self, ts_str: str) -> float:
        """
        Convert an ISO timestamp string to a Unix timestamp
        
        Args:
            ts_str: ISO timestamp string
            
        Returns:
            float: Unix timestamp
        """
        try:
            # Check if timestamp is already a number
            if isinstance(ts_str, (int, float)):
                return float(ts_str)

            # Handle string format like "2024-06-13T20:02:27.000+00:00"
            # Strip off the milliseconds and timezone for simpler parsing
            ts_str = ts_str.split('.')[0]
            dt = datetime.datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
            return dt.timestamp()
        except Exception as e:
            logger.error(f"Error converting timestamp '{ts_str}': {e}")
            return 0

    def get_gateway_stats(self, gateway: str, window_minutes: int = 15) -> Dict[str, Any]:
        """
        Get statistics for a specific gateway over the past 15 minutes.
        
        Args:
            gateway: Gateway ID to collect stats for
            window_minutes: Time window in minutes to look back (default: 15)
        
        Returns:
            Dictionary containing gateway statistics
        """
        try:
            now = datetime.datetime.now()
            window = now - datetime.timedelta(minutes=window_minutes)
            day_window = now - datetime.timedelta(hours=24)
            week_window = now - datetime.timedelta(days=7)

            # Get timestamp field
            ts_field = self.get_timestamp_field()
            logger.debug(f"Using timestamp field: {ts_field}")

            # Determine if we have string or numeric timestamps
            is_string_timestamp = ts_field in [
                "timestamp", "sample_timestamp",
                "pubsub_received_timestamp",
                "backend_processed_timestamp"
            ]

            # Create window timestamps in the appropriate format
            if is_string_timestamp:
                window_ts = window.isoformat()
                day_ts = day_window.isoformat()
                week_ts = week_window.isoformat()
                time_comparison = {"$gte": window_ts}
            else:
                # Convert to epoch for numeric comparison
                window_ts = int(window.timestamp())
                day_ts = int(day_window.timestamp())
                week_ts = int(week_window.timestamp())
                time_comparison = {"$gte": window_ts}

            # Find unique MAC addresses for this gateway
            mac_addresses = set()

            # Count total data points (elements in pubsub_message.data arrays)
            total_data_points = 0

            # Look for MAC addresses in the pubsub_message.data structure
            cursor = self.collection.find({"gateway": gateway}, {"pubsub_message.data": 1})

            for doc in cursor:
                if "pubsub_message" in doc and "data" in doc["pubsub_message"]:
                    # Count data points in this document
                    data_array = doc["pubsub_message"]["data"]
                    if isinstance(data_array, list):
                        total_data_points += len(data_array)

                        # Collect unique MAC addresses
                        for sensor in data_array:
                            if "mac_address" in sensor:
                                mac_addresses.add(sensor["mac_address"])

            # publish list of mac_addresses to it's own topic
            mac_address_topic = f"status/{gateway}/mac_addresses"
            self.mqtt_client.publish(mac_address_topic, json.dumps(list(mac_addresses)))

            total_elements = len(mac_addresses)

            # Query for recent readings (last 15 minutes)
            recent_readings = self.collection.count_documents({
                "gateway": gateway,
                ts_field: time_comparison
            })

            # Update time comparison for daily and weekly
            if is_string_timestamp:
                day_comparison = {"$gte": day_ts}
                week_comparison = {"$gte": week_ts}
            else:
                day_comparison = {"$gte": day_ts}
                week_comparison = {"$gte": week_ts}

            # Query for daily readings (last 24 hours)
            daily_readings = self.collection.count_documents({
                "gateway": gateway,
                ts_field: day_comparison
            })

            # Query for weekly readings (last 7 days)
            weekly_readings = self.collection.count_documents({
                "gateway": gateway,
                ts_field: week_comparison
            })

            # Get sensor type distribution
            sensor_types = {}
            cursor = self.collection.find({"gateway": gateway})

            for doc in cursor:
                if "pubsub_message" in doc and "data" in doc["pubsub_message"]:
                    data_points = doc["pubsub_message"]["data"]
                    if isinstance(data_points, list):
                        for point in data_points:
                            if "element_type" in point:
                                sensor_type = point["element_type"]
                                sensor_types[sensor_type] = sensor_types.get(sensor_type, 0) + 1

            # Store unique field counts
            unique_fields = {
                "mac_address": len(mac_addresses)
            }

            return {
                "elements": total_elements,
                "recentReadings": recent_readings,
                "hourlyReadings": daily_readings,
                "dailyReadings": weekly_readings,
                "dataPoints": total_data_points,
                "sensorTypes": sensor_types,
                "uniqueFields": unique_fields
            }

        except Exception as e:
            logger.error(f"Error getting stats for gateway {gateway}: {e}")
            return self._get_empty_stats()

    def _get_empty_stats(self):
        """Return empty statistics structure"""
        return {
            "elements": 0,
            "recentReadings": 0,
            "hourlyReadings": 0,
            "dailyReadings": 0,
            "dataPoints": 0,
            "sensorTypes": {},
            "uniqueFields": {
                "mac_address": 0
            }
        }

    def get_global_sensor_types(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all sensor types across all gateways
        
        Returns:
            Dict: Global sensor type statistics
        """
        try:
            sensor_types = {}
            pipeline = [
                {"$unwind": "$pubsub_message.data"},
                {"$group": {
                    "_id": "$pubsub_message.data.element_type",
                    "count": {"$sum": 1}
                }}
            ]

            results = self.collection.aggregate(pipeline)
            for result in results:
                if result["_id"]:  # Skip null values
                    sensor_types[result["_id"]] = {
                        "count": result["count"],
                        "lastUpdate": int(time.time() * 1000)
                    }

            return sensor_types

        except Exception as e:
            logger.error(f"Error getting global sensor type stats: {e}")
            return {}

    def collect_and_publish_stats(self, target_gateway=None):
        """
        Collect stats for all gateways or a specific one and publish to MQTT
        
        Args:
            target_gateway: Optional specific gateway to collect stats for
        """
        try:
            if not self.mqtt_connected:
                logger.warning("MQTT not connected, reconnecting...")
                self.connect_mqtt()
                if not self.mqtt_connected:
                    logger.error("Failed to connect to MQTT, skipping stats collection")
                    return

            # Analyze document structure first if needed
            if self.timestamp_field is None:
                logger.info("Document structure not yet analyzed, doing that now...")
                self.analyze_document_structure()

            if target_gateway:
                # Process only the specified gateway
                logger.info(f"Collecting stats for gateway: {target_gateway}")
                gateways = [target_gateway]
            else:
                # Get a list of all gateways
                logger.info("Collecting stats for all gateways")
                gateways = self.get_unique_gateways()

            # Get global sensor types
            sensor_types = self.get_global_sensor_types()

            # Build statistics for each gateway
            for gateway in gateways:
                stats = {}
                gateway_stats = self.get_gateway_stats(gateway)
                stats[gateway] = gateway_stats

                stats["sensorTypes"] = sensor_types
                json_payload = json.dumps(self._sanitize_doc(stats))

                info = self.mqtt_client.publish(f"{MQTT_TOPIC}/{MONGO_COLLECTION}", json_payload, qos=1)
                logger.info(f"Published stats to {MQTT_TOPIC} - gateway ID: {gateway} - message ID: {info.mid}")

        except Exception as e:
            logger.error(f"Error collecting/publishing stats: {e}")

    def run(self):
        """
        Main execution loop - now a wrapper around the continuous collection process
        
        This method is maintained for backward compatibility but main() now handles
        the execution flow based on environment variables.
        """
        try:
            # Connect to MongoDB and MQTT
            if not self.connect_mongo():
                logger.error("Failed to connect to MongoDB, exiting")
                return

            if not self.connect_mqtt():
                logger.error("Failed to connect to MQTT broker, exiting")
                return

            # Main loop
            logger.info(f"Starting collection loop with interval {UPDATE_INTERVAL} seconds")
            while True:
                self.collect_and_publish_stats()
                time.sleep(UPDATE_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Interrupted by user, shutting down")
        finally:
            # Clean up
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()

            if self.mongo_client:
                self.mongo_client.close()

            logger.info("Shutdown complete")


def main():
    """
    Main entry point
    """
    # Set even more detailed logging
    logging.getLogger('mongo_tasks').setLevel(logging.DEBUG)

    # Create collector instance
    collector = GatewayStatsCollector()

    # Connect to MongoDB
    print('Connecting to MongoDB...')
    if not collector.connect_mongo():
        print('Failed to connect to MongoDB')
        exit(1)
    else:
        print('Successfully connected to MongoDB')

    # Connect to MQTT
    print('Connecting to MQTT broker...')
    if not collector.connect_mqtt():
        print('Failed to connect to MQTT broker')
        exit(1)
    else:
        print('Successfully connected to MQTT broker')

    # Collect and publish stats
    print('Collecting and publishing stats...')
    target_gateway = os.getenv("TARGET_GATEWAY", "").strip()

    # Single execution mode - either for a specific gateway or looping through all gateways once
    if not os.getenv("CONTINUOUS_MODE", "").lower() in ("true", "1", "yes"):
        if target_gateway:
            print(f"Targeting specific gateway: {target_gateway}")
            collector.collect_and_publish_stats(target_gateway=target_gateway)
        else:
            print("Collecting stats for all gateways (single execution)")
            # This will loop through all gateways in a single execution
            collector.collect_and_publish_stats()
    else:
        # Continuous collection loop mode
        try:
            print(f"Starting continuous collection loop with interval {UPDATE_INTERVAL} seconds")
            while True:
                if target_gateway:
                    print(f"Collecting stats for gateway: {target_gateway}")
                    collector.collect_and_publish_stats(target_gateway=target_gateway)
                else:
                    print("Collecting stats for all gateways")
                    collector.collect_and_publish_stats()
                time.sleep(UPDATE_INTERVAL)
        except KeyboardInterrupt:
            print("Interrupted by user, shutting down")
        finally:
            # Clean up
            if collector.mqtt_client:
                collector.mqtt_client.loop_stop()
                collector.mqtt_client.disconnect()
            if collector.mongo_client:
                collector.mongo_client.close()
            print("Shutdown complete")

    print('Process complete')


if __name__ == "__main__":
    main()
