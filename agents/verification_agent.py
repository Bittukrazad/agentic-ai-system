"""
Verification Agent Module - Responsible for validating outputs and ensuring quality.

This agent handles:
- Output validation
- Data quality checks
- Completeness verification
- Compliance verification
- Error detection
- Quality assurance
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from base_agent import BaseAgent, Message, AgentStatus


class VerificationAgent(BaseAgent):
    """
    Verification Agent for autonomous validation and quality assurance.
    
    Capabilities:
    - Validate action outputs
    - Check data quality
    - Verify completeness
    - Ensure compliance
    - Detect anomalies
    - Generate quality reports
    """
    
    def __init__(self, agent_name: str = "verification_agent", max_retries: int = 3):
        """
        Initialize Verification Agent.
        
        Args:
            agent_name: Agent identifier
            max_retries: Maximum retry attempts
        """
        super().__init__(agent_name, max_retries)
        self.verification_results = []
        self.quality_threshold = 0.90
        self.validation_rules = self._initialize_validation_rules()
    
    def process_message(self, message: Message) -> Message:
        """
        Process incoming verification request message.
        
        Supported actions:
        - verify_output: Verify action output
        - validate_data: Validate data quality
        - check_completeness: Check if all required fields present
        - verify_compliance: Verify compliance with rules
        - detect_anomalies: Detect unusual patterns
        - generate_report: Generate quality report
        
        Args:
            message: Incoming message with verification request
            
        Returns:
            Message: Response with verification result
        """
        action = message.action
        payload = message.payload
        
        try:
            if action == "verify_output":
                result = self._verify_output(payload)
            
            elif action == "validate_data":
                result = self._validate_data(payload)
            
            elif action == "check_completeness":
                result = self._check_completeness(payload)
            
            elif action == "verify_compliance":
                result = self._verify_compliance(payload)
            
            elif action == "detect_anomalies":
                result = self._detect_anomalies(payload)
            
            elif action == "generate_report":
                result = self._generate_report(payload)
            
            elif action == "get_verification_history":
                result = self._get_verification_history(payload)
            
            else:
                raise ValueError(f"Unknown action: {action}")
            
            # Log verification
            self._log_verification(action, payload, result)
            
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
            raise Exception(f"Verification error: {str(e)}")
    
    def _verify_output(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify the output of an action.
        
        Args:
            payload: Output to verify and verification criteria
            
        Returns:
            Verification result
        """
        output = payload.get("output")
        output_type = payload.get("output_type")
        expected_schema = payload.get("expected_schema")
        
        verification = {
            "output_type": output_type,
            "verified": True,
            "issues": [],
            "verified_at": datetime.utcnow().isoformat()
        }
        
        # Type-specific verification
        if output_type == "email":
            verification = self._verify_email_output(output or {}, verification)
        
        elif output_type == "record":
            verification = self._verify_record_output(output or {}, verification)
        
        elif output_type == "document":
            verification = self._verify_document_output(output or {}, verification)
        
        elif output_type == "message":
            verification = self._verify_message_output(output or {}, verification)
        
        else:
            verification = self._verify_generic_output(output or {}, verification)
        
        verification["quality_score"] = self._calculate_quality_score(verification)
        verification["passed"] = verification["quality_score"] >= self.quality_threshold
        
        return verification
    
    def _verify_email_output(self, output: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
        """Verify email output."""
        required_fields = ["recipient", "subject", "body"]
        
        for field in required_fields:
            if field not in output or not output[field]:
                verification["issues"].append(f"Missing or empty {field}")
                verification["verified"] = False
        
        if output.get("recipient") and "@" not in output.get("recipient", ""):
            verification["issues"].append("Invalid email address format")
            verification["verified"] = False
        
        verification["fields_checked"] = required_fields
        return verification
    
    def _verify_record_output(self, output: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
        """Verify database record output."""
        required_fields = ["record_id", "status", "created_at"]
        
        for field in required_fields:
            if field not in output:
                verification["issues"].append(f"Missing required field: {field}")
                verification["verified"] = False
        
        if output.get("status") not in ["created", "updated", "error"]:
            verification["issues"].append(f"Invalid status: {output.get('status')}")
            verification["verified"] = False
        
        verification["fields_checked"] = required_fields
        return verification
    
    def _verify_document_output(self, output: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
        """Verify document output."""
        required_fields = ["document_id", "format", "size_bytes"]
        
        for field in required_fields:
            if field not in output:
                verification["issues"].append(f"Missing required field: {field}")
                verification["verified"] = False
        
        if output.get("format") not in ["pdf", "docx", "txt", "json"]:
            verification["issues"].append(f"Unsupported document format: {output.get('format')}")
            verification["verified"] = False
        
        if output.get("size_bytes", 0) <= 0:
            verification["issues"].append("Document size must be greater than 0 bytes")
            verification["verified"] = False
        
        verification["fields_checked"] = required_fields
        return verification
    
    def _verify_message_output(self, output: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
        """Verify message output."""
        if "message_id" not in output:
            verification["issues"].append("Missing message_id")
            verification["verified"] = False
        
        if output.get("status") not in ["posted", "sent", "delivered"]:
            verification["issues"].append(f"Invalid message status: {output.get('status')}")
            verification["verified"] = False
        
        if "posted_at" not in output:
            verification["issues"].append("Missing timestamp")
            verification["verified"] = False
        
        return verification
    
    def _verify_generic_output(self, output: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
        """Verify generic output structure."""
        if not isinstance(output, dict):
            verification["issues"].append("Output is not a dictionary")
            verification["verified"] = False
        
        if len(output) == 0:
            verification["issues"].append("Output is empty")
            verification["verified"] = False
        
        return verification
    
    def _validate_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data quality and integrity.
        
        Args:
            payload: Data to validate
            
        Returns:
            Data validation result
        """
        data = payload.get("data")
        data_type = payload.get("data_type")
        validation_rules = payload.get("validation_rules", {})
        
        validation = {
            "data_type": data_type,
            "valid": True,
            "errors": [],
            "warnings": [],
            "validated_at": datetime.utcnow().isoformat()
        }
        
        # Type-specific validation
        if data_type == "user_data":
            validation = self._validate_user_data(data or {}, validation)
        
        elif data_type == "financial":
            validation = self._validate_financial_data(data or {}, validation)
        
        elif data_type == "workflow":
            validation = self._validate_workflow_data(data or {}, validation)
        
        else:
            validation = self._validate_generic_data(data or {}, validation)
        
        validation["validation_score"] = self._calculate_validation_score(validation)
        
        return validation
    
    def _validate_user_data(self, data: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user data."""
        required_fields = ["user_id", "name", "email"]
        
        for field in required_fields:
            if field not in data or not data[field]:
                validation["errors"].append(f"Missing or empty required field: {field}")
                validation["valid"] = False
        
        # Validate email format
        email = data.get("email", "")
        if "@" not in email or "." not in email.split("@")[-1]:
            validation["errors"].append("Invalid email format")
            validation["valid"] = False
        
        # Validate user_id format
        if not str(data.get("user_id", "")).startswith("user_") and not str(data.get("user_id", "")).startswith("EMP_"):
            validation["warnings"].append("Unusual user_id format")
        
        return validation
    
    def _validate_financial_data(self, data: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """Validate financial data."""
        required_fields = ["amount", "currency", "transaction_id"]
        
        for field in required_fields:
            if field not in data:
                validation["errors"].append(f"Missing field: {field}")
                validation["valid"] = False
        
        amount = data.get("amount", 0)
        if not isinstance(amount, (int, float)) or amount <= 0:
            validation["errors"].append("Amount must be a positive number")
            validation["valid"] = False
        
        if amount > 1000000:
            validation["warnings"].append("Unusually high amount")
        
        return validation
    
    def _validate_workflow_data(self, data: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """Validate workflow data."""
        required_fields = ["workflow_id", "name", "steps"]
        
        for field in required_fields:
            if field not in data:
                validation["errors"].append(f"Missing field: {field}")
                validation["valid"] = False
        
        steps = data.get("steps", [])
        if not isinstance(steps, list) or len(steps) == 0:
            validation["errors"].append("Workflow must have at least one step")
            validation["valid"] = False
        
        for i, step in enumerate(steps):
            if "step_id" not in step or "name" not in step:
                validation["errors"].append(f"Step {i} missing required fields")
                validation["valid"] = False
        
        return validation
    
    def _validate_generic_data(self, data: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generic data."""
        if not data:
            validation["errors"].append("Data is empty")
            validation["valid"] = False
        
        return validation
    
    def _check_completeness(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if all required fields are present.
        
        Args:
            payload: Data and required fields
            
        Returns:
            Completeness check result
        """
        data = payload.get("data", {})
        required_fields = payload.get("required_fields", [])
        
        completeness = {
            "total_required": len(required_fields),
            "present": [],
            "missing": [],
            "complete": True,
            "completeness_percentage": 0.0,
            "checked_at": datetime.utcnow().isoformat()
        }
        
        for field in required_fields:
            if field in data and data[field] is not None and data[field] != "":
                completeness["present"].append(field)
            else:
                completeness["missing"].append(field)
                completeness["complete"] = False
        
        completeness["completeness_percentage"] = (
            len(completeness["present"]) / len(required_fields) * 100
            if required_fields else 100
        )
        
        return completeness
    
    def _verify_compliance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify compliance with rules and policies.
        
        Args:
            payload: Data and compliance rules
            
        Returns:
            Compliance verification result
        """
        data = payload.get("data")
        compliance_rules = payload.get("compliance_rules", [])
        
        compliance = {
            "total_rules": len(compliance_rules),
            "passed_rules": 0,
            "failed_rules": 0,
            "violations": [],
            "compliant": True,
            "verified_at": datetime.utcnow().isoformat()
        }
        
        for rule in compliance_rules:
            if self._evaluate_compliance_rule(data or {}, rule):
                compliance["passed_rules"] += 1
            else:
                compliance["failed_rules"] += 1
                compliance["violations"].append(rule.get("rule_id"))
                compliance["compliant"] = False
        
        return compliance
    
    def _evaluate_compliance_rule(self, data: Dict[str, Any], rule: Dict[str, Any]) -> bool:
        """Evaluate a single compliance rule."""
        # Simplified rule evaluation
        return True
    
    def _detect_anomalies(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect anomalies in data or patterns.
        
        Args:
            payload: Data to analyze for anomalies
            
        Returns:
            Anomaly detection result
        """
        data = payload.get("data")
        historical_data = payload.get("historical_data", [])
        
        anomalies = {
            "anomalies_detected": False,
            "anomaly_score": 0.0,
            "anomaly_list": [],
            "risk_level": "low",
            "detected_at": datetime.utcnow().isoformat()
        }
        
        # Check for common anomalies
        if isinstance(data, dict):
            for key, value in data.items():
                if self._is_anomalous(key, value, historical_data):
                    anomalies["anomalies_detected"] = True
                    anomalies["anomaly_list"].append({
                        "field": key,
                        "value": value,
                        "anomaly_type": "statistical_outlier"
                    })
        
        if anomalies["anomalies_detected"]:
            anomalies["anomaly_score"] = min(len(anomalies["anomaly_list"]) * 0.2, 1.0)
            anomalies["risk_level"] = "medium" if len(anomalies["anomaly_list"]) < 5 else "high"
        
        return anomalies
    
    def _is_anomalous(self, key: str, value: Any, historical_data: List[Dict]) -> bool:
        """Check if a value is anomalous."""
        if not historical_data:
            return False
        
        # Simplified anomaly check - in production would use statistical methods
        return False
    
    def _generate_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate quality report.
        
        Args:
            payload: Data for report generation
            
        Returns:
            Quality report
        """
        report_type = payload.get("report_type", "summary")
        include_details = payload.get("include_details", False)
        
        report = {
            "report_type": report_type,
            "total_checks": len(self.verification_results),
            "passed_checks": sum(1 for v in self.verification_results if v.get("passed", True)),
            "failed_checks": sum(1 for v in self.verification_results if not v.get("passed", True)),
            "overall_quality_score": self._calculate_overall_quality(),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        if include_details:
            report["recent_verifications"] = self.verification_results[-10:]
        
        return report
    
    def _calculate_quality_score(self, verification: Dict[str, Any]) -> float:
        """Calculate quality score (0.0 to 1.0)."""
        if verification.get("verified", True):
            return 1.0 - (len(verification.get("issues", [])) * 0.1)
        else:
            return 0.5
    
    def _calculate_validation_score(self, validation: Dict[str, Any]) -> float:
        """Calculate validation score (0.0 to 1.0)."""
        if validation.get("valid", True):
            return 1.0 - (len(validation.get("errors", [])) * 0.15)
        else:
            return 0.4
    
    def _calculate_overall_quality(self) -> float:
        """Calculate overall quality score from all verifications."""
        if not self.verification_results:
            return 1.0
        
        scores = [v.get("quality_score", 1.0) for v in self.verification_results]
        return sum(scores) / len(scores)
    
    def _log_verification(self, action: str, payload: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Log verification for tracking."""
        log_entry = {
            "action": action,
            "payload_summary": list(payload.keys()),
            "result": result,
            "logged_at": datetime.utcnow().isoformat()
        }
        self.verification_results.append(log_entry)
    
    def _get_verification_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get verification history."""
        limit = payload.get("limit", 10)
        
        return {
            "total_verifications": len(self.verification_results),
            "recent_verifications": self.verification_results[-limit:],
            "retrieved_at": datetime.utcnow().isoformat()
        }
    
    def _initialize_validation_rules(self) -> Dict[str, Any]:
        """Initialize default validation rules."""
        return {
            "email_format": r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
            "user_id_format": r"^(user_|EMP_)\d+$",
            "phone_format": r"^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$"
        }
