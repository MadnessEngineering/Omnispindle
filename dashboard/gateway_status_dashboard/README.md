# Gateway Statistics Dashboard

This directory contains the individual Node-RED nodes for the Gateway Statistics Dashboard, which displays MQTT data from gateways with date-based comparisons.

## Overview

The Gateway Statistics Dashboard allows for monitoring gateway data with the following features:
- Summary statistics for all gateways
- Detailed view of individual gateway metrics
- Date-based comparison of gateway statistics
- Visualization of sensor type distribution

## Components

The dashboard is split into the following components:

1. **Process_gateway_stats.json**: 
   - The core processing node that extracts date information from MQTT topics
   - Organizes data by date in the dateBasedStats structure
   - Calculates aggregate statistics for the dashboard

2. **Ui_Controller.json**:
   - Routes processed data to the appropriate UI components
   - Simple controller with two outputs (Summary and Details)

3. **Gateway_Summary.json**:
   - Displays an overview of all gateways
   - Shows aggregate statistics (total gateways, elements, readings)
   - Includes sensor type distribution chart
   - Has date selector for viewing historical data

4. **Gateway_Details.json**:
   - Shows detailed information for individual gateways
   - Provides date comparison functionality
   - Displays charts for sensor type distribution
   - Allows for selecting specific gateways

## Importing into Node-RED

To import these nodes into Node-RED:

1. Access your Node-RED editor
2. Click on the hamburger menu (≡) in the top-right corner
3. Select "Import" from the menu
4. Choose "Clipboard" as the import method
5. Open each JSON file and copy its contents
6. Paste the contents into the import dialog
7. Click "Import" to add the node to your flow
8. Repeat for each JSON file

Alternatively, you can import all nodes at once by merging the JSON arrays from each file.

## Configuration

After importing, you need to:

1. Connect the nodes as follows:
   - Connect your MQTT input node to the "Process Gateway Stats" node
   - Connect "Process Gateway Stats" to the "UI Controller" input
   - Connect the first output from "UI Controller" to "Gateway Summary"
   - Connect the second output from "UI Controller" to "Gateway Details"

2. Configure the MQTT input to subscribe to:
   `projects/em-beta/subscriptions/gateway-stats/#`

## Dependencies

- The dashboard requires Chart.js, which is loaded via CDN in the template nodes
- Requires the Node-RED Dashboard module to be installed
- Works with data published by the mongo_tasks.py script 
