import time
import asyncio
from typing import Dict, Any
import escalation
from escalation import escalate_alert


class AlertManager:
    def __init__(self):
        self.alerts: Dict[str, Any] = {}
        self.escalation_timeout = 10  # seconds for demo
        self.alert_counter = 0

    def process_new_alerts(self, new_alerts):
        active_ids = []
        for a in new_alerts:
            # Create a unique ID for the alert condition (e.g. layer + affected_id)
            condition_id = f"{a['layer']}_{a['affected_id']}"
            active_ids.append(condition_id)

            if condition_id not in self.alerts or self.alerts[condition_id]["status"] == "Resolved":
                self.alert_counter += 1
                alert_id = f"ALT-{self.alert_counter:04d}"
                self.alerts[condition_id] = {
                    "id": alert_id,
                    "condition_id": condition_id,
                    "layer": a["layer"],
                    "description": a["description"],
                    "status": "Detected",  # Detected -> Displayed -> Acknowledged/Escalated -> Resolved
                    "detected_at": time.time(),
                    "acknowledged_by": None,
                    "acknowledged_at": None,
                    "escalated_at": None,
                    "escalated_to": None,
                }

        # Resolve alerts that are no longer active
        for cid, alert in self.alerts.items():
            if alert["status"] not in ["Resolved"]:
                if cid not in active_ids:
                    alert["status"] = "Resolved"
                    alert["resolved_at"] = time.time()

    def get_all_alerts(self):
        return list(self.alerts.values())

    def acknowledge_alert(self, alert_id, user="Station Master"):
        for cid, alert in self.alerts.items():
            if alert["id"] == alert_id:
                if alert["status"] in ["Detected", "Displayed"]:
                    alert["status"] = "Acknowledged"
                    alert["acknowledged_by"] = user
                    alert["acknowledged_at"] = time.time()
                    return True
        return False

    async def run_escalation_checker(self):
        while True:
            try:
                await asyncio.sleep(2)
                now = time.time()
                for cid, alert in list(self.alerts.items()):
                    if alert["status"] in ["Detected", "Displayed"]:
                        if now - alert["detected_at"] > self.escalation_timeout:
                            alert["status"] = "Escalated"
                            alert["escalated_at"] = now
                            alert["escalated_to"] = escalation.ESCALATION_TARGET
                            # Trigger Twilio and store message body
                            try:
                                msg = escalate_alert(alert)
                                alert["escalation_message"] = msg
                            except Exception as e:
                                print(f"Escalation call failed: {e}")
            except Exception as e:
                print(f"Escalation checker error: {e}")
                await asyncio.sleep(5)


alert_manager = AlertManager()
