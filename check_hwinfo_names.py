import mmap

def check(name):
    try:
        shmem = mmap.mmap(-1, 4096, tagname=name, access=mmap.ACCESS_READ)
        sig = shmem.read(4)
        print(f"Name: {name} | Sig: {sig}")
        shmem.close()
    except Exception as e:
        print(f"Name: {name} | Error: {e}")

check("HWiNFO_SENS_SM2")
check("Global\\HWiNFO_SENS_SM2")
check("Local\\HWiNFO_SENS_SM2")
