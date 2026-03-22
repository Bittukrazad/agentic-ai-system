"""
Decision Agent Module - Responsible for autonomous decision-making and reasoning.

This agent handles:
- LLM-based reasoning
- Business rule evaluation
- Decision extraction
- Complex workflow logic
- Risk assessment
- Task prioritization
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from base_agent import BaseAgent, Message, AgentStatus


class DecisionType(Enum):
    """Types of decisions made by the agent."""
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    DELEGATE = "delegate"
    DEFER = "defer"
    AUTO_CORRECT = "auto_correct"


class DecisionAgent(BaseAgent):
    """
    Decision Agent for autonomous reasoning and decision-making.
    
    Capabilities:
    - Evaluate business rules
    - Make autonomous decisions
    - Extract structured decisions from text/data
    - Risk assessment
    - Conflict resolution
    - Task prioritization
    """
    
    def __init__(self, agent_name: str = "decision_agent", max_retries: int = 3):
        """
        Initialize Decision Agent.
        
        Args:
            agent_name: Agent identifier
            max_retries: Maximum retry attempts
        """
        super().__init__(agent_name, max_retries)
        self.decision_history = []
        self.decision_confidence_threshold = 0.75
        self.escalation_triggers = [
            "high_risk",
            "unusual_pattern",
            "policy_violation",
            "budget_overrun"
        ]
    
    def process_message(self, message: Message) -> Message:
        """
        Process incoming decision request message.
        
        Supported actions:
        - evaluate_request: Evaluate and approve/reject a request
        - extract_decisions: Extract decisions from text/data
        - assess_risk: Assess risk level of action
        - prioritize_tasks: Prioritize workflow tasks
        - resolve_conflict: Resolve conflicting decisions
        - evaluate_rules: Evaluate business rules
        
        Args:
            message: Incoming message with decision request
            
        Returns:
            Message: Response with decision and reasoning
        """
        action = message.action
        payload = message.payload
        
        try:
            if action == "evaluate_request":
                decision = self._evaluate_request(payload)
            
            elif action == "extract_decisions":
                decision = self._extract_decisions(payload)
            
            elif action == "assess_risk":
                decision = self._assess_risk(payload)
            
            elif action == "prioritize_tasks":
                decision = self._prioritize_tasks(payload)
            
            elif action == "resolve_conflict":
                decision = self._resolve_conflict(payload)
            
            elif action == "evaluate_rules":
                decision = self._evaluate_rules(payload)
            
            elif action == "get_decision_history":
                decision = self._get_decision_history(payload)
            
            else:
                raise ValueError(f"Unknown action: {action}")
            
            # Log decision for audit trail
            self._log_decision(decision, message)
            
            response = Message(
                workflow_id=message.workflow_id,
                step_id=message.step_id,
                from_agent=self.agent_name,
                to_agent=message.from_agent,
                action=f"{action}_response",
                payload=decision,
                status=AgentStatus.SUCCESS.value
            )
            
            return response
        
        except Exception as e:
            raise Exception(f"Decision processing error: {str(e)}")
    
    def _evaluate_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a request and make approval decision.
        
        Args:
            payload: Request details for evaluation
            
        Returns:
            Decision dictionary with approval status and reasoning
        """
        request_type = payload.get("request_type")
        request_data = payload.get("data", {})
        rules = payload.get("rules", {})
        
        decision = {
            "request_id": request_data.get("request_id"),
            "request_type": request_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Evaluate based on type
        if request_type == "procurement":
            decision = self._evaluate_procurement(request_data, rules, decision)
        
        elif request_type == "contract":
            decision = self._evaluate_contract(request_data, rules, decision)
        
        elif request_type == "employee_onboarding":
            decision = self._evaluate_onboarding(request_data, rules, decision)
        
        elif request_type == "task_assignment":
            decision = self._evaluate_task_assignment(request_data, rules, decision)
        
        else:
            decision["decision"] = DecisionType.DEFER.value
            decision["reasoning"] = f"Unknown request type: {request_type}"
            decision["confidence"] = 0.0
        
        return decision
    
    def _evaluate_procurement(self, data: Dict[str, Any], rules: Dict[str, Any], 
                            decision: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate procurement request."""
        amount = data.get("amount", 0)
        vendor = data.get("vendor")
        priority = data.get("priority", "normal")
        
        approval_threshold = rules.get("approval_threshold", 10000)
        
        if amount <= approval_threshold:
            decision["decision"] = DecisionType.APPROVE.value
            decision["reasoning"] = f"Amount ${amount} is within approval threshold"
            decision["confidence"] = 0.95
        else:
            decision["decision"] = DecisionType.ESCALATE.value
            decision["reasoning"] = f"Amount ${amount} exceeds approval threshold of ${approval_threshold}"
            decision["confidence"] = 0.90
            decision["escalate_to"] = "finance_manager"
        
        return decision
    
    def _evaluate_contract(self, data: Dict[str, Any], rules: Dict[str, Any],
                          decision: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate contract request."""
        contract_value = data.get("value", 0)
        contract_term = data.get("term_months", 12)
        vendor_rating = data.get("vendor_rating", 3)
        
        if vendor_rating < 2:
            decision["decision"] = DecisionType.REJECT.value
            decision["reasoning"] = "Vendor has insufficient rating"
            decision["confidence"] = 0.95
        elif contract_value > 500000:
            decision["decision"] = DecisionType.ESCALATE.value
            decision["reasoning"] = "High-value contract requires executive approval"
            decision["confidence"] = 0.90
            decision["escalate_to"] = "executive_team"
        else:
            decision["decision"] = DecisionType.APPROVE.value
            decision["reasoning"] = "Contract meets all approval criteria"
            decision["confidence"] = 0.92
        
        return decision
    
    def _evaluate_onboarding(self, data: Dict[str, Any], rules: Dict[str, Any],
                            decision: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate employee onboarding request."""
        employee_id = data.get("employee_id")
        department = data.get("department")
        documents_submitted = data.get("documents_submitted", [])
        required_docs = rules.get("required_documents", [])
        
        missing_docs = [doc for doc in required_docs if doc not in documents_submitted]
        
        if missing_docs:
            decision["decision"] = DecisionType.DEFER.value
            decision["reasoning"] = f"Missing documents: {', '.join(missing_docs)}"
            decision["confidence"] = 0.88
            decision["required_actions"] = [f"Obtain {doc}" for doc in missing_docs]
        else:
            decision["decision"] = DecisionType.APPROVE.value
            decision["reasoning"] = "All onboarding requirements met"
            decision["confidence"] = 0.96
        
        return decision
    
    def _evaluate_task_assignment(self, data: Dict[str, Any], rules: Dict[str, Any],
                                 decision: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate task assignment."""
        task_type = data.get("task_type")
        skill_required = data.get("skill_required")
        available_team = data.get("available_team", [])
        
        # Find best person for task
        best_person = None
        best_match = 0
        
        for person in available_team:
            skills = person.get("skills", [])
            workload = person.get("current_workload", 0)
            availability = person.get("availability", 0)
            
            if skill_required in skills:
                match_score = availability * (1 - (workload / 100))
                if match_score > best_match:
                    best_match = match_score
                    best_person = person.get("person_id")
        
        if best_person:
            decision["decision"] = DecisionType.DELEGATE.value
            decision["assigned_to"] = best_person
            decision["reasoning"] = f"Optimal match based on skills and availability"
            decision["confidence"] = best_match
        else:
            decision["decision"] = DecisionType.ESCALATE.value
            decision["reasoning"] = "No suitable team member available"
            decision["confidence"] = 0.70
            decision["escalate_to"] = "manager"
        
        return decision
    
    def _extract_decisions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured decisions from text or data.
        
        Args:
            payload: Source text or data
            
        Returns:
            Extracted decisions
        """
        source = payload.get("source")
        decisions_text = payload.get("text", "")
        
        # Simulated decision extraction (in production would use NLP/LLM)
        extracted = {
            "source": source,
            "decisions": [
                {
                    "decision_id": "dec_001",
                    "action": "Create new account",
                    "owner": "John Doe",
                    "due_date": "2026-03-25",
                    "priority": "high"
                },
                {
                    "decision_id": "dec_002",
                    "action": "Schedule onboarding session",
                    "owner": "HR Team",
                    "due_date": "2026-03-24",
                    "priority": "high"
                }
            ],
            "extracted_at": datetime.utcnow().isoformat()
        }
        
        return extracted
    
    def _assess_risk(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess risk level of a proposed action.
        
        Args:
            payload: Action details for risk assessment
            
        Returns:
            Risk assessment with level and mitigations
        """
        action = payload.get("action")
        action_type = payload.get("action_type")
        context = payload.get("context", {})
        
        risk_factors = []
        risk_score = 0.0
        
        # Analyze risk factors
        if action_type == "financial" and context.get("amount", 0) > 50000:
            risk_factors.append("High financial value")
            risk_score += 0.3
        
        if context.get("involves_external_party"):
            risk_factors.append("External party involvement")
            risk_score += 0.2
        
        if context.get("precedent_exists") is False:
            risk_factors.append("No precedent exists")
            risk_score += 0.15
        
        if context.get("time_sensitive"):
            risk_factors.append("Time-sensitive action")
            risk_score += 0.1
        
        risk_level = "low" if risk_score < 0.3 else "medium" if risk_score < 0.6 else "high"
        
        assessment = {
            "action": action,
            "risk_level": risk_level,
            "risk_score": min(risk_score, 1.0),
            "risk_factors": risk_factors,
            "mitigations": self._get_mitigations(risk_level),
            "recommendation": "proceed" if risk_score < 0.5 else "escalate",
            "assessed_at": datetime.utcnow().isoformat()
        }
        
        return assessment
    
    def _get_mitigations(self, risk_level: str) -> List[str]:
        """Get mitigation strategies based on risk level."""
        mitigations = {
            "low": ["Document decision", "Continue monitoring"],
            "medium": ["Obtain approval", "Add verification step", "Set monitoring alerts"],
            "high": ["Executive review required", "Split action into phases", "Daily monitoring", "Contingency plan"]
        }
        return mitigations.get(risk_level, [])
    
    def _prioritize_tasks(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prioritize workflow tasks based on urgency, dependencies, and impact.
        
        Args:
            payload: List of tasks to prioritize
            
        Returns:
            Prioritized task list
        """
        tasks = payload.get("tasks", [])
        
        # Score each task
        scored_tasks = []
        for task in tasks:
            score = self._calculate_priority_score(task)
            scored_tasks.append({**task, "priority_score": score})
        
        # Sort by priority
        prioritized = sorted(scored_tasks, key=lambda x: x["priority_score"], reverse=True)
        
        return {
            "prioritized_tasks": prioritized,
            "total_tasks": len(prioritized),
            "prioritized_at": datetime.utcnow().isoformat()
        }
    
    def _calculate_priority_score(self, task: Dict[str, Any]) -> float:
        """Calculate priority score for a task."""
        score = 0.0
        
        # Urgency
        urgency = task.get("urgency", 1)
        score += urgency * 0.4
        
        # Dependencies
        has_dependencies = len(task.get("depends_on", [])) > 0
        score += (0.3 if has_dependencies else 0.1) * 0.3
        
        # Impact
        impact = task.get("impact_level", 1)
        score += impact * 0.3
        
        return min(score, 10.0)
    
    def _resolve_conflict(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve conflicts between multiple decisions.
        
        Args:
            payload: Conflicting decisions
            
        Returns:
            Resolution recommendation
        """
        conflicts = payload.get("conflicts", [])
        
        # Analyze conflicts and recommend resolution
        resolution = {
            "conflicts_found": len(conflicts),
            "recommended_approach": "weighted_consensus",
            "final_decision": DecisionType.ESCALATE.value,
            "reasoning": "Conflicts found - escalation recommended",
            "escalate_to": "decision_committee",
            "resolved_at": datetime.utcnow().isoformat()
        }
        
        return resolution
    
    def _evaluate_rules(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate business rules against provided data.
        
        Args:
            payload: Rules and data to evaluate
            
        Returns:
            Rule evaluation results
        """
        rules = payload.get("rules", [])
        data = payload.get("data", {})
        
        results = {
            "total_rules": len(rules),
            "rules_passed": 0,
            "rules_failed": 0,
            "violations": [],
            "evaluated_at": datetime.utcnow().isoformat()
        }
        
        for rule in rules:
            # Simulated rule evaluation
            if self._evaluate_single_rule(rule, data):
                results["rules_passed"] += 1
            else:
                results["rules_failed"] += 1
                results["violations"].append(rule.get("rule_id"))
        
        return results
    
    def _evaluate_single_rule(self, rule: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Evaluate a single business rule."""
        # Simplified rule evaluation
        return True
    
    def _log_decision(self, decision: Dict[str, Any], message: Message) -> None:
        """Log decision for audit trail."""
        log_entry = {
            "decision": decision,
            "message": message.to_dict(),
            "logged_at": datetime.utcnow().isoformat()
        }
        self.decision_history.append(log_entry)
    
    def _get_decision_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve decision history."""
        limit = payload.get("limit", 10)
        return {
            "total_decisions": len(self.decision_history),
            "recent_decisions": self.decision_history[-limit:],
            "retrieved_at": datetime.utcnow().isoformat()
        }
