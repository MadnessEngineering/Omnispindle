# Node-RED MQTT Status Dashboard

This dashboard shows status lights for devices that publish to MQTT topics with the pattern `status/[DeviceName]/alive`.

## Features

- **Dynamic Device Detection**: Automatically adds new status lights when messages from new devices are received.
- **Status Indicators**: Shows green lights for online devices and red lights for offline devices.
- **Clean UI**: Simple, organized display of all registered devices with their current status.

## Setup Instructions

1. Import the `mqtt_status_lights.json` flow into your Node-RED instance.
2. Configure your MQTT broker connection in the MQTT input node.
3. Deploy the flow.

## How It Works

1. The flow subscribes to MQTT topics with the pattern `status/+/alive` where `+` is a wildcard that matches any device name.
2. When a message is received, the flow extracts the device name from the topic.
3. The status light for that device turns green if any message is received (indicating the device is alive).
4. If no message is received or the connection is lost, the status light turns red.

## Testing

You can test the dashboard by publishing messages to topics like:

```
status/device1/alive
status/thermostat/alive
status/doorlock/alive
```

Example MQTT commands for testing:

```bash
# Turn device1 status to green (online)
mosquitto_pub -t "status/device1/alive" -m "true"

# Turn thermostat status to green (online)
mosquitto_pub -t "status/thermostat/alive" -m "1"

# The content of the message doesn't matter, just the presence of any message
# will set the status to green
```

## Dashboard Structure

The flow creates a dedicated tab in the Node-RED dashboard with:

- A dynamic panel that automatically adds new devices as they appear
- LED indicators that show red/green status for each device
- Device names clearly labeled next to each status light

## Customization

You can modify the flow to:

- Change the colors of the status lights
- Add more complex status logic based on the message payload
- Adjust the layout and styling of the dashboard elements 
