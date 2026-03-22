"""
Monitoring Agent Module - Responsible for workflow health monitoring and issue detection.

This agent handles:
- SLA tracking and alerts
- Performance monitoring
- Bottleneck detection
- Process drift detection
- Anomaly alerts
- Health status reporting
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from base_agent import BaseAgent, Message, AgentStatus


class MonitoringAgent(BaseAgent):
    """
    Monitoring Agent for autonomous workflow health monitoring.
    
    Capabilities:
    - Track SLA compliance
    - Monitor performance metrics
    - Detect bottlenecks
    - Detect process drift
    - Generate alerts
    - Create health reports
    """
    
    def __init__(self, agent_name: str = "monitoring_agent", max_retries: int = 3):
        """
        Initialize Monitoring Agent.
        
        Args:
            agent_name: Agent identifier
            max_retries: Maximum retry attempts
        """
        super().__init__(agent_name, max_retries)
        self.metrics = {}
        self.alerts = []
        self.health_status = {}
        self.sla_targets = {}
        self.performance_thresholds = self._initialize_thresholds()
    
    def process_message(self, message: Message) -> Message:
        """
        Process incoming monitoring request message.
        
        Supported actions:
        - track_sla: Track SLA compliance
        - monitor_performance: Monitor workflow performance
        - detect_bottleneck: Detect performance bottlenecks
        - detect_drift: Detect process drift
        - check_health: Check workflow health
        - get_alerts: Get active alerts
        - get_metrics: Get collected metrics
        
        Args:
            message: Incoming message with monitoring request
            
        Returns:
            Message: Response with monitoring result
        """
        action = message.action
        payload = message.payload
        
        try:
            if action == "track_sla":
                result = self._track_sla(payload)
            
            elif action == "monitor_performance":
                result = self._monitor_performance(payload)
            
            elif action == "detect_bottleneck":
                result = self._detect_bottleneck(payload)
            
            elif action == "detect_drift":
                result = self._detect_drift(payload)
            
            elif action == "check_health":
                result = self._check_health(payload)
            
            elif action == "get_alerts":
                result = self._get_alerts(payload)
            
            elif action == "get_metrics":
                result = self._get_metrics(payload)
            
            elif action == "update_threshold":
                result = self._update_threshold(payload)
            
            else:
                raise ValueError(f"Unknown action: {action}")
            
            response = Message(
                workflow_id=message.workflow_id,
                step_id=message.step_id,
                from_agent=self.agent_name,
                to_agent=message.from_agent,
                action=f"{action}_response",
                payload=result,
                status=AgentStatus.SUCCESS.value
            )
            
            return response
        
        except Exception as e:
            raise Exception(f"Monitoring error: {str(e)}")
    
    def _track_sla(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Track SLA compliance for workflow.
        
        Args:
            payload: Workflow details and SLA targets
            
        Returns:
            SLA tracking result
        """
        workflow_id = payload.get("workflow_id")
        steps = payload.get("steps", [])
        sla_target = payload.get("sla_target_hours", 24)
        
        # Calculate total execution time
        start_time = None
        end_time = None
        total_duration = 0
        step_times = []
        
        for step in steps:
            if step.get("start_time"):
                step_start = datetime.fromisoformat(step["start_time"])
                if not start_time:
                    start_time = step_start
                
                if step.get("end_time"):
                    step_end = datetime.fromisoformat(step["end_time"])
                    end_time = step_end
                    duration = (step_end - step_start).total_seconds() / 3600
                    step_times.append({
                        "step_id": step.get("step_id"),
                        "duration_hours": round(duration, 2),
                        "status": "on_track" if duration < (sla_target / len(steps)) else "at_risk"
                    })
        
        if start_time and end_time:
            total_duration = (end_time - start_time).total_seconds() / 3600
        
        sla_status = "on_track" if total_duration <= sla_target else "at_risk"
        
        result = {
            "workflow_id": workflow_id,
            "sla_target_hours": sla_target,
            "current_duration_hours": round(total_duration, 2),
            "sla_status": sla_status,
            "time_remaining_hours": round(max(0, sla_target - total_duration), 2),
            "compliance_percentage": round(min(100, (sla_target / total_duration * 100))) if total_duration > 0 else 100,
            "step_times": step_times,
            "checked_at": datetime.utcnow().isoformat()
        }
        
        # Store metric
        self.metrics[f"sla_{workflow_id}"] = result
        
        # Create alert if at risk
        if sla_status == "at_risk":
            self._create_alert("sla_breach_risk", workflow_id or "", result)
        
        return result
    
    def _monitor_performance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Monitor workflow performance metrics.
        
        Args:
            payload: Workflow metrics data
            
        Returns:
            Performance monitoring result
        """
        workflow_id = payload.get("workflow_id")
        metrics_data = payload.get("metrics", {})
        
        performance = {
            "workflow_id": workflow_id,
            "metrics": {},
            "performance_score": 0.0,
            "status": "healthy",
            "monitored_at": datetime.utcnow().isoformat()
        }
        
        # Calculate key metrics
        metrics_scores = []
        
        if "avg_response_time" in metrics_data:
            threshold = self.performance_thresholds.get("response_time_threshold", 5000)
            response_time = metrics_data["avg_response_time"]
            score = max(0, (1 - (response_time / threshold))) * 100
            performance["metrics"]["response_time"] = {
                "value_ms": response_time,
                "threshold_ms": threshold,
                "score": round(score, 2)
            }
            metrics_scores.append(score)
        
        if "error_rate" in metrics_data:
            error_rate = metrics_data["error_rate"]
            score = (1 - error_rate) * 100
            performance["metrics"]["error_rate"] = {
                "percentage": round(error_rate * 100, 2),
                "threshold_percentage": 5.0,
                "score": round(score, 2)
            }
            metrics_scores.append(score)
        
        if "throughput" in metrics_data:
            throughput = metrics_data["throughput"]
            threshold = self.performance_thresholds.get("min_throughput", 10)
            score = min((throughput / threshold) * 100, 100)
            performance["metrics"]["throughput"] = {
                "value": throughput,
                "threshold": threshold,
                "score": round(score, 2)
            }
            metrics_scores.append(score)
        
        # Calculate overall score
        if metrics_scores:
            performance["performance_score"] = round(sum(metrics_scores) / len(metrics_scores), 2)
        
        # Determine status
        if performance["performance_score"] < 50:
            performance["status"] = "degraded"
            self._create_alert("performance_degradation", workflow_id or "", performance)
        elif performance["performance_score"] < 75:
            performance["status"] = "warning"
        
        self.metrics[f"performance_{workflow_id}"] = performance
        return performance
    
    def _detect_bottleneck(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect performance bottlenecks in workflow.
        
        Args:
            payload: Workflow step timing data
            
        Returns:
            Bottleneck detection result
        """
        workflow_id = payload.get("workflow_id")
        steps = payload.get("steps", [])
        
        bottlenecks = {
            "workflow_id": workflow_id,
            "bottlenecks_detected": False,
            "bottleneck_list": [],
            "detected_at": datetime.utcnow().isoformat()
        }
        
        if not steps:
            return bottlenecks
        
        # Calculate step durations
        step_durations = []
        for step in steps:
            if step.get("start_time") and step.get("end_time"):
                start = datetime.fromisoformat(step["start_time"])
                end = datetime.fromisoformat(step["end_time"])
                duration = (end - start).total_seconds()
                step_durations.append({
                    "step_id": step.get("step_id"),
                    "duration_seconds": duration
                })
        
        if step_durations:
            # Find steps that take significantly longer
            avg_duration = sum(s["duration_seconds"] for s in step_durations) / len(step_durations)
            threshold_multiplier = 1.5
            
            for step in step_durations:
                if step["duration_seconds"] > avg_duration * threshold_multiplier:
                    bottlenecks["bottlenecks_detected"] = True
                    bottlenecks["bottleneck_list"].append({
                        "step_id": step["step_id"],
                        "duration_seconds": round(step["duration_seconds"], 2),
                        "avg_duration_seconds": round(avg_duration, 2),
                        "deviation_multiplier": round(step["duration_seconds"] / avg_duration, 2)
                    })
        
        if bottlenecks["bottlenecks_detected"]:
            self._create_alert("bottleneck_detected", workflow_id or "", bottlenecks)
        
        return bottlenecks
    
    def _detect_drift(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect process drift from expected pattern.
        
        Args:
            payload: Current process data and expected pattern
            
        Returns:
            Drift detection result
        """
        workflow_id = payload.get("workflow_id")
        current_pattern = payload.get("current_pattern", {})
        expected_pattern = payload.get("expected_pattern", {})
        
        drift = {
            "workflow_id": workflow_id,
            "drift_detected": False,
            "drift_score": 0.0,
            "drift_details": [],
            "detected_at": datetime.utcnow().isoformat()
        }
        
        if not expected_pattern:
            return drift
        
        # Compare patterns
        drift_items = 0
        total_items = 0
        
        for key, expected_value in expected_pattern.items():
            total_items += 1
            current_value = current_pattern.get(key)
            
            if current_value != expected_value:
                drift_items += 1
                drift["drift_details"].append({
                    "aspect": key,
                    "expected": expected_value,
                    "current": current_value
                })
        
        if total_items > 0:
            drift["drift_score"] = round((drift_items / total_items) * 100, 2)
        
        drift["drift_detected"] = drift["drift_score"] > 20
        
        if drift["drift_detected"]:
            self._create_alert("process_drift_detected", workflow_id or "", drift)
        
        return drift
    
    def _check_health(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check overall workflow health.
        
        Args:
            payload: Workflow metrics
            
        Returns:
            Health check result
        """
        workflow_id = payload.get("workflow_id")
        workflow_status = payload.get("workflow_status", "running")
        last_update = payload.get("last_update")
        
        health = {
            "workflow_id": workflow_id,
            "overall_health": "healthy",
            "status": workflow_status,
            "components": {},
            "checked_at": datetime.utcnow().isoformat()
        }
        
        # Check if workflow is responsive
        if last_update:
            last_update_time = datetime.fromisoformat(last_update)
            time_since_update = (datetime.utcnow() - last_update_time).total_seconds()
            
            health["components"]["responsiveness"] = {
                "last_update": last_update,
                "seconds_since_update": round(time_since_update, 2),
                "status": "responsive" if time_since_update < 300 else "slow"
            }
        
        # Check workflow status
        if workflow_status == "error":
            health["overall_health"] = "unhealthy"
        elif workflow_status == "slow":
            health["overall_health"] = "degraded"
        
        self.health_status[workflow_id] = health
        return health
    
    def _get_alerts(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get active alerts.
        
        Args:
            payload: Alert filter options
            
        Returns:
            List of active alerts
        """
        severity = payload.get("severity")
        workflow_id = payload.get("workflow_id")
        limit = payload.get("limit", 20)
        
        filtered_alerts = self.alerts
        
        if workflow_id:
            filtered_alerts = [a for a in filtered_alerts if a["workflow_id"] == workflow_id]
        
        if severity:
            filtered_alerts = [a for a in filtered_alerts if a["severity"] == severity]
        
        return {
            "total_alerts": len(self.alerts),
            "filtered_alerts_count": len(filtered_alerts),
            "alerts": filtered_alerts[-limit:],
            "retrieved_at": datetime.utcnow().isoformat()
        }
    
    def _get_metrics(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get collected metrics.
        
        Args:
            payload: Metric filter options
            
        Returns:
            Collected metrics
        """
        metric_type = payload.get("metric_type")
        workflow_id = payload.get("workflow_id")
        
        filtered_metrics = {}
        
        for key, value in self.metrics.items():
            if workflow_id and workflow_id not in key:
                continue
            if metric_type and metric_type not in key:
                continue
            filtered_metrics[key] = value
        
        return {
            "total_metrics": len(self.metrics),
            "filtered_metrics": filtered_metrics,
            "retrieved_at": datetime.utcnow().isoformat()
        }
    
    def _update_threshold(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update performance thresholds.
        
        Args:
            payload: New threshold values
            
        Returns:
            Update confirmation
        """
        threshold_name = payload.get("threshold_name")
        threshold_value = payload.get("threshold_value")
        
        self.performance_thresholds[threshold_name or "default"] = threshold_value
        
        return {
            "threshold_name": threshold_name,
            "new_value": threshold_value,
            "status": "updated",
            "updated_at": datetime.utcnow().isoformat()
        }
    
    def _create_alert(self, alert_type: str, workflow_id: str, context: Dict[str, Any]) -> None:
        """
        Create alert for monitoring issue.
        
        Args:
            alert_type: Type of alert
            workflow_id: Workflow ID
            context: Additional context
        """
        severity = self._determine_severity(alert_type)
        
        alert = {
            "alert_id": f"alert_{datetime.utcnow().timestamp()}",
            "alert_type": alert_type,
            "workflow_id": workflow_id,
            "severity": severity,
            "context": context,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        self.alerts.append(alert)
    
    def _determine_severity(self, alert_type: str) -> str:
        """Determine alert severity level."""
        severity_map = {
            "sla_breach_risk": "high",
            "performance_degradation": "medium",
            "bottleneck_detected": "medium",
            "process_drift_detected": "low",
            "health_check_failed": "high"
        }
        return severity_map.get(alert_type, "medium")
    
    def _initialize_thresholds(self) -> Dict[str, Any]:
        """Initialize performance thresholds."""
        return {
            "response_time_threshold": 5000,  # milliseconds
            "error_rate_threshold": 0.05,  # 5%
            "min_throughput": 10,  # requests/second
            "max_queue_depth": 100,
            "cpu_threshold": 80,  # percentage
            "memory_threshold": 85  # percentage
        }
