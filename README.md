# TCL UDP Air Conditioner Integration for Home Assistant

A Home Assistant integration for TCL air conditioners that communicate via UDP broadcast protocol.

## Features

- **Local Control**: Communicates directly with AC units on your local network via UDP
- **Real-time Updates**: Receives status updates via UDP broadcast messages
- **Climate Entity**: Full climate entity support with standard Home Assistant interface
- **Power Control**: Turn AC on/off
- **Temperature Control**: Set target temperature (60-86°F)
- **Current Temperature**: Display current indoor temperature

## Installation

### HACS (Recommended)
1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL
6. Install "TCL UDP Air Conditioner"
7. Restart Home Assistant

### Manual Installation
1. Copy the `custom_components/tcl_udp_ac` directory to your Home Assistant's `custom_components` folder
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "TCL UDP Air Conditioner"
4. Click to add the integration
5. The integration will automatically discover TCL AC units broadcasting on your network

## Protocol Details

This integration implements the TCL UDP-based AC protocol:
- **Broadcast Port**: 10074 (for receiving status updates)
- **Command Port**: 10075 (for sending control commands)
- **Protocol**: XML-based

### Supported Commands
- `<turnOn value="0/1">` - Power on/off
- `<setTemp value="XX">` - Set target temperature
- `<inTemp value="XX">` - Current indoor temperature (read-only)

### Status Message Format
```xml
<msg cmd="status">
  <statusUpdateMsg>
    <turnOn value="1"/>
    <setTemp value="75"/>
    <inTemp value="67"/>
  </statusUpdateMsg>
</msg>
```

## Development

This integration is based on the Home Assistant integration blueprint and follows best practices for custom integrations.

### Requirements
- Python 3.13+
- Home Assistant 2024.1.0+

### Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Troubleshooting

### UDP Packets Not Received (Discovery/Status Updates Fail)

If the integration can send commands but cannot receive responses or status updates, your **firewall may be blocking UDP port 10074**.

#### Check if firewall is blocking

Run tcpdump to see if packets arrive at the network interface:
```bash
sudo tcpdump -i wlan0 -n udp port 10074
```

If you see packets in tcpdump but Home Assistant doesn't receive them, the firewall is likely blocking.

#### Solution for nftables (postmarketOS, Alpine, modern Linux)

```bash
# Add firewall rules
sudo nft add rule inet filter input iifname "wlan*" udp dport 10074 accept comment \"TCL AC UDP\"
sudo nft add rule inet filter input iifname "wlan*" udp dport 10075 accept comment \"TCL AC UDP Response\"

# Verify rules were added
sudo nft list chain inet filter input | grep 10074
```

To make rules persistent across reboots:
```bash
# Create startup script
echo '#!/bin/sh
nft add rule inet filter input iifname "wlan*" udp dport 10074 accept comment "TCL AC UDP"
nft add rule inet filter input iifname "wlan*" udp dport 10075 accept comment "TCL AC UDP"
' | sudo tee /etc/local.d/tcl_ac.start
sudo chmod +x /etc/local.d/tcl_ac.start
```

#### Solution for iptables (older Linux, Debian/Ubuntu)

```bash
sudo iptables -A INPUT -p udp --dport 10074 -j ACCEPT
sudo iptables -A INPUT -p udp --dport 10075 -j ACCEPT

# Save rules (Debian/Ubuntu)
sudo iptables-save > /etc/iptables.rules
```

### Test UDP Reception

You can test if UDP packets are being received properly:

```bash
# In container
docker exec -it homeassistant python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 10074))
s.settimeout(10)
print('Waiting for UDP packet on port 10074...')
try:
    data, addr = s.recvfrom(4096)
    print(f'SUCCESS! Received {len(data)} bytes from {addr}')
except socket.timeout:
    print('FAILED: No packet received (check firewall)')
s.close()
"
```

### Docker Networking

This integration requires Docker to use **host networking** mode:

```yaml
# docker-compose.yml
services:
  homeassistant:
    network_mode: host
```

If using bridge networking, UDP broadcast packets may not be properly forwarded.

### Debug Logging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.tcl_udp_ac: debug
```

## Credits

Built with the [Home Assistant Integration Blueprint](https://github.com/ludeeus/integration_blueprint)
