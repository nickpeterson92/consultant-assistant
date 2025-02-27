#states.py
 
 
from typing import Annotated, TypedDict, List
from operator import add

class OverallState(TypedDict):
    message: str
    summary: Annotated[List[str], add]


class PrivateState(TypedDict):
    summary: Annotated[List[str], add]