from enum import Enum, auto
from dataclasses import dataclass
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


@dataclass
class Token:
    type: TokenType
    text: str
    


    def __str__(self):
        # Equivalente a tu sobrecarga del operador <<
        return f"TOKEN({self.type.name}, {repr(self.text)})"

# --- Ejemplos de uso ---
# tok1 = Token(TokenType.SELECT, "SELECT")
# tok2 = Token(TokenType.ID, "usuarios")
# tok3 = Token(TokenType.NUM, "42.5")