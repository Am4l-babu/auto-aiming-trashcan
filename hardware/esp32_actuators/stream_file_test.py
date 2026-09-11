import socket, struct, wave, sys

path = sys.argv[1]
host = sys.argv[2] if len(sys.argv) > 2 else "10.38.122.18"
port = 8081

with wave.open(path, "rb") as w:
    rate = w.getframerate()
    channels = w.getnchannels()
    print(f"Streaming {path} -> {host}:{port} rate={rate} ch={channels}")
    header = struct.pack("<IB", rate, channels)
    with socket.create_connection((host, port), timeout=10) as s:
        s.sendall(header)
        chunk = w.readframes(4096)
        total = 0
        while chunk:
            s.sendall(chunk)
            total += len(chunk)
            chunk = w.readframes(4096)
print(f"Done, sent {total} bytes")
