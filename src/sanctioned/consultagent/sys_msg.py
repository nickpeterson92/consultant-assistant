#sys_msg.py


def chatbot_sys_msg(summary: str, existing_memory_content: str) -> str:
    CHATBOT_SYSTEM_MESSAGE = f"""You are a helpful assistant that supports the user with Salesforce tasks.
    Here is a summary of the conversation: {summary} 
    Here is your memory of records you helped the user with previously: {existing_memory_content}"""
    return CHATBOT_SYSTEM_MESSAGE


def summary_sys_msg(summary: str, memory:str) -> str:      
    SUMMARY_SYSTEM_MESSAGE = f"""You a helpful assistant that supports users with various end systems.
    CURENT INTERACTION INFORMATION:
    {summary}

    {memory}

    INSTRUCTIONS:

    1. Review the chat history carefully and prioritize key:value pairs.
    2. Identify new information about the interaction, such as:
        - Systemic Ids of any and all record types
        - New records of any type being created
        - Any updates to existing records
        - Any deletions of records
    3. The relationship between records is CRITICAL and must be accurately established or maintained
    4. Merge any new information with existing summary
    5. Format the summary as a clear, bulleted list
    6. If new infrmation conflicts with existing summary, use the most recent information

    Remember: Only include factual information either stated by the user or returned from any end system the user is interacting with.
              Do not make assumptions or inferences.

    Based on the chat history below, plese update the summary with the most recent information.
    """
    return SUMMARY_SYSTEM_MESSAGE


def memory_sys_msg(memory: str, summary: str) -> str:
    MEMORY_SYSTEM_MESSAGE = f"""You a helpful assistant that supports users with various end systems.
    CURENT INTERACTION SUMMARY:
    {summary}

    MEMORY OF RECORDS:
    {memory}

    INSTRUCTIONS:

    1. Review the CURRENT INTERACTION SUMMARY and MEMORY OF RECORDS carefully and prioritize key:value pairs.
    2. Identify new information about the interaction betweewn the CURRENT INTERACTION SUMMARY and MEMORY OF RECORDS, such as:
        - Systemic Ids of any and all record types
        - New records of any type being created
        - Any existing records that new records are related to
        - Any updates to existing records
        - Any deletions of records
    3. The relationship between records is CRITICAL and must be accurately established or maintained
    4. Merge any new information from the CURRENT INTERACTION SUMMARY into MEMORY OF RECORDS
    5. Format the memory as a clear, bulleted list
    6. If new infrmation conflicts with existing memory, use the most recent information

    Remember: Only include factual information either stated by the user or returned from any end system the user is interacting with.
              Do not make assumptions or inferences.

    Based on the CURRENT INTERACTION SUMMARY and MEMORY OF RECORDS, plese update the memory with the most recent information.
    """
    return MEMORY_SYSTEM_MESSAGE