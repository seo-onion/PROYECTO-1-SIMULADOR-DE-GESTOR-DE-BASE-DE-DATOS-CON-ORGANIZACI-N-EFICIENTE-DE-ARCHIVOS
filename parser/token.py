from enum import Enum, auto
from typing import Optional

class TokenType(Enum):
    CREATE = auto()
    TABLE = auto()
    INDEX = auto()
    FROM = auto()
    FILE = auto()
    SELECT = auto()
    WHERE = auto()
    INSERT = auto()
    INTO = auto()
    VALUES = auto()
    DELETE = auto()
    NULL = auto()
    
    BETWEEN = auto()
    AND = auto()
    IN = auto()
    
    POINT = auto()
    RADIUS = auto()
    K = auto()
    
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    COMA = auto()       # ,
    SEMICOLON = auto()  # ;
    ASTERISK = auto()   # *
    
    EQ = auto()         # =
    LT = auto()         # <
    GT = auto()         # >
    LE = auto()         # <=
    GE = auto()         # >=
    
    # --- Tipos de Datos Genéricos ---
    ID = auto()          
    NUM = auto()         
    STRING = auto()     
    
    # --- Control ---
    EOF = auto()        # Fin de archivo / Fin de query
    ERR = auto()        # Error léxico


class Token:
    def __init__(self, type: TokenType, text: str, line: int, column: int):
        self.type = type
        self.text = text
        self.line = line
        self.column = column
    
    def __str__(self):
        return f"TOKEN({self.type.name}, {repr(self.text)}, L:{self.line}, C:{self.column})"

    def __repr__(self):
        return self.__str__()
