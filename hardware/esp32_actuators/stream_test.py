"""One-off test: streams a short generated sine tone to the ESP32's audio
socket (port 8081), matching the wire protocol implemented in main.cpp:
5-byte header (4-byte LE sample rate + 1-byte channel count), then raw
16-bit PCM samples until the socket closes."""
import socket
import struct
import math
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "10.38.122.18"
PORT = 8081
RATE = 16000
DURATION_S = 1.5
FREQ = 660.0

samples = []
n = int(RATE * DURATION_S)
for i in range(n):
    t = i / RATE
    v = int(math.sin(2 * math.pi * FREQ * t) * 12000)
    samples.append(struct.pack("<h", v))

payload = b"".join(samples)
header = struct.pack("<IB", RATE, 1)  # mono

print(f"Connecting to {HOST}:{PORT} ...")
with socket.create_connection((HOST, PORT), timeout=5) as s:
    s.sendall(header)
    s.sendall(payload)
print(f"Sent {len(payload)} bytes of PCM ({DURATION_S}s at {RATE}Hz mono)")
