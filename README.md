# vMix Controller - Remote Control for vMix

## What is it

A remote control application for vMix over the network. Allows switching sources, managing transitions, and controlling overlays from another computer.

## Features

- Tile-based display of all vMix inputs
- Quick preview to program transitions
- Overlay management (4 layers)
- Fade to Black
- Adjustable interface scaling
- Fullscreen mode (F11)
- Saved connection settings

## Usage

### Connection Setup
1. Start vMix on the main computer
2. Enable API (Settings → API → Enable)
3. Enter IP address and port (default 8088) in the application
4. Click "Connect"

### Basic Operations
- Click tile → set to preview
- "QUICK PLAY" → transition preview to program
- LAYER 1-4 buttons → overlay selected source
- "FTB" → enable/disable fade to black
- Scale slider → adjust interface size

## Technical Details

- Written in Python using PyQt6
- Uses vMix HTTP API
- Supports vMix 23+
- No installation required on the vMix computer

## Troubleshooting

### Can't connect:
- Check if API is enabled in vMix
- Ensure firewall isn't blocking port 8088
- Verify IP address is correct

### Commands not working:
- Make sure source is selected in preview
- Check application console logs

## FAQ
Will you port app to different platforms?

>Code is fully compatabile with Windows/MacOS/Linux, if you need to, you can build app by yourself.
Moblie platform support is a bit complicated and needs a partial code rewrite. App is originally intended to use with Windows tablets. 

## Development

Feel free to enhance and improve the application. If you find a bug or have ideas — create an issue or pull request.
