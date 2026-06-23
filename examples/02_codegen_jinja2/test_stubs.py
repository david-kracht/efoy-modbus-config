from __future__ import annotations
import minimalmodbus
import efoy_registers

class DummyInstrument:
    """A minimal mock for minimalmodbus.Instrument to test generated stubs."""
    def read_register(self, registeraddress, number_of_decimals=0, functioncode=3, signed=False):
        print(f"  [Mock] read_register(addr={registeraddress}, fc={functioncode}, signed={signed})")
        # Return a deterministic dummy value based on the address
        return registeraddress + 1000

def main():
    print("--- Testing Generated MinimalModbus Stubs ---")
    
    # We pass the dummy instrument to the generated functions
    # since Python's type hints are ignored at runtime.
    instrument = DummyInstrument()
    
    print("\nTesting read_SystemType():")
    val = efoy_registers.read_SystemType(instrument)
    print(f"-> Returned: {val}")

    print("\nTesting read_AssemblyDate():")
    val = efoy_registers.read_AssemblyDate(instrument)
    print(f"-> Returned: {val}")
    
    print("\nTesting read_BatBocStatus():")
    # This register has scale_factor applied in the generated code
    val = efoy_registers.read_BatBocStatus(instrument)
    print(f"-> Returned: {val}")

if __name__ == "__main__":
    main()
