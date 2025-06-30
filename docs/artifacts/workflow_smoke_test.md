# Workflow Smoke Test Manual Script

## Prerequisites
- Start the system in A2A mode: `python3 start_system.py --a2a`
- Open the orchestrator CLI in another terminal: `python3 orchestrator_cli.py`

## Test Data Setup
The following test data should exist in your Salesforce sandbox:
- **Account**: Express Logistics and Transport (or any account with opportunities)
- **Opportunities**: At least one in "Proposal/Price Quote" or "Negotiation/Review" stage
- **Incident**: Any ServiceNow incident number (e.g., INC0010001)

---

## 1. Deal Risk Assessment Workflow

### Test Case: Identify At-Risk Deals
**Input:**
```
check for at-risk deals
```

**Expected Result:**
- Workflow finds opportunities in late stages (Proposal/Price Quote, Negotiation/Review)
- Identifies blockers across Salesforce, Jira, and ServiceNow
- Generates risk assessment report with recommendations

**Verification:**
- Check that opportunities are correctly identified
- Verify risk factors are analyzed
- Confirm comprehensive report is generated

---

## 2. Incident to Resolution Workflow

### Test Case: End-to-End Incident Management
**Input:**
```
handle incident INC0010001 to resolution
```
*Note: Replace with an actual incident number from your ServiceNow instance*

**Expected Result:**
- Fetches incident details from ServiceNow
- Links to related Salesforce case (if exists)
- Creates Jira issue for tracking
- Updates incident status
- Generates resolution report

**Verification:**
- Check ServiceNow incident is retrieved
- Verify Jira issue is created
- Confirm cross-system linking works

---

## 3. Customer 360 Report Workflow

### Test Case: Comprehensive Customer View
**Input:**
```
generate customer 360 report for Express Logistics
```

**Expected Result:**
- Gathers data from all three systems in parallel:
  - Salesforce: Account, contacts, opportunities, cases
  - Jira: Related issues and projects
  - ServiceNow: Incidents, changes, requests
- Compiles comprehensive 360-degree view
- Generates detailed report

**Verification:**
- Verify parallel data gathering (check logs)
- Confirm all systems are queried
- Check report completeness

---

## 4. Weekly Account Health Check Workflow

### Test Case: Account Health Analysis
**Input:**
```
run weekly health check for key accounts
```

**Expected Result:**
- Identifies key accounts (revenue > $100K)
- Analyzes multiple health metrics:
  - Open opportunities and their status
  - Recent activities and engagement
  - Support tickets and issues
  - Upcoming renewals
- Generates health score and recommendations

**Verification:**
- Check key accounts are identified correctly
- Verify all metrics are analyzed
- Confirm actionable recommendations

---

## 5. New Customer Onboarding Workflow

### Test Case A: Single Opportunity Match
**Input:**
```
start onboarding for Express Logistics SLA
```

**Expected Result:**
- Finds specific opportunity
- Updates to Closed Won (if not already)
- Creates onboarding case
- Parallel execution:
  - Creates Jira project
  - Sets up ServiceNow company
  - Creates onboarding tasks
- Schedules kickoff meeting
- Generates completion report

### Test Case B: Multiple Opportunity Match (Human-in-the-Loop)
**Input:**
```
we just closed the deal with Express Logistics! start onboarding
```

**Expected Result:**
- Finds multiple Express Logistics opportunities
- **INTERRUPTS** for human input
- Displays numbered list of opportunities

**Follow-up Input:**
```
2
```
*or*
```
the second one
```

**Expected Result:**
- Resumes workflow with selected opportunity
- Completes all onboarding steps
- Generates report

**Verification:**
- Verify human interrupt works correctly
- Check workflow resumes with same thread
- Confirm all parallel steps execute
- Verify completion report

---

## 6. Edge Cases and Error Handling

### Test Case: Non-existent Account
**Input:**
```
generate customer 360 for Acme123456789
```

**Expected Result:**
- Gracefully handles missing data
- Reports what was/wasn't found
- Completes workflow without crashing

### Test Case: Invalid Workflow Request
**Input:**
```
run workflow for something random
```

**Expected Result:**
- Workflow agent responds that no matching workflow exists
- Suggests available workflows

---

## 7. System Health Check

### Test Case: Verify All Agents
**Input:**
```
check agent status
```

**Expected Result:**
- Shows all 4 agents online
- Displays capabilities for each

---

## Logging and Monitoring

During testing, monitor these log files:
```bash
# Watch workflow execution
tail -f logs/workflow.log | grep -E "(workflow_.*_executing|workflow_completed|workflow_error)"

# Monitor parallel execution
tail -f logs/workflow.log | grep "parallel"

# Check for errors
tail -f logs/errors.log

# Track cross-system calls
tail -f logs/*.log | grep -E "(salesforce|jira|servicenow)_agent"
```

---

## Success Criteria

✅ All 5 workflows execute successfully
✅ Parallel steps execute concurrently (check timestamps in logs)
✅ Human-in-the-loop interrupts and resumes work
✅ Cross-system integration functions properly
✅ Comprehensive reports are generated
✅ Error cases are handled gracefully
✅ Workflow status shows "completed" not "running"

---

## Quick Test Commands

For rapid smoke testing, use these commands in sequence:

```bash
# 1. Quick at-risk deals check
check for at-risk deals

# 2. Customer report (should be fast with parallel execution)
generate customer 360 for GenePoint

# 3. Onboarding with interrupt
start onboarding for Express Logistics
# When prompted, respond with: 2

# 4. Account health
check health of Edge Communications

# 5. System check
check agent status
```

---

## Troubleshooting

If a workflow fails:
1. Check the specific agent logs
2. Look for "workflow_error" in logs/workflow.log
3. Verify all agents are online
4. Check for data prerequisites (accounts, opportunities, etc.)
5. Ensure proper environment variables are set

Remember: The system uses actual API calls, so ensure your sandbox data is appropriate for testing.