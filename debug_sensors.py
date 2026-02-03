import mmap
import struct

def main():
    try:
        shmem = mmap.mmap(-1, 0x200000, tagname="Global\\HWiNFO_SENS_SM2", access=mmap.ACCESS_READ)
        if shmem.read(4) != b'HWiS':
            print("No Signature")
            return

        shmem.seek(0)
        hdr = struct.unpack('<4sIIIIII', shmem.read(28))
        off_sensors, sz_sensor = hdr[3], hdr[4]
        off_read, sz_read = hdr[5], hdr[6]
        
        print(f"Sensors Offset: {off_sensors}, Size: {sz_sensor}")
        print(f"Readings Offset: {off_read}, Size: {sz_read}")

        # List first 30 Sensor Names (Motherboard, CPU, GPU, etc)
        sensors = []
        for i in range(30):
            shmem.seek(off_sensors + (i * sz_sensor))
            chunk = shmem.read(sz_sensor)
            if len(chunk) < sz_sensor: break
            # szSensorNameOrigin offset 4, length 128
            name = chunk[4:4+128].split(b'\x00')[0].decode('utf-8', 'ignore').strip()
            if name: sensors.append(name)
        
        print("\nTOP SENSORS:")
        for s in sensors: print(f" - {s}")

        # List first 100 Readings
        print("\nTOP READINGS:")
        for i in range(100):
            shmem.seek(off_read + (i * sz_read))
            chunk = shmem.read(sz_read)
            if len(chunk) < sz_read: break
            
            t_type = struct.unpack('<I', chunk[0:4])[0]
            if t_type == 0: break
            
            label = chunk[12:12+128].split(b'\x00')[0].decode('utf-8', 'ignore').strip()
            unit = chunk[140:140+16].split(b'\x00')[0].decode('utf-8', 'ignore').strip()
            val = struct.unpack('<d', chunk[156:164])[0]
            
            if label:
                print(f" [{i}] {label}: {val:.2f} {unit}")

        shmem.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
