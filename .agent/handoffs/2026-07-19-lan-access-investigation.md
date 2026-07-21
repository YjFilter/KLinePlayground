# LAN Access Investigation Handoff

## Current Symptom
- The host opens http://127.0.0.1:8000 and http://192.168.1.24:8000 successfully.
- Another LAN computer can ping 192.168.1.24 but cannot open the web app.

## Confirmed Host State
- Flask listens on 0.0.0.0:8000 using Python 3.11.
- Host address: 192.168.1.24/24 on WLAN LJM-5G.
- Windows classifies the WLAN as Public.
- Windows Defender is the only registered antivirus.
- Local health requests return HTTP 200.

## Firewall Changes
- Added inbound rule KLinePlayground TCP 8000 LAN: TCP 8000, Private/Public, RemoteAddress LocalSubnet.
- Added inbound rule KLinePlayground Python 8000 LAN: Python executable, LocalAddress 192.168.1.24, RemoteAddress 192.168.1.0/24, TCP 8000, all profiles.
- Both rules are enabled and verified with netsh.

## Pending Evidence
Run these commands on the client computer and capture complete output:

powershell -Command "Test-NetConnection 192.168.1.24 -Port 8000"
curl.exe -v --noproxy "*" http://192.168.1.24:8000/api/health
ipconfig | findstr /i "IPv4"

## Interpretation
- TcpTestSucceeded false and no host packet arrival: router/guest Wi-Fi/client isolation or wrong client subnet.
- TcpTestSucceeded true but browser fails: browser/system proxy, HTTPS upgrade, or browser policy.
- curl with --noproxy succeeds: configure proxy bypass for 192.168.1.* and local addresses.
- Host packet arrival followed by drop: inspect Windows Filtering Platform/firewall logs.

## Safety
- The temporary pktmon capture was stopped and its filter was removed.
- Do not delete or modify .runtime/ or offline market data.
- Existing uncommitted project changes remain intact; no commit was created.
