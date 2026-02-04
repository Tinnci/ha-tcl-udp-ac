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

## Credits

Built with the [Home Assistant Integration Blueprint](https://github.com/ludeeus/integration_blueprint)
