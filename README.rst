=================
STM32 CubeMX to Cmake
=================

.. image:: https://badge.fury.io/py/stm32_c2c.svg
   :target: https://pypi.python.org/pypi/stm32_c2c

Installation
------------
From this repository:

*git clone https://github.com/datashit/stm32_c2c.git*

*cd stm32_c2c*

*pip install .*

Or you can install it from PyPI:

*pip install stm32_c2c*

Usage
-----

Generate your initialization code from STM32CubeMX with the following Code Generation Options:

* Toolchain: SW4STM32
* [X] Generate under root

Then open your project directory and run *stm32_c2c <your_cube_mx_file>.ioc*. If your working directory contains only one CubeMX project file (*.ioc), you can simply run *stm32_c2c* and it will find your project file automatically. This will generate CMakeLists.txt, STM32Toolchain.cmake, openocd_debug.cfg and openocd_flash.cfg files.

To get all the things done right use *-DCMAKE_TOOLCHAIN_FILE=STM32Toolchain.cmake* command line option with CMake.

CMakeLists contains the separate target called *flash*, which compiles your code and then flashes it to the target processor with OpenOCD. By default stlink-v2 is specified as the debugging interface. You can specify any other interface with *--interface* command line option. You can also specify flash memory start address with *--memory_start* option (0x08000000 by default). Telnet and GDB ports can be changed with *--telnet-port* and *--gdb-port* (4444 and 3333 are the defaults).

This scripts also generates a bunch of shell script files:

* openocd_flash.sh - flashes the target MCU;
* openocd_debug.sh - open debugging port for the target MCU;
* gdb.sh - connect to the target MCU after openocd_debug.sh was started.
