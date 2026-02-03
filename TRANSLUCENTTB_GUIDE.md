# TranslucentTB Integration - J.A.R.V.I.S. Bot

## Overview
J.A.R.V.I.S. now has full control over your Windows taskbar appearance via TranslucentTB.

## Command Usage

### Basic Command
```
/taskbar <mode> [color] [blur_radius]
```

### Available Modes
1. **clear** - Fully transparent taskbar
2. **acrylic** - Frosted glass effect (Windows 11 style)
3. **blur** - Blurred background
4. **opaque** - Solid color
5. **normal** - Windows default appearance

### Parameters
- **mode** (required): One of the modes listed above
- **color** (optional): Hex color code (e.g., `#1E1E1E80`)
  - Format: `#RRGGBBAA` where AA is alpha/transparency
  - Default: `#00000000` (fully transparent black)
- **blur_radius** (optional): Blur intensity (0.0 - 20.0)
  - Default: 9.0

## Examples

### Simple Mode Switch
```
/taskbar clear
```
Makes the taskbar fully transparent.

### Custom Acrylic Effect
```
/taskbar acrylic #1E1E1E80 12
```
Creates a dark frosted glass effect with medium blur.

### Blurred Dark Taskbar
```
/taskbar blur #00000040 15
```
Creates a subtle dark blur with high intensity.

### Solid Color Taskbar
```
/taskbar opaque #2D2D2DFF
```
Creates a solid dark gray taskbar.

### Reset to Windows Default
```
/taskbar normal
```
Restores the standard Windows taskbar appearance.

## How It Works

1. **Configuration Update**: The bot modifies TranslucentTB's JSON configuration file
2. **App Restart**: TranslucentTB is automatically restarted to apply changes
3. **Instant Feedback**: You receive confirmation once the change is applied

## Technical Details

- **Config Path**: `C:\Users\akshu\AppData\Local\Packages\28017CharlesMilette.TranslucentTB_v826wp6bftszj\RoamingState\settings.json`
- **Restart Method**: Process kill + UWP app launch via shell protocol
- **Apply Time**: ~1-2 seconds

## Color Code Reference

### Common Colors
- Transparent Black: `#00000000`
- Semi-transparent Black: `#00000080`
- Dark Gray: `#2D2D2DFF`
- Light Gray: `#D3D3D3FF`
- Semi-transparent White: `#FFFFFF40`

### Alpha Values (Transparency)
- `00` = Fully transparent
- `40` = 25% opacity
- `80` = 50% opacity
- `C0` = 75% opacity
- `FF` = Fully opaque

## Notes
- Changes apply immediately to the desktop taskbar
- Dynamic modes (maximized window, start menu) are preserved
- The bot automatically handles TranslucentTB restart
- Works with TranslucentTB 2025.1.0.0 (Microsoft Store version)
