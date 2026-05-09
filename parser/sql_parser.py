from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Tuple

from .scanner import Scanner
from .token import Token, TokenType


@dataclass(slots=True)
class ColumnDefinition:
    name: str
    type_name: str
    index_technique: str | None = None


@dataclass(slots=True)
class CreateTableCommand:
    table_name: str
    columns: List[ColumnDefinition]
    source_path: str | None = None


@dataclass(slots=True)
class InsertCommand:
    table_name: str
    values: List[Any]


@dataclass(slots=True)
class SimpleCondition:
    column: str
    operator: str
    value: Any


@dataclass(slots=True)
class BetweenCondition:
    column: str
    low: Any
    high: Any


@dataclass(slots=True)
class RadiusCondition:
    column: str
    point: Tuple[float, ...]
    radius: float


@dataclass(slots=True)
class KNNCondition:
    column: str
    point: Tuple[float, ...]
    k: int


@dataclass(slots=True)
class SelectCommand:
    table_name: str
    condition: SimpleCondition | BetweenCondition | RadiusCondition | KNNCondition


@dataclass(slots=True)
class DeleteCommand:
    table_name: str
    condition: SimpleCondition


Command = CreateTableCommand | InsertCommand | SelectCommand | DeleteCommand


class SQLParserError(ValueError):
    pass


class SQLParser:
    def __init__(self, source: str):
        self._tokens = self._scan_tokens(source)
        self._current = 0

    def parse(self) -> List[Command]:
        commands: List[Command] = []
        while not self._is_at_end():
            commands.append(self._parse_statement())
            self._consume_optional(TokenType.SEMICOLON)
        return commands

    @staticmethod
    def _scan_tokens(source: str) -> List[Token]:
        scanner = Scanner(source)
        tokens: List[Token] = []
        while True:
            token = scanner.next_token()
            if token.type == TokenType.ERR:
                raise SQLParserError(
                    f"Error léxico en línea {token.line}, columna {token.column}: {token.text}"
                )
            tokens.append(token)
            if token.type == TokenType.EOF:
                return tokens

    def _parse_statement(self) -> Command:
        if self._match(TokenType.CREATE):
            return self._parse_create_table()
        if self._match(TokenType.SELECT):
            return self._parse_select()
        if self._match(TokenType.INSERT):
            return self._parse_insert()
        if self._match(TokenType.DELETE):
            return self._parse_delete()
        raise self._error(self._peek(), "Se esperaba CREATE, SELECT, INSERT o DELETE")

    def _parse_create_table(self) -> CreateTableCommand:
        self._consume(TokenType.TABLE, "Se esperaba TABLE después de CREATE")
        table_name = self._consume_identifier("Se esperaba el nombre de la tabla").text
        self._consume(TokenType.LPAREN, "Se esperaba '(' al definir la tabla")

        columns: List[ColumnDefinition] = []
        while True:
            column_name = self._consume_identifier("Se esperaba el nombre de la columna").text
            type_name = self._parse_type_name()
            index_technique = None
            if self._match(TokenType.INDEX):
                index_technique = self._consume_identifier(
                    "Se esperaba la técnica del índice después de INDEX"
                ).text
            columns.append(ColumnDefinition(column_name, type_name, index_technique))

            if self._match(TokenType.COMA):
                continue
            break

        self._consume(TokenType.RPAREN, "Se esperaba ')' al cerrar la definición de tabla")

        source_path = None
        if self._match(TokenType.FROM):
            self._consume(TokenType.FILE, "Se esperaba FILE después de FROM")
            source_path = self._parse_string_like()

        return CreateTableCommand(table_name, columns, source_path)

    def _parse_select(self) -> SelectCommand:
        self._consume(TokenType.ASTERISK, "Solo se soporta SELECT *")
        self._consume(TokenType.FROM, "Se esperaba FROM")
        table_name = self._consume_identifier("Se esperaba el nombre de la tabla").text
        self._consume(TokenType.WHERE, "Se esperaba WHERE")
        return SelectCommand(table_name, self._parse_condition())

    def _parse_insert(self) -> InsertCommand:
        self._consume(TokenType.INTO, "Se esperaba INTO después de INSERT")
        table_name = self._consume_identifier("Se esperaba el nombre de la tabla").text
        self._consume(TokenType.VALUES, "Se esperaba VALUES")
        self._consume(TokenType.LPAREN, "Se esperaba '(' después de VALUES")

        values = [self._parse_literal()]
        while self._match(TokenType.COMA):
            values.append(self._parse_literal())

        self._consume(TokenType.RPAREN, "Se esperaba ')' al cerrar VALUES")
        return InsertCommand(table_name, values)

    def _parse_delete(self) -> DeleteCommand:
        self._consume(TokenType.FROM, "Se esperaba FROM después de DELETE")
        table_name = self._consume_identifier("Se esperaba el nombre de la tabla").text
        self._consume(TokenType.WHERE, "Se esperaba WHERE")
        column = self._consume_identifier("Se esperaba la columna en DELETE").text
        self._consume(TokenType.EQ, "DELETE solo soporta condiciones de igualdad")
        return DeleteCommand(table_name, SimpleCondition(column, "=" ,self._parse_literal()))

    def _parse_condition(
        self,
    ) -> SimpleCondition | BetweenCondition | RadiusCondition | KNNCondition:
        column = self._consume_identifier("Se esperaba el nombre de la columna").text
        if self._peek().type in {TokenType.EQ, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE}:
            operator = self._advance().text
            return SimpleCondition(column, operator, self._parse_literal())
        if self._match(TokenType.BETWEEN):
            low = self._parse_literal()
            self._consume(TokenType.AND, "Se esperaba AND en BETWEEN")
            high = self._parse_literal()
            return BetweenCondition(column, low, high)
        if self._match(TokenType.IN):
            self._consume(TokenType.LPAREN, "Se esperaba '(' después de IN")
            point = self._parse_point()
            self._consume(TokenType.COMA, "Se esperaba ',' después de POINT(...)")
            if self._match(TokenType.RADIUS):
                radius = float(self._parse_number_literal())
                self._consume(TokenType.RPAREN, "Se esperaba ')' al cerrar la consulta espacial")
                return RadiusCondition(column, point, radius)
            if self._match(TokenType.K):
                k = int(self._parse_number_literal())
                self._consume(TokenType.RPAREN, "Se esperaba ')' al cerrar la consulta kNN")
                return KNNCondition(column, point, k)
            raise self._error(self._peek(), "Se esperaba RADIUS o K en consulta espacial")
        raise self._error(self._peek(), "Condición WHERE no soportada")

    def _parse_type_name(self) -> str:
        parts = []
        paren_depth = 0
        
        while not self._is_at_end():
            # Solo podemos detenernos si NO estamos dentro de un paréntesis
            if paren_depth == 0 and self._peek().type in {TokenType.COMA, TokenType.RPAREN, TokenType.INDEX}:
                break
                
            token = self._advance()
            parts.append(token.text)
            
            if token.type == TokenType.LPAREN:
                paren_depth += 1
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
                
        if not parts:
            raise self._error(self._peek(), "Se esperaba el tipo de dato")
            
        return " ".join(parts)

    def _parse_literal(self) -> Any:
        if self._match(TokenType.NULL):
            return None
        if self._check(TokenType.STRING):
            return self._advance().text
        if self._check(TokenType.NUM):
            return self._parse_number_literal()
        if self._check(TokenType.POINT):
            return self._parse_point()
        if self._check(TokenType.ID):
            return self._advance().text
        raise self._error(self._peek(), "Literal no válido")

    def _parse_point(self) -> Tuple[float, ...]:
        self._consume(TokenType.POINT, "Se esperaba POINT")
        self._consume(TokenType.LPAREN, "Se esperaba '(' después de POINT")
        coords = [float(self._parse_number_literal())]
        while self._match(TokenType.COMA):
            coords.append(float(self._parse_number_literal()))
        self._consume(TokenType.RPAREN, "Se esperaba ')' al cerrar POINT")
        return tuple(coords)

    def _parse_string_like(self) -> str:
        if self._check(TokenType.STRING):
            return self._advance().text
        if self._check(TokenType.ID):
            return self._advance().text
        raise self._error(self._peek(), "Se esperaba un path o cadena")

    def _parse_number_literal(self) -> int | float:
        token = self._consume(TokenType.NUM, "Se esperaba un número")
        if "." in token.text:
            return float(token.text)
        return int(token.text)

    def _consume_identifier(self, message: str) -> Token:
        if self._check(TokenType.ID):
            return self._advance()
        if self._peek().type in {TokenType.POINT, TokenType.RADIUS, TokenType.K}:
            return self._advance()
        raise self._error(self._peek(), message)

    def _match(self, *types: TokenType) -> bool:
        if self._peek().type in types:
            self._advance()
            return True
        return False

    def _consume(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        raise self._error(self._peek(), message)

    def _consume_optional(self, token_type: TokenType) -> None:
        if self._check(token_type):
            self._advance()

    def _check(self, token_type: TokenType) -> bool:
        return self._peek().type == token_type

    def _advance(self) -> Token:
        if not self._is_at_end():
            self._current += 1
        return self._tokens[self._current - 1]

    def _peek(self) -> Token:
        return self._tokens[self._current]

    def _is_at_end(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _error(self, token: Token, message: str) -> SQLParserError:
        return SQLParserError(f"{message} en línea {token.line}, columna {token.column}")


def parse_sql(source: str) -> List[Command]:
    return SQLParser(source).parse()
