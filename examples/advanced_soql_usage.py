"""
Examples of using advanced SOQL query builder features in Salesforce tools
"""

from src.utils.soql_query_builder import (
    SOQLQueryBuilder, SOQLOperator, SOSLQueryBuilder,
    AggregateQueryBuilder, QueryTemplates
)


def example_sales_analytics_tool(sf_connection):
    """Example tool that provides sales analytics using aggregate queries"""
    
    # 1. Get opportunity pipeline by stage
    pipeline_query = AggregateQueryBuilder.opportunity_pipeline_by_stage()
    results = sf_connection.query(pipeline_query)
    
    print("=== Opportunity Pipeline by Stage ===")
    for record in results['records']:
        print(f"Stage: {record['StageName']}")
        print(f"  Count: {record['OpportunityCount']}")
        print(f"  Total: ${record['TotalAmount']:,.2f}")
        print(f"  Average: ${record['AvgAmount']:,.2f}")
    
    # 2. Get top performing sales reps
    top_reps_query = AggregateQueryBuilder.top_sales_reps(min_revenue=500000)
    results = sf_connection.query(top_reps_query)
    
    print("\n=== Top Sales Representatives ===")
    for record in results['records']:
        print(f"Rep: {record['Owner']['Name']}")
        print(f"  Deals Won: {record['DealsWon']}")
        print(f"  Total Revenue: ${record['TotalRevenue']:,.2f}")
    
    # 3. Custom aggregate query - revenue by month
    monthly_revenue_query = (SOQLQueryBuilder('Opportunity')
        .select(['CALENDAR_MONTH(CloseDate) Month'])
        .select_count('Id', 'DealsCount')
        .select_sum('Amount', 'Revenue')
        .where('IsClosed', SOQLOperator.EQUALS, True)
        .where('IsWon', SOQLOperator.EQUALS, True)
        .where('CloseDate', SOQLOperator.GREATER_OR_EQUAL, 'THIS_YEAR')
        .group_by('CALENDAR_MONTH(CloseDate)')
        .order_by('Month')
        .build())
    
    results = sf_connection.query(monthly_revenue_query)
    
    print("\n=== Monthly Revenue This Year ===")
    for record in results['records']:
        print(f"Month {record['Month']}: ${record['Revenue']:,.2f} ({record['DealsCount']} deals)")


def example_account_intelligence_tool(sf_connection):
    """Example tool that provides account intelligence with subqueries"""
    
    # Get top accounts with their recent opportunities
    query = (SOQLQueryBuilder('Account')
        .select(['Id', 'Name', 'Industry', 'AnnualRevenue'])
        .with_subquery('Opportunities', 'Opportunity', lambda sq: sq
            .select(['Id', 'Name', 'Amount', 'StageName', 'CloseDate'])
            .where('IsClosed', SOQLOperator.EQUALS, False)
            .order_by('Amount', descending=True)
            .limit(5))
        .with_subquery('Contacts', 'Contact', lambda sq: sq
            .select(['Id', 'Name', 'Title', 'Email'])
            .where_not_null('Email')
            .order_by('LastActivityDate', descending=True)
            .limit(3))
        .where('AnnualRevenue', SOQLOperator.GREATER_THAN, 1000000)
        .order_by('AnnualRevenue', descending=True)
        .limit(10)
        .build())
    
    results = sf_connection.query(query)
    
    print("=== Top Accounts with Opportunities and Contacts ===")
    for account in results['records']:
        print(f"\nAccount: {account['Name']}")
        print(f"  Industry: {account['Industry']}")
        print(f"  Annual Revenue: ${account['AnnualRevenue']:,.2f}")
        
        if account.get('Opportunities'):
            print("  Open Opportunities:")
            for opp in account['Opportunities']['records']:
                print(f"    - {opp['Name']}: ${opp['Amount']:,.2f} ({opp['StageName']})")
        
        if account.get('Contacts'):
            print("  Key Contacts:")
            for contact in account['Contacts']['records']:
                print(f"    - {contact['Name']} ({contact['Title']}): {contact['Email']}")


def example_global_search_tool(sf_connection, search_term):
    """Example tool that searches across multiple objects using SOSL"""
    
    # Search across accounts, contacts, opportunities, and leads
    query = (SOSLQueryBuilder()
        .find(search_term)
        .returning('Account', ['Id', 'Name', 'Industry', 'Phone'],
                  where_clause="Industry != null",
                  order_by="Name ASC",
                  limit=10)
        .returning('Contact', ['Id', 'Name', 'Email', 'Phone', 'Account.Name'],
                  where_clause="Email != null",
                  limit=10)
        .returning('Opportunity', ['Id', 'Name', 'Amount', 'StageName', 'Account.Name'],
                  where_clause="Amount > 10000",
                  order_by="Amount DESC",
                  limit=10)
        .returning('Lead', ['Id', 'Name', 'Company', 'Email', 'Status'],
                  where_clause="Status IN ('New', 'Working')",
                  limit=10)
        .limit(50)
        .build())
    
    # For SOSL queries, use search() instead of query()
    results = sf_connection.search(query)
    
    print(f"=== Search Results for '{search_term}' ===")
    
    for result in results['searchRecords']:
        obj_type = result['attributes']['type']
        
        if obj_type == 'Account':
            print(f"\nAccount: {result['Name']}")
            print(f"  Industry: {result.get('Industry', 'N/A')}")
            print(f"  Phone: {result.get('Phone', 'N/A')}")
        
        elif obj_type == 'Contact':
            print(f"\nContact: {result['Name']}")
            print(f"  Email: {result.get('Email', 'N/A')}")
            print(f"  Account: {result.get('Account', {}).get('Name', 'N/A')}")
        
        elif obj_type == 'Opportunity':
            print(f"\nOpportunity: {result['Name']}")
            print(f"  Amount: ${result.get('Amount', 0):,.2f}")
            print(f"  Stage: {result.get('StageName', 'N/A')}")
            print(f"  Account: {result.get('Account', {}).get('Name', 'N/A')}")
        
        elif obj_type == 'Lead':
            print(f"\nLead: {result['Name']}")
            print(f"  Company: {result.get('Company', 'N/A')}")
            print(f"  Status: {result.get('Status', 'N/A')}")


def example_performance_dashboard_tool(sf_connection):
    """Example tool that creates a performance dashboard using multiple aggregate queries"""
    
    # 1. Account distribution by industry
    industry_query = AggregateQueryBuilder.account_summary_by_industry()
    
    # 2. Case volume by priority
    case_query = AggregateQueryBuilder.case_volume_by_priority()
    
    # 3. Lead conversion rates by source
    lead_conversion_query = (SOQLQueryBuilder('Lead')
        .select(['LeadSource'])
        .select_count('Id', 'TotalLeads')
        .select_sum('(CASE WHEN IsConverted = true THEN 1 ELSE 0 END)', 'ConvertedLeads')
        .where_not_null('LeadSource')
        .group_by('LeadSource')
        .having('COUNT(Id)', SOQLOperator.GREATER_THAN, 10)
        .order_by('ConvertedLeads', descending=True)
        .build())
    
    # Execute all queries
    industry_results = sf_connection.query(industry_query)
    case_results = sf_connection.query(case_query)
    lead_results = sf_connection.query(lead_conversion_query)
    
    print("=== Performance Dashboard ===")
    
    print("\n1. Accounts by Industry:")
    for record in industry_results['records'][:5]:  # Top 5
        print(f"  {record['Industry']}: {record['AccountCount']} accounts, ${record['TotalRevenue']:,.0f} revenue")
    
    print("\n2. Case Volume by Priority:")
    for record in case_results['records']:
        print(f"  {record['Priority']} - {record['Status']}: {record['CaseCount']} cases")
    
    print("\n3. Lead Conversion by Source:")
    for record in lead_results['records']:
        total = record['TotalLeads']
        converted = record['ConvertedLeads']
        rate = (converted / total * 100) if total > 0 else 0
        print(f"  {record['LeadSource']}: {converted}/{total} ({rate:.1f}% conversion)")


# Integration with existing tool pattern
class AnalyticsTool:
    """Example of integrating advanced queries into the existing tool pattern"""
    
    def __init__(self, sf_connection):
        self.sf = sf_connection
    
    def get_pipeline_summary(self):
        """Get opportunity pipeline summary using aggregates"""
        query = AggregateQueryBuilder.opportunity_pipeline_by_stage()
        results = self.sf.query(query)
        
        return {
            "pipeline_stages": [
                {
                    "stage": record['StageName'],
                    "count": record['OpportunityCount'],
                    "total_amount": record['TotalAmount'],
                    "avg_amount": record['AvgAmount']
                }
                for record in results['records']
            ],
            "query_used": query
        }
    
    def search_globally(self, search_term):
        """Search across all CRM objects"""
        query = QueryTemplates.search_across_objects(search_term)
        results = self.sf.search(query)
        
        return {
            "search_term": search_term,
            "results": results['searchRecords'],
            "total_results": len(results['searchRecords']),
            "query_used": query
        }
    
    def get_account_360(self, account_id):
        """Get comprehensive account view with related data"""
        query = (SOQLQueryBuilder('Account')
            .select(['Id', 'Name', 'Industry', 'AnnualRevenue', 'NumberOfEmployees'])
            .with_subquery('Opportunities', 'Opportunity', lambda sq: sq
                .select(['Id', 'Name', 'Amount', 'StageName', 'CloseDate'])
                .order_by('CloseDate', descending=True)
                .limit(10))
            .with_subquery('Contacts', 'Contact', lambda sq: sq
                .select(['Id', 'Name', 'Title', 'Email', 'Phone'])
                .order_by('CreatedDate', descending=True)
                .limit(10))
            .with_subquery('Cases', 'Case', lambda sq: sq
                .select(['Id', 'CaseNumber', 'Subject', 'Status', 'Priority'])
                .where('IsClosed', SOQLOperator.EQUALS, False)
                .order_by('Priority')
                .limit(5))
            .where_id(account_id)
            .build())
        
        results = self.sf.query(query)
        
        if results['records']:
            return {
                "account": results['records'][0],
                "query_used": query
            }
        else:
            return {"error": "Account not found", "query_used": query}


if __name__ == "__main__":
    print("Advanced SOQL Query Builder Examples")
    print("See the functions above for usage patterns with Salesforce tools")