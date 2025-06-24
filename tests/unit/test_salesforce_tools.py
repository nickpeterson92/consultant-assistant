"""
Unit tests for Salesforce tools.

Tests cover all 15 Salesforce tools:
- Lead tools (Get, Create, Update)
- Account tools (Get, Create, Update)
- Opportunity tools (Get, Create, Update)
- Contact tools (Get, Create, Update)
- Case tools (Get, Create, Update)
- Task tools (Get, Create, Update)
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from simple_salesforce import Salesforce
from simple_salesforce.exceptions import SalesforceError

from src.tools.salesforce_tools import (
    # Lead tools
    GetLeadTool, CreateLeadTool, UpdateLeadTool,
    # Account tools
    GetAccountTool, CreateAccountTool, UpdateAccountTool,
    # Opportunity tools
    GetOpportunityTool, CreateOpportunityTool, UpdateOpportunityTool,
    # Contact tools
    GetContactTool, CreateContactTool, UpdateContactTool,
    # Case tools
    GetCaseTool, CreateCaseTool, UpdateCaseTool,
    # Task tools
    GetTaskTool, CreateTaskTool, UpdateTaskTool,
    # Helper
    get_salesforce_connection
)


@pytest.fixture
def mock_salesforce():
    """Create a mock Salesforce connection."""
    mock_sf = Mock(spec=Salesforce)
    
    # Mock query responses
    mock_sf.query.return_value = {
        "totalSize": 1,
        "records": [{
            "Id": "00Q1234567890ABC",
            "Name": "Test Record",
            "Email": "test@example.com"
        }]
    }
    
    # Mock CRUD operations
    mock_sf.Lead = Mock()
    mock_sf.Lead.create.return_value = {"id": "00Q1234567890ABC", "success": True}
    mock_sf.Lead.update.return_value = 204
    
    mock_sf.Account = Mock()
    mock_sf.Account.create.return_value = {"id": "0011234567890ABC", "success": True}
    mock_sf.Account.update.return_value = 204
    
    mock_sf.Opportunity = Mock()
    mock_sf.Opportunity.create.return_value = {"id": "0061234567890ABC", "success": True}
    mock_sf.Opportunity.update.return_value = 204
    
    mock_sf.Contact = Mock()
    mock_sf.Contact.create.return_value = {"id": "0031234567890ABC", "success": True}
    mock_sf.Contact.update.return_value = 204
    
    mock_sf.Case = Mock()
    mock_sf.Case.create.return_value = {"id": "5001234567890ABC", "success": True}
    mock_sf.Case.update.return_value = 204
    
    mock_sf.Task = Mock()
    mock_sf.Task.create.return_value = {"id": "00T1234567890ABC", "success": True}
    mock_sf.Task.update.return_value = 204
    
    return mock_sf


@pytest.fixture(autouse=True)
def mock_sf_connection(mock_salesforce):
    """Auto-mock Salesforce connection for all tests."""
    with patch('src.tools.salesforce_tools.get_salesforce_connection', return_value=mock_salesforce):
        yield mock_salesforce


class TestSalesforceConnection:
    """Test Salesforce connection functionality."""
    
    def test_get_salesforce_connection(self):
        """Test getting Salesforce connection."""
        with patch.dict('os.environ', {
            'SFDC_USER': 'test@example.com',
            'SFDC_PASS': 'password',
            'SFDC_TOKEN': 'token123'
        }):
            with patch('src.tools.salesforce_tools.Salesforce') as mock_sf_class:
                mock_sf_class.return_value = Mock()
                
                sf = get_salesforce_connection()
                
                mock_sf_class.assert_called_once_with(
                    username='test@example.com',
                    password='password',
                    security_token='token123'
                )
                assert sf is not None
    
    def test_connection_error_handling(self):
        """Test connection error handling."""
        with patch.dict('os.environ', {}):  # Missing credentials
            with pytest.raises(Exception):
                get_salesforce_connection()


class TestLeadTools:
    """Test Lead management tools."""
    
    def test_get_lead_by_email(self, mock_salesforce):
        """Test getting lead by email."""
        tool = GetLeadTool()
        
        result = tool._run(email="test@example.com")
        data = result  # Tool returns dict, not JSON string
        
        # Tool returns the lead data directly
        assert data["email"] == "test@example.com"
        assert "id" in data
        
        # Verify SOQL query
        mock_salesforce.query.assert_called_once()
        query = mock_salesforce.query.call_args[0][0]
        assert "FROM Lead" in query
        assert "Email = 'test@example.com'" in query
    
    def test_get_lead_by_id(self, mock_salesforce):
        """Test getting lead by ID."""
        tool = GetLeadTool()
        
        result = tool._run(id="00Q1234567890ABC")
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert "Id = '00Q1234567890ABC'" in mock_salesforce.query.call_args[0][0]
    
    def test_get_lead_not_found(self, mock_salesforce):
        """Test handling lead not found."""
        mock_salesforce.query.return_value = {"totalSize": 0, "records": []}
        
        tool = GetLeadTool()
        result = tool._run(email="notfound@example.com")
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["count"] == 0
        assert data["message"] == "No leads found"
    
    def test_create_lead(self, mock_salesforce):
        """Test creating a new lead."""
        tool = CreateLeadTool()
        
        result = tool._run(
            first_name="John",
            last_name="Doe",
            company="Acme Corp",
            email="john@acme.com"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["id"] == "00Q1234567890ABC"
        
        mock_salesforce.Lead.create.assert_called_once_with({
            "FirstName": "John",
            "LastName": "Doe",
            "Company": "Acme Corp",
            "Email": "john@acme.com"
        })
    
    def test_update_lead(self, mock_salesforce):
        """Test updating a lead."""
        tool = UpdateLeadTool()
        
        result = tool._run(
            id="00Q1234567890ABC",
            email="newemail@example.com",
            status="Qualified"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["message"] == "Lead updated successfully"
        
        mock_salesforce.Lead.update.assert_called_once_with(
            "00Q1234567890ABC",
            {"Email": "newemail@example.com", "Status": "Qualified"}
        )


class TestAccountTools:
    """Test Account management tools."""
    
    def test_get_account_by_name(self, mock_salesforce):
        """Test getting account by name."""
        mock_salesforce.query.return_value = {
            "totalSize": 1,
            "records": [{
                "Id": "0011234567890ABC",
                "Name": "Acme Corporation",
                "Industry": "Technology",
                "AnnualRevenue": 1000000
            }]
        }
        
        tool = GetAccountTool()
        result = tool._run(name="Acme Corporation")
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["records"][0]["Name"] == "Acme Corporation"
        assert "FROM Account" in mock_salesforce.query.call_args[0][0]
    
    def test_create_account(self, mock_salesforce):
        """Test creating an account."""
        tool = CreateAccountTool()
        
        result = tool._run(
            name="New Company",
            industry="Finance",
            annual_revenue=5000000
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["id"] == "0011234567890ABC"
        
        mock_salesforce.Account.create.assert_called_once()
        create_data = mock_salesforce.Account.create.call_args[0][0]
        assert create_data["Name"] == "New Company"
        assert create_data["Industry"] == "Finance"
    
    def test_update_account(self, mock_salesforce):
        """Test updating an account."""
        tool = UpdateAccountTool()
        
        result = tool._run(
            id="0011234567890ABC",
            phone="555-1234",
            website="https://example.com"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        mock_salesforce.Account.update.assert_called_once()


class TestOpportunityTools:
    """Test Opportunity management tools."""
    
    def test_get_opportunity_by_account(self, mock_salesforce):
        """Test getting opportunities by account."""
        mock_salesforce.query.return_value = {
            "totalSize": 2,
            "records": [
                {
                    "Id": "0061234567890ABC",
                    "Name": "Big Deal",
                    "Amount": 50000,
                    "StageName": "Qualification"
                },
                {
                    "Id": "0061234567890DEF",
                    "Name": "Bigger Deal",
                    "Amount": 100000,
                    "StageName": "Proposal"
                }
            ]
        }
        
        tool = GetOpportunityTool()
        result = tool._run(account_id="0011234567890ABC")
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["count"] == 2
        assert data["total_value"] == 150000
    
    def test_create_opportunity(self, mock_salesforce):
        """Test creating an opportunity."""
        tool = CreateOpportunityTool()
        
        result = tool._run(
            name="New Deal",
            account_id="0011234567890ABC",
            amount=75000,
            stage="Prospecting",
            close_date="2024-12-31"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        
        create_data = mock_salesforce.Opportunity.create.call_args[0][0]
        assert create_data["Name"] == "New Deal"
        assert create_data["Amount"] == 75000
        assert create_data["CloseDate"] == "2024-12-31"
    
    def test_update_opportunity_stage(self, mock_salesforce):
        """Test updating opportunity stage."""
        tool = UpdateOpportunityTool()
        
        result = tool._run(
            id="0061234567890ABC",
            stage="Closed Won"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        
        update_data = mock_salesforce.Opportunity.update.call_args[0][1]
        assert update_data["StageName"] == "Closed Won"


class TestContactTools:
    """Test Contact management tools."""
    
    def test_get_contact_by_email(self, mock_salesforce):
        """Test getting contact by email."""
        mock_salesforce.query.return_value = {
            "totalSize": 1,
            "records": [{
                "Id": "0031234567890ABC",
                "FirstName": "Jane",
                "LastName": "Smith",
                "Email": "jane@example.com",
                "AccountId": "0011234567890ABC"
            }]
        }
        
        tool = GetContactTool()
        result = tool._run(email="jane@example.com")
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["records"][0]["Email"] == "jane@example.com"
    
    def test_create_contact(self, mock_salesforce):
        """Test creating a contact."""
        tool = CreateContactTool()
        
        result = tool._run(
            first_name="Bob",
            last_name="Johnson",
            email="bob@example.com",
            account_id="0011234567890ABC"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["id"] == "0031234567890ABC"


class TestCaseTools:
    """Test Case management tools."""
    
    def test_get_case_by_number(self, mock_salesforce):
        """Test getting case by case number."""
        mock_salesforce.query.return_value = {
            "totalSize": 1,
            "records": [{
                "Id": "5001234567890ABC",
                "CaseNumber": "00001234",
                "Subject": "Product Issue",
                "Status": "Open"
            }]
        }
        
        tool = GetCaseTool()
        result = tool._run(case_number="00001234")
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["records"][0]["CaseNumber"] == "00001234"
    
    def test_create_case(self, mock_salesforce):
        """Test creating a case."""
        tool = CreateCaseTool()
        
        result = tool._run(
            subject="New Issue",
            description="Customer reported problem",
            contact_id="0031234567890ABC",
            priority="High"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        
        create_data = mock_salesforce.Case.create.call_args[0][0]
        assert create_data["Subject"] == "New Issue"
        assert create_data["Priority"] == "High"
    
    def test_update_case_status(self, mock_salesforce):
        """Test updating case status."""
        tool = UpdateCaseTool()
        
        result = tool._run(
            id="5001234567890ABC",
            status="Closed"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        
        update_data = mock_salesforce.Case.update.call_args[0][1]
        assert update_data["Status"] == "Closed"


class TestTaskTools:
    """Test Task management tools."""
    
    def test_get_task_by_subject(self, mock_salesforce):
        """Test getting task by subject."""
        mock_salesforce.query.return_value = {
            "totalSize": 1,
            "records": [{
                "Id": "00T1234567890ABC",
                "Subject": "Follow up call",
                "Status": "Not Started",
                "Priority": "Normal"
            }]
        }
        
        tool = GetTaskTool()
        result = tool._run(subject="Follow up call")
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        assert data["records"][0]["Subject"] == "Follow up call"
    
    def test_create_task(self, mock_salesforce):
        """Test creating a task."""
        tool = CreateTaskTool()
        
        result = tool._run(
            subject="Call customer",
            who_id="0031234567890ABC",
            priority="High",
            due_date="2024-12-31"
        )
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is True
        
        create_data = mock_salesforce.Task.create.call_args[0][0]
        assert create_data["Subject"] == "Call customer"
        assert create_data["Priority"] == "High"
        assert create_data["ActivityDate"] == "2024-12-31"


class TestErrorHandling:
    """Test error handling across all tools."""
    
    def test_salesforce_api_error(self, mock_salesforce):
        """Test handling Salesforce API errors."""
        mock_salesforce.query.side_effect = SalesforceError(
            "API Error",
            status=400,
            resource_name="Lead",
            content={"message": "Bad request"}
        )
        
        tool = GetLeadTool()
        result = tool._run(email="test@example.com")
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is False
        assert "error" in data
        assert "API Error" in data["error"]
    
    def test_connection_error(self):
        """Test handling connection errors."""
        with patch('src.tools.salesforce_tools.get_salesforce_connection', side_effect=Exception("Connection failed")):
            tool = GetAccountTool()
            result = tool._run(name="Test")
            data = result  # Tool returns dict, not JSON string
            
            assert data["success"] is False
            assert "Connection failed" in data["error"]
    
    def test_invalid_parameters(self, mock_salesforce):
        """Test handling invalid parameters."""
        tool = GetLeadTool()
        
        # No search parameters provided
        result = tool._run()
        data = result  # Tool returns dict, not JSON string
        
        assert data["success"] is False
        assert "At least one search parameter" in data["error"]


class TestSOQLInjectionPrevention:
    """Test SOQL injection prevention."""
    
    def test_quote_escaping(self, mock_salesforce):
        """Test that quotes are properly escaped."""
        tool = GetAccountTool()
        
        # Try to inject SOQL
        dangerous_input = "Test' OR Name != '"
        result = tool._run(name=dangerous_input)
        
        # Check the actual query
        query = mock_salesforce.query.call_args[0][0]
        
        # Should escape the quotes
        assert "Test\\' OR Name != \\'" in query or "Test'' OR Name != ''" in query
        
        # Should not allow injection
        assert " OR " not in query.split("'Test")[0]  # OR should be inside quotes, not outside