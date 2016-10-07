# zcbmark
Python script for automated bench marking of zcash mining

## Usage



`$ python zcbmark.py --cpu-cores 4 --zcash-dir ~/development/zcash`

The following command will attempt to run `zcash-cli zcbenchmark solveequihash` four times,
using 1 core through to 4 cores.

Currenly it will attempt 20 repetitions, however this easily
modified in the source via the `NUMBER_OF_TIMES_TO_RUN` variable.

## Dependencies

- Linux (primarily due to zcash)
- > Python3.4
- Compiled [zcash repo](https://github.com/zcash/zcash)
- [lshw](https://www.ezix.org/project/wiki/HardwareLiSter)

Ensure zcashd is running. `./zcashd --daemon`

Developed using Arch Linux.




