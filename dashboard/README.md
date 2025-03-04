# Node-RED MQTT Status Dashboard

This dashboard shows status lights for devices that publish to MQTT topics with the pattern `status/[DeviceName]/alive`.

## Features

- **Dynamic Device Detection**: Automatically adds new status lights when messages from new devices are received.
- **Status Indicators**: Shows green lights for online devices and red lights for offline devices.
- **Clean UI**: Simple, organized display of all registered devices with their current status.
- **Zero Status Recognition**: Turns lights red when a "0" message is received.
- **Automatic Timeout**: Marks devices as offline if no messages have been received for an hour.
- **MCP Integration**: Can be deployed and controlled via MCP tools.

## Setup Instructions

### Manual Import
1. Import the `mqtt_status_lights.json` flow into your Node-RED instance.
2. Configure your MQTT broker connection in the MQTT input node.
3. Deploy the flow.

### Automated Deployment via Shell Script
Use the included deployment script:

```bash
# Make the script executable if needed
chmod +x deploy_to_nodered.sh

# Deploy to local Node-RED instance
./deploy_to_nodered.sh

# Or specify a custom server URL
./deploy_to_nodered.sh http://your-server:1880

# With authentication
./deploy_to_nodered.sh http://your-server:1880 username password
```

### Deployment via MCP
Use the MCP integration to deploy and control the dashboard:

```bash
# Deploy the dashboard to Node-RED using MCP
./deploy_flow_with_mcp.py --node-red-url http://your-nodered:1880 --mcp-url http://your-mcp:8000

# With authentication
./deploy_flow_with_mcp.py --node-red-url http://your-nodered:1880 --username user --password pass
```

## MCP Integration

This dashboard integrates with the MCP system through the following tools:

### `update_device_status_tool`
Updates the status of a device in the dashboard.

```python
# Example use in MCP
result = await update_device_status_tool(
    device_name="my_device",
    status=True  # True for online (green), False for offline (red)
)
```

### `deploy_nodered_flow_tool`
Deploys or updates the dashboard flow in Node-RED.

```python
# Example use in MCP
with open("mqtt_status_lights.json", "r") as f:
    flow_json = json.load(f)

result = await deploy_nodered_flow_tool(
    flow_json=flow_json,
    node_red_url="http://localhost:1880",
    username="optional_user",
    password="optional_pass"
)
```

## How It Works

1. The flow subscribes to MQTT topics with the pattern `status/+/alive` where `+` is a wildcard that matches any device name.
2. When a message is received, the flow extracts the device name from the topic.
3. The status light logic:
   - Turns green if a non-zero message is received (device is alive)
   - Turns red if a "0" message is received (device is offline)
   - Turns red if no messages have been received for 1 hour (timeout)

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

# Turn doorlock status to red (offline)
mosquitto_pub -t "status/doorlock/alive" -m "0"
```

Or use the MCP test script:

```bash
# Test with multiple simulated devices
./test_mcp_device_status.py

# Customize the devices and timing
./test_mcp_device_status.py --devices robot1 robot2 camera --interval 10
```

## Dashboard Structure

The flow creates a dedicated tab in the Node-RED dashboard with:

- A dynamic panel that automatically adds new devices as they appear
- LED indicators that show red/green status for each device
- Device names clearly labeled next to each status light
- Large status lights for all online devices

## Customization

You can modify the flow to:

- Change the colors of the status lights
- Adjust the timeout period (currently set to 1 hour)
- Add more complex status logic based on the message payload
- Adjust the layout and styling of the dashboard elements
