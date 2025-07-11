import os
import sys
import glob
import pytest
import yaml
from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener
from grammar.CypherLexer import CypherLexer
from grammar.CypherParser import CypherParser
from schema import CypherQuery
from pydantic import ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CypherErrorListener(ErrorListener):

    def __init__(self):
        super(CypherErrorListener, self).__init__()

    def syntaxError(self, recognizer, offendingSymbol, line: int, column: int,
                    msg: str, e: Exception) -> None:
        raise ValueError(f"Syntax error at line: {line}, msg: {msg}")


def get_query_files(cypher_dir: str = "queries") -> list:
    if not os.path.exists(cypher_dir):
        return []
    return glob.glob(os.path.join("queries", "**", "*.yml"), recursive=True)


@pytest.mark.parametrize("file_path", get_query_files("queries"))
def test_cypher_validation(file_path: str, request: pytest.FixtureRequest) -> None:
    with open(file_path, "r") as f:
        yaml_object = yaml.safe_load(f)

    try:
        # Load the query using the Pydantic schema
        validate_schema = CypherQuery(**yaml_object)
    except ValidationError as e:
        pytest.fail(f"Pydantic validation failed for {file_path}: {str(e)}", pytrace=False)

    # Save the query content for error reports
    request.node.user_data = {"query": validate_schema.query}

    # Split query into multiple lines in order to remove line comments
    lines = validate_schema.query.splitlines()
    uncomment_query = "\n".join(line.split("//")[0].rstrip() for line in lines)
    uncomment_query = uncomment_query.lstrip("\n")

    # Attempt to load/parse the query using the CypherParser
    lexer = CypherLexer(InputStream(uncomment_query))
    stream = CommonTokenStream(lexer)
    parser = CypherParser(stream)
    parser.addErrorListener(CypherErrorListener())

    # Attempt to parse the query or raise a generic exception
    try:
        parse_query = parser.oC_Query()
        assert parse_query.exception is None

    except Exception as e:
        pytest.fail(f"Parsing failed for file {file_path}: {str(e)}", pytrace=False)


def test_duplicate_guid() -> None:
    query_files = get_query_files("queries")
    guids = set()

    # Iterate over all query files and check for duplicate GUIDs
    for file_path in query_files:
        with open(file_path, "r") as f:
            yaml_object = yaml.safe_load(f)

        query_guid = yaml_object["guid"]
        if query_guid in guids:
            pytest.fail(f"Duplicate GUID found: {query_guid} in file {file_path}", pytrace=False)
        guids.add(query_guid)


if __name__ == "__main__":
    pytest.main(["-v", __file__])
