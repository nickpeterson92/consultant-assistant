"""
Test suite for advanced SOQL query builder features
"""

import pytest
from src.utils.soql_query_builder import (
    SOQLQueryBuilder, SOQLOperator, SOSLQueryBuilder, 
    AggregateQueryBuilder, QueryTemplates, SubqueryBuilder
)


class TestAggregateQueries:
    """Test aggregate function features"""
    
    def test_count_aggregate(self):
        """Test COUNT aggregate function"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['StageName'])
                .select_count('Id', 'RecordCount')
                .group_by('StageName')
                .build())
        
        expected = "SELECT StageName, COUNT(Id) RecordCount FROM Opportunity GROUP BY StageName"
        assert query == expected
    
    def test_sum_aggregate(self):
        """Test SUM aggregate function"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['AccountId'])
                .select_sum('Amount', 'TotalRevenue')
                .group_by('AccountId')
                .build())
        
        expected = "SELECT AccountId, SUM(Amount) TotalRevenue FROM Opportunity GROUP BY AccountId"
        assert query == expected
    
    def test_avg_aggregate(self):
        """Test AVG aggregate function"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['OwnerId'])
                .select_avg('Amount', 'AverageAmount')
                .group_by('OwnerId')
                .build())
        
        expected = "SELECT OwnerId, AVG(Amount) AverageAmount FROM Opportunity GROUP BY OwnerId"
        assert query == expected
    
    def test_multiple_aggregates(self):
        """Test multiple aggregate functions together"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['StageName'])
                .select_count('Id', 'OpportunityCount')
                .select_sum('Amount', 'TotalAmount')
                .select_avg('Amount', 'AvgAmount')
                .select_max('Amount', 'MaxDeal')
                .select_min('Amount', 'MinDeal')
                .group_by('StageName')
                .build())
        
        expected = ("SELECT StageName, COUNT(Id) OpportunityCount, SUM(Amount) TotalAmount, "
                   "AVG(Amount) AvgAmount, MAX(Amount) MaxDeal, MIN(Amount) MinDeal "
                   "FROM Opportunity GROUP BY StageName")
        assert query == expected


class TestGroupByHaving:
    """Test GROUP BY and HAVING clauses"""
    
    def test_group_by_single_field(self):
        """Test GROUP BY with single field"""
        query = (SOQLQueryBuilder('Account')
                .select(['Industry'])
                .select_count('Id', 'AccountCount')
                .group_by('Industry')
                .build())
        
        expected = "SELECT Industry, COUNT(Id) AccountCount FROM Account GROUP BY Industry"
        assert query == expected
    
    def test_group_by_multiple_fields(self):
        """Test GROUP BY with multiple fields"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['OwnerId', 'StageName'])
                .select_count('Id', 'Count')
                .group_by(['OwnerId', 'StageName'])
                .build())
        
        expected = "SELECT OwnerId, StageName, COUNT(Id) Count FROM Opportunity GROUP BY OwnerId, StageName"
        assert query == expected
    
    def test_having_clause(self):
        """Test HAVING clause"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['AccountId'])
                .select_sum('Amount', 'Total')
                .group_by('AccountId')
                .having('SUM(Amount)', SOQLOperator.GREATER_THAN, 100000)
                .build())
        
        expected = ("SELECT AccountId, SUM(Amount) Total FROM Opportunity "
                   "GROUP BY AccountId HAVING SUM(Amount) > 100000")
        assert query == expected
    
    def test_having_with_or(self):
        """Test HAVING with OR conditions"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['StageName'])
                .select_count('Id', 'Count')
                .select_sum('Amount', 'Total')
                .group_by('StageName')
                .having('COUNT(Id)', SOQLOperator.GREATER_THAN, 10)
                .or_having('SUM(Amount)', SOQLOperator.GREATER_THAN, 500000)
                .build())
        
        expected = ("SELECT StageName, COUNT(Id) Count, SUM(Amount) Total FROM Opportunity "
                   "GROUP BY StageName HAVING COUNT(Id) > 10 OR SUM(Amount) > 500000")
        assert query == expected
    
    def test_complete_aggregate_query(self):
        """Test complete query with WHERE, GROUP BY, HAVING, ORDER BY"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['OwnerId', 'Owner.Name'])
                .select_count('Id', 'OpportunityCount')
                .select_sum('Amount', 'TotalRevenue')
                .where('IsClosed', SOQLOperator.EQUALS, True)
                .where('IsWon', SOQLOperator.EQUALS, True)
                .group_by(['OwnerId', 'Owner.Name'])
                .having('SUM(Amount)', SOQLOperator.GREATER_THAN, 1000000)
                .order_by('TotalRevenue', descending=True)
                .limit(10)
                .build())
        
        expected = ("SELECT OwnerId, Owner.Name, COUNT(Id) OpportunityCount, SUM(Amount) TotalRevenue "
                   "FROM Opportunity WHERE IsClosed = true AND IsWon = true "
                   "GROUP BY OwnerId, Owner.Name HAVING SUM(Amount) > 1000000 "
                   "ORDER BY TotalRevenue DESC LIMIT 10")
        assert query == expected


class TestSubqueries:
    """Test subquery support"""
    
    def test_simple_subquery(self):
        """Test simple subquery"""
        subquery = SubqueryBuilder('Contacts', 'Contact')
        subquery.select(['Id', 'Name']).limit(5)
        result = subquery.build()
        
        expected = "(SELECT Id, Name FROM Contacts LIMIT 5)"
        assert result == expected
    
    def test_subquery_with_where(self):
        """Test subquery with WHERE clause"""
        subquery = SubqueryBuilder('Opportunities', 'Opportunity')
        subquery.select(['Id', 'Amount']).where('IsClosed', SOQLOperator.EQUALS, False).limit(10)
        result = subquery.build()
        
        expected = "(SELECT Id, Amount FROM Opportunities WHERE IsClosed = false LIMIT 10)"
        assert result == expected
    
    def test_with_subquery_method(self):
        """Test with_subquery method integration"""
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name'])
                .with_subquery('Opportunities', 'Opportunity', lambda sq: sq
                    .select(['Id', 'Name', 'Amount'])
                    .where('StageName', SOQLOperator.EQUALS, 'Closed Won')
                    .order_by('Amount', descending=True)
                    .limit(5))
                .where('Industry', SOQLOperator.EQUALS, 'Technology')
                .build())
        
        expected = ("SELECT Id, Name, (SELECT Id, Name, Amount FROM Opportunities "
                   "WHERE StageName = 'Closed Won' ORDER BY Amount DESC LIMIT 5) "
                   "FROM Account WHERE Industry = 'Technology'")
        assert query == expected


class TestSOSLQueries:
    """Test SOSL query builder"""
    
    def test_simple_sosl(self):
        """Test simple SOSL query"""
        query = (SOSLQueryBuilder()
                .find('Acme')
                .build())
        
        expected = "FIND '{Acme}' IN ALL FIELDS"
        assert query == expected
    
    def test_sosl_with_scope(self):
        """Test SOSL with custom scope"""
        query = (SOSLQueryBuilder()
                .find('test@example.com')
                .in_scope('EMAIL FIELDS')
                .build())
        
        expected = "FIND '{test@example.com}' IN EMAIL FIELDS"
        assert query == expected
    
    def test_sosl_with_returning(self):
        """Test SOSL with RETURNING clause"""
        query = (SOSLQueryBuilder()
                .find('Acme')
                .returning('Account', ['Id', 'Name'])
                .returning('Contact', ['Id', 'Name', 'Email'])
                .build())
        
        expected = ("FIND '{Acme}' IN ALL FIELDS "
                   "RETURNING Account(Id, Name), Contact(Id, Name, Email)")
        assert query == expected
    
    def test_sosl_with_where_and_order(self):
        """Test SOSL with WHERE and ORDER BY in RETURNING"""
        query = (SOSLQueryBuilder()
                .find('Technology')
                .returning('Account', ['Id', 'Name'], 
                          where_clause="Industry = 'Technology'",
                          order_by="Name ASC",
                          limit=10)
                .returning('Opportunity', ['Id', 'Name', 'Amount'],
                          where_clause="Amount > 50000",
                          order_by="Amount DESC")
                .limit(50)
                .build())
        
        expected = ("FIND '{Technology}' IN ALL FIELDS "
                   "RETURNING Account(Id, Name WHERE Industry = 'Technology' ORDER BY Name ASC LIMIT 10), "
                   "Opportunity(Id, Name, Amount WHERE Amount > 50000 ORDER BY Amount DESC) "
                   "LIMIT 50")
        assert query == expected


class TestAggregateQueryBuilder:
    """Test pre-built aggregate query patterns"""
    
    def test_opportunity_pipeline_by_stage(self):
        """Test opportunity pipeline query"""
        query = AggregateQueryBuilder.opportunity_pipeline_by_stage()
        
        # Check that it includes all expected components
        assert "StageName" in query
        assert "COUNT(Id) OpportunityCount" in query
        assert "SUM(Amount) TotalAmount" in query
        assert "AVG(Amount) AvgAmount" in query
        assert "GROUP BY StageName" in query
        assert "HAVING SUM(Amount) > 0" in query
        assert "ORDER BY TotalAmount DESC" in query
    
    def test_account_summary_by_industry(self):
        """Test account summary query"""
        query = AggregateQueryBuilder.account_summary_by_industry()
        
        assert "Industry" in query
        assert "COUNT(Id) AccountCount" in query
        assert "SUM(AnnualRevenue) TotalRevenue" in query
        assert "WHERE Industry != null" in query
        assert "GROUP BY Industry" in query
        assert "HAVING COUNT(Id) > 5" in query
    
    def test_top_sales_reps(self):
        """Test top sales reps query"""
        query = AggregateQueryBuilder.top_sales_reps(min_revenue=250000)
        
        assert "OwnerId, Owner.Name" in query
        assert "COUNT(Id) DealsWon" in query
        assert "SUM(Amount) TotalRevenue" in query
        assert "WHERE IsClosed = true AND IsWon = true" in query
        assert "GROUP BY OwnerId, Owner.Name" in query
        assert "HAVING SUM(Amount) > 250000" in query
        assert "ORDER BY TotalRevenue DESC" in query
        assert "LIMIT 10" in query


class TestQueryTemplates:
    """Test updated query templates with advanced features"""
    
    def test_get_top_opportunities_by_owner(self):
        """Test top opportunities aggregate query"""
        query = QueryTemplates.get_top_opportunities_by_owner()
        
        assert "SELECT OwnerId, Owner.Name" in query
        assert "COUNT(Id) OpportunityCount" in query
        assert "SUM(Amount) TotalPipeline" in query
        assert "WHERE IsClosed = false" in query
        assert "GROUP BY OwnerId, Owner.Name" in query
        assert "HAVING SUM(Amount) > 100000" in query
    
    def test_search_across_objects(self):
        """Test SOSL cross-object search"""
        query = QueryTemplates.search_across_objects('Acme Corp')
        
        assert "FIND '{Acme Corp}'" in query
        assert "Account(Id, Name, Industry)" in query
        assert "Contact(Id, Name, Email, Account.Name)" in query
        assert "Opportunity(Id, Name, Amount, StageName)" in query
        assert "Lead(Id, Name, Company, Email)" in query
        assert "LIMIT 20" in query
    
    def test_get_accounts_with_opportunities(self):
        """Test accounts with opportunity subquery"""
        query = QueryTemplates.get_accounts_with_opportunities()
        
        # Check for main query components
        assert "SELECT Id, Name, Industry, AnnualRevenue" in query
        assert "FROM Account" in query
        assert "WHERE Industry != null" in query
        
        # Check for subquery
        assert "(SELECT Id, Name, Amount, StageName FROM Opportunities" in query
        assert "WHERE IsClosed = false" in query
        assert "ORDER BY Amount DESC LIMIT 5)" in query


class TestEscaping:
    """Test that escaping still works with advanced features"""
    
    def test_aggregate_with_escaping(self):
        """Test that aggregate queries properly escape values"""
        query = (SOQLQueryBuilder('Account')
                .select(['Industry'])
                .select_count('Id', 'Count')
                .where('Name', SOQLOperator.LIKE, "Test's Company")
                .group_by('Industry')
                .having('COUNT(Id)', SOQLOperator.GREATER_THAN, 5)
                .build())
        
        # Check that the single quote is escaped
        assert "Test\\'s Company" in query
    
    def test_sosl_escaping(self):
        """Test SOSL query escaping"""
        query = (SOSLQueryBuilder()
                .find("Test's \"Special\" Search")
                .build())
        
        # Check that quotes are properly escaped
        assert "Test\\'s" in query
        assert '\\"Special\\"' in query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])