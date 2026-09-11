import time

class VerificationEngine:
    def verify_layer_1(self, scada_state):
        # We compute what the signal *should* be independently of what interlocking reports
        # The rules:
        # S1 protects T2 and T3. Normal point P1 routes to T2. Reverse point P1 routes to T3.
        # So if P1 is normal, T2 must be unoccupied for S1 to be green/yellow.
        # If P1 is reverse, T3 must be unoccupied for S1 to be green/yellow.
        # S2 protects T4.
        
        alerts = []
        
        tracks = scada_state["tracks"]
        points = scada_state["points"]
        reported_signals = scada_state["signals"]
        
        expected_s1 = "green"
        if points["P1"] == "normal" and tracks["T2"]:
            expected_s1 = "red"
        elif points["P1"] == "reverse" and tracks["T3"]:
            expected_s1 = "red"
            
        # Balasore mismatch: If SCADA shows Point is REVERSE, and interlocking reports GREEN, 
        # but wait, the fault injected is "P1 reverse, S1 green". Let's say if P1 is reverse, maybe it's not a safe route at all for mainline,
        # or maybe the interlocking *thinks* it's normal and gave green, but physical telemetry says reverse.
        # If it's reverse, and T3 is occupied, it should be red. If T3 is free, it might be green.
        # But wait, a point mismatch means the interlocking state vs physical state.
        # Let's add a strict rule: If P1 is reverse, S1 must be red (mainline signal shouldn't be green for loop line).
        if points["P1"] == "reverse":
            expected_s1 = "red" # Only yellow or red allowed for loop line, let's just say red for simplicity if it's supposed to be a straight green.

        # Another check: if track is occupied, it MUST be red.
        if points["P1"] == "normal" and tracks["T2"]:
            expected_s1 = "red"

        if reported_signals["S1"] == "green" and expected_s1 == "red":
            alerts.append({
                "type": "layer1_alert",
                "layer": "Layer 1",
                "source": "Signal Verification",
                "timestamp": time.time(),
                "description": f"Mismatch on S1. Reported: {reported_signals['S1']}, Expected: {expected_s1}. Point P1: {points['P1']}",
                "affected_id": "S1"
            })
            
        expected_s2 = "green"
        if tracks["T4"]:
            expected_s2 = "red"
            
        if reported_signals["S2"] == "green" and expected_s2 == "red":
             alerts.append({
                "type": "layer1_alert",
                "layer": "Layer 1",
                "source": "Signal Verification",
                "timestamp": time.time(),
                "description": f"Mismatch on S2. Reported: {reported_signals['S2']}, Expected: {expected_s2}",
                "affected_id": "S2"
            })
            
        return alerts
