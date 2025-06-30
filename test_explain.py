import httpx
import os
import time

def listen_to_sse_stream():
    """
    Connects to the SSE stream and prints incoming events.
    """
    server_ip = os.getenv("AWSIP", "localhost")
    url = f"http://{server_ip}:8000/sse"
    
    print(f"Connecting to SSE stream at: {url}")

    try:
        with httpx.stream("GET", url, timeout=None) as response:
            print("Successfully connected to stream. Waiting for events...")
            for line in response.iter_lines():
                if line:
                    print(f"Received: {line}")

    except httpx.ConnectError as e:
        print(f"Connection error: {e}")
    except KeyboardInterrupt:
        print("\nStream closed by user.")

if __name__ == "__main__":
    if not os.getenv("AWSIP"):
        print("WARNING: AWSIP environment variable not set. Defaulting to localhost.")
        print("If the server is remote, please set the AWSIP variable.\n")

    listen_to_sse_stream()
