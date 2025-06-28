#!/usr/bin/env python3
"""Test all workflow templates"""

import asyncio
import json
from src.a2a import A2AClient, A2ATask
from src.utils.logging import get_logger

logger = get_logger("workflow_test")

async def test_workflow(workflow_name: str, instruction: str, context: dict = None):
    """Test a specific workflow"""
    print(f"\n{'='*60}")
    print(f"Testing: {workflow_name}")
    print(f"Instruction: {instruction}")
    print('='*60)
    
    task = A2ATask(
        id=f"test_{workflow_name}",
        instruction=instruction,
        context=context or {},
        state_snapshot={}
    )
    
    try:
        async with A2AClient() as client:
            # Call workflow agent directly since orchestrator doesn't have A2A interface
            workflow_endpoint = "http://localhost:8004/a2a"
            result = await client.process_task(endpoint=workflow_endpoint, task=task)
            
            # Extract response
            if result.get("artifacts"):
                content = result["artifacts"][0].get("content", "No content")
                print(f"\nResult: {content}")
            else:
                print(f"\nRaw result: {json.dumps(result, indent=2)}")
                
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        logger.error(f"Workflow test failed: {workflow_name}", error=str(e))

async def main():
    """Test all workflows"""
    print("Testing All Workflow Templates")
    print("="*60)
    
    # Test 1: Deal Risk Assessment
    await test_workflow(
        "deal_risk_assessment",
        "Check for at-risk deals and opportunities closing this month"
    )
    
    # Give the system a moment between tests
    await asyncio.sleep(2)
    
    # Test 2: Customer 360 Report
    await test_workflow(
        "customer_360_report", 
        "Give me a complete 360 report for GenePoint"
    )
    
    await asyncio.sleep(2)
    
    # Test 3: Weekly Account Health Check
    await test_workflow(
        "weekly_account_health_check",
        "Run a health check on our key accounts"
    )
    
    await asyncio.sleep(2)
    
    # Test 4: Incident to Resolution (needs a case ID)
    await test_workflow(
        "incident_to_resolution",
        "Handle incident resolution for critical case",
        {"case_id": "500bm00000CZxJQAA1"}  # Example case ID
    )
    
    await asyncio.sleep(2)
    
    # Test 5: New Customer Onboarding (needs opportunity ID)
    await test_workflow(
        "new_customer_onboarding",
        "Start onboarding process for new customer",
        {"opportunity_id": "006bm00000HM6zHAAT"}  # Example opportunity ID
    )
    
    print("\n" + "="*60)
    print("All workflow tests completed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())