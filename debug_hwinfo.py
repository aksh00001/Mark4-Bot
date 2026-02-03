import mmap
import os

try:
    shmem = mmap.mmap(0, 4096, tagname="HWiNFO_SENS_SM2", access=mmap.ACCESS_READ)
    data = shmem.read(100)
    print(f"Local Mapping Data: {data[:20]}")
    shmem.close()
except:
    print("Local Mapping Failed")

try:
    shmem = mmap.mmap(0, 4096, tagname="Global\\HWiNFO_SENS_SM2", access=mmap.ACCESS_READ)
    data = shmem.read(100)
    print(f"Global Mapping Data: {data[:20]}")
    shmem.close()
except:
    print("Global Mapping Failed")
