# MilluBridge - Setup Configuration
# Copyright (C) 2025 maigre - Hemisphere Project
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from setuptools import setup, find_packages

setup(
    name='MilluBridge',
    version='1.0.0',
    author='Hemisphere Project',
    author_email='contact@hemisphere-project.com',
    description='OSC to MIDI bridge with ESP-NOW mesh synchronization for media playback.',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'dearpygui',
        'python-osc',
        'python-rtmidi',
    ],
    entry_points={
        'console_scripts': [
            'millubridge=main:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
)