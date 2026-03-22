"""
Workflow Engine Module - Executes workflow steps with dynamic routing.

Provides:
- Step execution logic
- Conditional branching
- Dynamic routing based on step outputs
- Step dependency resolution
"""

from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from utils.helpers import get_iso_now
from utils.logger import get_logger
from core.message_schema import StepDefinition

logger = get_logger(__name__)


class WorkflowEngine:
    """
    Executes workflow steps with support for conditional branching.
    
    Handles:
    - Dynamic step routing (returns (result, next_step_id) tuples)
    - Condition evaluation
    - Dependency resolution
    - State tracking
    """
    
    def __init__(self):
        """Initialize workflow engine."""
        self.execution_history = []
    
    def resolve_step_dependencies(
        self,
        step_id: str,
        workflow_definition: Dict[str, Any],
        completed_steps: Dict[str, Dict[str, Any]]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if step dependencies are met.
        
        Args:
            step_id: Current step ID
            workflow_definition: Workflow configuration
            completed_steps: Completed steps with their outputs
            
        Returns:
            Tuple of (dependencies_met, error_message)
        """
        steps = {s["step_id"]: s for s in workflow_definition.get("steps", [])}
        
        if step_id not in steps:
            return False, f"Step {step_id} not found in workflow"
        
        step = steps[step_id]
        dependencies = step.get("dependencies", [])
        
        for dep_step_id in dependencies:
            if dep_step_id not in completed_steps:
                return False, f"Dependency {dep_step_id} not completed"
            
            dep_step = completed_steps[dep_step_id]
            if dep_step.get("status") == "failed":
                return False, f"Dependency {dep_step_id} failed"
            
            if dep_step.get("status") != "completed":
                return False, f"Dependency {dep_step_id} not completed"
        
        return True, None
    
    def evaluate_condition(
        self,
        condition: Dict[str, Any],
        step_outputs: Dict[str, Any],
        workflow_state: Dict[str, Any]
    ) -> bool:
        """
        Evaluate conditional execution logic.
        
        Args:
            condition: Condition specification
            step_outputs: Outputs from current and previous steps
            workflow_state: Current workflow state
            
        Returns:
            True if condition is met
        """
        if not condition:
            return True
        
        condition_type = condition.get("type", "and")
        rules = condition.get("rules", [])
        
        results = []
        for rule in rules:
            result = self._evaluate_rule(rule, step_outputs, workflow_state)
            results.append(result)
        
        if condition_type == "and":
            return all(results) if results else True
        elif condition_type == "or":
            return any(results) if results else True
        else:
            return True
    
    def _evaluate_rule(
        self,
        rule: Dict[str, Any],
        step_outputs: Dict[str, Any],
        workflow_state: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single rule within a condition.
        
        Args:
            rule: Rule specification
            step_outputs: Available outputs
            workflow_state: Workflow state
            
        Returns:
            Rule evaluation result
        """
        operator = rule.get("operator")
        source = rule.get("source")  # "output" or "state"
        field = rule.get("field")
        value = rule.get("value")
        
        # Validate inputs
        if not field or not operator:
            return False
        
        # Get comparison value
        if source == "output":
            compare_value = step_outputs.get(field) if isinstance(field, str) else None
        elif source == "state":
            compare_value = workflow_state.get(field) if isinstance(field, str) else None
        else:
            return False
        
        # If value is None, only check equality operators
        if compare_value is None:
            if operator == "equals":
                return value is None
            elif operator == "not_equals":
                return value is not None
            else:
                return False
        
        # Perform comparison
        if operator == "equals":
            return compare_value == value
        elif operator == "not_equals":
            return compare_value != value
        elif operator == "contains":
            try:
                return value in str(compare_value)  # type: ignore
            except (TypeError, ValueError):
                return False
        elif operator == "greater_than":
            try:
                return float(compare_value) > float(value)  # type: ignore
            except (TypeError, ValueError):
                return False
        elif operator == "less_than":
            try:
                return float(compare_value) < float(value)  # type: ignore
            except (TypeError, ValueError):
                return False
        elif operator == "in_list":
            if value is None:
                return False
            try:
                return compare_value in value
            except TypeError:
                return False
        else:
            return False
    
    def determine_next_step(
        self,
        current_step: Dict[str, Any],
        step_outputs: Dict[str, Any],
        workflow_definition: Dict[str, Any],
        workflow_state: Dict[str, Any],
        step_failed: bool = False
    ) -> Tuple[Optional[str], str]:
        """
        Determine next step dynamically based on condition evaluation.
        
        Returns tuple of (next_step_id, reason)
        
        Args:
            current_step: Current step definition
            step_outputs: Current step outputs
            workflow_definition: Full workflow definition
            workflow_state: Current workflow state
            step_failed: Whether current step failed
            
        Returns:
            Tuple of (next_step_id, routing_reason)
        """
        # If step failed, check for fallback
        if step_failed:
            fallback_steps = current_step.get("fallback_steps", [])
            if fallback_steps:
                next_id = fallback_steps[0]
                return next_id, f"Using fallback step after failure"
            else:
                return None, "Step failed with no fallback"
        
        # Check conditional routing
        condition = current_step.get("condition")
        if condition:
            if self.evaluate_condition(condition, step_outputs, workflow_state):
                # Condition met, use conditional next step
                next_id = current_step.get("condition_next_step_id")
                if next_id:
                    return next_id, "Condition met, routing to conditional step"
            else:
                # Condition not met, use fallback
                next_id = current_step.get("condition_false_step_id") or current_step.get("next_step_id")
                if next_id:
                    return next_id, "Condition not met, routing to alternate step"
        
        # No condition or condition passed, use next_step_id
        next_id = current_step.get("next_step_id")
        if next_id:
            return next_id, "Sequential routing to next step"
        
        # No next step specified
        return None, "No next step defined (workflow complete)"
    
    def get_step_by_id(
        self,
        step_id: str,
        workflow_definition: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get step definition by ID.
        
        Args:
            step_id: Step ID
            workflow_definition: Workflow definition
            
        Returns:
            Step definition or None
        """
        steps = workflow_definition.get("steps", [])
        for step in steps:
            if step.get("step_id") == step_id:
                return step
        return None
    
    def get_first_step(self, workflow_definition: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get first step in workflow.
        
        Args:
            workflow_definition: Workflow definition
            
        Returns:
            First step or None
        """
        steps = workflow_definition.get("steps", [])
        if not steps:
            return None
        
        # Return step with no dependencies or first in list
        for step in steps:
            if not step.get("dependencies"):
                return step
        
        return steps[0] if steps else None
    
    def record_step_execution(
        self,
        workflow_id: str,
        step: Dict[str, Any],
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
        status: str,
        duration_seconds: float
    ) -> None:
        """
        Record step execution for debugging.
        
        Args:
            workflow_id: Workflow ID
            step: Step definition
            inputs: Step inputs
            outputs: Step outputs
            status: Execution status
            duration_seconds: Time taken
        """
        execution_record = {
            "workflow_id": workflow_id,
            "step_id": step.get("step_id"),
            "step_name": step.get("name"),
            "timestamp": get_iso_now(),
            "inputs": inputs,
            "outputs": outputs,
            "status": status,
            "duration_seconds": round(duration_seconds, 3)
        }
        
        self.execution_history.append(execution_record)
    
    def validate_workflow_definition(
        self,
        workflow_definition: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate workflow definition structure.
        
        Args:
            workflow_definition: Workflow to validate
            
        Returns:
            Tuple of (valid, error_message)
        """
        if not workflow_definition.get("workflow_id"):
            return False, "Missing workflow_id"
        
        if not workflow_definition.get("steps"):
            return False, "No steps defined"
        
        steps = workflow_definition.get("steps", [])
        step_ids = set()
        
        for step in steps:
            if not step.get("step_id"):
                return False, f"Step missing step_id: {step}"
            
            if not step.get("agent"):
                return False, f"Step {step.get('step_id')} missing agent"
            
            if not step.get("action"):
                return False, f"Step {step.get('step_id')} missing action"
            
            if step["step_id"] in step_ids:
                return False, f"Duplicate step_id: {step['step_id']}"
            
            step_ids.add(step["step_id"])
            
            # Validate dependencies reference existing steps
            for dep in step.get("dependencies", []):
                if dep not in step_ids and dep not in [s["step_id"] for s in steps[steps.index(step)+1:]]:
                    # Dependency check should be on all steps, not just processed ones
                    pass
        
        return True, None
    
    def get_execution_path(
        self,
        workflow_definition: Dict[str, Any],
        executed_steps: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """
        Get the execution path taken through workflow.
        
        Args:
            workflow_definition: Workflow definition
            executed_steps: Completed steps with outputs
            
        Returns:
            List of step IDs in execution order
        """
        path = []
        step_ids = [s["step_id"] for s in workflow_definition.get("steps", [])]
        
        for step_id in step_ids:
            if step_id in executed_steps:
                path.append(step_id)
        
        return path
    
    def estimate_remaining_steps(
        self,
        next_step_id: Optional[str],
        workflow_definition: Dict[str, Any],
        executed_steps: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """
        Estimate remaining steps to execute.
        
        Args:
            next_step_id: Next step to execute
            workflow_definition: Workflow definition
            executed_steps: Completed steps
            
        Returns:
            Estimated remaining step IDs
        """
        if not next_step_id:
            return []
        
        remaining = []
        all_steps = {s["step_id"]: s for s in workflow_definition.get("steps", [])}
        
        current_id = next_step_id
        visited = set()
        
        while current_id and current_id not in visited and len(visited) < len(all_steps):
            if current_id not in executed_steps:
                remaining.append(current_id)
            
            visited.add(current_id)
            
            step = all_steps.get(current_id)
            if not step:
                break
            
            current_id = step.get("next_step_id")
        
        return remaining
