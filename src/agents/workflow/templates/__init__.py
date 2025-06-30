"""Workflow templates module"""

from typing import Dict
from ..models import WorkflowDefinition

from .deal_risk_assessment import deal_risk_assessment
from .incident_to_resolution import incident_to_resolution
from .customer_360_report import customer_360_report
from .weekly_account_health_check import weekly_account_health_check
from .new_customer_onboarding import new_customer_onboarding


class WorkflowTemplates:
    """Library of reusable workflow templates"""
    
    @classmethod
    def get_all_templates(cls) -> Dict[str, WorkflowDefinition]:
        """Get all available workflow templates"""
        return {
            "deal_risk_assessment": deal_risk_assessment(),
            "incident_to_resolution": incident_to_resolution(),
            "customer_360_report": customer_360_report(),
            "weekly_account_health_check": weekly_account_health_check(),
            "new_customer_onboarding": new_customer_onboarding()
        }


__all__ = [
    'WorkflowTemplates',
    'deal_risk_assessment',
    'incident_to_resolution',
    'customer_360_report',
    'weekly_account_health_check',
    'new_customer_onboarding'
]