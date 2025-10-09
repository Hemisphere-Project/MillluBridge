# Build Instructions for MilluBridge

## Prerequisites
Before building the MilluBridge application, ensure you have the following installed on your system:

- Python 3.6 or higher
- Pip (Python package installer)
- PyInstaller

On Macos:
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python
brew install python-tk
```

## Installation of Dependencies
First, you need to install the required dependencies. You can do this by running the following command in your terminal:

```
pip install -r requirements.txt
```

This will install the necessary packages, including PySimpleGUI, python-osc, and python-rtmidi.

## Building the Application
To create standalone binaries for the MilluBridge application using PyInstaller, follow these steps:

1. Open your terminal or command prompt.
2. Navigate to the root directory of the MilluBridge project:

   ```
   cd path/to/MilluBridge
   ```

3. Run the following command to create the executable:

   ```
   pyinstaller --onefile src/main.py
   ```

   This command tells PyInstaller to package the application into a single executable file.

4. After the build process is complete, you will find the executable in the `dist` directory created by PyInstaller.

## Running the Application
You can now run the MilluBridge application by executing the generated binary from the `dist` folder. 

## Additional Notes
- If you encounter any issues during the build process, refer to the PyInstaller documentation for troubleshooting tips.
- You may want to customize the PyInstaller spec file for advanced configurations, such as adding icons or including additional data files.