"""Comprehensive tests for SOQL Query Builder.

Tests cover:
- Basic query construction
- Complex queries with multiple conditions
- Security (SOQL injection prevention)
- Edge cases and error handling
- Query templates
- Search query builder functionality
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from src.utils.soql_query_builder import (
    SOQLQueryBuilder,
    SearchQueryBuilder,
    QueryTemplates,
    SOQLOperator,
    SOQLCondition,
    escape_soql
)


class TestSOQLEscaping:
    """Test SOQL injection prevention."""
    
    def test_escape_single_quotes(self):
        """Test escaping of single quotes."""
        assert escape_soql("O'Brien") == "O\\'Brien"
        assert escape_soql("test's") == "test\\'s"
        assert escape_soql("multiple'quotes'here") == "multiple\\'quotes\\'here"
    
    def test_escape_none_values(self):
        """Test handling of None values."""
        assert escape_soql(None) == ""
    
    def test_escape_special_characters(self):
        """Test other special characters pass through."""
        assert escape_soql("test@example.com") == "test@example.com"
        assert escape_soql("50%") == "50%"
        assert escape_soql("user_name") == "user_name"


class TestSOQLQueryBuilder:
    """Test core query builder functionality."""
    
    def test_basic_select_query(self):
        """Test basic SELECT query construction."""
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name'])
                .build())
        assert query == "SELECT Id, Name FROM Account"
    
    def test_select_all_fields(self):
        """Test SELECT * equivalent."""
        query = SOQLQueryBuilder('Contact').build()
        assert query == "SELECT Id FROM Contact"
    
    def test_where_clause_single_condition(self):
        """Test single WHERE condition."""
        query = (SOQLQueryBuilder('Lead')
                .select(['Id', 'Name'])
                .where('Status', SOQLOperator.EQUALS, 'New')
                .build())
        assert query == "SELECT Id, Name FROM Lead WHERE Status = 'New'"
    
    def test_where_id_shorthand(self):
        """Test where_id convenience method."""
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name'])
                .where_id('001234567890ABC')
                .build())
        assert query == "SELECT Id, Name FROM Account WHERE Id = '001234567890ABC'"
    
    def test_where_like_shorthand(self):
        """Test where_like convenience method."""
        query = (SOQLQueryBuilder('Contact')
                .select(['Id', 'Name'])
                .where_like('Name', '%Smith%')
                .build())
        assert query == "SELECT Id, Name FROM Contact WHERE Name LIKE '%Smith%'"
    
    def test_multiple_where_conditions_and(self):
        """Test multiple WHERE conditions with AND."""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['Id', 'Name', 'Amount'])
                .where('StageName', SOQLOperator.EQUALS, 'Closed Won')
                .where('Amount', SOQLOperator.GREATER_THAN, 100000)
                .build())
        assert query == "SELECT Id, Name, Amount FROM Opportunity WHERE StageName = 'Closed Won' AND Amount > 100000"
    
    def test_or_where_conditions(self):
        """Test OR conditions."""
        query = (SOQLQueryBuilder('Lead')
                .select(['Id', 'Name'])
                .where('Status', SOQLOperator.EQUALS, 'New')
                .or_where('Status', SOQLOperator.EQUALS, 'Working')
                .build())
        assert query == "SELECT Id, Name FROM Lead WHERE Status = 'New' OR Status = 'Working'"
    
    def test_where_in_operator(self):
        """Test WHERE IN clause."""
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name'])
                .where_in('Industry', ['Technology', 'Healthcare', 'Finance'])
                .build())
        assert query == "SELECT Id, Name FROM Account WHERE Industry IN ('Technology', 'Healthcare', 'Finance')"
    
    def test_where_not_in_operator(self):
        """Test WHERE NOT IN clause."""
        query = (SOQLQueryBuilder('Lead')
                .select(['Id', 'Name'])
                .where('Status', SOQLOperator.NOT_IN, ['Unqualified', 'Lost'])
                .build())
        assert query == "SELECT Id, Name FROM Lead WHERE Status NOT IN ('Unqualified', 'Lost')"
    
    def test_null_checks(self):
        """Test null comparisons using = and !=."""
        query1 = (SOQLQueryBuilder('Contact')
                 .select(['Id', 'Name'])
                 .where('Email', SOQLOperator.EQUALS, None)
                 .build())
        assert query1 == "SELECT Id, Name FROM Contact WHERE Email = null"
        
        query2 = (SOQLQueryBuilder('Contact')
                 .select(['Id', 'Name'])
                 .where('Email', SOQLOperator.NOT_EQUALS, None)
                 .build())
        assert query2 == "SELECT Id, Name FROM Contact WHERE Email != null"
    
    def test_order_by_single_field(self):
        """Test ORDER BY clause."""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['Id', 'Name', 'Amount'])
                .order_by('Amount')
                .build())
        assert query == "SELECT Id, Name, Amount FROM Opportunity ORDER BY Amount ASC"
    
    def test_order_by_descending(self):
        """Test ORDER BY DESC."""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['Id', 'Name', 'Amount'])
                .order_by('Amount', descending=True)
                .build())
        assert query == "SELECT Id, Name, Amount FROM Opportunity ORDER BY Amount DESC"
    
    def test_order_by_multiple_fields(self):
        """Test multiple ORDER BY fields."""
        query = (SOQLQueryBuilder('Contact')
                .select(['Id', 'Name'])
                .order_by('LastName')
                .order_by('FirstName')
                .build())
        assert query == "SELECT Id, Name FROM Contact ORDER BY LastName ASC, FirstName ASC"
    
    def test_limit_clause(self):
        """Test LIMIT clause."""
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name'])
                .limit(10)
                .build())
        assert query == "SELECT Id, Name FROM Account LIMIT 10"
    
    def test_offset_clause(self):
        """Test OFFSET clause for pagination."""
        query = (SOQLQueryBuilder('Contact')
                .select(['Id', 'Name'])
                .limit(50)
                .offset(100)
                .build())
        assert query == "SELECT Id, Name FROM Contact LIMIT 50 OFFSET 100"
    
    def test_complex_query_with_all_clauses(self):
        """Test complex query with all features."""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['Id', 'Name', 'Amount', 'StageName', 'Account.Name'])
                .where('Amount', SOQLOperator.GREATER_THAN, 50000)
                .where('StageName', SOQLOperator.NOT_IN, ['Closed Lost', 'Closed Won'])
                .or_where('Priority__c', SOQLOperator.EQUALS, 'High')
                .order_by('Amount', descending=True)
                .order_by('CloseDate')
                .limit(25)
                .offset(50)
                .build())
        
        expected = ("SELECT Id, Name, Amount, StageName, Account.Name FROM Opportunity "
                   "WHERE Amount > 50000 AND StageName NOT IN ('Closed Lost', 'Closed Won') "
                   "OR Priority__c = 'High' "
                   "ORDER BY Amount DESC, CloseDate ASC "
                   "LIMIT 25 OFFSET 50")
        assert query == expected
    
    def test_soql_injection_prevention(self):
        """Test that malicious input is properly escaped."""
        malicious_input = "'; DELETE FROM Account WHERE '' = '"
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name'])
                .where_like('Name', f'%{malicious_input}%')
                .build())
        
        # The single quotes should be escaped
        assert "\\'" in query
        assert "DELETE" in query  # But as escaped string, not executable
    
    def test_date_queries(self):
        """Test date-based queries."""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['Id', 'Name'])
                .where('CloseDate', SOQLOperator.GREATER_THAN, '2024-01-01')
                .where('CloseDate', SOQLOperator.LESS_OR_EQUAL, '2024-12-31')
                .build())
        
        expected = ("SELECT Id, Name FROM Opportunity "
                   "WHERE CloseDate > '2024-01-01' AND CloseDate <= '2024-12-31'")
        assert query == expected
    
    def test_relationship_queries(self):
        """Test queries with relationship fields."""
        query = (SOQLQueryBuilder('Contact')
                .select(['Id', 'Name', 'Account.Name', 'Account.Industry'])
                .where('Account.Industry', SOQLOperator.EQUALS, 'Technology')
                .build())
        
        expected = ("SELECT Id, Name, Account.Name, Account.Industry FROM Contact "
                   "WHERE Account.Industry = 'Technology'")
        assert query == expected
    
    def test_empty_value_handling(self):
        """Test handling of empty strings and None values."""
        # Empty string gets quotes
        query1 = (SOQLQueryBuilder('Lead')
                 .select(['Id'])
                 .where('Email', SOQLOperator.EQUALS, '')
                 .build())
        assert query1 == "SELECT Id FROM Lead WHERE Email = ''"
        
        # None becomes null (no quotes)
        query2 = (SOQLQueryBuilder('Lead')
                 .select(['Id'])
                 .where('Email', SOQLOperator.EQUALS, None)
                 .build())
        assert query2 == "SELECT Id FROM Lead WHERE Email = null"


class TestQueryTemplates:
    """Test pre-built query templates."""
    
    def test_get_all_related_records(self):
        """Test template for getting all related records."""
        queries = QueryTemplates.get_all_related_records('001234567890ABC')
        
        assert 'contacts' in queries
        assert 'opportunities' in queries
        assert 'cases' in queries
        assert 'tasks' in queries
        
        # Check that account ID is properly included
        assert "AccountId = '001234567890ABC'" in queries['contacts']
        assert "AccountId = '001234567890ABC'" in queries['opportunities']
        assert "AccountId = '001234567890ABC'" in queries['cases']
        assert "WhatId = '001234567890ABC'" in queries['tasks']
    
    def test_get_recent_records(self):
        """Test template for recent records."""
        query = QueryTemplates.get_recent_records('Lead', days=7)
        
        # Should include CreatedDate filter
        assert "CreatedDate >=" in query
        assert "ORDER BY CreatedDate DESC" in query
        assert "LIMIT 100" in query
    
    def test_search_by_email_domain(self):
        """Test email domain search template."""
        query = QueryTemplates.search_by_email_domain('Contact', 'example.com')
        
        assert "Email LIKE '%@example.com'" in query
        assert "FROM Contact" in query


class TestSearchQueryBuilder:
    """Test the SearchQueryBuilder convenience class."""
    
    def setup_method(self):
        """Set up mock Salesforce connection."""
        self.mock_sf = Mock()
        self.mock_sf.query.return_value = {'records': []}
    
    def test_basic_search(self):
        """Test basic search functionality."""
        searcher = SearchQueryBuilder(self.mock_sf, 'Account')
        searcher.search_fields(['Name'], 'Acme')
        query = searcher.query_builder.build()
        
        assert "Name LIKE '%Acme%'" in query
    
    def test_multi_field_search(self):
        """Test searching across multiple fields."""
        searcher = SearchQueryBuilder(self.mock_sf, 'Contact')
        searcher.search_fields(['Name', 'Email', 'Phone'], 'john')
        query = searcher.query_builder.build()
        
        assert "Name LIKE '%john%'" in query
        assert "OR Email LIKE '%john%'" in query
        assert "OR Phone LIKE '%john%'" in query
    
    def test_with_additional_filters(self):
        """Test adding additional filters to search."""
        searcher = SearchQueryBuilder(self.mock_sf, 'Lead')
        searcher.search_fields(['Name', 'Company'], 'tech')
        searcher.query_builder.where('Status', SOQLOperator.EQUALS, 'New')
        query = searcher.query_builder.build()
        
        assert "LIKE '%tech%'" in query
        assert "AND Status = 'New'" in query
    
    def test_recent_first_ordering(self):
        """Test recent_first convenience method."""
        searcher = SearchQueryBuilder(self.mock_sf, 'Opportunity')
        searcher.search_fields(['Name'], 'deal').recent_first()
        query = searcher.query_builder.build()
        
        assert "ORDER BY CreatedDate DESC" in query
    
    def test_execute_search(self):
        """Test executing the search."""
        mock_results = [
            {'Id': '001', 'Name': 'Test Account'},
            {'Id': '002', 'Name': 'Another Account'}
        ]
        self.mock_sf.query.return_value = {'records': mock_results}
        
        searcher = SearchQueryBuilder(self.mock_sf, 'Account')
        results = searcher.search_fields(['Name'], 'Account').execute()
        
        assert results == mock_results
        self.mock_sf.query.assert_called_once()
    
    def test_empty_search_term_handling(self):
        """Test handling of empty search terms."""
        searcher = SearchQueryBuilder(self.mock_sf, 'Contact')
        searcher.search_fields(['Name'], '')
        query = searcher.query_builder.build()
        
        # Should still create a valid query
        assert "Name LIKE '%%'" in query


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_no_fields_selected(self):
        """Test query with no fields selected defaults to Id."""
        query = SOQLQueryBuilder('Account').build()
        assert query == "SELECT Id FROM Account"
    
    def test_duplicate_fields_removed(self):
        """Test that duplicate fields are removed."""
        query = (SOQLQueryBuilder('Contact')
                .select(['Id', 'Name', 'Id', 'Email', 'Name'])
                .build())
        # Should only include each field once
        assert query.count('Id') == 1
        assert query.count('Name') == 1
    
    def test_special_characters_in_values(self):
        """Test handling of special characters."""
        query = (SOQLQueryBuilder('Account')
                .select(['Id'])
                .where_like('Name', '%Test & Co.%')
                .build())
        assert "Test & Co." in query
    
    def test_very_long_in_clause(self):
        """Test IN clause with many values."""
        values = [f'Value{i}' for i in range(100)]
        query = (SOQLQueryBuilder('Lead')
                .select(['Id'])
                .where_in('CustomField__c', values)
                .build())
        
        # All values should be included
        for value in values:
            assert value in query
    
    def test_numeric_value_handling(self):
        """Test numeric values don't get quotes."""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['Id'])
                .where('Amount', SOQLOperator.EQUALS, 100000)
                .build())
        assert "Amount = 100000" in query  # No quotes around number
    
    def test_boolean_value_handling(self):
        """Test boolean values."""
        query = (SOQLQueryBuilder('Lead')
                .select(['Id'])
                .where('IsConverted', SOQLOperator.EQUALS, True)
                .build())
        assert "IsConverted = true" in query  # Lowercase 'true'


class TestRealWorldScenarios:
    """Test real-world query scenarios."""
    
    def test_get_high_value_opportunities(self):
        """Test query for high-value opportunities."""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['Id', 'Name', 'Amount', 'StageName', 'Account.Name'])
                .where('Amount', SOQLOperator.GREATER_THAN, 1000000)
                .where('IsClosed', SOQLOperator.EQUALS, False)
                .where_in('StageName', ['Negotiation/Review', 'Proposal/Price Quote'])
                .order_by('Amount', descending=True)
                .limit(10)
                .build())
        
        assert "Amount > 1000000" in query
        assert "IsClosed = false" in query
        assert "StageName IN" in query
        assert "ORDER BY Amount DESC" in query
    
    def test_find_stale_leads(self):
        """Test query for leads with no recent activity."""
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        query = (SOQLQueryBuilder('Lead')
                .select(['Id', 'Name', 'LastActivityDate', 'Owner.Name'])
                .where('Status', SOQLOperator.NOT_IN, ['Converted', 'Unqualified'])
                .where('LastActivityDate', SOQLOperator.LESS_THAN, cutoff_date)
                .order_by('LastActivityDate')
                .build())
        
        assert "Status NOT IN" in query
        assert f"LastActivityDate < '{cutoff_date}'" in query
    
    def test_account_hierarchy_query(self):
        """Test query for account hierarchy."""
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name', 'ParentId', 'Parent.Name', 
                        'Type', 'Industry', 'AnnualRevenue'])
                .where('ParentId', SOQLOperator.EQUALS, '001234567890ABC')
                .or_where('Parent.ParentId', SOQLOperator.EQUALS, '001234567890ABC')
                .order_by('Name')
                .build())
        
        assert "ParentId = '001234567890ABC'" in query
        assert "OR Parent.ParentId = '001234567890ABC'" in query


if __name__ == '__main__':
    pytest.main([__file__, '-v'])