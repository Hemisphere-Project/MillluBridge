# Hasseb DALI Controller

This is a Python application to control a Hasseb DALI Master device using a GUI built with Dear PyGui.

## Prerequisites

- Python 3.8 or higher
- [uv](https://github.com/astral-sh/uv) (recommended for fast package management)
- Hasseb DALI Master USB device connected

## Setup and Run

### Using `uv` (Recommended)

1.  **Create a virtual environment:**
    ```bash
    uv venv
    ```

2.  **Activate the virtual environment:**
    - On Linux/macOS:
        ```bash
        source .venv/bin/activate
        ```
    - On Windows:
        ```bash
        .venv\Scripts\activate
        ```

3.  **Install dependencies:**
    ```bash
    uv pip install -r requirements.txt
    # OR if using pyproject.toml
    uv pip install .
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```

### Using standard `pip`

1.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    ```

2.  **Activate the virtual environment:**
    - On Linux/macOS:
        ```bash
        source venv/bin/activate
        ```
    - On Windows:
        ```bash
        venv\Scripts\activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```

## Troubleshooting

- **Device not found:** Ensure the Hasseb device is plugged in and you have permissions to access USB devices (you might need `udev` rules on Linux).
    - **Linux udev rules:**
      Create a file `/etc/udev/rules.d/99-hasseb.rules` with the content:
      ```
      SUBSYSTEM=="usb", ATTRS{idVendor}=="04cc", ATTRS{idProduct}=="0802", MODE="0666"
      SUBSYSTEM=="hidraw", ATTRS{idVendor}=="04cc", ATTRS{idProduct}=="0802", MODE="0666"
      ```
      Then reload rules: `sudo udevadm control --reload-rules && sudo udevadm trigger`
- **Import errors:** Ensure you have activated the virtual environment before running the script.
