from setuptools import setup, find_packages

setup(
    name='MilluBridge',
    version='0.1.0',
    author='Your Name',
    author_email='your.email@example.com',
    description='A bridge between OSC messages and MIDI output.',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'PySimpleGUI',
        'python-osc',
        'python-rtmidi',
    ],
    entry_points={
        'console_scripts': [
            'millubridge=main:main',  # Adjust this based on your main function location
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)