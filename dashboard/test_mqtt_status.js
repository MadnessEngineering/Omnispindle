/**
 * This script simulates device status messages for testing the Node-RED dashboard.
 * 
 * Usage: node test_mqtt_status.js [broker_url]
 * Default broker URL: mqtt://localhost:1883
 */

const mqtt = require('mqtt');

// Get the broker URL from command line args or use default
const brokerUrl = process.argv[2] || 'mqtt://localhost:1883';

// Create an MQTT client
const client = mqtt.connect(brokerUrl);

// List of sample devices
const devices = [
    'device1',
    'thermostat',
    'doorlock',
    'camera',
    'lightswitch'
];

// Track connection status
client.on('connect', () =>
{
    console.log(`Connected to MQTT broker at ${brokerUrl}`);
    console.log('Starting device status simulation...');

    // Start the simulation
    simulateDevices();
});

// Handle connection errors
client.on('error', (err) =>
{
    console.error('Connection error:', err);
    client.end();
});

/**
 * Simulates random device status changes
 */
function simulateDevices()
{
    // Initial status messages for all devices
    devices.forEach(device =>
    {
        publishStatus(device, true);
        console.log(`Initialized ${device} as ONLINE`);
    });

    // Randomly change device statuses
    setInterval(() =>
    {
        // Pick a random device
        const deviceIndex = Math.floor(Math.random() * devices.length);
        const device = devices[deviceIndex];

        // Random status (90% chance of being online, 10% chance of being offline)
        const status = Math.random() > 0.1;

        // Publish the status
        publishStatus(device, status);

        console.log(`${device} is now ${status ? 'ONLINE' : 'OFFLINE'}`);
    }, 5000); // Every 5 seconds
}

/**
 * Publishes a status message for a device
 * @param {string} device - Device name
 * @param {boolean} status - Online status
 */
function publishStatus(device, status)
{
    const topic = `status/${device}/alive`;

    if (status)
    {
        // If the device is online, publish a message
        client.publish(topic, 'true');
    } else
    {
        // For offline status, we simply don't publish
        // In a real implementation, we could use MQTT's "will" feature
        // But for this simulation, we'll manually publish a "false" status
        client.publish(topic, 'false');
    }
}

// Handle Ctrl+C to gracefully exit
process.on('SIGINT', () =>
{
    console.log('Stopping simulation');
    client.end();
    process.exit();
}); 
