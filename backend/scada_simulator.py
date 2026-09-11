import asyncio
import time
import random

class SCADASimulator:
    def __init__(self):
        # 4 Track sections: T1, T2, T3, T4 (True if occupied)
        self.tracks = {"T1": False, "T2": False, "T3": False, "T4": False}
        
        # 2 Point machines: P1, P2 ("normal" or "reverse")
        self.points = {"P1": "normal", "P2": "normal"}
        
        # 2 Signals: S1, S2 ("red", "yellow", "green")
        self.signals = {"S1": "green", "S2": "green"}
        
        self.fault_active = False

    def get_state(self):
        return {
            "type": "scada_state",
            "timestamp": time.time(),
            "tracks": self.tracks,
            "points": self.points,
            "signals": self.signals,
            "fault_active": self.fault_active
        }

    def inject_fault(self):
        self.fault_active = True
        print("SCADA Simulator: Fault injected!")
        # A Balasore-style fault: Interlocking thinks point is normal and signal is green,
        # but in physical reality the point is reverse, or the SCADA telemetry shows a mismatch.
        # We will make the SCADA telemetry show the physical mismatch (point is reverse, signal is green).
        self.points["P1"] = "reverse"
        self.signals["S1"] = "green" 
        # But this is a mismatch based on interlocking rules.

    def resolve_fault(self):
        self.fault_active = False
        self.points["P1"] = "normal"
        self.signals["S1"] = "green"

    async def run(self):
        # Background task that just keeps state updated or adds some random noise
        # For simplicity, we'll just keep it static unless a fault is injected, 
        # or we could make trains move. Let's make one train move around.
        train_pos = 0
        while True:
            await asyncio.sleep(1.5)
            
            if not self.fault_active:
                # Simple cycle for occupancy
                train_pos = (train_pos + 1) % 5
                
                self.tracks = {
                    "T1": train_pos == 1,
                    "T2": train_pos == 2,
                    "T3": train_pos == 3,
                    "T4": train_pos == 4,
                }
                
                # Update signals according to basic interlocking rules based on tracks
                # S1 protects T2, T3. S2 protects T4.
                if self.tracks["T2"]:
                    self.signals["S1"] = "red"
                elif self.tracks["T3"]:
                    self.signals["S1"] = "yellow"
                else:
                    self.signals["S1"] = "green"
                    
                if self.tracks["T4"]:
                    self.signals["S2"] = "red"
                else:
                    self.signals["S2"] = "green"
            else:
                # Fault is active, so we just hold the mismatch state.
                self.tracks["T2"] = True # let's say a train is on T2
                self.signals["S1"] = "green" # Interlocking improperly showing green despite occupied/mismatched point
                self.points["P1"] = "reverse"
                

scada_sim = SCADASimulator()
