# MilluBridge

MilluBridge is a Python application that serves as a bridge between OSC (Open Sound Control) messages and MIDI (Musical Instrument Digital Interface) outputs. It provides a user-friendly GUI built with PySimpleGUI, allowing users to monitor OSC messages and send corresponding MIDI messages to selected output ports.

## Features

- OSC status LED indicating incoming messages.
- Scrollable log monitor for recent OSC messages.
- Dropdown menu for selecting MIDI output ports.
- Start/Stop Bridge functionality.
- Cross-platform compatibility (MacOS, Linux, Windows).

## Prerequisites

On Macos:
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"    # HomeBrew
brew install python
brew install python-tk
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/MilluBridge.git
   cd MilluBridge
   ```

2. Create a virtual environment with uv:
   ```
   uv venv
   source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   uv pip install -r requirements.txt
   ```

## Usage

To run the application, execute the following command:
```
python src/main.py
```

## Build Instructions

To create standalone binaries using PyInstaller, follow these steps:

1. Install PyInstaller:
   ```
   uv pip install pyinstaller
   ```

2. Navigate to the project directory and run:
   ```
   pyinstaller --onefile src/main.py
   ```

3. The executable will be created in the `dist` folder.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for details.